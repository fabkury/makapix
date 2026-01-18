import { useRouter } from 'next/router';
import { useCallback, useMemo } from 'react';

export interface FilterConfig {
  // New badge-based dimension filters
  base?: number;        // Single badge value (8, 16, 32, 64) or 128 for 128+
  size?: number[];      // Up to 3 badge values with OR logic

  // File size (keep slider)
  file_bytes?: { min?: number; max?: number };

  // Animation kind (single select badge-style)
  kind?: string[];

  // Sorting
  sortBy?: string;
  sortOrder?: "asc" | "desc";
}

// Helper functions
function parseNumberParam(val: string | string[] | undefined): number | undefined {
  const v = Array.isArray(val) ? val[0] : val;
  if (!v) return undefined;
  const num = parseInt(v, 10);
  return isNaN(num) ? undefined : num;
}

function parseNumberArrayParam(val: string | string[] | undefined): number[] | undefined {
  if (!val) return undefined;
  const arr = Array.isArray(val) ? val : [val];
  const nums = arr.map(v => parseInt(v, 10)).filter(n => !isNaN(n));
  return nums.length > 0 ? nums : undefined;
}

function parseRangeParam(min: string | string[] | undefined, max: string | string[] | undefined) {
  const minVal = Array.isArray(min) ? min[0] : min;
  const maxVal = Array.isArray(max) ? max[0] : max;
  if (!minVal && !maxVal) return undefined;
  return {
    min: minVal ? parseInt(minVal, 10) : undefined,
    max: maxVal ? parseInt(maxVal, 10) : undefined,
  };
}

function parseArrayParam(val: string | string[] | undefined): string[] | undefined {
  if (!val) return undefined;
  return Array.isArray(val) ? val : [val];
}

export function useFilters() {
  const router = useRouter();

  // Parse filters from URL query params
  const filters: FilterConfig = useMemo(() => {
    const query = router.query;

    // Parse base: check for base_gte (128+) or base array
    let base: number | undefined;
    if (query.base_gte) {
      base = 128; // 128+ indicator
    } else if (query.base) {
      const baseArr = parseNumberArrayParam(query.base as string | string[]);
      base = baseArr?.[0]; // Single select, take first
    }

    // Parse size: collect from both size array and size_gte
    let size: number[] | undefined;
    const sizeArr = parseNumberArrayParam(query.size as string | string[]);
    const sizeGte = parseNumberParam(query.size_gte as string);
    if (sizeArr || sizeGte) {
      size = sizeArr ? [...sizeArr] : [];
      if (sizeGte) {
        size.push(128); // 128+ indicator
      }
    }

    return {
      base,
      size,
      file_bytes: parseRangeParam(query.file_bytes_min as string, query.file_bytes_max as string),
      kind: parseArrayParam(query.kind),
      sortBy: (query.sort as string) || undefined,
      sortOrder: (query.order as 'asc' | 'desc') || undefined,
    };
  }, [router.query]);

  // Check if any filters are active (non-default values)
  const hasActiveFilters = useMemo(() => {
    return !!(
      filters.base !== undefined ||
      (filters.size && filters.size.length > 0) ||
      filters.file_bytes ||
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

    // Base filter (single select badge)
    if (newFilters.base !== undefined) {
      if (newFilters.base >= 128) {
        query.base_gte = '128';
      } else {
        query.base = String(newFilters.base);
      }
    }

    // Size filter (multi-select badges, max 3)
    if (newFilters.size && newFilters.size.length > 0) {
      const regularSizes = newFilters.size.filter(s => s < 128);
      const has128Plus = newFilters.size.some(s => s >= 128);

      if (regularSizes.length > 0) {
        query.size = regularSizes.map(String);
      }
      if (has128Plus) {
        query.size_gte = '128';
      }
    }

    // File bytes range
    if (newFilters.file_bytes?.min) query.file_bytes_min = String(newFilters.file_bytes.min);
    if (newFilters.file_bytes?.max) query.file_bytes_max = String(newFilters.file_bytes.max);

    // Kind (animation type)
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

    // Base filter
    if (filters.base !== undefined) {
      if (filters.base >= 128) {
        params.set('base_gte', '128');
      } else {
        params.append('base', String(filters.base));
      }
    }

    // Size filter (multi-select with OR logic)
    if (filters.size && filters.size.length > 0) {
      const regularSizes = filters.size.filter(s => s < 128);
      const has128Plus = filters.size.some(s => s >= 128);

      regularSizes.forEach(s => params.append('size', String(s)));
      if (has128Plus) {
        params.set('size_gte', '128');
      }
    }

    // File bytes range
    if (filters.file_bytes?.min) params.set('file_bytes_min', String(filters.file_bytes.min));
    if (filters.file_bytes?.max) params.set('file_bytes_max', String(filters.file_bytes.max));

    // Kind filter
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
