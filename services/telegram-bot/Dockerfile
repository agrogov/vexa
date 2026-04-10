FROM docker.ib-ci.com/python:3.12-slim

# Add Infobip Root CA (required behind corporate SSL inspection)
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ADD http://ca.infobip.com/crl/RootCA.crt /usr/local/share/ca-certificates/infobip-rootca.crt
RUN update-ca-certificates
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

COPY services/telegram-bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/telegram-bot/bot.py .

EXPOSE 8200

CMD ["python", "bot.py"]
