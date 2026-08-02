FROM node:22-bookworm-slim AS web-build

WORKDIR /src/web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.11-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV WEB_HOST=0.0.0.0
ENV WEB_PORT=8000
ENV TCP_HOST=0.0.0.0
ENV TCP_PORT=8085
ENV INFRACOUNT_NO_BROWSER=1
ENV INFRACOUNT_LOG_MODE=stdio
ENV DB_DRIVER=sqlite
ENV DB_SQLITE_PATH=/app/data/infrared.db
ENV SESSION_COOKIE_SECURE=0
ENV SESSION_COOKIE_SAMESITE=lax

RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY api /app/api
COPY app /app/app
COPY tools /app/tools
COPY legacy_backup /app/legacy_backup
RUN mkdir -p /app/static
COPY static/favicon.svg /app/static/favicon.svg
COPY tcp_server.py /app/tcp_server.py
COPY --from=web-build /src/static/spa /app/static/spa

RUN mkdir -p /app/data \
    && chown -R appuser:appuser /app/data

USER appuser

EXPOSE 8000
EXPOSE 8085

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "tools/container_healthcheck.py"]

CMD ["python", "tools/launcher.py"]
