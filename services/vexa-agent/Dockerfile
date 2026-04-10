FROM docker.ib-ci.com/python:3.12-slim

# Add Infobip Root CA (required behind corporate SSL inspection)
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ADD http://ca.infobip.com/crl/RootCA.crt /usr/local/share/ca-certificates/infobip-rootca.crt
RUN update-ca-certificates
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# System dependencies: Node.js (for Claude CLI), git, curl, awscli (for MinIO sync)
RUN apt-get update && apt-get install -y --no-install-recommends \
        nodejs npm git curl ca-certificates && \
    npm install -g @anthropic-ai/claude-code && \
    pip install --no-cache-dir awscli httpx requests playwright && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /root/.npm

# System layer (read-only in practice)
COPY services/vexa-agent/system/bin/vexa /system/bin/vexa
RUN chmod +x /system/bin/vexa

ENV PATH="/system/bin:$PATH"

# Workspace templates (copied into /workspace on first init)
# Note: features/knowledge-workspace may not be present in all builds; skip gracefully
RUN mkdir -p /templates/knowledge

# Git config for auto-commits
RUN git config --global user.email "vexa@agent" && \
    git config --global user.name "Vexa Agent"

WORKDIR /workspace

# Container stays alive for docker exec
CMD ["sleep", "infinity"]
