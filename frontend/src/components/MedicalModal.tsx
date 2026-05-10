'use client'
import { motion } from 'framer-motion'
import { StructuredResponse, URGENCY_CONFIG, SPECIALTY_ICONS } from '@/lib/types'

const URGENCY_CLASS: Record<string, string> = {
  baja:  'urgency-low',
  media: 'urgency-med',
  alta:  'urgency-high',
}

export default function MedicalModal({ data, onClose }: { data: StructuredResponse | null; onClose: () => void }) {
  if (!data) return null
  const urgCfg = URGENCY_CONFIG[data.urgencia]

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal aria-labelledby="modal-title">
      <motion.div
        className="modal-box"
        initial={{ opacity: 0, scale: .95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: .95, y: 16 }}
        transition={{ duration: .18 }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-header">
          <div className="modal-icon" style={{ background: '#dbeafe' }}>🩺</div>
          <h2 className="modal-title" id="modal-title">Detalles del Análisis Clínico</h2>
          <button className="modal-close" onClick={onClose} aria-label="Cerrar">✕</button>
        </div>

        {/* Body */}
        <div className="modal-body">
          {/* Síntomas */}
          {data.sintomas.length > 0 && (
            <div>
              <div className="modal-section-label">Síntomas reportados</div>
              <div className="chip-row">
                {data.sintomas.map(s => (
                  <span key={s} className="chip chip-symptom">{s}</span>
                ))}
              </div>
            </div>
          )}

          {/* Urgencia */}
          <div>
            <div className="modal-section-label">Nivel de urgencia</div>
            <span className={`urgency-pill ${URGENCY_CLASS[data.urgencia]}`}>
              {urgCfg.icon} {urgCfg.label}
            </span>
            {data.urgencia === 'alta' && (
              <p style={{ marginTop: 8, fontSize: 13, color: '#dc2626', background: '#fef2f2', padding: '8px 12px', borderRadius: 8 }}>
                ⚠️ Requiere atención en emergencias inmediatamente.
              </p>
            )}
          </div>

          {/* Especialidad sugerida (una sola) */}
          {data.especialidades_sugeridas.length > 0 && (
            <div>
              <div className="modal-section-label">Especialidad sugerida</div>
              <div className="chip-row">
                {(() => {
                  const s = data.especialidades_sugeridas[0]
                  return (
                    <span key={s} className="chip chip-specialty">
                      {SPECIALTY_ICONS[s] ?? '🏥'} {s.replace(/_/g, ' ')}
                    </span>
                  )
                })()}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <button className="btn-primary" onClick={onClose}>Entendido</button>
        </div>
      </motion.div>
    </div>
  )
}
