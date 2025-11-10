const express = require('express')

function createRouter(service) {
  const router = express.Router()

  router.get('/hello', (req, res) => {
    res.json({ message: 'hello' })
  })

  router.get('/inference/current', async (req, res) => {
    try {
      const reload = String(req.query.reload || 'false') === 'true'
      const data = await service.getCurrentInference({ reload })
      res.json(data)
    } catch (e) {
      res.status(500).json({ error: `Failed to fetch current epoch stats: ${e.message}` })
    }
  })

  router.get('/models/current', async (req, res) => {
    try {
      const data = await service.getCurrentModels()
      res.json(data)
    } catch (e) {
      res.status(500).json({ error: `Failed to fetch current models: ${e.message}` })
    }
  })

  router.get('/timeline', async (req, res) => {
    try {
      const data = await service.getTimeline()
      res.json(data)
    } catch (e) {
      res.status(500).json({ error: `Failed to fetch timeline: ${e.message}` })
    }
  })

  // Placeholders (return 501 for now)
  router.get('/inference/epochs/:epochId', (req, res) => {
    res.status(501).json({ error: 'Not implemented yet' })
  })
  router.get('/models/epochs/:epochId', (req, res) => {
    res.status(501).json({ error: 'Not implemented yet' })
  })
  router.get('/participants/:participantId', (req, res) => {
    const participantId = req.params.participantId
    const epochId = req.query.epoch_id ? parseInt(String(req.query.epoch_id), 10) : undefined
    service.getParticipantDetails({ participantId, epochId })
      .then((data) => res.json(data))
      .catch((e) => res.status(500).json({ error: `Failed to fetch participant details: ${e.message}` }))
  })
  router.get('/participants/:participantId/inferences', (req, res) => {
    const participantId = req.params.participantId
    const epochId = req.query.epoch_id ? parseInt(String(req.query.epoch_id), 10) : undefined
    service.getParticipantInferences({ participantId, epochId })
      .then((data) => res.json(data))
      .catch((e) => res.status(500).json({ error: `Failed to fetch participant inferences: ${e.message}` }))
  })

  return router
}

module.exports = { createRouter }