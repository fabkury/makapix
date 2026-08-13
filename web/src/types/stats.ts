/**
 * Shared response types for the artwork statistics endpoints
 * (docs/artwork-views/): GET /api/post/{id}/stats and
 * GET /api/user/{sqid}/artist-dashboard.
 *
 * Views (deliberate looks, deduped per visitor per day) and Impressions
 * (playback exposure) are separate metrics, never summed (D2).
 * `views_by_type` is intentionally an open Record: current payloads carry
 * canonical {view, impression} keys, but the UI must never crash on
 * historical keys.
 */

export interface DailyViewCount {
  date: string; // YYYY-MM-DD
  views: number;
  unique_viewers: number;
  impressions: number;
}

export interface PostStatsResponse {
  post_id: number | string;
  // All statistics (including unauthenticated), 30-day window
  total_views: number;
  unique_viewers: number;
  total_impressions: number;
  views_by_country: Record<string, number>;
  views_by_device: Record<string, number>;
  views_by_type: Record<string, number>;
  daily_views: DailyViewCount[];
  total_reactions: number;
  reactions_by_emoji: Record<string, number>;
  total_comments: number;
  // Authenticated-only statistics
  total_views_authenticated: number;
  unique_viewers_authenticated: number;
  total_impressions_authenticated: number;
  views_by_country_authenticated: Record<string, number>;
  views_by_device_authenticated: Record<string, number>;
  views_by_type_authenticated: Record<string, number>;
  daily_views_authenticated: DailyViewCount[];
  total_reactions_authenticated: number;
  reactions_by_emoji_authenticated: Record<string, number>;
  total_comments_authenticated: number;
  // Timestamps
  first_view_at: string | null;
  last_view_at: string | null;
  computed_at: string;
}

export interface ArtistStatsResponse {
  user_id: number;
  user_key: string;
  total_posts: number;
  total_views: number;
  unique_viewers: number;
  total_impressions: number;
  views_by_country: Record<string, number>;
  views_by_device: Record<string, number>;
  daily_views: DailyViewCount[];
  total_reactions: number;
  reactions_by_emoji: Record<string, number>;
  total_comments: number;
  total_views_authenticated: number;
  unique_viewers_authenticated: number;
  total_impressions_authenticated: number;
  views_by_country_authenticated: Record<string, number>;
  views_by_device_authenticated: Record<string, number>;
  daily_views_authenticated: DailyViewCount[];
  total_reactions_authenticated: number;
  reactions_by_emoji_authenticated: Record<string, number>;
  total_comments_authenticated: number;
  first_post_at: string | null;
  latest_post_at: string | null;
  computed_at: string;
}

export interface PostStatsListItem {
  post_id: number;
  public_sqid: string;
  title: string;
  created_at: string;
  total_views: number;
  unique_viewers: number;
  total_impressions: number;
  total_reactions: number;
  total_comments: number;
  total_views_authenticated: number;
  unique_viewers_authenticated: number;
  total_impressions_authenticated: number;
  total_reactions_authenticated: number;
  total_comments_authenticated: number;
}

export interface ArtistDashboardResponse {
  artist_stats: ArtistStatsResponse;
  posts: PostStatsListItem[];
  total_posts: number;
  page: number;
  page_size: number;
  has_more: boolean;
}
