'use client'
import { AgentStep } from '@/lib/types'
import { motion, AnimatePresence } from 'framer-motion'

const STATUS_ICON: Record<string, string> = {
  pending: '○',
  active: '●',
  done: '✓',
}

export default function AgentThinking({ steps }: { steps: AgentStep[] }) {
  return (
    <div className="thinking-panel">
      <div className="thinking-title">
        <span>🧠</span> MediBot está analizando tu consulta…
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <AnimatePresence initial={false}>
          {steps.map((step) => (
            <motion.div
              key={step.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              className={`thinking-step step-${step.status}`}
            >
              <div className="thinking-step-icon" style={{ fontSize: 10, fontWeight: 700 }}>
                {STATUS_ICON[step.status]}
              </div>
              <div>
                <div className="thinking-step-text">{step.icon} {step.label}</div>
                {step.status === 'active' && step.detail && (
                  <div className="step-detail">{step.detail}</div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}
