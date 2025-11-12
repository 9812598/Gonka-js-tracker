const path = require('path')
const dotenv = require('dotenv')

// Load environment variables robustly:
// 1) from current working directory
dotenv.config()
// 2) explicitly from backend2/.env (fills missing vars if cwd differs)
dotenv.config({ path: path.resolve(__dirname, '..', '.env') })

const toInt = (val, def) => {
  const n = parseInt(val, 10)
  return Number.isFinite(n) ? n : def
}

const INFERENCE_URLS = (process.env.INFERENCE_URLS || 'http://node2.gonka.ai:8000')
  .split(',')
  .map((u) => u.trim())
  .filter(Boolean)

const DEFAULT_CORS = [
  'http://localhost:3000',
  'http://localhost:3001',
  'https://tracker.gonka.top',
  'http://tracker.gonka.top'
]

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

// Resolve DB path robustly across environments
const resolveDbPath = (p) => {
  const val = (p || '').trim()
  if (!val) {
    // Default to project-level backend2/cache.db absolute path
    return path.resolve(__dirname, '..', 'cache.db')
  }
  // If absolute, use as-is; otherwise resolve relative to current working directory
  return path.isAbsolute(val) ? val : path.resolve(process.cwd(), val)
}

module.exports = {
  port: toInt(process.env.PORT, 8080),
  corsOrigin,
  inferenceUrls: INFERENCE_URLS,
  dbPath: resolveDbPath(process.env.CACHE_DB_PATH),
  timeouts: {
    http: toInt(process.env.HTTP_TIMEOUT_MS, 30000)
  }
}