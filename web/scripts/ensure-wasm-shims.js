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

function copyIfChanged(sourcePath, targetPath) {
  try {
    if (!fs.existsSync(sourcePath)) {
      console.warn(`[postinstall] missing source ${sourcePath}; skipping copy`);
      return;
    }
    fs.mkdirSync(path.dirname(targetPath), { recursive: true });
    const src = fs.readFileSync(sourcePath);
    if (fs.existsSync(targetPath)) {
      const dst = fs.readFileSync(targetPath);
      if (src.equals(dst)) return;
    }
    fs.writeFileSync(targetPath, src);
    console.log(`[postinstall] copied ${sourcePath} -> ${targetPath}`);
  } catch (err) {
    console.warn(`[postinstall] failed to copy ${sourcePath}:`, err && err.message ? err.message : err);
  }
}

// Next.js / webpack can attempt to bundle the URL("zstd.wasm", import.meta.url) reference
// inside `zstd-wasm/lib/zstd.js` even though we provide `wasmBinary` at runtime.
// The upstream package does not ship a `zstd.wasm` file, so we create a tiny placeholder
// to satisfy the resolver. Runtime never fetches it because `wasmBinary` is provided.
const zstdPlaceholder = path.join(__dirname, '..', 'node_modules', 'zstd-wasm', 'lib', 'zstd.wasm');
ensureFileExists(zstdPlaceholder, Buffer.from([]));

// wasm-webp ships its WASM inside node_modules/wasm-webp/dist/esm/webp-wasm.wasm,
// but the encoder in src/lib/artwork-scaler/encoder.ts overrides Emscripten's
// locateFile to serve from /wasm/webp-wasm.wasm (matching the convention used
// by the other WASM modules). Mirror the file into public/wasm on install.
const webpWasmSrc = path.join(__dirname, '..', 'node_modules', 'wasm-webp', 'dist', 'esm', 'webp-wasm.wasm');
const webpWasmDst = path.join(__dirname, '..', 'public', 'wasm', 'webp-wasm.wasm');
copyIfChanged(webpWasmSrc, webpWasmDst);


