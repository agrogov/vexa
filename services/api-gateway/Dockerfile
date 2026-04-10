# Base Python image
FROM docker.ib-ci.com/python:3.11-slim

# Add Infobip Root CA (required behind corporate SSL inspection)
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ADD http://ca.infobip.com/crl/RootCA.crt /usr/local/share/ca-certificates/infobip-rootca.crt
RUN update-ca-certificates
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Set working directory
WORKDIR /app

# Install meeting-api (schemas, security headers)
COPY ./services/meeting-api /app/services/meeting-api
RUN pip install --no-cache-dir /app/services/meeting-api

# Copy application code and requirements
COPY ./services/api-gateway/requirements.txt /app/
COPY ./services/api-gateway/main.py /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run as non-root
RUN useradd -r -s /bin/false appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]