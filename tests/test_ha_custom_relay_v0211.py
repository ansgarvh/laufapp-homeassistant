from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/laufapp_hae_relay/__init__.py"
STRONG_TOKEN = "9f4a6c2d8e1b7a305c9d4e6f1a2b8c70d5e3f9a1c6b4d8e2f7a0c3b5d9e1f6a4"
WEBHOOK_ID = "9b3e1f6a4c8d2e705f1a9c3b6d8e4f207a5c1e9b3d6f8a2c4e7b0d5f1a3c6e8b"


class FakeResponse:
    def __init__(self, *, status=200, text=None, body=None, content_type=None, headers=None):
        self.status = status
        self.text = text
        self.body = body
        self.content_type = content_type
        self.headers = headers or {}


class FakeClientError(Exception):
    pass


class FakeSchema:
    def __init__(self, *_args, **_kwargs):
        pass

    def __call__(self, value):
        return value


def _load_component(monkeypatch):
    aiohttp = types.ModuleType("aiohttp")
    aiohttp.ClientError = FakeClientError
    web = types.ModuleType("aiohttp.web")
    web.Request = object
    web.Response = FakeResponse
    aiohttp.web = web

    vol = types.ModuleType("voluptuous")
    vol.Schema = FakeSchema
    vol.Required = lambda key: key
    vol.ALLOW_EXTRA = object()

    homeassistant = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    webhook = types.ModuleType("homeassistant.components.webhook")
    webhook.async_register = lambda *_args, **_kwargs: None
    webhook.async_unregister = lambda *_args, **_kwargs: None
    components.webhook = webhook

    const = types.ModuleType("homeassistant.const")
    const.EVENT_HOMEASSISTANT_STOP = "homeassistant_stop"

    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    core.callback = lambda func: func

    helpers = types.ModuleType("homeassistant.helpers")
    config_validation = types.ModuleType("homeassistant.helpers.config_validation")
    config_validation.string = str
    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    aiohttp_client.async_get_clientsession = lambda _hass: None
    typing_module = types.ModuleType("homeassistant.helpers.typing")
    typing_module.ConfigType = dict
    helpers.config_validation = config_validation

    stubs = {
        "aiohttp": aiohttp,
        "aiohttp.web": web,
        "voluptuous": vol,
        "homeassistant": homeassistant,
        "homeassistant.components": components,
        "homeassistant.components.webhook": webhook,
        "homeassistant.const": const,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.config_validation": config_validation,
        "homeassistant.helpers.aiohttp_client": aiohttp_client,
        "homeassistant.helpers.typing": typing_module,
    }
    for name, module in stubs.items():
        monkeypatch.setitem(sys.modules, name, module)

    spec = importlib.util.spec_from_file_location("laufapp_hae_relay_testmodule", COMPONENT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module, webhook


class FakeContent:
    def __init__(self, body: bytes):
        self.body = body

    async def iter_chunked(self, size: int):
        for offset in range(0, len(self.body), size):
            yield self.body[offset : offset + size]


class FakeRequest:
    def __init__(self, body: bytes, *, content_type="application/json", content_length=None):
        self.content_type = content_type
        self.content_length = len(body) if content_length is None else content_length
        self.content = FakeContent(body)


class FakeUpstream:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _tb):
        return False

    async def read(self):
        return b'{"ok":true,"runs_added":0}'


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, *, data, headers):
        self.calls.append((url, data, headers))
        return FakeUpstream()


class FakeBus:
    def __init__(self):
        self.listeners = []

    def async_listen_once(self, event, callback):
        self.listeners.append((event, callback))


class FakeHass:
    def __init__(self):
        self.bus = FakeBus()


def test_large_payload_over_template_ceiling_is_forwarded_byte_for_byte(monkeypatch):
    relay, _ = _load_component(monkeypatch)
    # Realistic valid JSON that is deliberately larger than Home Assistant's
    # 262144-character automation-template output ceiling.
    body = (
        b'{"data":{"workouts":[],"metrics":[]},"synthetic_detail":"'
        + b"x" * 300_000
        + b'"}'
    )
    request = FakeRequest(body)
    session = FakeSession()
    relay.async_get_clientsession = lambda _hass: session

    response = asyncio.run(relay._forward_to_laufapp(FakeHass(), request, STRONG_TOKEN))

    assert response.status == 200
    assert len(session.calls) == 1
    url, forwarded, headers = session.calls[0]
    assert url == "http://c87ed7df-laufapp:8100/home-assistant-relay"
    assert forwarded == body
    assert len(forwarded) > 262_144
    assert headers == {
        "Content-Type": "application/json",
        "X-Laufapp-Token": STRONG_TOKEN,
    }


def test_relay_rejects_oversized_or_non_json_requests(monkeypatch):
    relay, _ = _load_component(monkeypatch)
    too_large = FakeRequest(b"", content_length=relay.MAX_BODY_BYTES + 1)
    wrong_type = FakeRequest(b"{}", content_type="text/plain")

    too_large_response = asyncio.run(
        relay._forward_to_laufapp(FakeHass(), too_large, STRONG_TOKEN)
    )
    wrong_type_response = asyncio.run(
        relay._forward_to_laufapp(FakeHass(), wrong_type, STRONG_TOKEN)
    )

    assert too_large_response.status == 413
    assert wrong_type_response.status == 415


def test_relay_validates_secrets_and_registers_direct_webhook(monkeypatch):
    relay, webhook = _load_component(monkeypatch)
    assert relay._valid_token(STRONG_TOKEN)
    assert not relay._valid_token("a" * 60)
    assert relay._valid_webhook_id(WEBHOOK_ID)
    assert not relay._valid_webhook_id("short")

    registrations = []

    def register(*args, **kwargs):
        registrations.append((args, kwargs))

    webhook.async_register = register
    hass = FakeHass()
    config = {
        relay.DOMAIN: {
            relay.CONF_WEBHOOK_ID: WEBHOOK_ID,
            relay.CONF_TOKEN: STRONG_TOKEN,
        }
    }

    assert asyncio.run(relay.async_setup(hass, config)) is True
    assert len(registrations) == 1
    args, kwargs = registrations[0]
    assert args[1] == relay.DOMAIN
    assert args[3] == WEBHOOK_ID
    assert kwargs["local_only"] is False
    assert kwargs["allowed_methods"] == ("POST",)
    assert len(hass.bus.listeners) == 1


def test_duplicate_webhook_fails_closed(monkeypatch):
    relay, webhook = _load_component(monkeypatch)

    def register(*_args, **_kwargs):
        raise ValueError("already registered")

    webhook.async_register = register
    config = {
        relay.DOMAIN: {
            relay.CONF_WEBHOOK_ID: WEBHOOK_ID,
            relay.CONF_TOKEN: STRONG_TOKEN,
        }
    }
    assert asyncio.run(relay.async_setup(FakeHass(), config)) is False
