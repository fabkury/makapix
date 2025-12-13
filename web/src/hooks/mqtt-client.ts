import mqtt, { MqttClient } from "mqtt";

export interface PostNotification {
  post_id: number;
  owner_id: string;
  owner_handle: string;
  title: string;
  art_url: string;
  canvas: string;
  promoted_category: string | null;
  created_at: string;
}

export type NotificationCallback = (notification: PostNotification) => void;

/**
 * Minimal MQTT client wrapper for the web UI.
 *
 * Notes:
 * - Uses WebSocket MQTT (see NEXT_PUBLIC_MQTT_WS_URL)
 * - Auth: username=userId, password=access_token (when present)
 * - Subscribes to user-scoped notification topics:
 *   - makapix/post/new/user/{userId}/#
 */
export class MQTTClient {
  private client: MqttClient | null = null;
  private callbacks = new Set<NotificationCallback>();

  constructor(private readonly brokerUrl: string) {}

  async connect(userId: string): Promise<void> {
    const token =
      typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

    // mqtt.js connects immediately; wrap with a Promise to await initial connect/err.
    await new Promise<void>((resolve, reject) => {
      const client = mqtt.connect(this.brokerUrl, {
        clientId: `web-client-${userId}-${Math.random().toString(16).slice(2)}`,
        username: userId,
        password: token || undefined,
        protocolVersion: 5,
        clean: true,
        reconnectPeriod: 5000,
        connectTimeout: 30_000,
      });

      this.client = client;

      const onConnect = () => {
        client.off("error", onError);
        // Subscribe to user notifications
        const userTopic = `makapix/post/new/user/${userId}/#`;
        client.subscribe(userTopic, { qos: 1 }, (err) => {
          if (err) {
            reject(err);
            return;
          }
          resolve();
        });
      };

      const onError = (err: Error) => {
        client.off("connect", onConnect);
        reject(err);
      };

      client.once("connect", onConnect);
      client.once("error", onError);

      client.on("message", (_topic, payload) => {
        try {
          const notification = JSON.parse(payload.toString()) as PostNotification;
          this.callbacks.forEach((cb) => cb(notification));
        } catch {
          // Ignore malformed messages
        }
      });
    });
  }

  onNotification(callback: NotificationCallback): () => void {
    this.callbacks.add(callback);
    return () => {
      this.callbacks.delete(callback);
    };
  }

  disconnect(): void {
    if (this.client) {
      this.client.end(true);
      this.client = null;
    }
    this.callbacks.clear();
  }
}


