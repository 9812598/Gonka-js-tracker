const express = require('express')
const cors = require('cors')
const config = require('./config')
const { CacheDB } = require('./db')
const { GonkaClient } = require('./client')
const { InferenceService } = require('./service')
const { createRouter } = require('./router')

function buildApp() {
  const app = express()
  app.use(cors({ origin: config.corsOrigin, credentials: true }))
  app.use(express.json())

  console.log(`[backend2] Cache DB path: ${config.dbPath}`)
  const db = new CacheDB(config.dbPath)
  // Ensure DB schema is initialized (creates tables if missing)
  db.initialize()
  const client = new GonkaClient(config.inferenceUrls, config.timeouts.http)
  const service = new InferenceService(client, db)
  const router = createRouter(service)

  app.use('/v1', router)
  app.get('/health', (req, res) => res.json({ ok: true }))

  return app
}

if (require.main === module) {
  const app = buildApp()
  app.listen(config.port, () => {
    console.log(`Backend2 listening on http://localhost:${config.port}`)
  })
}

module.exports = { buildApp }