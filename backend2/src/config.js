require('dotenv').config()

const toInt = (val, def) => {
  const n = parseInt(val, 10)
  return Number.isFinite(n) ? n : def
}

const INFERENCE_URLS = (process.env.INFERENCE_URLS || 'http://node2.gonka.ai:8000')
  .split(',')
  .map((u) => u.trim())
  .filter(Boolean)

const DEFAULT_CORS = ['http://localhost:3000', 'http://localhost:3001']

const CORS_ENV = process.env.CORS_ORIGIN
let corsOrigin
if (!CORS_ENV || CORS_ENV.trim() === '') {
  corsOrigin = DEFAULT_CORS
} else if (CORS_ENV.includes(',')) {
  corsOrigin = CORS_ENV.split(',').map((o) => o.trim()).filter(Boolean)
} else if (CORS_ENV === '*') {
  corsOrigin = '*'
} else {
  corsOrigin = CORS_ENV.trim()
}

module.exports = {
  port: toInt(process.env.PORT, 8080),
  corsOrigin,
  inferenceUrls: INFERENCE_URLS,
  dbPath: process.env.CACHE_DB_PATH || 'backend2/cache.db',
  timeouts: {
    http: toInt(process.env.HTTP_TIMEOUT_MS, 30000)
  }
}