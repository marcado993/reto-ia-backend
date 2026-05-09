'use client'
import { motion } from 'framer-motion'

export default function ConfirmReset({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="modal-bg" onClick={onCancel} role="dialog" aria-modal aria-labelledby="reset-title">
      <motion.div
        className="modal-box"
        style={{ maxWidth: 380 }}
        initial={{ opacity: 0, scale: .95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: .95 }}
        transition={{ duration: .18 }}
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-hd">
          <div className="modal-hd-ic" style={{ background: '#fee2e2', color: '#dc2626' }}>
            <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </div>
          <h2 className="modal-hd-title" id="reset-title">¿Reiniciar consulta?</h2>
          <button className="modal-x" onClick={onCancel} aria-label="Cancelar">
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="modal-body" style={{ padding: '24px 18px' }}>
          <p style={{ fontSize: 13, color: 'var(--slate)', lineHeight: 1.6, margin: 0 }}>
            Se borrará todo el historial de la conversación actual. Esta acción es irreversible. ¿Deseas continuar?
          </p>
        </div>
        <div className="modal-ft">
          <button className="btn-ghost" onClick={onCancel}>Cancelar</button>
          <button className="btn-primary btn-red" onClick={onConfirm} style={{ background: '#dc2626' }}>Reiniciar Consulta</button>
        </div>
      </motion.div>
    </div>
  )
}
