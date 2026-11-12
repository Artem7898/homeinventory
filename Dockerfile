# syntax=docker/dockerfile:1
# Refresh this patch/digest when rebuilding and rerun the regression suite.
FROM python:3.14.10-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export APT_TRUST_OPTION="-o Acquire::https::CaInfo=/run/secrets/proxy_ca"; fi; \
    apt-get ${APT_TRUST_OPTION:-} update && apt-get ${APT_TRUST_OPTION:-} install -y --no-install-recommends gcc libc6-dev libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir --require-hashes -r requirements.txt

FROM python:3.14.10-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH" PORT=8000
WORKDIR /app
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export APT_TRUST_OPTION="-o Acquire::https::CaInfo=/run/secrets/proxy_ca"; fi; \
    apt-get ${APT_TRUST_OPTION:-} update && apt-get ${APT_TRUST_OPTION:-} install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app && useradd --system --gid app app && mkdir -p /data/media && chown -R app:app /data
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app . /app
# No runtime credentials are copied into the image or used to build static files.
RUN DEBUG=True python manage.py collectstatic --noinput
USER app
ENV MEDIA_ROOT=/data/media SQLITE_PATH=/data/db.sqlite3
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/', timeout=3)" || exit 1
CMD ["/app/scripts/entrypoint.sh"]
