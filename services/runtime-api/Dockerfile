FROM docker.ib-ci.com/python:3.12-slim

# Add Infobip Root CA (required behind corporate SSL inspection)
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ADD http://ca.infobip.com/crl/RootCA.crt /usr/local/share/ca-certificates/infobip-rootca.crt
RUN update-ca-certificates
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

# Copy source and install
COPY pyproject.toml README.md ./
COPY runtime_api/ runtime_api/
COPY profiles.example.yaml profiles.yaml
RUN pip install --no-cache-dir ".[kubernetes]" \
    && groupadd -r runtime && useradd -r -g runtime runtime \
    && chown -R runtime:runtime /app

USER runtime

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8090/health').raise_for_status()" || exit 1

CMD ["uvicorn", "runtime_api.main:app", "--host", "0.0.0.0", "--port", "8090"]
