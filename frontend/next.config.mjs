/** @type {import('next').NextConfig} */

// Server-side env var (not NEXT_PUBLIC) for Docker dev where backend DNS is 'backend'.
// Falls back to NEXT_PUBLIC_API_BASE_URL (.env.local for direct dev), then hardcoded local.
const API_BASE_URL =
    process.env.BACKEND_INTERNAL_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://127.0.0.1:8000";

const nextConfig = {
    skipTrailingSlashRedirect: true,
    async rewrites() {
        return {
            beforeFiles: [
                {
                    // Use a regex capture group (.*) instead of :path* wildcard.
                    // :path* is processed by Next.js's path normalizer which strips trailing
                    // slashes BEFORE the rewrite fires. The regex (.*) captures the raw
                    // path string — including trailing slashes — so FastAPI's
                    // redirect_slashes=False doesn't cause 404s on list endpoints (/projects/).
                    source: "/api/:path(.*)",
                    destination: `${API_BASE_URL}/:path`,
                },
            ],
        };
    },
};

export default nextConfig;
