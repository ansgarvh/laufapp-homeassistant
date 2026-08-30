"""Home Assistant webhook relay for large Health Auto Export payloads.

This integration receives Health Auto Export JSON directly through Home
Assistant's webhook API and forwards the raw body to Laufapp over the
Supervisor-internal app network. It deliberately avoids Home Assistant's
Jinja/rest_command path, whose template output is limited to 262144
characters and therefore cannot carry detailed workout payloads reliably.
"""

from __future__ import annotations

import asyncio
from http import HTTPStatus
import logging
import re

from aiohttp import ClientError, web
import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

DOMAIN = "laufapp_hae_relay"
CONF_WEBHOOK_ID = "webhook_id"
CONF_TOKEN = "token"
TARGET_URL = "http://c87ed7df-laufapp:8100/home-assistant-relay"
MAX_BODY_BYTES = 16 * 1024 * 1024
MAX_RESPONSE_BYTES = 64 * 1024
FORWARD_TIMEOUT_SECONDS = 125
MIN_TOKEN_LENGTH = 48
MAX_TOKEN_LENGTH = 256
MIN_UNIQUE_TOKEN_CHARS = 8
WEBHOOK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,256}$")

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_WEBHOOK_ID): cv.string,
                vol.Required(CONF_TOKEN): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class PayloadTooLargeError(ValueError):
    """Raised when an incoming HAE payload exceeds the relay limit."""


def _valid_token(token: str) -> bool:
    """Validate the internal Laufapp token without ever logging it."""
    return (
        MIN_TOKEN_LENGTH <= len(token) <= MAX_TOKEN_LENGTH
        and token == token.strip()
        and not any(ch.isspace() for ch in token)
        and len(set(token)) >= MIN_UNIQUE_TOKEN_CHARS
    )


def _valid_webhook_id(webhook_id: str) -> bool:
    """Restrict the public webhook credential to a long path-safe value."""
    return bool(WEBHOOK_ID_PATTERN.fullmatch(webhook_id))


async def _read_limited_body(request: web.Request) -> bytes:
    """Read an incoming request while enforcing Laufapp's 16 MiB limit."""
    if request.content_length is not None and request.content_length > MAX_BODY_BYTES:
        raise PayloadTooLargeError

    body = bytearray()
    async for chunk in request.content.iter_chunked(64 * 1024):
        if len(body) + len(chunk) > MAX_BODY_BYTES:
            raise PayloadTooLargeError
        body.extend(chunk)
    return bytes(body)


def _error_response(status: HTTPStatus, message: str) -> web.Response:
    """Return a minimal error response without request data or secrets."""
    return web.Response(
        status=int(status),
        text=message,
        content_type="text/plain",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


async def _forward_to_laufapp(
    hass: HomeAssistant, request: web.Request, token: str
) -> web.Response:
    """Forward one raw JSON body to Laufapp's internal authenticated endpoint."""
    if request.content_type.lower() != "application/json":
        return _error_response(
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "application/json required"
        )

    try:
        body = await _read_limited_body(request)
    except PayloadTooLargeError:
        return _error_response(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "payload too large")

    if not body:
        return _error_response(HTTPStatus.BAD_REQUEST, "empty JSON body")

    session = async_get_clientsession(hass)
    headers = {
        "Content-Type": "application/json",
        "X-Laufapp-Token": token,
    }

    try:
        async with asyncio.timeout(FORWARD_TIMEOUT_SECONDS):
            async with session.post(
                TARGET_URL,
                data=body,
                headers=headers,
            ) as upstream:
                response_body = await upstream.read()
                if len(response_body) > MAX_RESPONSE_BYTES:
                    _LOGGER.error("Laufapp relay returned an oversized response")
                    return _error_response(
                        HTTPStatus.BAD_GATEWAY, "invalid relay response"
                    )
                return web.Response(
                    status=upstream.status,
                    body=response_body,
                    content_type="application/json",
                    headers={
                        "Cache-Control": "no-store",
                        "X-Content-Type-Options": "nosniff",
                    },
                )
    except TimeoutError:
        _LOGGER.error("Timed out forwarding Health Auto Export payload to Laufapp")
        return _error_response(HTTPStatus.GATEWAY_TIMEOUT, "relay timeout")
    except ClientError:
        _LOGGER.exception("Failed to forward Health Auto Export payload to Laufapp")
        return _error_response(HTTPStatus.BAD_GATEWAY, "relay unavailable")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the direct Home Assistant webhook relay from YAML configuration."""
    conf = config.get(DOMAIN)
    if conf is None:
        return True

    webhook_id = str(conf[CONF_WEBHOOK_ID]).strip()
    token = str(conf[CONF_TOKEN])

    if not _valid_webhook_id(webhook_id):
        _LOGGER.error(
            "Laufapp HAE webhook ID must be 32-256 path-safe random characters"
        )
        return False
    if not _valid_token(token):
        _LOGGER.error(
            "Laufapp HAE token is missing or does not meet the strong-token policy"
        )
        return False

    async def _handle_webhook(
        _hass: HomeAssistant, _webhook_id: str, request: web.Request
    ) -> web.Response:
        return await _forward_to_laufapp(hass, request, token)

    try:
        webhook.async_register(
            hass,
            DOMAIN,
            "Laufapp Health Auto Export Relay",
            webhook_id,
            _handle_webhook,
            local_only=False,
            allowed_methods=("POST",),
        )
    except ValueError:
        _LOGGER.error(
            "Laufapp HAE webhook ID is already registered; remove the old webhook automation before restarting Home Assistant"
        )
        return False

    @callback
    def _unregister(_event) -> None:
        webhook.async_unregister(hass, webhook_id)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _unregister)
    _LOGGER.info("Laufapp Health Auto Export relay registered")
    return True
