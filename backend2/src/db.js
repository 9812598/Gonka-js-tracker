let Database
try {
  Database = require('better-sqlite3')
} catch (e) {
  Database = null
  console.warn('[backend2] better-sqlite3 not available, using in-memory cache fallback')
}
const path = require('path')
const fs = require('fs')

class CacheDB {
  constructor(dbPath) {
    this.dbPath = dbPath
    const dir = path.dirname(dbPath)
    if (!Database) {
      // In-memory fallback
      this._mem = {
        inference_stats: [],
        models_api_cache: new Map(),
        timeline_cache: null
      }
      return
    }
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true })
    }
    this.db = new Database(this.dbPath)
  }

  initialize() {
    if (!Database) return
    // inference_stats
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS inference_stats (
        epoch_id INTEGER NOT NULL,
        height INTEGER NOT NULL,
        participant_index TEXT NOT NULL,
        stats_json TEXT NOT NULL,
        seed_signature TEXT,
        cached_at TEXT NOT NULL,
        PRIMARY KEY (epoch_id, height, participant_index)
      );
      CREATE INDEX IF NOT EXISTS idx_epoch_height ON inference_stats(epoch_id, height);
    `)

    // models_api_cache
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS models_api_cache (
        epoch_id INTEGER NOT NULL,
        height INTEGER NOT NULL,
        models_all_json TEXT NOT NULL,
        models_stats_json TEXT NOT NULL,
        cached_at TEXT NOT NULL,
        PRIMARY KEY (epoch_id, height)
      );
      CREATE INDEX IF NOT EXISTS idx_models_api_epoch ON models_api_cache(epoch_id);
    `)

    // participant_inferences
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS participant_inferences (
        epoch_id INTEGER NOT NULL,
        participant_id TEXT NOT NULL,
        inference_id TEXT NOT NULL,
        status TEXT NOT NULL,
        start_block_height TEXT NOT NULL,
        start_block_timestamp TEXT NOT NULL,
        validated_by_json TEXT,
        prompt_hash TEXT,
        response_hash TEXT,
        prompt_payload TEXT,
        response_payload TEXT,
        prompt_token_count TEXT,
        completion_token_count TEXT,
        model TEXT,
        last_updated TEXT NOT NULL,
        PRIMARY KEY (epoch_id, participant_id, inference_id)
      );
      CREATE INDEX IF NOT EXISTS idx_participant_inferences ON participant_inferences(epoch_id, participant_id, status);
    `)

    // timeline_cache
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS timeline_cache (
        id INTEGER PRIMARY KEY,
        timeline_json TEXT NOT NULL,
        cached_at TEXT NOT NULL
      );
    `)
  }

  saveStatsBatch(epochId, height, statsList) {
    if (!Database) {
      const now = new Date().toISOString()
      for (const s of statsList) {
        const idx = s.index
        const seed = s.seed_signature || null
        const json = JSON.stringify(s)
        // unique by epoch_id, height, participant_index
        const key = `${epochId}:${height}:${idx}`
        const existingIndex = this._mem.inference_stats.findIndex((r) => r.key === key)
        const row = { key, epoch_id: epochId, height, participant_index: idx, stats_json: json, seed_signature: seed, cached_at: now }
        if (existingIndex >= 0) this._mem.inference_stats[existingIndex] = row
        else this._mem.inference_stats.push(row)
      }
      return
    }
    const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO inference_stats 
      (epoch_id, height, participant_index, stats_json, seed_signature, cached_at)
      VALUES (?, ?, ?, ?, ?, ?)
    `)
    const now = new Date().toISOString()
    const tx = this.db.transaction((rows) => {
      for (const s of rows) {
        const idx = s.index
        const seed = s.seed_signature || null
        const json = JSON.stringify(s)
        stmt.run(epochId, height, idx, json, seed, now)
      }
    })
    tx(statsList)
  }

  getStats(epochId, height) {
    if (!Database) {
      return this._mem.inference_stats
        .filter((r) => r.epoch_id === epochId && r.height === height)
        .map((r) => JSON.parse(r.stats_json))
    }
    const rows = this.db.prepare(`
      SELECT stats_json FROM inference_stats WHERE epoch_id = ? AND height = ?
    `).all(epochId, height)
    return rows.map((r) => JSON.parse(r.stats_json))
  }

  saveModelsCache(epochId, height, modelsAll, modelsStats) {
    const now = new Date().toISOString()
    if (!Database) {
      this._mem.models_api_cache.set(`${epochId}:${height}`, {
        models_all_json: JSON.stringify(modelsAll),
        models_stats_json: JSON.stringify(modelsStats),
        cached_at: now
      })
      return
    }
    this.db.prepare(`
      INSERT OR REPLACE INTO models_api_cache (epoch_id, height, models_all_json, models_stats_json, cached_at)
      VALUES (?, ?, ?, ?, ?)
    `).run(epochId, height, JSON.stringify(modelsAll), JSON.stringify(modelsStats), now)
  }

  getModelsCache(epochId, height) {
    if (!Database) {
      const row = this._mem.models_api_cache.get(`${epochId}:${height}`)
      if (!row) return null
      return {
        models_all: JSON.parse(row.models_all_json),
        models_stats: JSON.parse(row.models_stats_json),
        cached_at: row.cached_at
      }
    }
    const row = this.db.prepare(`
      SELECT models_all_json, models_stats_json, cached_at FROM models_api_cache WHERE epoch_id = ? AND height = ?
    `).get(epochId, height)
    if (!row) return null
    return {
      models_all: JSON.parse(row.models_all_json),
      models_stats: JSON.parse(row.models_stats_json),
      cached_at: row.cached_at
    }
  }

  saveTimelineCache(timeline) {
    const now = new Date().toISOString()
    if (!Database) {
      this._mem.timeline_cache = { timeline_json: JSON.stringify(timeline), cached_at: now }
      return
    }
    this.db.prepare(`
      INSERT OR REPLACE INTO timeline_cache (id, timeline_json, cached_at)
      VALUES (1, ?, ?)
    `).run(JSON.stringify(timeline), now)
  }

  getTimelineCache() {
    if (!Database) {
      const row = this._mem.timeline_cache
      if (!row) return null
      return { timeline: JSON.parse(row.timeline_json), cached_at: row.cached_at }
    }
    const row = this.db.prepare(`
      SELECT timeline_json, cached_at FROM timeline_cache WHERE id = 1
    `).get()
    if (!row) return null
    return { timeline: JSON.parse(row.timeline_json), cached_at: row.cached_at }
  }
}

module.exports = { CacheDB }