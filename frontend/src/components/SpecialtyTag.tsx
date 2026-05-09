import { SPECIALTY_ICONS } from '@/lib/types'

interface Props {
  name: string
}

export default function SpecialtyTag({ name }: Props) {
  const icon = SPECIALTY_ICONS[name] || '🏥'
  return (
    <span className="specialty-tag bg-teal-50 border border-teal-200 text-teal-800">
      <span className="text-sm">{icon}</span>
      <span className="font-medium">{name}</span>
    </span>
  )
}