#!/usr/bin/env python3
"""Quick test script to verify Mosquitto setup

Required environment variables:
  MQTT_BROKER_HOST - MQTT broker hostname (default: localhost)
  MQTT_BROKER_PORT - MQTT broker port (default: 1883)
  MQTT_BACKEND_PASSWORD - Password for svc_backend user
  MQTT_PLAYER_PASSWORD - Password for player_client user
"""
import os
import paho.mqtt.client as mqtt
import json
import time

BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
BACKEND_PASSWORD = os.getenv("MQTT_BACKEND_PASSWORD")
PLAYER_PASSWORD = os.getenv("MQTT_PLAYER_PASSWORD")

if not BACKEND_PASSWORD or not PLAYER_PASSWORD:
    print("ERROR: MQTT_BACKEND_PASSWORD and MQTT_PLAYER_PASSWORD environment variables are required")
    exit(1)

def create_client(client_id: str) -> mqtt.Client:
    """Create an MQTT client that uses the newest callback API when available."""
    kwargs = {"client_id": client_id, "protocol": mqtt.MQTTv5}
    callback_api = getattr(mqtt, "CallbackAPIVersion", None)
    if callback_api is not None and hasattr(callback_api, "VERSION2"):
        kwargs["callback_api_version"] = callback_api.VERSION2
    return mqtt.Client(**kwargs)

# Test backend connection
print(f"Testing backend connection to {BROKER_HOST}:{BROKER_PORT}...")
backend = create_client("test_backend")
backend.username_pw_set("svc_backend", BACKEND_PASSWORD)
try:
    backend.connect(BROKER_HOST, BROKER_PORT)
    backend.loop_start()
    time.sleep(1)
    backend.publish("art/recent", json.dumps({"test": "data"}), qos=1)
    print("[OK] Backend can publish to art/recent")
    backend.subscribe("views/submit/#", qos=1)
    print("[OK] Backend can subscribe to views/submit/#")
    backend.loop_stop()
    backend.disconnect()
except Exception as e:
    print(f"[ERR] Backend test failed: {e}")

# Test player connection
print(f"\nTesting player connection to {BROKER_HOST}:{BROKER_PORT}...")
player = create_client("test_player")
player.username_pw_set("player_client", PLAYER_PASSWORD)
try:
    player.connect(BROKER_HOST, BROKER_PORT)
    player.loop_start()
    time.sleep(1)
    player.subscribe("art/recent", qos=1)
    print("[OK] Player can subscribe to art/recent")
    player.publish("views/submit/test_art", json.dumps({"test": "data"}), qos=1)
    print("[OK] Player can publish to views/submit/test_art")
    
    # Test that player CANNOT publish to art/#
    try:
        player.publish("art/test", "should fail", qos=1)
        print("[ERR] Player incorrectly allowed to publish to art/#")
    except:
        print("[OK] Player correctly blocked from publishing to art/#")
    
    player.loop_stop()
    player.disconnect()
except Exception as e:
    print(f"[ERR] Player test failed: {e}")

print("\nTest complete!")
