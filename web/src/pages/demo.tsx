import Head from "next/head";
import { useCallback, useEffect, useRef, useState } from "react";
import type { MqttClient } from "mqtt";
import { postJson } from "../lib/api";

type Message = {
  topic: string;
  payload: string;
  receivedAt: string;
};

const DemoPage = () => {
  const [mqttStatus, setMqttStatus] = useState<"connecting" | "connected" | "error">(
    "connecting",
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const clientRef = useRef<MqttClient | null>(null);

  useEffect(() => {
    let active = true;

    (async () => {
      const mqtt = await import("mqtt");
      if (!active) {
        return;
      }

      const wsUrl = process.env.NEXT_PUBLIC_MQTT_WS_URL ?? "ws://localhost:9001";
      const client = mqtt.connect(wsUrl, {
        clientId: `web-demo-${Math.random().toString(16).slice(2)}`,
        reconnectPeriod: 2_000,
      });

      clientRef.current = client;

      client.on("connect", () => {
        if (!active) {
          return;
        }
        setMqttStatus("connected");
        client.subscribe("posts/new/demo", (err) => {
          if (err) {
            console.error("Subscription error", err);
            setMqttStatus("error");
          }
        });
      });

      client.on("message", (topic, payload) => {
        if (!active) {
          return;
        }
        setMessages((prev) =>
          [
            {
              topic,
              payload: payload.toString(),
              receivedAt: new Date().toISOString(),
            },
            ...prev,
          ].slice(0, 10),
        );
      });

      client.on("error", (err) => {
        console.error("MQTT error", err);
        if (active) {
          setMqttStatus("error");
        }
      });
    })().catch((err) => {
      console.error("Failed to start MQTT client", err);
      setMqttStatus("error");
    });

    return () => {
      active = false;
      clientRef.current?.end(true);
      clientRef.current = null;
    };
  }, []);

  const publishDemo = useCallback(async () => {
    try {
      await postJson("/mqtt/demo", {});
      alert("MQTT demo message published! Retained payload should appear below.");
    } catch (error) {
      console.error(error);
      alert("Failed to publish MQTT demo message.");
    }
  }, []);

  return (
    <>
      <Head>
        <title>Makapix MQTT Demo</title>
      </Head>
      <main className="container">
        <h1>MQTT Demo</h1>
        <p>
          Browser client status: <strong className={mqttStatus}>{mqttStatus}</strong>
        </p>
        <button type="button" onClick={publishDemo}>
          Publish MQTT Demo Message
        </button>
        <p className="hint">
          TLS is enforced for device connections on port 8883. The browser connects via
          WebSockets (ws://localhost:9001) for ease of testing. See the docs for details.
        </p>

        <section>
          <h2>Recent Messages</h2>
          {messages.length === 0 ? (
            <p>No messages received yet. Publish one above!</p>
          ) : (
            <ul>
              {messages.map((message, index) => (
                <li key={`${message.topic}-${index}`}>
                  <strong>{message.topic}</strong> @ <code>{message.receivedAt}</code>
                  <pre>{message.payload}</pre>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
      <style jsx>{`
        .container {
          max-width: 720px;
          margin: 3rem auto;
          padding: 0 1rem;
          font-family: system-ui, sans-serif;
        }
        button {
          background: #2563eb;
          border: none;
          color: white;
          padding: 0.75rem 1.25rem;
          border-radius: 0.5rem;
          cursor: pointer;
          font-size: 1rem;
          margin-bottom: 1rem;
        }
        button:hover {
          background: #1d4ed8;
        }
        .connected {
          color: #16a34a;
        }
        .connecting {
          color: #ca8a04;
        }
        .error {
          color: #dc2626;
        }
        pre {
          background: #111827;
          color: #f9fafb;
          padding: 0.5rem;
          border-radius: 0.5rem;
          overflow-x: auto;
        }
        ul {
          list-style: none;
          padding-left: 0;
        }
        li {
          margin-bottom: 1rem;
          border-bottom: 1px solid #e5e7eb;
          padding-bottom: 1rem;
        }
        .hint {
          font-size: 0.9rem;
          color: #4b5563;
        }
      `}</style>
    </>
  );
};

export default DemoPage;
