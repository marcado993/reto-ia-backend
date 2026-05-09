import { AgentStep } from '@/lib/types'
import { motion, AnimatePresence } from 'framer-motion'

interface Props {
  steps: AgentStep[]
}

export default function AgentSteps({ steps }: Props) {
  return (
    <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 shadow-sm w-full max-w-md my-2" aria-live="polite">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-6 h-6 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center font-bold text-xs cross-pulse" aria-hidden="true">+</div>
        <span className="text-sm font-semibold text-slate-700">MediBot esta analizando...</span>
      </div>
      <div className="space-y-2">
        <AnimatePresence>
          {steps.map((step) => (
            <motion.div
              key={step.id}
              initial={{ opacity: 0, height: 0, y: -10 }}
              animate={{ opacity: 1, height: 'auto', y: 0 }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.3 }}
              className={`agent-step agent-step-${step.status} relative pl-6 flex flex-col`}
            >
              <div className="flex items-center w-full">
                <div className={`absolute left-1.5 top-1.5 w-2 h-2 rounded-full ${step.status === 'active' ? 'bg-primary-500 animate-pulse' : step.status === 'done' ? 'bg-emerald-500' : 'bg-slate-300'}`}></div>
                {/* Connecting line */}
                <div className="absolute left-2.5 top-3.5 bottom-[-12px] w-[2px] bg-slate-200 last-of-type:hidden"></div>
                
                <span className="text-sm mr-2" aria-hidden="true">{step.icon}</span>
                <span className={`text-sm ${step.status === 'active' ? 'font-semibold text-slate-800' : step.status === 'done' ? 'text-slate-600' : 'text-slate-400'}`}>
                  {step.label}
                </span>
                
                {step.status === 'done' && (
                  <svg className="w-4 h-4 text-emerald-500 ml-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5} aria-label="Completado">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                )}
                {step.status === 'active' && (
                  <div className="ml-auto flex items-center gap-1" aria-label="Procesando">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary-500 animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-1.5 h-1.5 rounded-full bg-primary-500 animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-1.5 h-1.5 rounded-full bg-primary-500 animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                )}
              </div>
              
              {/* Chain of thought details */}
              {step.detail && step.status !== 'pending' && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.2 }}
                  className="mt-1 ml-6 text-xs text-slate-500 border-l-2 border-slate-200 pl-2 py-0.5"
                >
                  <em className="text-slate-600">"{step.detail}"</em>
                </motion.div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}