import { useEffect, useMemo, useState } from 'react'

type NodeStatus = 'working' | 'not_working' | 'unknown'

interface ParticipantDetails {
  address: string
  status?: string
  models?: string[]
  inference_url?: string
  weight?: number
  current_epoch_stats?: {
    inference_count?: number
    missed_requests?: number
    validated_inferences?: number
  }
}

export function MyNodes() {
  const apiUrl = import.meta.env.VITE_API_URL || '/api'
  const [inputText, setInputText] = useState('')
  const [addresses, setAddresses] = useState<string[]>([])
  const [loadingMap, setLoadingMap] = useState<Record<string, boolean>>({})
  const [statusMap, setStatusMap] = useState<Record<string, NodeStatus>>({})
  const [errorMap, setErrorMap] = useState<Record<string, string>>({})
  const [detailsMap, setDetailsMap] = useState<Record<string, ParticipantDetails | null>>({})

  // Load saved addresses
  useEffect(() => {
    try {
      const saved = localStorage.getItem('myNodes.addresses')
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed)) {
          setAddresses(parsed)
        }
      }
    } catch {}
  }, [])

  // Persist addresses
  useEffect(() => {
    try {
      localStorage.setItem('myNodes.addresses', JSON.stringify(addresses))
    } catch {}
  }, [addresses])

  const parseInput = (text: string): string[] => {
    return Array.from(
      new Set(
        text
          .split(/[\s,]+/)
          .map((s) => s.trim())
          .filter((s) => s.length > 0)
      )
    )
  }

  const isLikelyAddress = (s: string) => /^gonka[0-9a-z]+$/.test(s)

  const addAddresses = () => {
    const parsed = parseInput(inputText)
    if (parsed.length === 0) return
    const filtered = parsed.filter(isLikelyAddress)
    const merged = Array.from(new Set([...addresses, ...filtered]))
    setAddresses(merged)
    setInputText('')
  }

  const removeAddress = (addr: string) => {
    setAddresses((prev) => prev.filter((a) => a !== addr))
    setStatusMap((prev) => {
      const next = { ...prev }
      delete next[addr]
      return next
    })
    setDetailsMap((prev) => {
      const next = { ...prev }
      delete next[addr]
      return next
    })
    setLoadingMap((prev) => {
      const next = { ...prev }
      delete next[addr]
      return next
    })
  }

  const deriveStatus = (details: ParticipantDetails | null): NodeStatus => {
    if (!details) return 'unknown'
    const status = (details.status || '').toLowerCase()
    const hasModels = (details.models || []).length > 0
    const hasUrl = !!details.inference_url
    const hasActivity = (details.current_epoch_stats?.inference_count || 0) > 0
    // Treat ramping/enabled as effectively working for end-user purposes
    if (status === 'active' || status === 'ramping' || status === 'enabled' || hasModels || hasUrl || hasActivity) return 'working'
    if (status === 'inactive' || status === 'offline') return 'not_working'
    return 'unknown'
  }

  const fetchStatus = async (addr: string) => {
    setLoadingMap((prev) => ({ ...prev, [addr]: true }))
    try {
      const res = await fetch(`${apiUrl}/v1/participants/${encodeURIComponent(addr)}`)
      if (!res.ok) {
        const errText = await res.text().catch(() => '')
        setDetailsMap((prev) => ({ ...prev, [addr]: null }))
        setStatusMap((prev) => ({ ...prev, [addr]: 'unknown' }))
        setErrorMap((prev) => ({ ...prev, [addr]: `HTTP ${res.status}${errText ? ` - ${errText}` : ''}` }))
        return
      }
      const raw = await res.json()
      const json: ParticipantDetails = raw && raw.participant ? raw.participant : raw
      setDetailsMap((prev) => ({ ...prev, [addr]: json }))
      setStatusMap((prev) => ({ ...prev, [addr]: deriveStatus(json) }))
      setErrorMap((prev) => ({ ...prev, [addr]: '' }))
    } catch {
      setDetailsMap((prev) => ({ ...prev, [addr]: null }))
      setStatusMap((prev) => ({ ...prev, [addr]: 'unknown' }))
      setErrorMap((prev) => ({ ...prev, [addr]: 'Network error' }))
    } finally {
      setLoadingMap((prev) => ({ ...prev, [addr]: false }))
    }
  }

  const refreshAll = () => {
    addresses.forEach((addr) => fetchStatus(addr))
  }

  useEffect(() => {
    // fetch statuses when addresses change
    addresses.forEach((addr) => {
      if (!statusMap[addr]) fetchStatus(addr)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [addresses])

  const summaryCounts = useMemo(() => {
    let working = 0
    let notWorking = 0
    let unknown = 0
    for (const a of addresses) {
      const s = statusMap[a]
      if (s === 'working') working++
      else if (s === 'not_working') notWorking++
      else unknown++
    }
    return { working, notWorking, unknown }
  }, [addresses, statusMap])

  return (
    <div>
      <div className="bg-white rounded-lg shadow-sm p-4 md:p-6 mb-6 border border-gray-200">
        <div className="mb-4">
          <h2 className="text-lg md:text-xl font-bold text-gray-900 mb-1">My Nodes</h2>
          <p className="text-xs md:text-sm text-gray-500">Add one or multiple addresses separated by spaces, commas, or newlines.</p>
        </div>

        <div className="flex flex-col gap-3">
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Paste addresses here (space, comma, or newline separated)"
            className="w-full min-h-[120px] px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-gray-500"
          />
          <div className="flex items-center gap-3">
            <button
              onClick={addAddresses}
              className="px-5 py-2.5 bg-gray-900 text-white font-medium rounded-md hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
            >
              Add Addresses
            </button>
            <button
              onClick={refreshAll}
              className="px-5 py-2.5 bg-white text-gray-900 border border-gray-300 font-medium rounded-md hover:bg-gray-50"
            >
              Refresh Statuses
            </button>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm p-4 md:p-6 border border-gray-200">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base md:text-lg font-bold text-gray-900">Added Wallets</h3>
          <div className="text-xs text-gray-600">
            <span className="mr-3">Working: {summaryCounts.working}</span>
            <span className="mr-3">Not Working: {summaryCounts.notWorking}</span>
            <span>Unknown: {summaryCounts.unknown}</span>
          </div>
        </div>

        {addresses.length === 0 ? (
          <p className="text-sm text-gray-600">No addresses added yet.</p>
        ) : (
          <div className="divide-y divide-gray-200">
            {addresses.map((addr) => {
              const status = statusMap[addr] || 'unknown'
              const loading = !!loadingMap[addr]
              const details = detailsMap[addr]
              const badgeClass =
                status === 'working'
                  ? 'bg-green-100 text-green-800'
                  : status === 'not_working'
                  ? 'bg-red-100 text-red-800'
                  : 'bg-gray-100 text-gray-800'

              return (
                <div key={addr} className="py-3 flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm md:text-base text-gray-900">{addr}</span>
                      <span className={`text-xs px-2 py-0.5 rounded ${badgeClass}`}>
                        {loading ? 'Checking...' : status === 'working' ? 'Working' : status === 'not_working' ? 'Not working' : 'Unknown'}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-gray-600">
                      {details ? (
                        <>
                          {details.status && (
                            <span className="mr-3">Chain status: {details.status}</span>
                          )}
                          {details.models && details.models.length > 0 && (
                            <span className="mr-3">Models: {details.models.join(', ')}</span>
                          )}
                          {typeof details.weight === 'number' && details.weight > 0 && (
                            <span className="mr-3">Weight: {details.weight}</span>
                          )}
                          {details.current_epoch_stats && (
                            <span>
                              Inferences: {details.current_epoch_stats.inference_count || 0}, Missed: {details.current_epoch_stats.missed_requests || 0}
                            </span>
                          )}
                        </>
                      ) : (
                        <span>{errorMap[addr] || 'No details found'}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => fetchStatus(addr)}
                      className="text-xs px-3 py-1 bg-white border border-gray-300 rounded hover:bg-gray-50"
                    >
                      Recheck
                    </button>
                    <button
                      onClick={() => removeAddress(addr)}
                      className="text-xs px-3 py-1 bg-red-50 text-red-700 border border-red-200 rounded hover:bg-red-100"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}