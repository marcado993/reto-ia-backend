interface Props {
  message: string
}

export default function UrgencyAlert({ message }: Props) {
  return (
    <div className="urgency-alert flex items-start gap-2">
      <span className="text-xl">⚠️</span>
      <div>
        <p className="font-semibold">Urgencia Detectada</p>
        <p className="text-sm">{message}</p>
      </div>
    </div>
  )
}