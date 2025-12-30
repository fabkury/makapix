const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  eslint: {
    dirs: ["src"],
  },
  async headers() {
    // SharedArrayBuffer is required by parts of the client-side decode stack (WASM modules / Pyodide).
    // Browsers only expose SharedArrayBuffer in cross-origin isolated contexts, which requires COOP+COEP.
    //
    // IMPORTANT: When COEP is set to `require-corp`, ALL subresources (JS, CSS, images, etc.)
    // must have `Cross-Origin-Resource-Policy` headers. We set CORP on all routes to ensure
    // static assets under /_next/* are also covered.
    return [
      // CORP header on ALL responses - safe for same-origin resources and required for COEP
      {
        source: "/:path*",
        headers: [
          { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
        ],
      },
      // COOP + COEP only on the divoom-import page (enables SharedArrayBuffer)
      {
        source: "/divoom-import",
        headers: [
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
          // Use `require-corp` for broad browser support (notably iOS Safari).
          // This matches the working servoom deployment and enables SharedArrayBuffer when
          // combined with COOP + CORS/CORP-compliant subresources.
          { key: "Cross-Origin-Embedder-Policy", value: "require-corp" },
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
  webpack: (config, { isServer }) => {
    // Some client-side dependencies (zstd/lzo) reference `.wasm` assets via `new URL("*.wasm", import.meta.url)`.
    // Ensure webpack can resolve and emit these as static assets.
    config.experiments = { ...(config.experiments || {}), asyncWebAssembly: true };
    config.resolve.extensions = [...(config.resolve.extensions || []), ".wasm"];
    config.module.rules.push({
      test: /\.wasm$/,
      type: "asset/resource",
    });
    
    // Client-side builds: stub out Node.js modules that some WASM libraries try to import
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        path: false,
        crypto: false,
      };
    }
    
    return config;
  },
};

export default nextConfig;
