"""MQTT publisher backed by a single, long-lived auto-reconnecting client.

The previous implementation rebuilt the client on every failed publish (leaking
orphan loop threads) and defined ``on_disconnect`` with paho's v1 signature.
Under ``CallbackAPIVersion.VERSION2`` paho invokes ``on_disconnect`` with five
positional arguments, so the v1 handler raised ``TypeError`` inside the network
loop thread the moment the broker dropped the connection (e.g. a broker restart
for certificate rotation). That wedged the publisher: the API kept receiving and
processing player requests but could never deliver responses again until the
process was restarted.

This module now creates the client once and lets paho's background loop own all
connection management, including automatic reconnection with backoff — the same
pattern the request/status/view subscribers already use to survive broker
restarts.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any
from uuid import uuid4

from paho.mqtt import client as mqtt_client
from paho.mqtt.client import MQTTMessageInfo

logger = logging.getLogger(__name__)

# Single shared publisher client; paho's loop thread keeps it connected.
_client_lock = threading.Lock()
_client_instance: mqtt_client.Client | None = None

# How long a publish will wait for a live connection before giving up on the
# current attempt (covers cold start and the window just after a broker restart
# while paho is reconnecting in the background).
_CONNECT_WAIT_SECONDS = 5.0


def _make_client() -> mqtt_client.Client:
    """Create, configure, and start the long-lived publisher client."""
    client = mqtt_client.Client(
        callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2,
        client_id=f"api-publisher-{uuid4().hex[:8]}",
        protocol=mqtt_client.MQTTv5,
        transport="tcp",
    )

    # Set username/password for api-server
    username = os.getenv("MQTT_USERNAME", "api-server")
    password = os.getenv("MQTT_PASSWORD", "")
    if username:
        client.username_pw_set(username, password)

    # The API server talks to the broker over the internal plaintext 1883
    # listener; TLS is only configured when explicitly enabled.
    use_tls = os.getenv("MQTT_TLS_ENABLED", "false").lower() == "true"
    if use_tls:
        ca_file = os.getenv("MQTT_CA_FILE")
        if ca_file and os.path.exists(ca_file):
            client.tls_set(ca_certs=ca_file)
        else:
            # Development fallback
            client.tls_set()
            client.tls_insecure_set(True)
            logger.warning("MQTT TLS insecure mode enabled (development only)")

    # paho CallbackAPIVersion.VERSION2 passes five positional arguments to both
    # callbacks. Matching that signature is what lets the publisher survive a
    # broker restart instead of raising TypeError in the loop thread.
    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logger.info("MQTT publisher connected successfully")
        else:
            logger.error(f"MQTT publisher connection failed: {reason_code}")

    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
        logger.warning(f"MQTT publisher disconnected (reason_code={reason_code})")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    # Automatic reconnection with exponential backoff, driven by loop_start().
    client.reconnect_delay_set(min_delay=1, max_delay=60)

    host = os.getenv("MQTT_BROKER_HOST", "mqtt")
    # Use internal non-TLS port for API server communication
    port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    logger.info(f"Connecting MQTT publisher to {host}:{port}")

    # connect_async + loop_start hands all connection management (the initial
    # connect and every later reconnect) to the background thread, so a broker
    # outage at startup or mid-run self-heals without rebuilding the client.
    client.connect_async(host, port, keepalive=60)
    client.loop_start()
    return client


def _ensure_connected() -> mqtt_client.Client:
    """Return the shared publisher client, creating it once on first use.

    Reconnections after the first successful connect are handled automatically
    by paho's loop thread; this only creates the singleton and waits briefly for
    a live link so the first publish doesn't race the initial handshake.
    """
    global _client_instance

    with _client_lock:
        if _client_instance is None:
            _client_instance = _make_client()
        client = _client_instance

    if not client.is_connected():
        deadline = time.monotonic() + _CONNECT_WAIT_SECONDS
        while time.monotonic() < deadline and not client.is_connected():
            time.sleep(0.1)

    return client


def publish(
    topic: str,
    payload: dict[str, Any],
    qos: int = 1,
    retain: bool = False,
    max_retries: int = 3,
) -> bool:
    """
    Publish MQTT message with retry logic.

    Args:
        topic: MQTT topic
        payload: Message payload (will be JSON-encoded)
        qos: Quality of Service level (0, 1, or 2)
        retain: Whether to retain the message
        max_retries: Maximum number of retry attempts

    Returns:
        True if published successfully, False otherwise. The shared client keeps
        reconnecting in the background regardless, so later publishes recover on
        their own.
    """
    try:
        client = _ensure_connected()
    except Exception as e:
        logger.error(f"MQTT connection failed: {e}")
        return False

    payload_json = json.dumps(payload)

    for attempt in range(max_retries):
        try:
            info: MQTTMessageInfo = client.publish(
                topic,
                payload_json,
                qos=qos,
                retain=retain,
            )

            # Wait for publish confirmation
            info.wait_for_publish(timeout=5.0)

            if info.rc == mqtt_client.MQTT_ERR_SUCCESS:
                logger.debug(f"Published MQTT message to {topic}")
                return True
            else:
                logger.warning(
                    f"MQTT publish failed with rc={info.rc} (attempt {attempt + 1}/{max_retries})"
                )
        except Exception as e:
            logger.warning(
                f"MQTT publish exception (attempt {attempt + 1}/{max_retries}): {e}"
            )

        if attempt < max_retries - 1:
            time.sleep(0.5 * (attempt + 1))  # Exponential backoff

    logger.error(
        f"Failed to publish MQTT message to {topic} after {max_retries} attempts"
    )
    return False


def stop_publisher() -> None:
    """Stop the shared publisher's loop thread and disconnect from the broker."""
    global _client_instance

    with _client_lock:
        if _client_instance is not None:
            try:
                _client_instance.loop_stop()
                _client_instance.disconnect()
            finally:
                _client_instance = None
                logger.info("MQTT publisher stopped")
