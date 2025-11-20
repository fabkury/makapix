# player_client.py
import json, time, itertools
from datetime import datetime
import paho.mqtt.client as mqtt

BROKER_HOST = "127.0.0.1"
BROKER_PORT = 1883
USERNAME = "player_client"
PASSWORD = "jrRC5P9izjw58sGs7oVFza27"

RECENT_TOPIC = "art/recent"
VIEW_PUB_PREFIX = "views/submit/"

artwork_ids = []

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[player] connected rc={rc}")
    client.subscribe(RECENT_TOPIC, qos=1)
    print(f"[player] subscribed to {RECENT_TOPIC}")

def on_message(client, userdata, msg):
    global artwork_ids
    if msg.topic == RECENT_TOPIC:
        try:
            data = json.loads(msg.payload.decode("utf-8"))
            artwork_ids = data.get("artwork_ids", [])
            print(f"[player] received {len(artwork_ids)} recent artworks")
        except Exception as e:
            print(f"[player] parse error: {e}")

def main():
    client = mqtt.Client(client_id="player_demo_1", protocol=mqtt.MQTTv5)
    client.username_pw_set(USERNAME, PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=30)
    client.loop_start()

    # Wait until we receive the retained RECENT list
    for _ in range(60):
        if artwork_ids:
            break
        time.sleep(0.5)

    if not artwork_ids:
        print("[player] no recent artworks received within timeout")
        client.loop_stop()
        return

    # Simulate display: one every 5 seconds, publish a view for each
    for art_id in artwork_ids:
        print(f"[player] displaying {art_id}")
        view_topic = VIEW_PUB_PREFIX + art_id
        payload = json.dumps({"artwork_id": art_id, "ts": datetime.utcnow().isoformat(), "player_id": "player_demo_1"})
        client.publish(view_topic, payload=payload, qos=1, retain=False)
        print(f"[player] published view -> {view_topic}")
        time.sleep(5)

    client.loop_stop()
    print("[player] done.")

if __name__ == "__main__":
    main()

