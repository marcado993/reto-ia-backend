'use client'

import { HospitalRecommendation } from '@/lib/types'
import MiniMap from './MiniMap'

interface Props {
  hospitals: HospitalRecommendation[]
}

export default function HospitalComparisonCard({ hospitals }: Props) {
  if (!hospitals || hospitals.length === 0) return null

  const minCopago = Math.min(...hospitals.map(h => h.copago_paciente))

  return (
    <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-100 flex items-center gap-2">
        <span className="text-lg">🏥</span>
        <h3 className="font-semibold text-slate-900 text-sm">Hospitales Recomendados</h3>
        <span className="text-xs text-slate-400 ml-auto">{hospitals.length} opciones en su red</span>
      </div>

      <div className="p-4">
        <div className="hospital-grid">
          {hospitals.map((h, i) => {
            const isBest = h.copago_paciente === minCopago
            return (
              <div key={i} className={`hospital-card ${isBest ? 'hospital-card-best' : 'hospital-card-default'}`}>
                {isBest && (
                  <div className="hospital-best-badge mb-2">
                    ✓ Mejor precio
                  </div>
                )}
                <p className="font-semibold text-sm text-slate-900 leading-tight">{h.nombre}</p>
                <p className="text-xs text-slate-500 mt-0.5">{h.tipo === 'iess' ? 'IESS — Publico' : h.tipo === 'issfa' ? 'ISSFA — Publico' : 'Privado'} · Red: {h.red}</p>
                <div className="mt-3 pt-3 border-t border-slate-100">
                  <div className="flex items-baseline justify-between">
                    <div>
                      <p className="text-[10px] text-slate-400 uppercase tracking-wider font-medium">Copago</p>
                      <p className={`text-xl font-bold ${isBest ? 'text-green-700' : 'text-slate-800'}`}>
                        ${h.copago_paciente.toFixed(2)}
                      </p>
                    </div>
                    {h.costo_consulta > 0 && (
                      <div className="text-right">
                        <p className="text-[10px] text-slate-400">Costo base</p>
                        <p className="text-xs text-slate-500">${h.costo_consulta.toFixed(2)}</p>
                      </div>
                    )}
                  </div>
                  {h.distancia_km !== null && (
                    <p className="text-xs text-slate-400 mt-1.5 flex items-center gap-1">
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                      {h.distancia_km.toFixed(1)} km
                    </p>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {hospitals.some(h => h.lat !== null && h.lon !== null) && (
          <div className="mt-4">
            <MiniMap hospitals={hospitals} />
          </div>
        )}
      </div>
    </div>
  )
}