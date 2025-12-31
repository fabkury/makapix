/**
 * React hook for Social Notifications.
 *
 * @deprecated Use useSocialNotificationsContext from contexts/SocialNotificationsContext instead.
 * This hook is kept for backwards compatibility but delegates to the context.
 */

export {
  useSocialNotificationsSafe as useSocialNotifications,
  type SocialNotificationFull,
} from "../contexts/SocialNotificationsContext";
