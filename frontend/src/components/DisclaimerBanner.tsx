interface Props {
  message?: string
}

export default function DisclaimerBanner({ message }: Props) {
  const text = message || 'Este sistema no sustituye consejo medico profesional. Consulte siempre a un profesional de salud.'
  return (
    <div className="disclaimer">
      ⚕️ {text}
    </div>
  )
}