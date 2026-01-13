/**
 * TypeScript types for user profile features.
 */

export interface BadgeGrant {
  badge: string;
  granted_at: string;
}

export interface TagBadgeInfo {
  badge: string;
  label: string;
  icon_url_16: string;
}

export interface UserProfileStats {
  total_posts: number;
  total_reactions_received: number;
  total_views: number;
  follower_count: number;
}

export interface UserHighlightItem {
  id: number;
  post_id: number;
  position: number;
  post_public_sqid: string;
  post_title: string;
  post_art_url: string;
  post_width: number;
  post_height: number;
  created_at: string;
}

export interface UserProfileEnhanced {
  id: number;
  user_key: string;
  public_sqid: string | null;
  handle: string;
  bio?: string | null;
  tagline?: string | null;
  website?: string | null;
  avatar_url?: string | null;
  badges: BadgeGrant[];
  reputation: number;
  hidden_by_user: boolean;
  hidden_by_mod: boolean;
  non_conformant: boolean;
  deactivated: boolean;
  created_at: string;
  // Enhanced fields
  tag_badges: TagBadgeInfo[];
  stats: UserProfileStats;
  is_following: boolean;
  is_own_profile: boolean;
  highlights: UserHighlightItem[];
}

export interface FollowResponse {
  following: boolean;
  follower_count: number;
}

export interface BadgeDefinition {
  badge: string;
  label: string;
  description?: string | null;
  icon_url_64: string;
  icon_url_16?: string | null;
  is_tag_badge: boolean;
}

export interface ReactedPostItem {
  id: number;
  public_sqid: string;
  title: string;
  art_url: string;
  width: number;
  height: number;
  owner_handle: string;
  reacted_at: string;
  emoji: string;
}

export interface ReactedPostsResponse {
  items: ReactedPostItem[];
  next_cursor: string | null;
}

export interface UserHighlightsResponse {
  items: UserHighlightItem[];
  total: number;
}
