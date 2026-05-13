/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/backend/:path*',
        destination: `${process.env.BACKEND_API_URL || 'http://trustbrain_backend:8000'}/:path*`,
      },
    ]
  },
}

export default nextConfig
