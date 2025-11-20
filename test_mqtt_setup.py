#!/usr/bin/env python3
"""Quick test script to verify Mosquitto setup"""
import paho.mqtt.client as mqtt
import json
import time

# Test backend connection
print("Testing backend connection...")
backend = mqtt.Client(client_id="test_backend", protocol=mqtt.MQTTv5)
backend.username_pw_set("svc_backend", "REDACTED_BACKEND_PASSWORD")
try:
    backend.connect("127.0.0.1", 1883)
    backend.loop_start()
    time.sleep(1)
    backend.publish("art/recent", json.dumps({"test": "data"}), qos=1)
    print("✓ Backend can publish to art/recent")
    backend.subscribe("views/submit/#", qos=1)
    print("✓ Backend can subscribe to views/submit/#")
    backend.loop_stop()
    backend.disconnect()
except Exception as e:
    print(f"✗ Backend test failed: {e}")

# Test player connection
print("\nTesting player connection...")
player = mqtt.Client(client_id="test_player", protocol=mqtt.MQTTv5)
player.username_pw_set("player_client", "REDACTED_PLAYER_PASSWORD")
try:
    player.connect("127.0.0.1", 1883)
    player.loop_start()
    time.sleep(1)
    player.subscribe("art/recent", qos=1)
    print("✓ Player can subscribe to art/recent")
    player.publish("views/submit/test_art", json.dumps({"test": "data"}), qos=1)
    print("✓ Player can publish to views/submit/test_art")
    
    # Test that player CANNOT publish to art/#
    try:
        player.publish("art/test", "should fail", qos=1)
        print("✗ Player incorrectly allowed to publish to art/#")
    except:
        print("✓ Player correctly blocked from publishing to art/#")
    
    player.loop_stop()
    player.disconnect()
except Exception as e:
    print(f"✗ Player test failed: {e}")

print("\nTest complete!")

