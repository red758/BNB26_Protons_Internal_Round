/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow frontend to proxy to backend in development
  async rewrites() {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE;
    if (!apiBase) return [];
    return [
      {
        source: '/api/proxy/:path*',
        destination: `${apiBase}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
