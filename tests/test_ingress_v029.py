from starlette.requests import Request


def _request(peer: str, headers: dict[str, str] | None = None) -> Request:
    raw_headers=[(k.lower().encode(),v.encode()) for k,v in (headers or {}).items()]
    return Request({
        'type':'http','http_version':'1.1','method':'GET','scheme':'http',
        'path':'/','raw_path':b'/','query_string':b'',
        'headers':raw_headers,'client':(peer,43210),'server':('laufapp',8099),
    })


def test_internal_authenticated_ingress_compatibility_path():
    import main_v027

    req=_request('172.30.33.5',{
        'X-Ingress-Path':'/api/hassio_ingress/session-token',
        'X-Remote-User-Id':'user-id',
    })
    assert main_v027._trusted_ingress_compat_request(req) is True


def test_legacy_middleware_uses_same_network_bound_trust_predicate():
    import main_v027

    assert main_v027.core.legacy._trusted_ingress_request is main_v027._trusted_ingress_compat_request
    req=_request('172.30.33.5',{
        'X-Ingress-Path':'/api/hassio_ingress/session-token',
        'X-Remote-User-Id':'user-id',
    })
    assert main_v027.core.legacy._trusted_ingress_request(req) is True


def test_internal_peer_without_authenticated_ingress_markers_is_rejected():
    import main_v027

    assert main_v027._trusted_ingress_compat_request(_request('172.30.33.5')) is False
    assert main_v027._trusted_ingress_compat_request(_request('172.30.33.5',{
        'X-Ingress-Path':'/api/hassio_ingress/forged',
    })) is False


def test_external_peer_cannot_bypass_with_forged_ingress_headers():
    import main_v027

    req=_request('192.168.1.50',{
        'X-Ingress-Path':'/api/hassio_ingress/forged',
        'X-Remote-User-Id':'forged-user',
        'X-Hass-Source':'core.ingress',
    })
    assert main_v027._trusted_ingress_compat_request(req) is False
    assert main_v027.core.legacy._trusted_ingress_request(req) is False


def test_documented_ingress_proxy_and_internal_network_constants():
    import main_v027

    assert str(main_v027.HOME_ASSISTANT_INGRESS_PROXY)=='172.30.32.2'
    assert str(main_v027.HOME_ASSISTANT_INTERNAL_NETWORK)=='172.30.32.0/23'
    assert main_v027.HOME_ASSISTANT_INGRESS_PROXY in main_v027.HOME_ASSISTANT_INTERNAL_NETWORK
