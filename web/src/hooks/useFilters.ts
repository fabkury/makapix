import { useRouter } from 'next/router';
import { useCallback, useMemo } from 'react';

export interface FilterConfig {
  // Numeric filters
  width?: { min?: number; max?: number };
  height?: { min?: number; max?: number };
  file_bytes?: { min?: number; max?: number };
  frame_count?: { min?: number; max?: number };
  unique_colors?: { min?: number; max?: number };
  reactions?: { min?: number; max?: number };
  comments?: { min?: number; max?: number };

  // Date filters
  creation_date?: { min?: string; max?: string };

  // Boolean filters
  has_transparency?: boolean | null;
  has_semitransparency?: boolean | null;

  // Array filters (multi-select)
  file_format?: string[];
  kind?: string[];

  // Sorting
  sortBy?: string;
  sortOrder?: "asc" | "desc";
}

// Helper functions
function parseRangeParam(min: string | string[] | undefined, max: string | string[] | undefined) {
  const minVal = Array.isArray(min) ? min[0] : min;
  const maxVal = Array.isArray(max) ? max[0] : max;
  if (!minVal && !maxVal) return undefined;
  return {
    min: minVal ? parseInt(minVal, 10) : undefined,
    max: maxVal ? parseInt(maxVal, 10) : undefined,
  };
}

function parseBoolParam(val: string | string[] | undefined): boolean | null {
  const v = Array.isArray(val) ? val[0] : val;
  if (v === 'true') return true;
  if (v === 'false') return false;
  return null;
}

function parseArrayParam(val: string | string[] | undefined): string[] | undefined {
  if (!val) return undefined;
  return Array.isArray(val) ? val : [val];
}

function parseDateRangeParam(min: string | string[] | undefined, max: string | string[] | undefined) {
  const minVal = Array.isArray(min) ? min[0] : min;
  const maxVal = Array.isArray(max) ? max[0] : max;
  if (!minVal && !maxVal) return undefined;
  return {
    min: minVal || undefined,
    max: maxVal || undefined,
  };
}

export function useFilters() {
  const router = useRouter();

  // Parse filters from URL query params
  const filters: FilterConfig = useMemo(() => {
    const query = router.query;
    return {
      width: parseRangeParam(query.width_min as string, query.width_max as string),
      height: parseRangeParam(query.height_min as string, query.height_max as string),
      file_bytes: parseRangeParam(query.file_bytes_min as string, query.file_bytes_max as string),
      frame_count: parseRangeParam(query.frame_count_min as string, query.frame_count_max as string),
      unique_colors: parseRangeParam(query.unique_colors_min as string, query.unique_colors_max as string),
      reactions: parseRangeParam(query.reactions_min as string, query.reactions_max as string),
      comments: parseRangeParam(query.comments_min as string, query.comments_max as string),
      creation_date: parseDateRangeParam(query.created_after as string, query.created_before as string),
      has_transparency: parseBoolParam(query.has_transparency),
      has_semitransparency: parseBoolParam(query.has_semitransparency),
      file_format: parseArrayParam(query.file_format),
      kind: parseArrayParam(query.kind),
      sortBy: (query.sort as string) || undefined,
      sortOrder: (query.order as 'asc' | 'desc') || undefined,
    };
  }, [router.query]);

  // Check if any filters are active (non-default values)
  const hasActiveFilters = useMemo(() => {
    return !!(
      filters.width ||
      filters.height ||
      filters.file_bytes ||
      filters.frame_count ||
      filters.unique_colors ||
      filters.reactions ||
      filters.comments ||
      filters.creation_date ||
      filters.has_transparency !== null && filters.has_transparency !== undefined ||
      filters.has_semitransparency !== null && filters.has_semitransparency !== undefined ||
      (filters.file_format && filters.file_format.length > 0 && filters.file_format.length < 4) ||
      (filters.kind && filters.kind.length > 0 && filters.kind.length < 2) ||
      (filters.sortBy && filters.sortBy !== 'created_at') ||
      (filters.sortOrder && filters.sortOrder !== 'desc')
    );
  }, [filters]);

  // Update URL when filters change
  const setFilters = useCallback((newFilters: FilterConfig) => {
    const query: Record<string, string | string[]> = {};

    // Preserve existing route params that aren't filter-related
    const preserveParams = ['tag', 'id', 'sqid', 'q'];
    preserveParams.forEach(param => {
      if (router.query[param]) {
        query[param] = router.query[param] as string;
      }
    });

    // Add range params
    if (newFilters.width?.min) query.width_min = String(newFilters.width.min);
    if (newFilters.width?.max) query.width_max = String(newFilters.width.max);
    if (newFilters.height?.min) query.height_min = String(newFilters.height.min);
    if (newFilters.height?.max) query.height_max = String(newFilters.height.max);
    if (newFilters.file_bytes?.min) query.file_bytes_min = String(newFilters.file_bytes.min);
    if (newFilters.file_bytes?.max) query.file_bytes_max = String(newFilters.file_bytes.max);
    if (newFilters.frame_count?.min) query.frame_count_min = String(newFilters.frame_count.min);
    if (newFilters.frame_count?.max) query.frame_count_max = String(newFilters.frame_count.max);
    if (newFilters.unique_colors?.min) query.unique_colors_min = String(newFilters.unique_colors.min);
    if (newFilters.unique_colors?.max) query.unique_colors_max = String(newFilters.unique_colors.max);
    if (newFilters.reactions?.min) query.reactions_min = String(newFilters.reactions.min);
    if (newFilters.reactions?.max) query.reactions_max = String(newFilters.reactions.max);
    if (newFilters.comments?.min) query.comments_min = String(newFilters.comments.min);
    if (newFilters.comments?.max) query.comments_max = String(newFilters.comments.max);

    // Date params
    if (newFilters.creation_date?.min) query.created_after = newFilters.creation_date.min;
    if (newFilters.creation_date?.max) query.created_before = newFilters.creation_date.max;

    // Boolean params
    if (newFilters.has_transparency !== null && newFilters.has_transparency !== undefined) {
      query.has_transparency = String(newFilters.has_transparency);
    }
    if (newFilters.has_semitransparency !== null && newFilters.has_semitransparency !== undefined) {
      query.has_semitransparency = String(newFilters.has_semitransparency);
    }

    // Array params
    if (newFilters.file_format && newFilters.file_format.length > 0) {
      query.file_format = newFilters.file_format;
    }
    if (newFilters.kind && newFilters.kind.length > 0) {
      query.kind = newFilters.kind;
    }

    // Sort params
    if (newFilters.sortBy && newFilters.sortBy !== 'created_at') {
      query.sort = newFilters.sortBy;
    }
    if (newFilters.sortOrder && newFilters.sortOrder !== 'desc') {
      query.order = newFilters.sortOrder;
    }

    // Update URL without full navigation
    router.replace(
      { pathname: router.pathname, query },
      undefined,
      { shallow: true }
    );
  }, [router]);

  // Build API query string from filters
  const buildApiQuery = useCallback((baseParams: Record<string, string> = {}) => {
    const params = new URLSearchParams(baseParams);

    // Add filter params for API
    if (filters.width?.min) params.set('width_min', String(filters.width.min));
    if (filters.width?.max) params.set('width_max', String(filters.width.max));
    if (filters.height?.min) params.set('height_min', String(filters.height.min));
    if (filters.height?.max) params.set('height_max', String(filters.height.max));
    if (filters.file_bytes?.min) params.set('file_bytes_min', String(filters.file_bytes.min));
    if (filters.file_bytes?.max) params.set('file_bytes_max', String(filters.file_bytes.max));
    if (filters.frame_count?.min) params.set('frame_count_min', String(filters.frame_count.min));
    if (filters.frame_count?.max) params.set('frame_count_max', String(filters.frame_count.max));
    if (filters.unique_colors?.min) params.set('unique_colors_min', String(filters.unique_colors.min));
    if (filters.unique_colors?.max) params.set('unique_colors_max', String(filters.unique_colors.max));
    if (filters.reactions?.min) params.set('reactions_min', String(filters.reactions.min));
    if (filters.reactions?.max) params.set('reactions_max', String(filters.reactions.max));
    if (filters.comments?.min) params.set('comments_min', String(filters.comments.min));
    if (filters.comments?.max) params.set('comments_max', String(filters.comments.max));

    // Date params
    if (filters.creation_date?.min) params.set('created_after', filters.creation_date.min);
    if (filters.creation_date?.max) params.set('created_before', filters.creation_date.max);

    // Boolean params
    if (filters.has_transparency !== null && filters.has_transparency !== undefined) {
      params.set('has_transparency', String(filters.has_transparency));
    }
    if (filters.has_semitransparency !== null && filters.has_semitransparency !== undefined) {
      params.set('has_semitransparency', String(filters.has_semitransparency));
    }

    // Array params
    if (filters.file_format && filters.file_format.length > 0) {
      filters.file_format.forEach(f => params.append('file_format', f));
    }
    if (filters.kind && filters.kind.length > 0) {
      filters.kind.forEach(k => params.append('kind', k));
    }

    // Sort params
    if (filters.sortBy) params.set('sort', filters.sortBy);
    if (filters.sortOrder) params.set('order', filters.sortOrder);

    return params.toString();
  }, [filters]);

  // Clear all filters
  const clearFilters = useCallback(() => {
    const query: Record<string, string> = {};

    // Preserve existing route params that aren't filter-related
    const preserveParams = ['tag', 'id', 'sqid', 'q'];
    preserveParams.forEach(param => {
      if (router.query[param]) {
        query[param] = router.query[param] as string;
      }
    });

    router.replace(
      { pathname: router.pathname, query },
      undefined,
      { shallow: true }
    );
  }, [router]);

  return { filters, setFilters, buildApiQuery, clearFilters, hasActiveFilters };
}
