import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { StructuredResponse, URGENCY_CONFIG } from '@/lib/types'
import UrgencyBadge from './UrgencyBadge'
import SpecialtyTag from './SpecialtyTag'
import { X, Activity } from 'lucide-react'

interface Props {
  isOpen: boolean
  data: StructuredResponse | null
  onClose: () => void
}

export default function MedicalDetailsModal({ isOpen, data, onClose }: Props) {
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    if (isOpen) {
      document.body.style.overflow = 'hidden'
      window.addEventListener('keydown', handleEsc)
    } else {
      document.body.style.overflow = 'auto'
    }
    return () => {
      document.body.style.overflow = 'auto'
      window.removeEventListener('keydown', handleEsc)
    }
  }, [isOpen, onClose])

  if (!data) return null

  const urgencyConfig = URGENCY_CONFIG[data.urgencia]

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4" role="dialog" aria-modal="true" aria-labelledby="details-title">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm"
          />

          {/* Modal Content */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="relative bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden z-10 flex flex-col max-h-[90dvh]"
          >
            {/* Header */}
            <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-3 bg-slate-50">
              <div className="w-8 h-8 rounded-full bg-primary-100 text-primary-600 flex items-center justify-center">
                <Activity className="w-4 h-4" />
              </div>
              <h3 id="details-title" className="text-base font-bold text-slate-900">Detalles Clínicos Identificados</h3>
              <button
                onClick={onClose}
                className="ml-auto p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-200 rounded-full transition-colors"
                aria-label="Cerrar detalles"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            {/* Body */}
            <div className="p-5 overflow-y-auto space-y-6">
              {data.sintomas.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Síntomas Reportados</h4>
                  <div className="flex flex-wrap gap-2">
                    {data.sintomas.map(s => (
                      <span key={s} className="px-3 py-1.5 rounded-full text-sm font-medium bg-primary-50 text-primary-700 border border-primary-200">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {urgencyConfig && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Nivel de Urgencia</h4>
                  <UrgencyBadge urgency={data.urgencia} />
                  {data.urgencia === 'alta' && (
                    <p className="mt-2 text-sm text-red-600 bg-red-50 p-2 rounded-lg border border-red-100">
                      Condición de emergencia. Por favor, acuda al centro médico más cercano de inmediato.
                    </p>
                  )}
                </div>
              )}

              {data.especialidades_sugeridas.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Especialidad sugerida</h4>
                  <div className="flex flex-wrap gap-2">
                    <SpecialtyTag
                      key={data.especialidades_sugeridas[0]}
                      name={data.especialidades_sugeridas[0]}
                    />
                  </div>
                </div>
              )}
            </div>
            
            {/* Footer */}
            <div className="px-5 py-4 bg-slate-50 border-t border-slate-100 flex justify-end">
              <button
                onClick={onClose}
                className="px-5 py-2 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-offset-2 transition-colors"
              >
                Entendido
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
