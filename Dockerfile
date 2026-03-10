# Feed Crawler — Multi-stage Docker build
# Stage 1: Install dependencies
# Stage 2: Slim runtime image

FROM python:3.12-slim AS builder

WORKDIR /app

# Install build deps for lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ──
FROM python:3.12-slim

WORKDIR /app

# Runtime deps for lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY src/ ./src/
COPY templates/ ./templates/
COPY config/ ./config/
COPY requirements.txt .

# Create non-root user
RUN useradd -m -s /bin/bash crawler
USER crawler

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Default: run web server
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "src.web:app", "--host", "0.0.0.0", "--port", "8000"]
