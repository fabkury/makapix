FROM eclipse-mosquitto:2.0

RUN apk add --no-cache bash openssl mosquitto-clients

# All broker config is sourced from mqtt/config/, which is also the directory
# bind-mounted onto /mosquitto/config at runtime. Sourcing the baked copies from
# the same tree keeps them from diverging from what actually runs (the mount
# would otherwise shadow a baked copy from a different path — see git history).
COPY mqtt/config/mosquitto.conf /mosquitto/config/mosquitto.conf
COPY mqtt/config/acls /mosquitto/config/acls
COPY mqtt/config/scripts/gen-certs.sh /mosquitto/config/scripts/gen-certs.sh
COPY mqtt/config/scripts/gen-passwd.sh /mosquitto/config/scripts/gen-passwd.sh

RUN chmod +x /mosquitto/config/scripts/gen-certs.sh && \
    chmod +x /mosquitto/config/scripts/gen-passwd.sh && \
    chown mosquitto:mosquitto /mosquitto/config/acls && \
    chmod 600 /mosquitto/config/acls

ENTRYPOINT ["/mosquitto/config/scripts/gen-certs.sh"]
