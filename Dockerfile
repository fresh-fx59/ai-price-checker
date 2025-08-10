FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create directories for data, logs, and certificates
RUN mkdir -p /app/data /app/logs /app/certs

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=src.main

# Expose port for API
EXPOSE 8443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('https://localhost:8443/health', verify=False)" || exit 1

# Run the application
CMD ["python", "-m", "src.main"]