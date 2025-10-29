#!/usr/bin/env python3
"""
MQTT Player Stub - Physical device stub for testing MQTT notifications.

This script connects to the MQTT broker using TLS client certificates
and subscribes to notification topics, logging received messages.

Usage:
    python mqtt_player_stub.py --device-id <device_id> --user-id <user_id> \
        --ca-cert <ca.crt> --client-cert <client.crt> --client-key <client.key> \
        --broker-host <host> --broker-port <port>
"""

import argparse
import json
import logging
import sys
from pathlib import Path

try:
    import paho.mqtt.client as mqtt_client
except ImportError:
    print("Error: paho-mqtt not installed. Install with: pip install paho-mqtt")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def on_connect(client, userdata, flags, rc, properties=None):
    """Callback when MQTT client connects."""
    if rc == 0:
        logger.info("Connected to MQTT broker successfully")
        
        # Subscribe to user-specific notifications
        user_id = userdata.get("user_id")
        if user_id:
            user_topic = f"makapix/posts/new/user/{user_id}/+"
            client.subscribe(user_topic, qos=1)
            logger.info(f"Subscribed to {user_topic}")
        
        # Subscribe to category notifications
        category_topic = "makapix/posts/new/category/+/+"
        client.subscribe(category_topic, qos=1)
        logger.info(f"Subscribed to {category_topic}")
        
        # Subscribe to generic notifications (for debugging)
        generic_topic = "makapix/posts/new/+"
        client.subscribe(generic_topic, qos=1)
        logger.info(f"Subscribed to {generic_topic}")
    else:
        logger.error(f"Failed to connect to MQTT broker: rc={rc}")
        sys.exit(1)


def on_disconnect(client, userdata, rc, properties=None):
    """Callback when MQTT client disconnects."""
    logger.warning(f"Disconnected from MQTT broker (rc={rc})")


def on_message(client, userdata, msg):
    """Callback when MQTT message is received."""
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        logger.info(f"Received notification on topic: {msg.topic}")
        logger.info(f"Post ID: {payload.get('post_id')}")
        logger.info(f"Title: {payload.get('title')}")
        logger.info(f"Owner: {payload.get('owner_handle')}")
        logger.info(f"Category: {payload.get('promoted_category', 'None')}")
        logger.info(f"Art URL: {payload.get('art_url')}")
        logger.info("---")
        
        # In a real implementation, this would display the image on a physical device
        # For now, we just log it
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON payload: {e}")
    except Exception as e:
        logger.error(f"Error processing message: {e}")


def main():
    parser = argparse.ArgumentParser(description="MQTT Player Stub")
    parser.add_argument("--device-id", required=True, help="Device UUID")
    parser.add_argument("--user-id", required=True, help="User UUID")
    parser.add_argument("--ca-cert", required=True, help="Path to CA certificate")
    parser.add_argument("--client-cert", required=True, help="Path to client certificate")
    parser.add_argument("--client-key", required=True, help="Path to client private key")
    parser.add_argument("--broker-host", default="localhost", help="MQTT broker host")
    parser.add_argument("--broker-port", type=int, default=8883, help="MQTT broker port")
    
    args = parser.parse_args()
    
    # Verify certificate files exist
    for cert_file, name in [
        (args.ca_cert, "CA certificate"),
        (args.client_cert, "Client certificate"),
        (args.client_key, "Client key"),
    ]:
        if not Path(cert_file).exists():
            logger.error(f"{name} not found: {cert_file}")
            sys.exit(1)
    
    # Create MQTT client
    client_id = f"device-{args.device_id[:8]}"
    client = mqtt_client.Client(
        callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt_client.MQTTv5,
        transport="tcp",
    )
    
    # Configure TLS
    client.tls_set(
        ca_certs=args.ca_cert,
        certfile=args.client_cert,
        keyfile=args.client_key,
    )
    
    # Set callbacks
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    
    # Store user_id in userdata for callback
    client.user_data_set({"user_id": args.user_id})
    
    # Connect to broker
    logger.info(f"Connecting to MQTT broker at {args.broker_host}:{args.broker_port}...")
    try:
        client.connect(args.broker_host, args.broker_port, keepalive=60)
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        sys.exit(1)
    
    # Start loop
    logger.info("Listening for notifications... (Press Ctrl+C to stop)")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        client.disconnect()
        sys.exit(0)


if __name__ == "__main__":
    main()

