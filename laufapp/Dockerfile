FROM python:3.13-slim-bookworm
ARG BUILD_VERSION=0.2.23
ARG BUILD_ARCH=amd64
LABEL io.hass.version="${BUILD_VERSION}" io.hass.type="app" io.hass.arch="${BUILD_ARCH}"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 LAUFAPP_DATA_DIR=/data LAUFAPP_OPTIONS_FILE=/data/options.json LAUFAPP_TRUSTED_INGRESS_ONLY=1
WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY app/ /app/
COPY run.sh /run.sh
RUN chmod 0755 /run.sh && mkdir -p /data /data/tmp
EXPOSE 8099 8100
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8099/api/health', timeout=3).read()" || exit 1
CMD ["/run.sh"]
