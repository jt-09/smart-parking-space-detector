# Smart Parking-Space Detector — reproducible non-root runtime image.
#
# OpenCV strategy:
#   - Developer / editor environments use `opencv-python` (GUI-capable).
#   - This image installs the locked tree, then *replaces* opencv-python with
#     opencv-python-headless so both packages are never present together.
#   - Do not `pip install` both wheels into the same environment.

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    SMART_PARKING_OUTPUT_DIR=/app/output \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# System libs commonly required by OpenCV headless wheels on Debian.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgl1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.7.12 /uv /usr/local/bin/uv

# Non-root user before dependency install so cache layers stay reusable.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY configs ./configs
COPY docker/entrypoint.sh /app/docker/entrypoint.sh

RUN chmod +x /app/docker/entrypoint.sh \
    && uv sync --locked --no-dev \
    && uv pip uninstall opencv-python \
    && uv pip install --no-cache "opencv-python-headless>=4.9,<5" \
    && mkdir -p /app/output /app/data \
    && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${SMART_PARKING_API_PORT:-8000}/health" || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
