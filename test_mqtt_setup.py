#!/usr/bin/env python3
"""Quick test script to verify Mosquitto setup"""
import paho.mqtt.client as mqtt
import json
import time

def create_client(client_id: str) -> mqtt.Client:
    """Create an MQTT client that uses the newest callback API when available."""
    kwargs = {"client_id": client_id, "protocol": mqtt.MQTTv5}
    callback_api = getattr(mqtt, "CallbackAPIVersion", None)
    if callback_api is not None and hasattr(callback_api, "VERSION2"):
        kwargs["callback_api_version"] = callback_api.VERSION2
    return mqtt.Client(**kwargs)

# Test backend connection
print("Testing backend connection...")
backend = create_client("test_backend")
backend.username_pw_set("svc_backend", "MD9VZNN9BaUaveP9aMHEBY3Z")
try:
    backend.connect("htzvps", 1883)
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
print("\nTesting player connection...")
player = create_client("test_player")
player.username_pw_set("player_client", "jrRC5P9izjw58sGs7oVFza27")
try:
    player.connect("htzvps", 1883)
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
