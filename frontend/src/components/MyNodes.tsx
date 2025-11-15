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
    invalidated_inferences?: number
  }
}

export function MyNodes() {
  const apiUrl = import.meta.env.VITE_API_URL || '/api'
  const [inputText, setInputText] = useState('')
  const [addresses, setAddresses] = useState<string[]>([])
  const [, setLoadingMap] = useState<Record<string, boolean>>({})
  const [statusMap, setStatusMap] = useState<Record<string, NodeStatus>>({})
  const [errorMap, setErrorMap] = useState<Record<string, string>>({})
  const [detailsMap, setDetailsMap] = useState<Record<string, ParticipantDetails | null>>({})
  const [copiedAddr, setCopiedAddr] = useState<string | null>(null)

  // Load saved addresses strictly from backend
  useEffect(() => {
    const loadWallets = async () => {
      try {
        const res = await fetch(`${apiUrl}/v1/wallets`)
        if (res.ok) {
          const data = await res.json()
          const list: string[] = Array.isArray(data?.wallets) ? data.wallets.map((w: any) => String(w.address)) : []
          if (list.length > 0) {
            setAddresses(list)
            return
          }
        }
      } catch {}
    }
    loadWallets()
  }, [])

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

  const AddressLabel = ({ addr, className = '' }: { addr: string; className?: string }) => {
    const short = `....${addr.slice(-6)}`
    return (
      <span className={`relative inline-flex items-center group ${className}`}>
        <span className="font-mono">{short}</span>
        <span className="absolute -top-6 left-0 bg-gray-800 text-white text-xs px-2 py-1 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 z-10">
          {addr}
        </span>
      </span>
    )
  }

  const copyAddr = (addr: string) => {
    navigator.clipboard
      .writeText(addr)
      .then(() => {
        setCopiedAddr(addr)
        setTimeout(() => setCopiedAddr(null), 1500)
      })
      .catch(() => {
        // noop
      })
  }

  const addAddresses = () => {
    const parsed = parseInput(inputText)
    if (parsed.length === 0) return
    const filtered = parsed.filter(isLikelyAddress)
    const newOnes = filtered.filter((a) => !addresses.includes(a))
    if (newOnes.length === 0) {
      setInputText('')
      return
    }
    // Persist to backend, only update state after backend confirms
    (async () => {
      try {
        await Promise.all(
          newOnes.map(async (addr) => {
            const res = await fetch(`${apiUrl}/v1/wallets`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ address: addr })
            })
            if (!res.ok) {
              const errText = await res.text().catch(() => '')
              setErrorMap((prev) => ({ ...prev, [addr]: `Add failed: HTTP ${res.status}${errText ? ` - ${errText}` : ''}` }))
            }
          })
        )
        // Re-sync with backend to ensure persistence
        const res = await fetch(`${apiUrl}/v1/wallets`)
        if (res.ok) {
          const data = await res.json()
          const list: string[] = Array.isArray(data?.wallets) ? data.wallets.map((w: any) => String(w.address)) : []
          setAddresses(list)
        } else {
          const errText = await res.text().catch(() => '')
          console.error('Failed to reload wallets:', res.status, errText)
        }
      } catch (e) {
        console.error('Network error while adding wallets', e)
      }
    })()
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
    // Persist removal to backend
    ;(async () => {
      try {
        await fetch(`${apiUrl}/v1/wallets/${encodeURIComponent(addr)}`, { method: 'DELETE' })
        // Re-sync with backend to ensure persistence
        const res = await fetch(`${apiUrl}/v1/wallets`)
        if (res.ok) {
          const data = await res.json()
          const list: string[] = Array.isArray(data?.wallets) ? data.wallets.map((w: any) => String(w.address)) : []
          setAddresses(list)
        }
      } catch {}
    })()
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

  const calcMetrics = (d: ParticipantDetails | null) => {
    const inference = d?.current_epoch_stats?.inference_count || 0
    const missed = d?.current_epoch_stats?.missed_requests || 0
    const validated = d?.current_epoch_stats?.validated_inferences || 0
    const invalidated = d?.current_epoch_stats?.invalidated_inferences || 0
    const totalInferenced = inference + missed
    const missedRate = totalInferenced > 0 ? (missed / totalInferenced) * 100 : 0
    const invalidationRate = (validated + invalidated) > 0 ? (invalidated / (validated + invalidated)) * 100 : 0
    return { totalInferenced, inference, missed, validated, invalidated, missedRate, invalidationRate }
  }

  const formatPct = (v: number) => `${v.toFixed(2)}%`

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

      {/* Host Dashboard-style metrics table */}
      {addresses.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm p-4 md:p-6 mb-6 border border-gray-200">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-base md:text-lg font-bold text-gray-900">Host Dashboard Metrics</h3>
            <div className="text-xs text-gray-600">
              <span className="mr-3">Working: {summaryCounts.working}</span>
              <span className="mr-3">Not Working: {summaryCounts.notWorking}</span>
              <span>Unknown: {summaryCounts.unknown}</span>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs md:text-sm">
              <thead>
                <tr className="text-left text-gray-600">
                  <th className="py-2 pr-4">Wallet</th>
                  <th className="py-2 pr-4">Chain</th>
                  {/** Jail/Health columns temporarily disabled until we can match external tracker logic */}
                  <th className="py-2 pr-4">Models</th>
                  <th className="py-2 pr-4">Total inferenced</th>
                  <th className="py-2 pr-4">Validated</th>
                  <th className="py-2 pr-4">Invalidated</th>
                  <th className="py-2 pr-4">Invalidation rate</th>
                  <th className="py-2 pr-4">Missed</th>
                  <th className="py-2 pr-4">Missed rate</th>
                  <th className="py-2 pr-4">Uptime</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {addresses.map((addr) => {
                  const details = detailsMap[addr]
                  const metrics = calcMetrics(details || null)
                  // const isJailed = (details?.status || '').toLowerCase().includes('jail')
                  return (
                    <tr key={addr}>
                      <td className="py-2 pr-4 text-gray-900">
                        <div className="flex items-center gap-2">
                          <AddressLabel addr={addr} />
                          <button
                            onClick={() => copyAddr(addr)}
                            className="text-[10px] px-2 py-0.5 bg-white border border-gray-300 rounded hover:bg-gray-50"
                          >
                            {copiedAddr === addr ? 'Copied!' : 'Copy'}
                          </button>
                        </div>
                      </td>
                      <td className="py-2 pr-4">{details?.status || '-'}</td>
                      {/** Jail/Health cells temporarily disabled until we can match external tracker logic */}
                      <td className="py-2 pr-4">
                        {(details?.models?.length || 0) > 0 ? (
                          details!.models!.join(', ')
                        ) : (
                          <span className="text-red-600 font-semibold">Not Found</span>
                        )}
                      </td>
                      <td className="py-2 pr-4">{metrics.totalInferenced}</td>
                      <td className="py-2 pr-4">{metrics.validated}</td>
                      <td className={`py-2 pr-4 ${metrics.invalidated > 0 ? 'text-red-600 font-semibold' : 'text-gray-900'}`}>{metrics.invalidated}</td>
                      <td className="py-2 pr-4">{formatPct(metrics.invalidationRate)}</td>
                      <td className={`py-2 pr-4 ${metrics.missed > 0 ? 'text-red-600 font-semibold' : 'text-gray-900'}`}>{metrics.missed}</td>
                      <td className="py-2 pr-4">{formatPct(metrics.missedRate)}</td>
                      <td className="py-2 pr-4">{formatPct(100 - metrics.missedRate)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

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
              const details = detailsMap[addr]

              return (
                <div key={addr} className="py-3 flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm md:text-base text-gray-900 break-all">{addr}</span>
                      <button
                        onClick={() => copyAddr(addr)}
                        className="text-xs px-2 py-0.5 bg-white border border-gray-300 rounded hover:bg-gray-50"
                      >
                        {copiedAddr === addr ? 'Copied!' : 'Copy'}
                      </button>
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