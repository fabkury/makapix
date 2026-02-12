/**
 * MQTT client for web player notifications.
 * 
 * Connects to MQTT broker via WebSocket and subscribes to notification topics.
 */

import mqtt, { MqttClient, IClientOptions } from "mqtt";

// Logger that only outputs in development mode
const logger = {
  log: (...args: unknown[]) => {
    if (process.env.NODE_ENV === 'development') {
      // eslint-disable-next-line no-console
      console.log('[MQTT]', ...args);
    }
  },
  error: (...args: unknown[]) => {
    // Always log errors
    // eslint-disable-next-line no-console
    console.error('[MQTT]', ...args);
  },
};

export interface PostNotification {
  post_id: string;
  owner_id: string;
  owner_handle: string;
  title: string;
  art_url: string;
  width: number;
  height: number;
  promoted_category: string | null;
  created_at: string;
}

export interface SocialNotification {
  id: string;
  notification_type: "reaction" | "comment" | "comment_reply" | "moderator_granted" | "moderator_revoked" | "follow";
  post_id: number | null;
  actor_handle: string | null;
  actor_avatar_url: string | null;
  emoji: string | null;
  comment_preview: string | null;
  content_title: string | null;
  content_sqid: string | null;
  content_art_url: string | null;
  created_at: string;
}

export type NotificationCallback = (notification: PostNotification) => void;
export type SocialNotificationCallback = (notification: SocialNotification) => void;

export class MQTTClient {
  private client: MqttClient | null = null;
  private url: string;
  private userId: string | null = null;
  private isConnected = false;
  private callbacks: Set<NotificationCallback> = new Set();
  private socialCallbacks: Set<SocialNotificationCallback> = new Set();

  constructor(url: string) {
    this.url = url;
  }

  /**
   * Connect to MQTT broker.
   */
  connect(userId: string): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.client?.connected) {
        resolve();
        return;
      }

      this.userId = userId;

      // For WebSocket, we use shared webclient credentials
      // This is safe because web clients can only READ (subscribe) to topics
      const options: IClientOptions = {
        // Protocol is inferred from URL (ws:// or wss://)
        reconnectPeriod: 5000,
        connectTimeout: 10000,
        // Shared webclient user for all web browser clients
        username: "webclient",
        password: process.env.NEXT_PUBLIC_MQTT_WEBCLIENT_PASSWORD || "",
        // Client ID includes userId for debugging/tracking
        clientId: `web-${userId}-${Date.now()}`,
        clean: true,
      };

      try {
        this.client = mqtt.connect(this.url, options);

        this.client.on("connect", () => {
          this.isConnected = true;
          logger.log("Client connected");
          this.subscribeToTopics();
          resolve();
        });

        this.client.on("error", (error) => {
          logger.error("Client error:", error);
          this.isConnected = false;
          reject(error);
        });

        this.client.on("disconnect", () => {
          logger.log("Client disconnected");
          this.isConnected = false;
        });

        this.client.on("reconnect", () => {
          logger.log("Client reconnecting...");
        });

        this.client.on("message", (topic, message) => {
          try {
            const payload = JSON.parse(message.toString());

            // Route message based on topic
            if (topic.startsWith("makapix/social-notifications/")) {
              // Social notification (reaction or comment)
              const notification: SocialNotification = payload;
              this.socialCallbacks.forEach((callback) => callback(notification));
            } else {
              // Post notification (new post from followed user or category)
              const notification: PostNotification = payload;
              this.callbacks.forEach((callback) => callback(notification));
            }
          } catch (error) {
            logger.error("Failed to parse message:", error);
          }
        });
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Subscribe to notification topics.
   */
  private subscribeToTopics(): void {
    if (!this.client || !this.userId) {
      return;
    }

    // Subscribe to user-specific notifications (new posts from followed users)
    const userTopic = `makapix/posts/new/user/${this.userId}/+`;
    this.client.subscribe(userTopic, { qos: 1 }, (error) => {
      if (error) {
        logger.error(`Failed to subscribe to ${userTopic}:`, error);
      } else {
        logger.log(`Subscribed to ${userTopic}`);
      }
    });

    // Subscribe to category notifications (daily's-best)
    const categoryTopic = `makapix/posts/new/category/daily's-best/+`;
    this.client.subscribe(categoryTopic, { qos: 1 }, (error) => {
      if (error) {
        logger.error(`Failed to subscribe to ${categoryTopic}:`, error);
      } else {
        logger.log(`Subscribed to ${categoryTopic}`);
      }
    });

    // Subscribe to social notifications (reactions and comments on user's posts)
    const socialTopic = `makapix/social-notifications/user/${this.userId}`;
    this.client.subscribe(socialTopic, { qos: 1 }, (error) => {
      if (error) {
        logger.error(`Failed to subscribe to ${socialTopic}:`, error);
      } else {
        logger.log(`Subscribed to ${socialTopic}`);
      }
    });
  }

  /**
   * Register a callback for post notifications (new posts from followed users).
   */
  onNotification(callback: NotificationCallback): () => void {
    this.callbacks.add(callback);
    // Return unsubscribe function
    return () => {
      this.callbacks.delete(callback);
    };
  }

  /**
   * Register a callback for social notifications (reactions and comments).
   */
  onSocialNotification(callback: SocialNotificationCallback): () => void {
    this.socialCallbacks.add(callback);
    // Return unsubscribe function
    return () => {
      this.socialCallbacks.delete(callback);
    };
  }

  /**
   * Disconnect from MQTT broker.
   */
  disconnect(): void {
    if (this.client) {
      this.client.end();
      this.client = null;
      this.isConnected = false;
      this.callbacks.clear();
      this.socialCallbacks.clear();
    }
  }

  /**
   * Check if client is connected.
   */
  get connected(): boolean {
    return this.isConnected;
  }
}

