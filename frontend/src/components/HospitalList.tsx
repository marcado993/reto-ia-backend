'use client'
import { HospitalRecommendation } from '@/lib/types'
import dynamic from 'next/dynamic'

const MiniMap = dynamic(() => import('./MiniMap'), { ssr: false })

export default function HospitalList({ hospitals }: { hospitals: HospitalRecommendation[] }) {
  if (!hospitals.length) return null
  const minCopago = Math.min(...hospitals.map(h => h.copago_paciente))

  return (
    <div>
      <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--gray-400)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 8 }}>
        Hospitales en tu red · {hospitals.length} opciones
      </p>
      <div className="hospitals-grid">
        {hospitals.map((h, i) => {
          const isBest = i === 0 && h.copago_paciente === minCopago
          return (
            <div key={i} className={`hospital-card ${isBest ? 'best' : ''}`}>
              {isBest && <span className="hospital-badge">✓ Mejor precio</span>}
              <div className="hospital-name">{h.nombre}</div>
              <div className="hospital-type">
                {h.tipo === 'iess' ? 'IESS — Público' : h.tipo === 'issfa' ? 'ISSFA — Público' : 'Privado'} · Red {h.red}
              </div>
              <div className="hospital-copago">${h.copago_paciente.toFixed(2)}</div>
              {h.distancia_km !== null && (
                <div className="hospital-dist">📍 {h.distancia_km.toFixed(1)} km</div>
              )}
            </div>
          )
        })}
      </div>

      {hospitals.some(h => h.lat !== null && h.lon !== null) && (
        <div className="map-wrap">
          <MiniMap hospitals={hospitals} />
        </div>
      )}
    </div>
  )
}
