/* eslint-disable no-console */
/**
 * Prevent dev server breakage due to stale/corrupted `.next` output.
 *
 * This repo sometimes runs Next in environments where `.next` can persist
 * across runs (including volume mounts). Clearing it is cheap and avoids
 * hard-to-debug MODULE_NOT_FOUND errors for vendor chunks.
 */
const fs = require("fs");
const path = require("path");

const nextDir = path.join(__dirname, "..", ".next");

try {
  fs.rmSync(nextDir, { recursive: true, force: true });
} catch (err) {
  console.warn("[dev] Failed to clear .next cache:", err);
}


