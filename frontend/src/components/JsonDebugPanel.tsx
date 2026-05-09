import { StructuredResponse } from '@/lib/types'

interface Props {
  data: StructuredResponse
}

export default function JsonDebugPanel({ data }: Props) {
  return (
    <details className="mt-2">
      <summary className="text-xs text-gray-400 cursor-pointer">Ver datos estructurados (JSON)</summary>
      <pre className="text-xs bg-gray-50 p-2 rounded-lg mt-1 overflow-x-auto">
        {JSON.stringify(data, null, 2)}
      </pre>
    </details>
  )
}