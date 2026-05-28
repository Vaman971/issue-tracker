/** @type {import('next').NextConfig} */
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const nextConfig = {
  // Proxy API requests during development
  skipTrailingSlashRedirect: true,
  async rewrites() {
      return {
        beforeFiles: [
          {
            source: '/api/:path*',
            destination: `${API_BASE_URL}/:path*`
          }
        ]
      }
  }
};

export default nextConfig;
