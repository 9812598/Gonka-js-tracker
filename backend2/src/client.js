const axios = require('axios')

class GonkaClient {
  constructor(baseUrls, timeoutMs = 30000) {
    this.baseUrls = baseUrls || []
    this.timeoutMs = timeoutMs
    this.currentIndex = 0
  }

  _currentBase() {
    return this.baseUrls[this.currentIndex]
  }

  _rotate() {
    this.currentIndex = (this.currentIndex + 1) % this.baseUrls.length
  }

  async _get(path, { params, headers } = {}) {
    const attempts = this.baseUrls.length || 1
    let lastErr
    for (let i = 0; i < attempts; i++) {
      const base = this._currentBase() || ''
      const url = base.replace(/\/$/, '') + '/' + path.replace(/^\//, '')
      try {
        const res = await axios.get(url, { params, headers, timeout: this.timeoutMs })
        return res.data
      } catch (e) {
        lastErr = e
        this._rotate()
      }
    }
    throw lastErr || new Error('Request failed')
  }

  async getLatestEpoch() {
    return this._get('/v1/epochs/latest')
  }

  async getLatestHeight() {
    const data = await this._get('/chain-rpc/status')
    return parseInt(data?.result?.sync_info?.latest_block_height || '0', 10)
  }

  async getCurrentEpochParticipants() {
    return this._get('/v1/epochs/current/participants')
  }

  async getEpochParticipants(epochId) {
    return this._get(`/v1/epochs/${epochId}/participants`)
  }

  async getAllParticipants(height) {
    const params = { 'pagination.limit': '10000' }
    const headers = {}
    if (height) headers['X-Cosmos-Block-Height'] = String(height)
    return this._get('/chain-api/productscience/inference/inference/participant', { params, headers })
  }

  async getBlock(height) {
    return this._get(`/chain-api/cosmos/base/tendermint/v1beta1/blocks/${height}`)
  }

  async getModelsAll() {
    return this._get('/models/all')
  }

  async getModelsStats() {
    return this._get('/models/stats')
  }
}

module.exports = { GonkaClient }