FROM eclipse-mosquitto:2.0

RUN apk add --no-cache bash openssl mosquitto-clients

COPY mqtt/mosquitto.conf /mosquitto/config/mosquitto.conf
COPY mqtt/aclfile /mosquitto/config/aclfile
COPY mqtt/scripts/gen-certs.sh /mosquitto/config/scripts/gen-certs.sh

RUN chmod +x /mosquitto/config/scripts/gen-certs.sh && \
    chown mosquitto:mosquitto /mosquitto/config/aclfile && \
    chmod 600 /mosquitto/config/aclfile

ENTRYPOINT ["/mosquitto/config/scripts/gen-certs.sh"]
