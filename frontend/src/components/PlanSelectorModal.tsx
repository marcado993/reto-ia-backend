'use client'

import { motion } from 'framer-motion'
import Image from 'next/image'
import { HealthPlan } from '@/lib/types'

// Map each plan name/network to its logo and brand color
const PLAN_META: Record<string, { logo: string; color: string; badge: string; desc: string }> = {
  saludsa_red: {
    logo: '/logo-saludsa.png',
    color: '#059669',
    badge: 'Privado · Nacional',
    desc: 'Saludsa. Principal aseguradora privada de salud en Ecuador con red nacional.',
  },
  bmi_red: {
    logo: '/logo-bmi.png',
    color: '#7c3aed',
    badge: 'Privado · Latina',
    desc: 'BMI Ecuador. Cobertura regional con hospitales premium en Ecuador.',
  },
  bupa_red_interna: {
    logo: '/logo-bupa.png',
    color: '#0369a1',
    badge: 'Privado · Internacional',
    desc: 'Bupa Ecuador. Red amplia de clínicas privadas con cobertura internacional.',
  },
  humana_red: {
    logo: '/logo-humana.png',
    color: '#e11d48',
    badge: 'Privado · Corporativo',
    desc: 'Humana S.A. Soluciones de medicina prepagada corporativa y familiar.',
  },
  iess: {
    logo: '/logo-iess.png',
    color: '#1d4ed8',
    badge: 'Público · IESS',
    desc: 'Instituto Ecuatoriano de Seguridad Social. Cobertura total sin copago para afiliados.',
  },
}

function getPlanMeta(plan: HealthPlan) {
  return PLAN_META[plan.provider_network] ?? {
    logo: '/medibot-avatar.png',
    color: '#2563eb',
    badge: plan.is_public ? 'Público' : 'Privado',
    desc: plan.name,
  }
}

function formatCopago(plan: HealthPlan): string {
  if (plan.is_public) return 'Sin copago'
  if (plan.copago_consulta_usd) return `Consulta: $${plan.copago_consulta_usd}`
  if (plan.copago_pct) return `Copago: ${Math.round(plan.copago_pct * 100)}%`
  return 'Según cobertura'
}

// Group plans by network/provider
function groupPlans(plans: HealthPlan[]): { network: string; meta: ReturnType<typeof getPlanMeta>; plans: HealthPlan[] }[] {
  const map = new Map<string, HealthPlan[]>()
  for (const p of plans) {
    const key = p.provider_network
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(p)
  }
  return Array.from(map.entries()).map(([network, plans]) => ({
    network,
    meta: getPlanMeta(plans[0]),
    plans,
  }))
}

interface Props {
  plans: HealthPlan[]
  onSelect: (planId: number) => void
  onClose: () => void
}

export default function PlanSelectorModal({ plans, onSelect, onClose }: Props) {
  const groups = groupPlans(plans)

  return (
    <div
      className="modal-bg"
      onClick={onClose}
      role="dialog"
      aria-modal
      aria-labelledby="plan-modal-title"
    >
      <motion.div
        className="modal-box"
        style={{ maxWidth: 580 }}
        initial={{ opacity: 0, scale: .95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: .95 }}
        transition={{ duration: .2 }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-hd">
          <div className="modal-hd-ic" style={{ background: '#EFF6FF', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Image src="/icon-insurance.png" alt="Seguro" width={24} height={24} style={{ objectFit: 'contain' }} />
          </div>
          <div>
            <div className="modal-hd-title" id="plan-modal-title">Selecciona tu plan de seguro</div>
            <div style={{ fontSize: 11, color: '#94A3B8', marginTop: 1 }}>Necesitamos saber tu cobertura para calcular tu copago exacto</div>
          </div>
          <button className="modal-x" onClick={onClose} aria-label="Cerrar">✕</button>
        </div>

        {/* Body */}
        <div className="modal-body" style={{ gap: 14, paddingBottom: 8 }}>
          {groups.map(group => (
            <div key={group.network}>
              {/* Aseguradora header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <div style={{ width: 36, height: 36, borderRadius: 9, overflow: 'hidden', position: 'relative', flexShrink: 0, border: '1px solid #E2E8F0', background: '#F8FAFC' }}>
                  <Image src={group.meta.logo} alt={group.network} fill style={{ objectFit: 'contain', padding: 4 }} />
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>
                    {group.network === 'iess' ? 'IESS' :
                     group.network === 'issfa' ? 'ISSFA' :
                     group.network === 'bupa_red_interna' ? 'Bupa Ecuador' :
                     group.network === 'saludsa_red' ? 'Saludsa' :
                     group.network === 'bmi_red' ? 'BMI' : group.network}
                  </div>
                  <div style={{ fontSize: 11, color: '#94A3B8' }}>{group.meta.desc}</div>
                </div>
                <span style={{
                  marginLeft: 'auto', fontSize: 9, fontWeight: 700, padding: '2px 7px',
                  borderRadius: 5, background: `${group.meta.color}15`, color: group.meta.color,
                  border: `1px solid ${group.meta.color}30`, whiteSpace: 'nowrap',
                }}>
                  {group.meta.badge}
                </span>
              </div>

              {/* Plan options */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, paddingLeft: 46 }}>
                {group.plans.map(plan => (
                  <button
                    key={plan.id}
                    onClick={() => { onSelect(plan.id); onClose() }}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '10px 14px', borderRadius: 10, cursor: 'pointer',
                      border: '1.5px solid #E2E8F0', background: '#FAFBFF',
                      fontFamily: 'inherit', transition: 'all .15s', textAlign: 'left',
                      width: '100%',
                    }}
                    onMouseEnter={e => {
                      const el = e.currentTarget
                      el.style.borderColor = group.meta.color
                      el.style.background = `${group.meta.color}08`
                    }}
                    onMouseLeave={e => {
                      const el = e.currentTarget
                      el.style.borderColor = '#E2E8F0'
                      el.style.background = '#FAFBFF'
                    }}
                    aria-label={`Seleccionar ${plan.name}`}
                  >
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#0F172A' }}>{plan.name}</div>
                      <div style={{ fontSize: 11, color: '#94A3B8', marginTop: 2 }}>{formatCopago(plan)}</div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      {plan.is_public && (
                        <span style={{ fontSize: 9, fontWeight: 800, background: '#D1FAE5', color: '#065F46', padding: '2px 7px', borderRadius: 5, letterSpacing: '.05em' }}>
                          GRATIS
                        </span>
                      )}
                      {plan.copago_emergencia_usd && (
                        <span style={{ fontSize: 10, color: '#94A3B8' }}>Emergencia: ${plan.copago_emergencia_usd}</span>
                      )}
                      <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="#CBD5E1" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7"/>
                      </svg>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="modal-ft" style={{ justifyContent: 'center', padding: '12px 20px' }}>
          <p style={{ fontSize: 11, color: '#94A3B8', textAlign: 'center' }}>
            Los datos de copago son referenciales y pueden variar según tu contrato. Ante emergencias llama al <strong>911</strong>.
          </p>
        </div>
      </motion.div>
    </div>
  )
}
