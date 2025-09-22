/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  // Expose public API base URL to the client (Vercel: set NEXT_PUBLIC_API_BASE_URL)
  env: {
    NEXT_PUBLIC_API_BASE_URL:
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      (process.env.NODE_ENV === 'production'
        ? 'https://api.jagadeeshkovi.com'
        : 'http://localhost:8000'),
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${
          process.env.NEXT_PUBLIC_API_BASE_URL ||
          (process.env.NODE_ENV === 'production'
            ? 'https://api.jagadeeshkovi.com'
            : 'http://localhost:8000')
        }/api/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
