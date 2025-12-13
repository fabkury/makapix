const nextConfig = {
  reactStrictMode: true,
  eslint: {
    dirs: ["src"],
  },
  // Expose build-time derived constants to the client.
  // We derive this from the backend env var MAKAPIX_ARTWORK_SIZE_LIMIT (bytes).
  env: {
    NEXT_PUBLIC_MAKAPIX_ARTWORK_SIZE_LIMIT_BYTES:
      process.env.MAKAPIX_ARTWORK_SIZE_LIMIT ?? "5242880",
  },
};

export default nextConfig;
