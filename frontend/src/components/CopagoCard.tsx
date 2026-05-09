interface Props {
  copago: number
  moneda: string
  desglose: string
  planNombre: string
  urgencia: string
}

export default function CopagoCard({ copago, moneda, desglose, planNombre, urgencia }: Props) {
  const isEmergency = urgencia === 'alta'
  return (
    <div className="copago-card">
      <div className={`copago-head ${isEmergency ? 'emergency' : ''}`}>
        <div>
          <div className="copago-label">Tu copago estimado</div>
          <div className="copago-amount">${copago.toFixed(2)}</div>
          <div className="copago-currency">{moneda} · {planNombre}</div>
        </div>
        <div style={{ fontSize: 36, opacity: .9 }}>{isEmergency ? '🚑' : '🏥'}</div>
      </div>
      {desglose && (
        <div className="copago-body">{desglose}</div>
      )}
    </div>
  )
}