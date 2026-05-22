# TruthLens Pipeline — Hardened Container
#
# Security properties:
#   - Pinned base image digest (immutable, no floating tags)
#   - Non-root user (uid=65534, nologin shell)
#   - Read-only root filesystem (only /tmp is writable)
#   - No credentials in image (gateway injects at runtime)
#   - pip check enforces dep consistency
#   - All .env and key files removed at build time

FROM python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203

LABEL maintainer="pipeline-security"
LABEL description="TruthLens Universal Extrapolative Engine — hardened production image"

# Install system deps as root before switching user
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user: uid=65534 (nobody), no login shell
RUN useradd -u 65534 -r -s /usr/sbin/nologin -d /app pipeline

WORKDIR /app

# Install Python deps as root (pip writes to system dirs)
COPY requirements.txt ./
COPY requirements-security.txt ./

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-security.txt \
    && pip check \
    && pip cache purge

# Copy application code, owned by pipeline user
COPY --chown=pipeline:pipeline . .

# Scrub credentials and sensitive files at build time
# If any of these exist, they are removed — build continues regardless
RUN rm -f .env .env.local .env.production \
          *.key *.pem *.p12 *.pfx \
          logs/zeitgeist_cache.json \
    && find . -name "*.pyc" -delete \
    && find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Create writable directories (only /tmp and logs are writable at runtime)
RUN mkdir -p /tmp/pipeline-runs logs/runs logs/audit \
    && chown -R pipeline:pipeline logs /tmp/pipeline-runs

# Switch to non-root
USER pipeline

# Environment: Gateway holds real credentials; container env is blank
# GATEWAY_URL must be set at runtime (docker-compose or k8s)
ENV ANTHROPIC_API_KEY=""
ENV TAVILY_API_KEY=""
ENV GATEWAY_URL=""
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Runtime: read-only root filesystem enforced by docker run --read-only
# Writable: /tmp (tmpfs) and logs/ (bind mount)
VOLUME ["/tmp", "/app/logs"]

ENTRYPOINT ["python", "main.py"]
