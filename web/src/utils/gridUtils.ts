/**
 * Grid utility functions for CardGrid and infinite scroll.
 */

const TILE_SIZE = 128;
const MAX_COLUMNS = 8;
const BUFFER_FACTOR = 2.5;
const MIN_PAGE_SIZE = 20;
const MAX_PAGE_SIZE = 100;

/**
 * Calculate optimal page size based on viewport dimensions.
 *
 * Uses visible grid capacity (columns × rows) multiplied by a buffer factor
 * to determine how many items to fetch per request.
 *
 * @returns Page size between MIN_PAGE_SIZE and MAX_PAGE_SIZE
 */
export function calculatePageSize(): number {
  if (typeof window === "undefined") return MIN_PAGE_SIZE;

  const columns = Math.min(
    MAX_COLUMNS,
    Math.max(1, Math.floor(window.innerWidth / TILE_SIZE))
  );
  const visibleRows = Math.max(1, Math.floor(window.innerHeight / TILE_SIZE));
  const rawSize = Math.round(columns * visibleRows * BUFFER_FACTOR);

  return Math.min(MAX_PAGE_SIZE, Math.max(MIN_PAGE_SIZE, rawSize));
}
