FROM docker.ib-ci.com/python:3.11-slim

# Add Infobip Root CA (required behind corporate SSL inspection)
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ADD http://ca.infobip.com/crl/RootCA.crt /usr/local/share/ca-certificates/infobip-rootca.crt
RUN update-ca-certificates
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

# Install schema-sync library
COPY ./libs/schema-sync /app/libs/schema-sync
RUN pip install --no-cache-dir /app/libs/schema-sync

# Install admin models (User, APIToken)
COPY ./libs/admin-models /app/libs/admin-models
RUN pip install --no-cache-dir /app/libs/admin-models

# Install meeting-api models (CalendarEvent, database)
COPY ./services/meeting-api /app/services/meeting-api
RUN pip install --no-cache-dir /app/services/meeting-api

COPY ./services/calendar-service/ /app/

RUN pip install --no-cache-dir -r requirements.txt

RUN useradd -r -s /bin/false appuser
USER appuser

EXPOSE 8050

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8050"]
