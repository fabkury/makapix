const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  // Transpile npm packages that ship ES2020+ syntax (e.g. ?., ??) so older
  // browsers like Safari 12 (iPad Mini 2 / iOS 12) can parse the bundles.
  transpilePackages: [
    'mqtt',
    'lucide-react',
    // wasm-webp ships its Emscripten glue as raw ESM, with Node-only `createRequire`
    // and `import.meta.url` branches that Next.js/Terser can't consume unparsed.
    // Transpiling the package lets SWC lower the syntax; paired with the Node-stub
    // fallbacks below, the dead Node branches are stripped at bundle time.
    'wasm-webp',
    // @radix-ui top-level components
    '@radix-ui/react-accordion',
    '@radix-ui/react-alert-dialog',
    '@radix-ui/react-checkbox',
    '@radix-ui/react-label',
    '@radix-ui/react-radio-group',
    '@radix-ui/react-scroll-area',
    '@radix-ui/react-select',
    '@radix-ui/react-slider',
    '@radix-ui/react-switch',
    '@radix-ui/react-tabs',
    // @radix-ui internal packages that ship ES2020+ syntax
    '@radix-ui/primitive',
    '@radix-ui/react-dialog',
    '@radix-ui/react-dismissable-layer',
    '@radix-ui/react-focus-scope',
    '@radix-ui/react-popper',
    '@radix-ui/react-portal',
    '@radix-ui/react-presence',
    '@radix-ui/react-slot',
    '@radix-ui/react-use-escape-keydown',
    '@radix-ui/react-use-layout-effect',
    'framer-motion',
    'react-markdown',
    'class-variance-authority',
    'tailwind-merge',
  ],
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

    // wasm-webp's Emscripten glue uses `new URL('./', import.meta.url)` in a
    // Node-only branch. Webpack 5's asset detector follows that to the
    // directory's index.js and emits it as an asset/resource in
    // static/media/, which Terser then fails to minify (raw ESM inside an
    // asset). Disable asset-URL parsing for this package — we serve its
    // WASM ourselves from /wasm/webp-wasm.wasm via Emscripten's locateFile.
    config.module.rules.push({
      test: /[\\/]node_modules[\\/]wasm-webp[\\/]/,
      parser: { url: false },
    });

    // Client-side builds: stub out Node.js modules that some WASM libraries try to import
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        path: false,
        crypto: false,
        // Needed by wasm-webp's Emscripten glue (Node fallback uses createRequire
        // from 'module' and fileURLToPath from 'url'). These branches are dead
        // in the browser, but the imports still need to resolve.
        module: false,
        url: false,
      };
    }

    return config;
  },
};

export default nextConfig;
