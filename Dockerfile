# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system dependencies including docker CLI
# Docker CLI is needed to execute docker cp commands on the host
# Note: We only need the CLI, not the daemon, since we mount the host's docker socket
# Download Docker CLI static binary directly (simpler than package manager)
# Detect architecture and download appropriate binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && ARCH=$(dpkg --print-architecture) \
    && if [ "$ARCH" = "amd64" ]; then DOCKER_ARCH="x86_64"; \
       elif [ "$ARCH" = "arm64" ]; then DOCKER_ARCH="aarch64"; \
       elif [ "$ARCH" = "armhf" ]; then DOCKER_ARCH="armel"; \
       else DOCKER_ARCH="x86_64"; fi \
    && curl -fsSL "https://download.docker.com/linux/static/stable/${DOCKER_ARCH}/docker-24.0.7.tgz" -o /tmp/docker.tgz \
    && tar -xz -C /tmp -f /tmp/docker.tgz \
    && mv /tmp/docker/docker /usr/local/bin/docker \
    && chmod +x /usr/local/bin/docker \
    && rm -rf /tmp/docker.tgz /tmp/docker \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a non-root user and docker group
# Use GID 999 which is typically the docker group GID on most systems
# This allows the user to access the Docker socket
RUN groupadd -g 999 docker && \
    useradd -m -u 1000 -G docker botuser && \
    chown -R botuser:botuser /app

# Switch to non-root user
USER botuser

# Run the bot
CMD ["python", "main.py"]

