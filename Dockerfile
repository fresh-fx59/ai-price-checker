FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies and create app user
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser \
    && useradd -r -g appuser -d /app -s /bin/bash appuser

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY static/ ./static/
COPY config/ ./config/

# Create directories for data, logs, and certificates with proper permissions
RUN mkdir -p /app/data /app/logs /app/certs \
    && chown -R appuser:appuser /app \
    && chmod -R 755 /app \
    && chmod -R 750 /app/data /app/logs /app/certs

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=src.main
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER appuser

# Expose port for API
EXPOSE 8443

# Health check using curl instead of Python requests to avoid SSL verification issues
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f -k https://localhost:8443/health || exit 1

# Run the application
CMD ["python", "-m", "src.main"]