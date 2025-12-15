const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  eslint: {
    dirs: ["src"],
  },
  async headers() {
    // SharedArrayBuffer is required by parts of the client-side decode stack (WASM modules / Pyodide).
    // Browsers only expose SharedArrayBuffer in cross-origin isolated contexts, which requires COOP+COEP.
    // Limit the headers to the Divoom import page to avoid impacting the rest of the app.
    return [
      {
        source: "/divoom-import/:path*",
        headers: [
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
          // Use `require-corp` for broad browser support (notably iOS Safari).
          // This matches the working servoom deployment and enables SharedArrayBuffer when
          // combined with COOP + CORS/CORP-compliant subresources.
          { key: "Cross-Origin-Embedder-Policy", value: "require-corp" },
          { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
        ],
      },
    ];
  },
  // Expose build-time derived constants to the client.
  // We derive this from the backend env var MAKAPIX_ARTWORK_SIZE_LIMIT (bytes).
  env: {
    NEXT_PUBLIC_MAKAPIX_ARTWORK_SIZE_LIMIT_BYTES:
      process.env.MAKAPIX_ARTWORK_SIZE_LIMIT ?? "5242880",
  },
  webpack: (config) => {
    // Some client-side dependencies (zstd/lzo) reference `.wasm` assets via `new URL("*.wasm", import.meta.url)`.
    // Ensure webpack can resolve and emit these as static assets.
    config.experiments = { ...(config.experiments || {}), asyncWebAssembly: true };
    config.resolve.extensions = [...(config.resolve.extensions || []), ".wasm"];
    config.module.rules.push({
      test: /\.wasm$/,
      type: "asset/resource",
    });
    return config;
  },
};

export default nextConfig;
