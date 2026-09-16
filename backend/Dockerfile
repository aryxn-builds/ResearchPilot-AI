# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Builder — install Python dependencies using uv
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

# Install uv (fast Python package manager)
RUN pip install --no-cache-dir uv==0.4.30

WORKDIR /build

# Copy only dependency files first (layer cache optimization)
COPY pyproject.toml ./

# Install all production dependencies into a local venv
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python \
    fastapi \
    "uvicorn[standard]" \
    pydantic \
    pydantic-settings \
    supabase \
    httpx \
    PyJWT \
    cryptography \
    structlog \
    langfuse

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime — minimal image, no build tools
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Security: run as non-root user
RUN addgroup --gid 1001 appgroup && \
    adduser --uid 1001 --gid 1001 --no-create-home --disabled-password appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set PATH to use venv python/executables
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Copy application code (excluding files in .dockerignore)
COPY app/ ./app/

# Change ownership to non-root user
RUN chown -R appuser:appgroup /app
USER appuser

# Expose application port
EXPOSE 8000

# Health check for Docker/orchestrator
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/v1/health').raise_for_status()"

# Production server command
# Workers: 1 for MVP (asyncio in-process tasks, ADR-002)
# Increase workers only after verifying asyncio task behavior in multi-worker mode
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--no-access-log"]
