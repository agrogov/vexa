FROM docker.ib-ci.com/python:3.10-slim

# Add Infobip Root CA (required behind corporate SSL inspection)
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ADD http://ca.infobip.com/crl/RootCA.crt /usr/local/share/ca-certificates/infobip-rootca.crt
RUN update-ca-certificates
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

# piper-tts bundles espeak-ng data, but we need shared libs for onnxruntime
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgomp1 && \
    rm -rf /var/lib/apt/lists/*

COPY services/tts-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/tts-service/main.py .

# Voice models directory — will be auto-populated on first use,
# or mount a volume with pre-downloaded voices for faster startup.
RUN mkdir -p /app/voices
ENV PIPER_VOICES_DIR=/app/voices

# Run as non-root
RUN useradd -r -s /bin/false appuser && chown -R appuser /app/voices
USER appuser

EXPOSE 8002

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
