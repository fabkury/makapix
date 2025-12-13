/* eslint-disable no-console */
const fs = require('fs');
const path = require('path');

function ensureFileExists(targetPath, contents) {
  try {
    fs.mkdirSync(path.dirname(targetPath), { recursive: true });
    if (!fs.existsSync(targetPath)) {
      fs.writeFileSync(targetPath, contents);
      console.log(`[postinstall] created ${targetPath}`);
    }
  } catch (err) {
    console.warn(`[postinstall] failed to create ${targetPath}:`, err && err.message ? err.message : err);
  }
}

// Next.js / webpack can attempt to bundle the URL("zstd.wasm", import.meta.url) reference
// inside `zstd-wasm/lib/zstd.js` even though we provide `wasmBinary` at runtime.
// The upstream package does not ship a `zstd.wasm` file, so we create a tiny placeholder
// to satisfy the resolver. Runtime never fetches it because `wasmBinary` is provided.
const zstdPlaceholder = path.join(__dirname, '..', 'node_modules', 'zstd-wasm', 'lib', 'zstd.wasm');
ensureFileExists(zstdPlaceholder, Buffer.from([]));


