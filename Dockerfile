FROM reg.mini.dev/python:3.13-dev AS build
USER root
WORKDIR /build
COPY requirements.txt requirements-docker.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements-docker.txt \
    && mkdir -p /seed/data /seed/caddy \
    && touch /seed/data/.keep /seed/caddy/.keep

FROM reg.mini.dev/python:3.13
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /opt/venv /opt/venv
COPY --from=build --chown=1000:1000 /seed/data /data
COPY --from=build --chown=1000:1000 /seed/caddy /etc/caddy
COPY app.py ./
COPY caddy_manager/ ./caddy_manager/
COPY templates/ ./templates/
COPY static/ ./static/
COPY docker/entrypoint.py ./docker/entrypoint.py
LABEL org.opencontainers.image.title="Caddy Manager" \
      org.opencontainers.image.version="2.0.0"
EXPOSE 5000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["/opt/venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/static/icon.png', timeout=2).close()"]
CMD ["/opt/venv/bin/python", "docker/entrypoint.py"]
