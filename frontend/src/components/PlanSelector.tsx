import { HealthPlan } from '@/lib/types'

interface Props {
  plans: HealthPlan[]
  selectedPlanId: number | null
  onSelect: (planId: number | null) => void
}

export default function PlanSelector({ plans, selectedPlanId, onSelect }: Props) {
  if (plans.length === 0) {
    return <p className="text-xs text-slate-400">Cargando planes...</p>
  }

  return (
    <div className="space-y-2 mt-2">
      {plans.map(plan => (
        <button
          key={plan.id}
          onClick={() => onSelect(plan.id)}
          className={`plan-card w-full text-left ${selectedPlanId === plan.id ? 'plan-card-active' : 'plan-card-default'} ${plan.is_public ? 'plan-card-public' : ''}`}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-slate-900 leading-tight">{plan.name}</p>
              <p className="text-[10px] text-slate-500 mt-0.5">
                {plan.is_public ? 'Cobertura total' : `Copago ${plan.copago_pct ? `${Math.round(Number(plan.copago_pct) * 100)}%` : '$' + (plan.copago_consulta_usd || '0')}`}
              </p>
            </div>
            {plan.is_public && (
              <span className="text-[9px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded font-bold">GRATIS</span>
            )}
          </div>
        </button>
      ))}
    </div>
  )
}