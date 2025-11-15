import { useEffect, useState } from 'react'
import { InferenceDetail } from '../types/inference'

interface InferenceDetailModalProps {
  inference: InferenceDetail | null
  onClose: () => void
}

export function InferenceDetailModal({ inference, onClose }: InferenceDetailModalProps) {
  const [copiedField, setCopiedField] = useState<string | null>(null)
  
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }

    document.addEventListener('keydown', handleEscape)
    return () => {
      document.removeEventListener('keydown', handleEscape)
    }
  }, [onClose])

  if (!inference) {
    return null
  }

  const copyToClipboard = (text: string, fieldName: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedField(fieldName)
      setTimeout(() => setCopiedField(null), 2000)
    })
  }

  const formatTimestamp = (timestamp: string) => {
    const ts = parseInt(timestamp) / 1000
    return new Date(ts * 1000).toLocaleString()
  }

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[60] p-4"
      onClick={(e) => {
        e.stopPropagation()
        onClose()
      }}
    >
      <div 
        className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center">
          <h2 className="text-xl font-semibold text-gray-900">Inference Details</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
          >
            &times;
          </button>
        </div>

        <div className="px-6 py-4 space-y-6">
          <div>
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Inference ID</label>
            <div className="mt-1 flex items-center justify-between bg-gray-50 p-2 rounded">
              <code className="text-sm font-mono text-gray-900 break-all">{inference.inference_id}</code>
              <button
                onClick={() => copyToClipboard(inference.inference_id, 'inference_id')}
                className="ml-2 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 flex-shrink-0"
              >
                {copiedField === 'inference_id' ? 'Copied!' : 'Copy'}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</label>
              <div className="mt-1">
                <span className={`inline-block px-2 py-1 text-xs font-semibold rounded ${
                  inference.status === 'FINISHED' || inference.status === 'VALIDATED' 
                    ? 'bg-green-100 text-green-700 border border-green-300'
                    : inference.status === 'EXPIRED'
                    ? 'bg-yellow-100 text-yellow-700 border border-yellow-300'
                    : 'bg-red-100 text-red-700 border border-red-300'
                }`}>
                  {inference.status}
                </span>
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Model</label>
              <div className="mt-1 text-sm text-gray-900">
                {inference.model ? (
                  inference.model
                ) : (
                  <span className="text-red-600 font-semibold">Not Found</span>
                )}
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Block Height</label>
              <div className="mt-1 text-sm font-mono text-gray-900">{inference.start_block_height}</div>
            </div>

            <div>
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Timestamp</label>
              <div className="mt-1 text-sm text-gray-900">{formatTimestamp(inference.start_block_timestamp)}</div>
            </div>

            <div>
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Prompt Tokens</label>
              <div className="mt-1 text-sm text-gray-900">{inference.prompt_token_count || '0'}</div>
            </div>

            <div>
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Completion Tokens</label>
              <div className="mt-1 text-sm text-gray-900">{inference.completion_token_count || '0'}</div>
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Validated By ({inference.validated_by.length})</label>
            {inference.validated_by.length > 0 ? (
              <div className="mt-2 space-y-1">
                {inference.validated_by.map((validator, idx) => (
                  <div key={idx} className="text-sm font-mono text-gray-700 bg-gray-50 p-2 rounded break-all">
                    {validator}
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-1 text-sm text-gray-400">No validators</div>
            )}
          </div>

          {inference.prompt_hash && (
            <div>
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Prompt Hash</label>
              <div className="mt-1 flex items-center justify-between bg-gray-50 p-2 rounded">
                <code className="text-sm font-mono text-gray-900 break-all">{inference.prompt_hash}</code>
                <button
                  onClick={() => copyToClipboard(inference.prompt_hash!, 'prompt_hash')}
                  className="ml-2 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 flex-shrink-0"
                >
                  {copiedField === 'prompt_hash' ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>
          )}

          {inference.response_hash && (
            <div>
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Response Hash</label>
              <div className="mt-1 flex items-center justify-between bg-gray-50 p-2 rounded">
                <code className="text-sm font-mono text-gray-900 break-all">{inference.response_hash}</code>
                <button
                  onClick={() => copyToClipboard(inference.response_hash!, 'response_hash')}
                  className="ml-2 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 flex-shrink-0"
                >
                  {copiedField === 'response_hash' ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

