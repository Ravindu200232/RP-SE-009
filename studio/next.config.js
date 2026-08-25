
const API_HOST = process.env.STUDIO_API || 'http://127.0.0.1:7824'
const APP_HOST = process.env.STUDIO_APP || 'http://127.0.0.1:5173'
const EXTRA_DEV_ORIGINS = String(process.env.STUDIO_DEV_ORIGINS || '')
  .split(',').map(value => value.trim()).filter(Boolean)

module.exports = {
  basePath: '/__agentforge',

  turbopack: { root: __dirname },

  reactStrictMode: false,

  allowedDevOrigins: ['127.0.0.1', 'localhost', ...EXTRA_DEV_ORIGINS],
  async rewrites() {
    return {
      beforeFiles: [
        {
          source: '/__agentforge/api/:path*',
          destination: `${API_HOST}/__agentforge/api/:path*`,
          basePath: false,
        },
        {

          source: '/:path((?!__agentforge).*)',
          destination: `${APP_HOST}/:path*`,
          basePath: false,
        },
      ],
    }
  },
}
