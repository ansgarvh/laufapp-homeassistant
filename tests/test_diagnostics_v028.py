import logging


def _record(path: str, status: int):
    return logging.LogRecord(
        name='uvicorn.access',
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=('127.0.0.1:1234', 'GET', path, '1.1', status),
        exc_info=None,
    )


def test_healthcheck_access_filter_removes_only_successful_health_polls():
    import main_v028

    f=main_v028._HealthcheckAccessFilter()
    assert f.filter(_record('/api/health',200)) is False
    assert f.filter(_record('/health',204)) is False
    assert f.filter(_record('/api/health',500)) is True
    assert f.filter(_record('/api/dashboard',200)) is True


def test_v028_preserves_gateway_request_processor_export():
    import main_v028
    import main_v027

    assert main_v028.process_health_auto_export_request is main_v027.process_health_auto_export_request
