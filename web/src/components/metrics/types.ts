export interface DailyCount {
  date: string;
  count: number;
}

export interface HourlyCount {
  hour: string;
  count: number;
}

export interface SitewideStats {
  total_page_views_14d: number;
  unique_visitors_14d: number;
  new_signups_14d: number;
  new_posts_14d: number;
  total_api_calls_14d: number;
  total_errors_14d: number;
  total_page_views_14d_authenticated: number;
  unique_visitors_14d_authenticated: number;
  daily_views: DailyCount[];
  daily_signups: DailyCount[];
  daily_posts: DailyCount[];
  daily_views_authenticated: DailyCount[];
  daily_unique_visitors: DailyCount[];
  daily_unique_visitors_authenticated: DailyCount[];
  hourly_views: HourlyCount[];
  hourly_views_authenticated: HourlyCount[];
  hourly_unique_visitors: HourlyCount[];
  hourly_unique_visitors_authenticated: HourlyCount[];
  views_by_page: Record<string, number>;
  views_by_country: Record<string, number>;
  views_by_device: Record<string, number>;
  top_referrers: Record<string, number>;
  views_by_page_authenticated: Record<string, number>;
  views_by_country_authenticated: Record<string, number>;
  views_by_device_authenticated: Record<string, number>;
  top_referrers_authenticated: Record<string, number>;
  errors_by_type: Record<string, number>;
  // Player Activity
  total_player_artwork_views_14d: number;
  active_players_14d: number;
  daily_player_views: DailyCount[];
  views_by_player: Record<string, number>;
  computed_at: string;
}

export interface OnlinePlayer {
  id: string;
  name: string | null;
  device_model: string | null;
  firmware_version: string | null;
  last_seen_at: string | null;
  owner_handle: string | null;
}

export interface TrendPoint {
  x: string;
  primary: number;
  secondary?: number;
}
