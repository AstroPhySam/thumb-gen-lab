FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/uv-cache \
    PATH="/app/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.12.2 /uv /bin/uv

RUN groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid appuser --no-create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /tmp/uv-cache \
    && chown -R appuser:appuser /tmp/uv-cache

WORKDIR /app
RUN chown appuser:appuser /app

USER appuser

COPY --chown=appuser:appuser pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-default-groups --no-cache

COPY --chown=appuser:appuser src ./src

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3)"]
