# backend_service.py
# Demo MQTT backend service that publishes artwork lists and receives view events
#
# Required environment variables:
#   MQTT_BACKEND_PASSWORD - Password for the svc_backend MQTT user
#
# Optional environment variables:
#   MQTT_BROKER_HOST - MQTT broker hostname (default: 127.0.0.1)
#   MQTT_BROKER_PORT - MQTT broker port (default: 1883)

import json, csv, os, time, threading
from collections import defaultdict
from datetime import datetime
import paho.mqtt.client as mqtt

BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "127.0.0.1")
BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
USERNAME = "svc_backend"
PASSWORD = os.getenv("MQTT_BACKEND_PASSWORD")

if not PASSWORD:
    raise ValueError("MQTT_BACKEND_PASSWORD environment variable is required")

RECENT_TOPIC = "art/recent"
VIEWS_SUB_TOPIC = "views/submit/#"
CSV_PATH = "views.csv"

# Prepare the recent list (50 artwork IDs)
RECENT_ARTWORKS = [f"art_{i:03d}" for i in range(1, 51)]

# In-memory counts mirrored to CSV
counts = defaultdict(int)
counts_lock = threading.Lock()

def load_csv():
    if not os.path.exists(CSV_PATH):
        return
    with open(CSV_PATH, newline="") as f:
        r = csv.reader(f)
        for row in r:
            if len(row) == 2:
                art_id, c = row
                try:
                    counts[art_id] = int(c)
                except:
                    pass

def save_csv():
    tmp = CSV_PATH + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.writer(f)
        for art_id in sorted(counts.keys()):
            w.writerow([art_id, counts[art_id]])
    os.replace(tmp, CSV_PATH)

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[backend] connected rc={rc}")
    # Publish retained recent list
    payload = json.dumps({"artwork_ids": RECENT_ARTWORKS, "generated_at": datetime.utcnow().isoformat()})
    client.publish(RECENT_TOPIC, payload=payload, qos=1, retain=True)
    print(f"[backend] published retained recent list to {RECENT_TOPIC}")

    # Subscribe to views
    client.subscribe(VIEWS_SUB_TOPIC, qos=1)
    print(f"[backend] subscribed to {VIEWS_SUB_TOPIC}")

def on_message(client, userdata, msg):
    try:
        # Topic: views/submit/<artwork_id>
        parts = msg.topic.split("/")
        if len(parts) == 3 and parts[0] == "views" and parts[1] == "submit":
            art_id = parts[2]
            with counts_lock:
                counts[art_id] += 1
                save_csv()
            print(f"[backend] view received for {art_id} | total={counts[art_id]}")
        else:
            print(f"[backend] unexpected topic: {msg.topic}")
    except Exception as e:
        print(f"[backend] error processing message: {e}")

def main():
    load_csv()
    client = mqtt.Client(client_id="backend_service", protocol=mqtt.MQTTv5)
    client.username_pw_set(USERNAME, PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=30)
    client.loop_forever()

if __name__ == "__main__":
    main()
