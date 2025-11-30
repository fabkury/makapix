"""MQTT publisher with connection pooling and retry logic."""

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

# Singleton MQTT client instance
_client_lock = threading.Lock()
_client_instance: mqtt_client.Client | None = None


def _build_client() -> mqtt_client.Client:
    """Build and configure MQTT client for server publishing."""
    global _client_instance
    
    with _client_lock:
        if _client_instance is not None and _client_instance.is_connected():
            return _client_instance
        
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
        
        # Configure TLS only if explicitly enabled
        # API server uses internal port 1883 (no TLS needed within docker network)
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
        
        # Set callbacks
        def on_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                logger.info("MQTT publisher connected successfully")
            else:
                logger.error(f"MQTT publisher connection failed with code {rc}")
        
        def on_disconnect(client, userdata, rc, properties=None):
            logger.warning(f"MQTT publisher disconnected (rc={rc})")
        
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        
        _client_instance = client
        return client


def _ensure_connected() -> mqtt_client.Client:
    """Ensure MQTT client is connected."""
    client = _build_client()
    
    if not client.is_connected():
        host = os.getenv("MQTT_BROKER_HOST", "mqtt")
        # Use internal non-TLS port for API server communication
        port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
        
        logger.info(f"Connecting MQTT publisher to {host}:{port}")
        try:
            client.connect(host, port, keepalive=60)
            client.loop_start()
            
            # Wait for connection (max 5 seconds)
            for _ in range(50):
                if client.is_connected():
                    break
                time.sleep(0.1)
            
            if not client.is_connected():
                raise RuntimeError("MQTT connection timeout")
        except Exception as e:
            logger.error(f"Failed to connect MQTT publisher: {e}")
            raise
    
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
        True if published successfully, False otherwise
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
                logger.warning(f"MQTT publish failed with rc={info.rc} (attempt {attempt + 1}/{max_retries})")
        except Exception as e:
            logger.warning(f"MQTT publish exception (attempt {attempt + 1}/{max_retries}): {e}")
        
        if attempt < max_retries - 1:
            time.sleep(0.5 * (attempt + 1))  # Exponential backoff
    
    logger.error(f"Failed to publish MQTT message to {topic} after {max_retries} attempts")
    return False

