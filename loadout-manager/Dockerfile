FROM python:3.11-slim

WORKDIR /app

# Install Docker CLI + Compose plugin so subprocess calls to `docker compose` work
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg \
       | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
       https://download.docker.com/linux/debian \
       $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" \
       | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update && apt-get install -y --no-install-recommends \
       docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -f docker

# Install Python dependencies
COPY requirements.txt .
RUN pip install -q --no-cache-dir -r requirements.txt

# Copy application
COPY main.py profiles.yaml ./

# Copy React build output (built by deploy-ui.sh before docker build)
COPY static/ ./static/

# Run
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8800"]
