/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/jobs/:path*',
        destination: 'http://127.0.0.1:5000/jobs/:path*',
      },
      {
        source: '/auth/:path*',
        destination: 'http://127.0.0.1:5000/auth/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
