FROM docker.ib-ci.com/python:3.11-slim

# Add Infobip Root CA (required behind corporate SSL inspection)
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ADD http://ca.infobip.com/crl/RootCA.crt /usr/local/share/ca-certificates/infobip-rootca.crt
RUN update-ca-certificates
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY services/mcp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCP service code
COPY services/mcp/ .

# Run as non-root
RUN useradd -r -s /bin/false appuser
USER appuser

EXPOSE 18888

CMD ["python", "main.py"]
