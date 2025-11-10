const { CacheDB } = require('./db')

function computeMissedRate(currentStats) {
  const missed = parseInt(currentStats?.missed_requests || '0', 10)
  const inf = parseInt(currentStats?.inference_count || '0', 10)
  const total = missed + inf
  return total === 0 ? 0 : Math.round((missed / total) * 10000) / 10000
}

function computeInvalidationRate(currentStats) {
  const invalidated = parseInt(currentStats?.invalidated_inferences || '0', 10)
  const inf = parseInt(currentStats?.inference_count || '0', 10)
  return inf === 0 ? 0 : Math.round((invalidated / inf) * 10000) / 10000
}

class InferenceService {
  constructor(client, db) {
    this.client = client
    this.db = db
    this.currentCache = null
    this.lastFetchTime = 0
  }

  async _avgBlockTime(currentHeight) {
    try {
      const reference = currentHeight - 10000
      const curr = await this.client.getBlock(currentHeight)
      const ref = await this.client.getBlock(reference)
      const currTs = curr?.block?.header?.time || curr?.result?.block?.header?.time
      const refTs = ref?.block?.header?.time || ref?.result?.block?.header?.time
      const currDate = new Date(currTs)
      const refDate = new Date(refTs)
      const diffSec = Math.max(1, (currDate - refDate) / 1000)
      const diffBlocks = currentHeight - reference
      return Math.round((diffSec / diffBlocks) * 100) / 100
    } catch (e) {
      return 6.0
    }
  }

  async getCurrentInference({ reload = false } = {}) {
    const now = Date.now()
    if (!reload && this.currentCache && now - this.lastFetchTime < 30000) {
      return this.currentCache
    }

    const height = await this.client.getLatestHeight()
    const epochData = await this.client.getCurrentEpochParticipants()
    const epochId = epochData?.active_participants?.epoch_group_id || 0

    const allParticipants = await this.client.getAllParticipants(height)
    const list = Array.isArray(allParticipants?.participant) ? allParticipants.participant : []

    const active = new Map()
    for (const p of epochData?.active_participants?.participants || []) {
      active.set(p.index, {
        weight: p.weight || 0,
        models: Array.isArray(p.models) ? p.models : [],
        validator_key: p.validator_key || null
      })
    }

    const participants = []
    const saveRows = []
    for (const p of list) {
      if (!active.has(p.index)) continue
      const extra = active.get(p.index)
      const stat = {
        index: p.index,
        address: p.address,
        weight: extra.weight,
        validator_key: extra.validator_key,
        inference_url: p.inference_url,
        status: p.status,
        models: extra.models,
        current_epoch_stats: p.current_epoch_stats,
        missed_rate: computeMissedRate(p.current_epoch_stats),
        invalidation_rate: computeInvalidationRate(p.current_epoch_stats)
      }
      participants.push(stat)
      const rowForSave = { ...stat, seed_signature: null }
      saveRows.push(rowForSave)
    }

    // persist batch
    try {
      this.db.saveStatsBatch(epochId, height, saveRows)
    } catch (_) {}

    // extra info for timer
    const avgBlockTime = await this._avgBlockTime(height)
    const currBlock = await this.client.getBlock(height)
    const currentBlockTimestamp = (currBlock?.block?.header?.time || currBlock?.result?.block?.header?.time || new Date().toISOString())

    const response = {
      epoch_id: epochId,
      height,
      participants,
      cached_at: new Date().toISOString(),
      is_current: true,
      current_block_height: height,
      current_block_timestamp: currentBlockTimestamp,
      avg_block_time: avgBlockTime
    }

    this.currentCache = response
    this.lastFetchTime = now
    return response
  }

  async getCurrentModels() {
    const height = await this.client.getLatestHeight()
    const latest = await this.client.getLatestEpoch()
    const epochId = latest?.latest_epoch?.index || 0
    let modelsAll, modelsStats

    try {
      modelsAll = await this.client.getModelsAll()
      modelsStats = await this.client.getModelsStats()
    } catch (e) {
      // Fallback: synthesize models from current participants when upstream endpoint is unavailable
      const current = await this.getCurrentInference()
      const map = new Map()
      for (const p of current.participants || []) {
        for (const m of Array.isArray(p.models) ? p.models : []) {
          const prev = map.get(m) || { id: m, total_weight: 0, participant_count: 0, proposed_by: '-', v_ram: '-', throughput_per_nonce: '-', units_of_compute_per_token: '-', hf_repo: '-', hf_commit: '-', model_args: [], validation_threshold: { value: '0', exponent: 0 } }
          prev.total_weight += (p.weight || 0)
          prev.participant_count += 1
          map.set(m, prev)
        }
      }
      modelsAll = { models: Array.from(map.values()) }
      modelsStats = { stats: Array.from(map.keys()).map((modelId) => ({ model: modelId, ai_tokens: '0', inferences: 0 })) }
    }

    try { this.db.saveModelsCache(epochId, height, modelsAll, modelsStats) } catch (_) {}

    const avgBlockTime = await this._avgBlockTime(height)
    const currBlock = await this.client.getBlock(height)
    const ts = (currBlock?.block?.header?.time || currBlock?.result?.block?.header?.time || new Date().toISOString())

    return {
      epoch_id: epochId,
      height,
      models: Array.isArray(modelsAll?.models) ? modelsAll.models : [],
      stats: Array.isArray(modelsStats?.stats) ? modelsStats.stats : [],
      cached_at: new Date().toISOString(),
      is_current: true,
      current_block_timestamp: ts,
      avg_block_time: avgBlockTime
    }
  }

  async getTimeline() {
    const height = await this.client.getLatestHeight()
    const latest = await this.client.getLatestEpoch()
    const epochId = latest?.latest_epoch?.index || 0
    const avgBlockTime = await this._avgBlockTime(height)
    const currBlock = await this.client.getBlock(height)
    const ts = (currBlock?.block?.header?.time || currBlock?.result?.block?.header?.time || new Date().toISOString())
    const refHeight = Math.max(1, height - 10000)
    const refBlock = await this.client.getBlock(refHeight)
    const refTs = (refBlock?.block?.header?.time || refBlock?.result?.block?.header?.time || ts)

    const makeBlock = (h, t) => ({ height: h, timestamp: t })

    const response = {
      current_block: makeBlock(height, ts),
      reference_block: makeBlock(refHeight, refTs),
      avg_block_time: avgBlockTime,
      events: [],
      current_epoch_start: height, // placeholder
      current_epoch_index: epochId,
      epoch_length: 25000,
      epoch_stages: null,
      next_epoch_stages: null
    }
    try { this.db.saveTimelineCache(response) } catch (_) {}
    return response
  }

  // Participant details for modal
  async getParticipantDetails({ participantId, epochId }) {
    // Build participant snapshot using chain data even if not active
    const height = await this.client.getLatestHeight()
    const epochData = await this.client.getCurrentEpochParticipants()
    const allParticipants = await this.client.getAllParticipants(height)
    const list = Array.isArray(allParticipants?.participant) ? allParticipants.participant : []
    const active = new Map()
    for (const p of epochData?.active_participants?.participants || []) {
      active.set(p.index, {
        weight: p.weight || 0,
        models: Array.isArray(p.models) ? p.models : [],
        validator_key: p.validator_key || null
      })
    }
    const base = list.find(p => p.index === participantId)
    if (!base) {
      throw new Error('Participant not found')
    }
    const extra = active.get(base.index) || { weight: 0, models: [], validator_key: null }
    const participant = {
      index: base.index,
      address: base.address,
      weight: extra.weight,
      validator_key: extra.validator_key,
      inference_url: base.inference_url,
      status: base.status,
      models: extra.models,
      current_epoch_stats: base.current_epoch_stats,
      missed_rate: computeMissedRate(base.current_epoch_stats),
      invalidation_rate: computeInvalidationRate(base.current_epoch_stats)
    }

    const details = {
      participant,
      rewards: [],
      seed: null,
      warm_keys: [],
      ml_nodes: []
    }
    return details
  }

  // Participant inferences breakdown
  async getParticipantInferences({ participantId, epochId }) {
    // Provide empty lists for now; later can hydrate from cache/source
    const latest = await this.client.getLatestEpoch()
    const effectiveEpochId = epochId || (latest?.latest_epoch?.index || 0)
    return {
      epoch_id: effectiveEpochId,
      participant_id: participantId,
      successful: [],
      expired: [],
      invalidated: [],
      cached_at: new Date().toISOString()
    }
  }
}

module.exports = { InferenceService }