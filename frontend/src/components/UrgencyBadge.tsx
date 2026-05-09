import { URGENCY_CONFIG } from '@/lib/types'

interface Props {
  urgency: 'baja' | 'media' | 'alta'
}

export default function UrgencyBadge({ urgency }: Props) {
  const config = URGENCY_CONFIG[urgency]
  return (
    <span className={`urgency-badge ${config.bgClass} ${config.pulse ? 'animate-pulse' : ''}`}>
      {config.icon} {config.label}
    </span>
  )
}