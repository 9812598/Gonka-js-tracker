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
        timeline_cache: null,
        wallets: [],
        users: [],
        user_wallets: []
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

    // wallets (user-saved addresses)
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS wallets (
        address TEXT PRIMARY KEY,
        label TEXT,
        created_at TEXT NOT NULL
      );
    `)

    // users
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, -- Google sub
        email TEXT,
        name TEXT,
        picture TEXT,
        created_at TEXT NOT NULL
      );
      CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);
    `)

    // user_wallets (per user list)
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS user_wallets (
        user_id TEXT NOT NULL,
        address TEXT NOT NULL,
        label TEXT,
        created_at TEXT NOT NULL,
        PRIMARY KEY (user_id, address),
        FOREIGN KEY (user_id) REFERENCES users(id)
      );
      CREATE INDEX IF NOT EXISTS idx_user_wallets_user ON user_wallets(user_id);
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

  // --- Wallets persistence ---
  listWallets() {
    if (!Database) {
      // return a copy to avoid mutation
      return this._mem.wallets.slice()
    }
    const rows = this.db.prepare(`
      SELECT address, label, created_at FROM wallets ORDER BY created_at DESC
    `).all()
    return rows
  }

  addWallet(address, label = null) {
    const addr = String(address || '').trim()
    if (!addr) return null
    const now = new Date().toISOString()
    if (!Database) {
      const existingIdx = this._mem.wallets.findIndex((w) => w.address === addr)
      const row = { address: addr, label: label || null, created_at: now }
      if (existingIdx >= 0) {
        // update label
        this._mem.wallets[existingIdx] = { ...this._mem.wallets[existingIdx], label: row.label }
      } else {
        this._mem.wallets.push(row)
      }
      return row
    }
    this.db.prepare(`
      INSERT OR IGNORE INTO wallets (address, label, created_at) VALUES (?, ?, ?)
    `).run(addr, label || null, now)
    // If already existed, update label if provided
    if (label && label.trim() !== '') {
      this.db.prepare(`UPDATE wallets SET label = ? WHERE address = ?`).run(label, addr)
    }
    const row = this.db.prepare(`
      SELECT address, label, created_at FROM wallets WHERE address = ?
    `).get(addr)
    return row
  }

  deleteWallet(address) {
    const addr = String(address || '').trim()
    if (!addr) return false
    if (!Database) {
      const before = this._mem.wallets.length
      this._mem.wallets = this._mem.wallets.filter((w) => w.address !== addr)
      return this._mem.wallets.length < before
    }
    const info = this.db.prepare(`DELETE FROM wallets WHERE address = ?`).run(addr)
    return (info.changes || 0) > 0
  }

  // --- Users ---
  upsertUser({ id, email, name, picture }) {
    const uid = String(id || '').trim()
    if (!uid) return null
    const now = new Date().toISOString()
    if (!Database) {
      const idx = this._mem.users.findIndex(u => u.id === uid)
      const row = { id: uid, email: email || null, name: name || null, picture: picture || null, created_at: now }
      if (idx >= 0) {
        this._mem.users[idx] = { ...this._mem.users[idx], email: row.email, name: row.name, picture: row.picture }
      } else {
        this._mem.users.push(row)
      }
      return row
    }
    this.db.prepare(`
      INSERT INTO users (id, email, name, picture, created_at)
      VALUES (?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        email = excluded.email,
        name = excluded.name,
        picture = excluded.picture
    `).run(uid, email || null, name || null, picture || null, now)
    const row = this.db.prepare(`SELECT id, email, name, picture, created_at FROM users WHERE id = ?`).get(uid)
    return row
  }

  getUserById(id) {
    const uid = String(id || '').trim()
    if (!uid) return null
    if (!Database) {
      return this._mem.users.find(u => u.id === uid) || null
    }
    return this.db.prepare(`SELECT id, email, name, picture, created_at FROM users WHERE id = ?`).get(uid) || null
  }

  // --- Per-user wallets ---
  listUserWallets(userId) {
    const uid = String(userId || '').trim()
    if (!uid) return []
    if (!Database) {
      return this._mem.user_wallets.filter(w => w.user_id === uid).slice()
    }
    const rows = this.db.prepare(`
      SELECT address, label, created_at FROM user_wallets WHERE user_id = ? ORDER BY created_at DESC
    `).all(uid)
    return rows
  }

  addUserWallet(userId, address, label = null) {
    const uid = String(userId || '').trim()
    const addr = String(address || '').trim()
    if (!uid || !addr) return null
    const now = new Date().toISOString()
    if (!Database) {
      const idx = this._mem.user_wallets.findIndex(w => w.user_id === uid && w.address === addr)
      const row = { user_id: uid, address: addr, label: label || null, created_at: now }
      if (idx >= 0) {
        this._mem.user_wallets[idx] = { ...this._mem.user_wallets[idx], label: row.label }
      } else {
        this._mem.user_wallets.push(row)
      }
      return { address: row.address, label: row.label, created_at: row.created_at }
    }
    this.db.prepare(`
      INSERT OR IGNORE INTO user_wallets (user_id, address, label, created_at) VALUES (?, ?, ?, ?)
    `).run(uid, addr, label || null, now)
    if (label && label.trim() !== '') {
      this.db.prepare(`UPDATE user_wallets SET label = ? WHERE user_id = ? AND address = ?`).run(label, uid, addr)
    }
    const row = this.db.prepare(`
      SELECT address, label, created_at FROM user_wallets WHERE user_id = ? AND address = ?
    `).get(uid, addr)
    return row
  }

  deleteUserWallet(userId, address) {
    const uid = String(userId || '').trim()
    const addr = String(address || '').trim()
    if (!uid || !addr) return false
    if (!Database) {
      const before = this._mem.user_wallets.length
      this._mem.user_wallets = this._mem.user_wallets.filter(w => !(w.user_id === uid && w.address === addr))
      return this._mem.user_wallets.length < before
    }
    const info = this.db.prepare(`DELETE FROM user_wallets WHERE user_id = ? AND address = ?`).run(uid, addr)
    return (info.changes || 0) > 0
  }
}

module.exports = { CacheDB }