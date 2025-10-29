/**
 * React hook for MQTT notifications.
 * 
 * Manages MQTT connection lifecycle and provides notifications.
 */

import { useEffect, useRef, useState } from "react";
import { MQTTClient, PostNotification, NotificationCallback } from "./mqtt-client";

const MQTT_URL = process.env.NEXT_PUBLIC_MQTT_WS_URL || "ws://localhost:9001";

export function useMqttNotifications(userId: string | null) {
  const [notifications, setNotifications] = useState<PostNotification[]>([]);
  const [connected, setConnected] = useState(false);
  const clientRef = useRef<MQTTClient | null>(null);

  useEffect(() => {
    if (!userId) {
      return;
    }

    // Create MQTT client
    const client = new MQTTClient(MQTT_URL);
    clientRef.current = client;

    // Connect
    client
      .connect(userId)
      .then(() => {
        setConnected(true);
      })
      .catch((error) => {
        console.error("Failed to connect to MQTT:", error);
        setConnected(false);
      });

    // Register notification callback
    const unsubscribe = client.onNotification((notification) => {
      setNotifications((prev) => [notification, ...prev].slice(0, 50)); // Keep last 50
    });

    // Cleanup on unmount
    return () => {
      unsubscribe();
      client.disconnect();
      setConnected(false);
    };
  }, [userId]);

  const clearNotifications = () => {
    setNotifications([]);
  };

  return {
    notifications,
    connected,
    clearNotifications,
  };
}

