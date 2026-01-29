/**
 * Navigation Context System
 * 
 * Manages card-grid context passed from list pages to post pages
 * for enabling swipe navigation between posts.
 */

export type SourceType = 'recent' | 'recommended' | 'profile' | 'hashtag' | 'search';

export interface NavigationSource {
  type: SourceType;
  id?: string; // For profile (user_id), hashtag (tag name), search (query)
}

export interface NavigationContextPost {
  public_sqid: string;
  id: number;
  owner_id: string;
}

export interface NavigationContext {
  posts: NavigationContextPost[];
  currentIndex: number;
  source: NavigationSource;
  cursor: string | null;
  prevCursor?: string | null; // For backward extension
  timestamp: number; // For expiration checking
}

const STORAGE_KEY = 'makapix_nav_context';
const CONTEXT_EXPIRY_MS = 30 * 60 * 1000; // 30 minutes

/**
 * Check if context is expired
 */
function isContextExpired(context: NavigationContext): boolean {
  const age = Date.now() - context.timestamp;
  return age > CONTEXT_EXPIRY_MS;
}

/**
 * Store navigation context in sessionStorage
 */
export function setNavigationContext(
  posts: NavigationContextPost[],
  currentIndex: number,
  source: NavigationSource,
  cursor: string | null,
  prevCursor?: string | null
): void {
  if (typeof window === 'undefined') return;

  const context: NavigationContext = {
    posts,
    currentIndex,
    source,
    cursor,
    prevCursor,
    timestamp: Date.now(),
  };

  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(context));
  } catch (err) {
    console.warn('Failed to store navigation context:', err);
  }
}

/**
 * Retrieve navigation context from sessionStorage
 */
export function getNavigationContext(): NavigationContext | null {
  if (typeof window === 'undefined') return null;

  try {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (!stored) return null;

    const context: NavigationContext = JSON.parse(stored);
    
    // Check if expired
    if (isContextExpired(context)) {
      clearNavigationContext();
      return null;
    }

    return context;
  } catch (err) {
    console.warn('Failed to retrieve navigation context:', err);
    return null;
  }
}

/**
 * Clear navigation context from sessionStorage
 */
export function clearNavigationContext(): void {
  if (typeof window === 'undefined') return;

  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch (err) {
    console.warn('Failed to clear navigation context:', err);
  }
}

/**
 * Update the current index in the stored context
 */
export function updateContextIndex(newIndex: number): void {
  if (typeof window === 'undefined') return;

  const context = getNavigationContext();
  if (!context) return;

  const updated: NavigationContext = {
    ...context,
    currentIndex: newIndex,
    timestamp: Date.now(), // Refresh timestamp
  };

  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch (err) {
    console.warn('Failed to update navigation context index:', err);
  }
}

/**
 * Extend context with new posts (for pagination)
 */
export function extendContext(
  newPosts: NavigationContextPost[],
  direction: 'forward' | 'backward',
  newCursor: string | null
): void {
  if (typeof window === 'undefined') return;

  const context = getNavigationContext();
  if (!context) return;

  let updated: NavigationContext;

  if (direction === 'forward') {
    // Append new posts and update cursor
    updated = {
      ...context,
      posts: [...context.posts, ...newPosts],
      cursor: newCursor,
      timestamp: Date.now(),
    };
  } else {
    // Prepend new posts and update prevCursor
    updated = {
      ...context,
      posts: [...newPosts, ...context.posts],
      prevCursor: newCursor,
      timestamp: Date.now(),
    };
  }

  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch (err) {
    console.warn('Failed to extend navigation context:', err);
  }
}

/**
 * Find the index of a post in the context by its sqid
 */
export function findPostIndex(context: NavigationContext, sqid: string): number {
  return context.posts.findIndex((post) => post.public_sqid === sqid);
}

