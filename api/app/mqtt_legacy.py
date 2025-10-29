from __future__ import annotations

import json
import logging
import os
from typing import Any
from uuid import uuid4

from paho.mqtt import client as mqtt_client
from paho.mqtt.client import MQTTMessageInfo

logger = logging.getLogger(__name__)


def _build_client() -> mqtt_client.Client:
    client = mqtt_client.Client(
        callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2,
        client_id=f"api-publisher-{uuid4().hex}",
        protocol=mqtt_client.MQTTv5,
        transport="tcp",
    )
    username = os.getenv("MQTT_USERNAME")
    password = os.getenv("MQTT_PASSWORD")
    if username:
        client.username_pw_set(username, password)

    use_tls = os.getenv("MQTT_TLS", "true").lower() == "true"
    if use_tls:
        ca_file = os.getenv("MQTT_CA_FILE")
        if ca_file and os.path.exists(ca_file):
            client.tls_set(ca_certs=ca_file)
        else:
            client.tls_set()
            client.tls_insecure_set(True)
    return client


def publish_demo_message(payload: dict[str, Any] | None = None) -> str:
    host = os.getenv("MQTT_HOST", "mqtt")
    port = int(os.getenv("MQTT_PORT", "8883"))
    topic = "posts/new/demo"

    message = payload or {
        "title": "Demo publish",
        "body": "Hello from FastAPI over MQTT!",
    }

    client = _build_client()
    logger.info("Connecting to MQTT broker %s:%s", host, port)
    client.connect(host, port, keepalive=60)
    client.loop_start()
    try:
        info: MQTTMessageInfo = client.publish(
            topic,
            json.dumps(message),
            qos=0,
            retain=True,
        )
        info.wait_for_publish()
        if info.rc != mqtt_client.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish failed with rc={info.rc}")
        logger.info("Published MQTT message to %s", topic)
    finally:
        client.loop_stop()
        client.disconnect()
    return topic
