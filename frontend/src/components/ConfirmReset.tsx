'use client'
import { motion } from 'framer-motion'

export default function ConfirmReset({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="modal-backdrop" onClick={onCancel} role="dialog" aria-modal aria-labelledby="reset-title">
      <motion.div
        className="modal-box"
        style={{ maxWidth: 380 }}
        initial={{ opacity: 0, scale: .95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: .95 }}
        transition={{ duration: .18 }}
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header">
          <div className="modal-icon" style={{ background: '#fee2e2' }}>🗑️</div>
          <h2 className="modal-title" id="reset-title">¿Reiniciar conversación?</h2>
          <button className="modal-close" onClick={onCancel} aria-label="Cancelar">✕</button>
        </div>
        <div className="modal-body">
          <p style={{ fontSize: 14, color: 'var(--gray-600)', lineHeight: 1.6 }}>
            Se borrará todo el historial de esta consulta. Esta acción no se puede deshacer.
          </p>
        </div>
        <div className="modal-footer">
          <button className="btn-ghost" onClick={onCancel}>Cancelar</button>
          <button className="btn-primary btn-danger" onClick={onConfirm}>Sí, reiniciar</button>
        </div>
      </motion.div>
    </div>
  )
}
