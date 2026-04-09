/** Browser-side WebP support detection and art_url fallback for legacy browsers. */

let _supportsWebP: boolean | null = null;

/** Detect WebP support via canvas (synchronous, result cached). */
export function supportsWebP(): boolean {
  if (_supportsWebP !== null) return _supportsWebP;
  try {
    const canvas = document.createElement("canvas");
    canvas.width = 1;
    canvas.height = 1;
    _supportsWebP =
      canvas.toDataURL("image/webp").indexOf("data:image/webp") === 0;
  } catch {
    _supportsWebP = false;
  }
  return _supportsWebP;
}

/**
 * If the browser lacks WebP support, rewrite a .webp art_url to a compatible
 * format:  PNG for known-static images (preserves transparency), GIF otherwise.
 * GIF is the safe default because it is always generated (even for animations),
 * whereas PNG is not created for animated artwork.
 *
 * URLs that don't end in `.webp` pass through unchanged.
 */
export function ensureCompatibleArtUrl(
  url: string,
  frameCount?: number,
): string {
  if (supportsWebP()) return url;
  if (frameCount === 1) return url.replace(/\.webp$/, ".png");
  return url.replace(/\.webp$/, ".gif");
}
