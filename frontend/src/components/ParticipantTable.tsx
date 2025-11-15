import { Participant } from '../types/inference'
import { ParticipantModal } from './ParticipantModal'

interface ParticipantTableProps {
  participants: Participant[]
  epochId: number
  isCurrentEpoch: boolean
  currentEpochId: number | null
  selectedParticipantId?: string | null
  onParticipantSelect: (participantId: string | null) => void
}

export function ParticipantTable({ participants, epochId, isCurrentEpoch, currentEpochId, selectedParticipantId, onParticipantSelect }: ParticipantTableProps) {
  const sortedParticipants = [...participants].sort((a, b) => b.weight - a.weight)

  const shouldHighlightRed = (participant: Participant) => {
    return participant.missed_rate > 0.10 || participant.invalidation_rate > 0.10
  }

  const handleRowClick = (participant: Participant) => {
    onParticipantSelect(participant.index)
  }

  const handleCloseModal = () => {
    onParticipantSelect(null)
  }
  
  const selectedParticipant = selectedParticipantId 
    ? participants.find(p => p.index === selectedParticipantId) || null
    : null

  return (
    <div className="overflow-x-auto border border-gray-200 rounded-md">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
              Participant Index
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
              Weight
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
              Models
            </th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-gray-700 uppercase tracking-wider">
              Total
            </th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-gray-700 uppercase tracking-wider">
              Missed
            </th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-gray-700 uppercase tracking-wider">
              Validated
            </th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-gray-700 uppercase tracking-wider">
              Invalid
            </th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-gray-700 uppercase tracking-wider">
              Missed Rate
            </th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-gray-700 uppercase tracking-wider">
              Invalid Rate
            </th>
            {/**
             * Jail/Health columns temporarily disabled until we can match external tracker logic
             * <th className="px-2 py-3 text-center text-xs font-semibold text-gray-700 uppercase tracking-wider w-16">Jail</th>
             * <th className="px-2 py-3 text-center text-xs font-semibold text-gray-700 uppercase tracking-wider w-16">Health</th>
             */}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {sortedParticipants.map((participant) => {
            const totalInferenced = parseInt(participant.current_epoch_stats.inference_count) + 
                                   parseInt(participant.current_epoch_stats.missed_requests)
            // Jail/Health derivation temporarily disabled until we can match external tracker logic
            // const statusLower = (participant.status || '').toLowerCase()
            // const derivedJailed = statusLower.includes('jail')
            //   ? true
            //   : (statusLower === 'active' || statusLower === 'enabled' || statusLower === 'ramping')
            //     ? false
            //     : undefined
            // const jail = (participant.is_jailed === true || participant.is_jailed === false)
            //   ? participant.is_jailed
            //   : derivedJailed

            // const hasModels = (participant.models || []).length > 0
            // const hasUrl = !!participant.inference_url
            // const hasActivity = parseInt(participant.current_epoch_stats.inference_count) > 0
            // const derivedHealthy = (statusLower === 'inactive' || statusLower === 'offline')
            //   ? false
            //   : (statusLower === 'active' || statusLower === 'enabled' || statusLower === 'ramping' || hasModels || hasUrl || hasActivity)
            //     ? true
            //     : undefined
            // const healthy = (participant.node_healthy === true || participant.node_healthy === false)
            //   ? participant.node_healthy
            //   : derivedHealthy
            
            return (
              <tr
                key={participant.index}
                onClick={() => handleRowClick(participant)}
                className={`cursor-pointer ${
                  shouldHighlightRed(participant) 
                    ? 'bg-red-50 border-l-4 border-l-red-600' 
                    : 'hover:bg-gray-50'
                }`}
              >
                <td className="px-4 py-3 text-sm font-mono text-gray-900 whitespace-nowrap">
                  {participant.index}
                </td>
                <td className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap">
                  {participant.weight.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-sm">
                  {participant.models.length > 0 ? (
                    <div className="flex flex-wrap gap-1 max-w-xs">
                      {participant.models.slice(0, 3).map((model, idx) => (
                        <span
                          key={idx}
                          className="inline-block px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-700 border border-gray-300 rounded whitespace-nowrap"
                        >
                          {model}
                        </span>
                      ))}
                      {participant.models.length > 3 && (
                        <span className="text-xs text-gray-500 whitespace-nowrap">
                          +{participant.models.length - 3} more
                        </span>
                      )}
                    </div>
                  ) : (
                    <span className="text-gray-400 text-xs">-</span>
                  )}
                </td>
                <td className="px-4 py-3 text-sm text-gray-900 text-right font-medium whitespace-nowrap">
                  {totalInferenced.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-sm text-right whitespace-nowrap">
                  <span className={parseInt(participant.current_epoch_stats.missed_requests) > 0 ? 'text-red-600 font-semibold' : 'text-gray-600'}>
                    {parseInt(participant.current_epoch_stats.missed_requests).toLocaleString()}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-gray-900 text-right whitespace-nowrap">
                  {parseInt(participant.current_epoch_stats.validated_inferences).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-sm text-right whitespace-nowrap">
                  <span className={parseInt(participant.current_epoch_stats.invalidated_inferences) > 0 ? 'text-red-600 font-semibold' : 'text-gray-600'}>
                    {parseInt(participant.current_epoch_stats.invalidated_inferences).toLocaleString()}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-right whitespace-nowrap">
                  <span className={`font-semibold ${participant.missed_rate > 0.10 ? 'text-red-600' : 'text-gray-900'}`}>
                    {(participant.missed_rate * 100).toFixed(2)}%
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-right whitespace-nowrap">
                  <span className={`font-semibold ${participant.invalidation_rate > 0.10 ? 'text-red-600' : 'text-gray-900'}`}>
                    {(participant.invalidation_rate * 100).toFixed(2)}%
                  </span>
                </td>
                {/** Jail/Health cells temporarily disabled until we can match external tracker logic */}
              </tr>
            )
          })}
        </tbody>
      </table>

      <ParticipantModal 
        participant={selectedParticipant}
        epochId={epochId}
        isCurrentEpoch={isCurrentEpoch}
        currentEpochId={currentEpochId}
        onClose={handleCloseModal} 
      />
    </div>
  )
}

