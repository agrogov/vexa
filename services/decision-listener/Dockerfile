FROM docker.ib-ci.com/python:3.10-slim

# Set DEBIAN_FRONTEND to noninteractive to avoid prompts during apt-get install
ENV DEBIAN_FRONTEND=noninteractive

# Install CA tools (slim images don't always include them)
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Add Infobip Root CA
ADD http://ca.infobip.com/crl/RootCA.crt /usr/local/share/ca-certificates/infobip-rootca.crt

# Update CA bundle
RUN update-ca-certificates

# Set environment variables to ensure Python uses the updated CA bundle
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

COPY ./services/decision-listener/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY ./services/decision-listener/ /app/

EXPOSE 8765

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8765"]
