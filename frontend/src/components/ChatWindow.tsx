'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import Image from 'next/image'
import { motion, AnimatePresence } from 'framer-motion'
import { sendMessage, fetchHealthPlans, fetchProvidersByPlan } from '@/lib/api'
import {
  ChatMessage, HealthPlan, AgentStep, StructuredResponse,
  NetworkProvider,
  AGENT_STEP_ICONS, URGENCY_CONFIG, SPECIALTY_ICONS,
} from '@/lib/types'
import MiniMap from './MiniMap'
import ConfirmReset from './ConfirmReset'
import PlanSelectorModal from './PlanSelectorModal'

// ── Constants ─────────────────────────────────────────────────
const SUGGESTIONS = [
  { icon: '💓', text: 'Me duele el pecho y me cuesta respirar' },
  { icon: '🌡️', text: 'Tengo fiebre alta y dolor de cabeza' },
  { icon: '🤢', text: 'Me duele el estómago y tengo náuseas' },
  { icon: '🦴', text: 'Me lastimé la rodilla y no puedo caminar' },
]

const NAV = [
  { id: 'chat', icon: '/icon-chat.png', label: 'Consulta actual' },
  { id: 'plan', icon: '/icon-insurance.png', label: 'Mi seguro' },
  { id: 'hospitals', icon: '/icon-hospital.png', label: 'Red hospitalaria' },
  { id: 'emergency', icon: '/icon-emergency.png', label: 'Emergencias' },
]

// ── Agent steps builder ───────────────────────────────────────
function buildSteps(): AgentStep[] {
  return [
    { id: 'analyze',   label: 'Analizando síntomas',       icon: AGENT_STEP_ICONS.analyze,   status: 'pending', detail: 'Extrayendo entidades clínicas...' },
    { id: 'symptoms',  label: 'Mapeando condiciones',       icon: AGENT_STEP_ICONS.symptoms,  status: 'pending', detail: 'Base de conocimiento médico...' },
    { id: 'specialty', label: 'Identificando especialidad', icon: AGENT_STEP_ICONS.specialty, status: 'pending', detail: 'Seleccionando departamento...' },
    { id: 'urgency',   label: 'Evaluando urgencia',         icon: AGENT_STEP_ICONS.urgency,   status: 'pending', detail: 'Reglas de triaje clínico...' },
    { id: 'copago',    label: 'Calculando copago',          icon: AGENT_STEP_ICONS.copago,    status: 'pending', detail: 'Cruzando tarifario de tu plan...' },
    { id: 'hospital',  label: 'Buscando hospitales',        icon: AGENT_STEP_ICONS.hospital,  status: 'pending', detail: 'Optimizando por costo y distancia...' },
  ]
}
function advance(steps: AgentStep[], idx: number): AgentStep[] {
  return steps.map((s, i) => ({ ...s, status: i < idx ? 'done' : i === idx ? 'active' : 'pending' })) as AgentStep[]
}
function fmt(d: Date) { return d.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' }) }

// ── Agent Thinking ────────────────────────────────────────────
function AgentThinking({ steps }: { steps: AgentStep[] }) {
  const ic: Record<string, string> = { pending: '○', active: '●', done: '✓' }
  return (
    <div className="think-panel">
      <div className="think-head">🧠 Analizando tu consulta…</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {steps.map(s => (
          <motion.div key={s.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className={`think-step ts-${s.status}`}>
            <div className="ts-ic">{ic[s.status]}</div>
            <div>
              <div className="ts-txt">{s.icon} {s.label}</div>
              {s.status === 'active' && s.detail && <div className="ts-detail">{s.detail}</div>}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

// ── Right Panel — Clinical Analysis ──────────────────────────
function RightPanel({ data }: { data: StructuredResponse | null }) {
  const urgClass = !data ? '' : data.urgencia === 'baja' ? 'u-baja' : data.urgencia === 'media' ? 'u-media' : 'u-alta'
  const urgCfg   = data ? URGENCY_CONFIG[data.urgencia] : null
  const minCop   = data?.hospitales_comparacion.length
    ? Math.min(...data.hospitales_comparacion.map(h => h.copago_paciente))
    : null

  return (
    <aside className="right-panel">
      <div className="rp-header">
        <span className="rp-title">Panel Clínico</span>
        <span style={{ fontSize: 11, color: '#94A3B8' }}>Análisis en tiempo real</span>
      </div>

      {!data ? (
        <div className="rp-empty">
          <div className="rp-empty-icon">🩺</div>
          <div className="rp-empty-txt">
            El análisis clínico aparecerá aquí después de tu primera consulta.
          </div>
        </div>
      ) : (
        <div className="rp-body">
          {/* Urgencia alert */}
          {data.urgencia === 'alta' && (
            <div className="urgency-alert">
              <div className="ua-head">🚨 Urgencia Alta</div>
              <div className="ua-body">Acude a emergencias de inmediato. No esperes cita médica.</div>
            </div>
          )}

          {/* Síntomas */}
          {data.sintomas.length > 0 && (
            <div>
              <div className="rp-section-lbl"><span>🩺</span> Síntomas detectados</div>
              <div className="chips">
                {data.sintomas.map(s => <span key={s} className="chip chip-sym">{s}</span>)}
              </div>
            </div>
          )}

          {/* Urgencia pill */}
          {urgCfg && (
            <div>
              <div className="rp-section-lbl"><span>⚡</span> Nivel de urgencia</div>
              <span className={`urgency-pill ${urgClass}`}>{urgCfg.icon} {urgCfg.label}</span>
            </div>
          )}

          {/* Especialidad sugerida (una sola) */}
          {data.especialidades_sugeridas.length > 0 && (
            <div>
              <div className="rp-section-lbl"><span>👨‍⚕️</span> Especialidad sugerida</div>
              <div className="chips">
                {(() => {
                  const s = data.especialidades_sugeridas[0]
                  return (
                    <span key={s} className="chip chip-spec">
                      {SPECIALTY_ICONS[s] ?? '🏥'} {s.replace(/_/g, ' ')}
                    </span>
                  )
                })()}
              </div>
            </div>
          )}

          {/* Servicio recomendado */}
          {data.servicio_recomendado && (
            <div>
              <div className="rp-section-lbl"><span>🧪</span> Servicio recomendado</div>
              <div style={{
                background: '#F0FDF4', border: '1px solid #BBF7D0', borderRadius: 10,
                padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 4,
              }}>
                <div style={{ fontSize: 13.5, fontWeight: 800, color: '#065F46' }}>
                  {data.servicio_recomendado.label}
                </div>
                {data.servicio_recomendado.razon && (
                  <div style={{ fontSize: 11.5, color: '#047857' }}>
                    {data.servicio_recomendado.razon}
                  </div>
                )}
                {data.costo_base > 0 && (
                  <div style={{ fontSize: 11.5, color: '#065F46', marginTop: 2 }}>
                    Costo del servicio: <strong>${data.costo_base.toFixed(2)} {data.moneda}</strong>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Diagnóstico EndlessMedical */}
          {data.condiciones_probables && data.condiciones_probables.length > 0 && (
            <div>
              <div className="rp-section-lbl"><span>🧬</span> Diagnóstico inteligente (EndlessMedical)</div>
              <div style={{
                background: 'linear-gradient(135deg, #F0F9FF 0%, #E0F2FE 100%)',
                border: '1.5px solid #7DD3FC', borderRadius: 12, padding: 12,
                display: 'flex', flexDirection: 'column', gap: 6,
              }}>
                <div style={{ fontSize: 11, color: '#0369A1', fontWeight: 600, marginBottom: 4 }}>
                  Posibles condiciones basadas en tus síntomas:
                </div>
                {data.condiciones_probables.slice(0, 3).map((c, i) => {
                  const pct = Math.round((c.probabilidad || 0) * 100)
                  const barColor = i === 0 ? '#0EA5E9' : i === 1 ? '#22C55E' : '#A855F7'
                  return (
                    <div key={i} style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      padding: '8px 10px', background: '#fff',
                      border: '1px solid #BAE6FD', borderRadius: 8,
                    }}>
                      <div style={{
                        width: 22, height: 22, borderRadius: '50%',
                        background: barColor, color: '#fff',
                        fontSize: 10, fontWeight: 800,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        flexShrink: 0,
                      }}>{i + 1}</div>
                      <div style={{ flex: 1, fontSize: 12.5, fontWeight: 700, color: '#0F172A', minWidth: 0 }}>
                        {c.nombre}
                      </div>
                      <div style={{
                        height: 6, width: 70, background: '#E0F2FE', borderRadius: 99, overflow: 'hidden', flexShrink: 0,
                      }}>
                        <div style={{ height: '100%', width: `${pct}%`, background: barColor, transition: 'width .6s ease' }} />
                      </div>
                      <div style={{ fontSize: 12, fontWeight: 800, color: '#0369A1', minWidth: 36, textAlign: 'right' }}>
                        {pct}%
                      </div>
                    </div>
                  )
                })}
                <div style={{ fontSize: 10, color: '#64748B', marginTop: 4, fontStyle: 'italic' }}>
                  ⚠️ Este diagnóstico es orientativo. No reemplaza la evaluación médica profesional.
                </div>
              </div>
            </div>
          )}

          {/* Copago + Costo */}
          {(data.costo_base > 0 || data.copago_estimado > 0) && (
            <div>
              <div className="rp-section-lbl"><span>💰</span> Costo y copago · {data.plan_seguro || 'Sin plan'}</div>
              <div style={{
                background: 'linear-gradient(135deg, #EFF6FF 0%, #F0FDFA 100%)',
                border: '1px solid #BFDBFE', borderRadius: 12, padding: 12,
                display: 'flex', flexDirection: 'column', gap: 6,
              }}>
                {data.costo_base > 0 && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}>
                    <span style={{ color: '#475569' }}>Costo del servicio</span>
                    <span style={{ fontWeight: 700, color: '#0F172A' }}>${data.costo_base.toFixed(2)}</span>
                  </div>
                )}
                {data.costo_base > 0 && data.copago_estimado >= 0 && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}>
                    <span style={{ color: '#475569' }}>Cubierto por tu plan</span>
                    <span style={{ fontWeight: 700, color: '#059669' }}>
                      ${Math.max(data.costo_base - data.copago_estimado, 0).toFixed(2)}
                    </span>
                  </div>
                )}
                <div style={{ height: 1, background: '#BFDBFE', margin: '2px 0' }} />
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontSize: 12.5, fontWeight: 700, color: '#0F172A' }}>Tú pagas</span>
                  <span style={{ fontSize: 22, fontWeight: 800, color: '#1d4ed8', fontFamily: 'JetBrains Mono, monospace' }}>
                    ${data.copago_estimado.toFixed(2)}
                  </span>
                </div>
                {data.desglose_cobertura && (
                  <div style={{ fontSize: 11, color: '#475569', lineHeight: 1.4, marginTop: 2 }}>
                    {data.desglose_cobertura}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Hospitales */}
          {data.hospitales_comparacion.length > 0 && (
            <div>
              <div className="rp-section-lbl"><span>🏥</span> Red de hospitales</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {data.hospitales_comparacion.map((h, i) => {
                  const isBest = h.copago_paciente === minCop
                  return (
                    <motion.div key={i} initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * .08 }}
                      className={`rp-hospital ${isBest ? 'best' : ''}`}>
                      {isBest && <span className="rp-h-badge">MEJOR PRECIO</span>}
                      <div className="rp-h-name">{h.nombre}</div>
                      <div className="rp-h-type">
                        {h.tipo === 'iess' ? 'IESS · Público' : h.tipo === 'issfa' ? 'ISSFA · Público' : 'Privado'} · Red {h.red}
                      </div>
                      <div className="rp-h-price">${h.copago_paciente.toFixed(2)} <span style={{ fontSize: 11, color: '#94A3B8', fontWeight: 400 }}>USD</span></div>
                      {h.distancia_km !== null && <div className="rp-h-dist">📍 {h.distancia_km.toFixed(1)} km</div>}
                    </motion.div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </aside>
  )
}

// ─────────────────────────────────────────────────────────────
// MAIN ChatWindow
// ─────────────────────────────────────────────────────────────
export default function ChatWindow() {
  const [messages,     setMessages]     = useState<ChatMessage[]>([])
  const [input,        setInput]        = useState('')
  const [loading,      setLoading]      = useState(false)
  const [sessionId,    setSessionId]    = useState<string | null>(null)
  const [plans,        setPlans]        = useState<HealthPlan[]>([])
  const [planId,       setPlanId]       = useState<number | null>(null)
  const [agentSteps,   setAgentSteps]   = useState<AgentStep[]>([])
  const [structured,   setStructured]   = useState<StructuredResponse | null>(null)
  const [error,        setError]        = useState<string | null>(null)
  const [showReset,    setShowReset]    = useState(false)
  const [showPlanModal,setShowPlanModal] = useState(false)
  const [activeNav,    setActiveNav]    = useState('chat')
  const [backendOk,    setBackendOk]    = useState<boolean | null>(null)
  const [networkProviders, setNetworkProviders] = useState<NetworkProvider[]>([])
  const [userLocation, setUserLocation] = useState<{ lat: number; lon: number } | null>(null)

  const bottomRef   = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Obtener geolocalización del usuario (una sola vez al montar)
  useEffect(() => {
    if (!navigator.geolocation) return
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUserLocation({ lat: pos.coords.latitude, lon: pos.coords.longitude })
      },
      (err) => {
        console.warn('Geolocalización no disponible:', err.message)
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 }
    )
  }, [])

  useEffect(() => {
    fetchHealthPlans()
      .then(data => {
        setPlans(data)
        setBackendOk(true)
        // Show plan picker on first load
        setShowPlanModal(true)
      })
      .catch(() => { setError('No se puede conectar con el servidor. ¿Está el backend corriendo?'); setBackendOk(false) })
  }, [])

  useEffect(() => {
    const t = setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }), 80)
    return () => clearTimeout(t)
  }, [messages, agentSteps])

  // Cargar prestadores de la red cuando se selecciona/cambia el plan
  useEffect(() => {
    if (!planId) { setNetworkProviders([]); return }
    let cancel = false
    fetchProvidersByPlan(planId)
      .then(res => { if (!cancel) setNetworkProviders(res.providers || []) })
      .catch(() => { if (!cancel) setNetworkProviders([]) })
    return () => { cancel = true }
  }, [planId])

  useEffect(() => {
    if (!textareaRef.current) return
    textareaRef.current.style.height = 'auto'
    textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
  }, [input])

  const handleSend = useCallback(async () => {
    if (!input.trim() || loading) return
    setError(null)

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(), role: 'user',
      content: input.trim(), timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    const steps = buildSteps()
    setAgentSteps(advance(steps, 0))
    const timers = steps.map((_, i) =>
      setTimeout(() => setAgentSteps(prev => advance(prev, i + 1)), (i + 1) * 700)
    )

    try {
      const data = await sendMessage({
        message: userMsg.content,
        sessionId,
        planId,
        userLat: userLocation?.lat ?? null,
        userLon: userLocation?.lon ?? null,
      })
      timers.forEach(clearTimeout)
      setSessionId(data.session_id)
      setAgentSteps(prev => prev.map(s => ({ ...s, status: 'done' as const })))
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(), role: 'assistant',
        content: data.reply, timestamp: new Date(),
        structuredData: data.structured,
      }])
      if (data.structured) setStructured(data.structured)
    } catch (err: any) {
      timers.forEach(clearTimeout)
      const msg = err.message || 'Error de conexión con el servidor.'
      setError(msg)
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(), role: 'assistant',
        content: `⚠️ ${msg}`, timestamp: new Date(),
      }])
    } finally {
      setLoading(false)
      setTimeout(() => setAgentSteps([]), 1800)
    }
  }, [input, loading, sessionId, planId, userLocation])

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }
  const handleReset = () => {
    setMessages([]); setStructured(null); setSessionId(null)
    setError(null); setShowReset(false)
  }

  const selectedPlan = plans.find(p => p.id === planId)
  const threads      = messages.filter(m => m.role === 'user').slice(-5).reverse()

  return (
    <div className="app-shell">

      {/* ── LEFT SIDEBAR ──────────────────────────────────── */}
      <aside className="sidebar">
        {/* Brand */}
        <div className="sb-brand">
          <div className="sb-logo">M</div>
          <div>
            <div className="sb-name">MediBot AI</div>
            <div className="sb-tagline">Entiende tu cobertura</div>
          </div>
        </div>

        {/* Plan selector */}
        <div className="sb-plan-box">
          <div className="sb-plan-label">Tu plan de seguro</div>
          <select className="sb-plan-select" value={planId ?? ''}
            onChange={e => setPlanId(e.target.value ? Number(e.target.value) : null)}
            aria-label="Plan de seguro">
            <option value="">— Seleccionar plan —</option>
            {plans.map(p => (
              <option key={p.id} value={p.id}>{p.name}{p.is_public ? ' · Gratis' : ''}</option>
            ))}
          </select>
          {selectedPlan && (
            <div className="sb-plan-badges">
              {selectedPlan.is_public
                ? <span className="sb-badge sb-badge-green">COBERTURA TOTAL</span>
                : <>
                  {selectedPlan.copago_consulta_usd != null && <span className="sb-badge sb-badge-blue">CONSULTA ${selectedPlan.copago_consulta_usd}</span>}
                  {selectedPlan.copago_emergencia_usd != null && <span className="sb-badge sb-badge-red">EMERGENCIA ${selectedPlan.copago_emergencia_usd}</span>}
                </>}
            </div>
          )}
        </div>

        {/* Backend status */}
        <div style={{ padding: '0 12px 6px' }}>
          {backendOk === true  && <span style={{ fontSize: 10, color: '#6ee7b7' }}>● Backend conectado</span>}
          {backendOk === false && <span style={{ fontSize: 10, color: '#fca5a5' }}>● Backend sin conexión</span>}
          {backendOk === null  && <span style={{ fontSize: 10, color: 'rgba(255,255,255,.3)' }}>● Verificando...</span>}
        </div>

        {/* Navigation */}
        <div className="sb-section-lbl">Menú</div>
        <nav className="sb-nav">
          {NAV.map(item => (
            <button key={item.id} className={`sb-item ${activeNav === item.id ? 'active' : ''}`}
              onClick={() => setActiveNav(item.id)}>
              <Image src={item.icon} alt={item.label} width={22} height={22} className="sb-item-img" />
              {item.label}
            </button>
          ))}
        </nav>

        {/* Recent threads */}
        {threads.length > 0 && (
          <>
            <div className="sb-section-lbl" style={{ marginTop: 4 }}>Consultas recientes</div>
            <div className="sb-threads">
              {threads.map((m, i) => (
                <div key={m.id} className="sb-thread">
                  <div className="sb-thread-dot" />
                  <div className="sb-thread-text">{m.content}</div>
                </div>
              ))}
            </div>
          </>
        )}

        <div style={{ flex: 1 }} />
        <div className="sb-footer">
          ⚠️ No reemplaza al médico.<br />Emergencias: <strong>911</strong>
        </div>
      </aside>

      {/* ── MAIN CHAT ─────────────────────────────────────── */}
      <div className="main-chat">
        {/* Topbar */}
        <div className="chat-topbar">
          <div className="chat-topbar-left">
            <div className="chat-topbar-avatar">
              <Image src="/medibot-avatar.png" alt="MediBot" fill style={{ objectFit: 'cover' }} />
            </div>
            <div>
              <div className="chat-topbar-name">MediBot AI</div>
              <div className="chat-topbar-status">
                <span className="status-dot" />
                Asistente clínico activo
              </div>
            </div>
          </div>
          <div className="chat-topbar-right">
            {/* Plan indicator / picker button */}
            <button
              onClick={() => setShowPlanModal(true)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '5px 11px',
                borderRadius: 8, border: planId ? '1.5px solid #BFDBFE' : '1.5px solid #FCA5A5',
                background: planId ? '#EFF6FF' : '#FEF2F2', cursor: 'pointer',
                fontSize: 12, fontWeight: 600, fontFamily: 'inherit',
                color: planId ? '#1d4ed8' : '#b91c1c', transition: 'all .15s',
              }}
              aria-label="Cambiar plan de seguro"
            >
              🛡️ {planId ? (plans.find(p => p.id === planId)?.name ?? 'Mi seguro') : 'Selecciona tu seguro'}
            </button>
            {sessionId && (
              <div title={`Sesión: ${sessionId}`}
                style={{ fontSize: 10, color: '#94A3B8', cursor: 'default', padding: '0 4px' }}>
                📋 #{sessionId.slice(0,8)}
              </div>
            )}
            {messages.length > 0 && (
              <button className="topbar-btn danger" onClick={() => setShowReset(true)}
                aria-label="Reiniciar chat" title="Reiniciar conversación">
                <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                </svg>
              </button>
            )}
          </div>
        </div>

        {/* Messages */}
        <div className="messages-scroll" role="log" aria-live="polite" aria-label="Conversación">

          {/* Empty state */}
          {messages.length === 0 && !loading && (
            <div className="empty-center">
              <div className="empty-av">
                <Image src="/medibot-avatar.png" alt="MediBot" fill style={{ objectFit: 'cover' }} />
              </div>
              <h1 className="empty-title">Hola, soy MediBot AI</h1>
              {!planId ? (
                <p className="empty-sub" style={{ marginTop: 8, color: '#dc2626', fontWeight: 600 }}>
                  Selecciona tu aseguradora para habilitar el chat.
                </p>
              ) : (
                <p className="empty-sub" style={{ marginTop: 8 }}>
                  Describe tus síntomas y te diré la especialidad exacta, tu copago y el hospital más conveniente de tu red.
                </p>
              )}
              <div className="how-row">
                {[
                  ['1', 'Elige tu seguro ←'],
                  ['2', 'Describe síntomas'],
                  ['3', 'Recibe copago + hospital'],
                ].map(([n, l]) => (
                  <div className="how-card" key={n}>
                    <div className="how-n">{n}</div>
                    <div className="how-lbl">{l}</div>
                  </div>
                ))}
              </div>
              <div className="suggestions">
                {SUGGESTIONS.map(s => (
                  <button key={s.text} className="sugg-btn" onClick={() => setInput(s.text)}>
                    {s.icon} {s.text}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div style={{ maxWidth: 660, margin: '0 auto 10px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 9, padding: '9px 13px', fontSize: 12.5, color: '#b91c1c' }}>
              {error}
            </div>
          )}

          {/* Messages */}
          <div style={{ maxWidth: 660, width: '100%', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 2 }}>
            <AnimatePresence initial={false}>
              {messages.map((msg, idx) => {
                const isBot  = msg.role === 'assistant'
                const isLast = isBot && idx === messages.length - 1
                const sd     = isLast ? structured : (isBot && msg.structuredData ? msg.structuredData : null)
                const urgClass = sd ? (sd.urgencia === 'baja' ? 'u-baja' : sd.urgencia === 'media' ? 'u-media' : 'u-alta') : ''
                const urgCfg   = sd ? URGENCY_CONFIG[sd.urgencia] : null
                const minCop   = sd?.hospitales_comparacion.length ? Math.min(...sd.hospitales_comparacion.map(h => h.copago_paciente)) : null

                return (
                  <motion.div key={msg.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: .18 }} className={`msg-wrap ${isBot ? '' : 'user'}`}>
                    {isBot
                      ? <div className="msg-av"><Image src="/medibot-avatar.png" alt="MediBot" fill style={{ objectFit: 'cover' }} /></div>
                      : <div className="msg-av-user">U</div>
                    }
                    <div className="msg-body">
                      <div className={`bubble ${isBot ? 'bot' : 'user'}`}>{msg.content}</div>
                      <span className="msg-time">{fmt(msg.timestamp)}</span>

                      {/* ── Clinical inline cards (only on bot messages with structured data) ── */}
                      {sd && isBot && (
                        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                          style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>

                          {/* Summary row: servicio + copago */}
                          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                            {sd.servicio_recomendado && (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 12px', borderRadius: 99, fontSize: 13, fontWeight: 700, background: '#F0FDF4', color: '#065F46', border: '1px solid #BBF7D0' }}>
                                🧪 {sd.servicio_recomendado.label}
                              </span>
                            )}
                            {sd.costo_base > 0 && (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 12px', borderRadius: 99, fontSize: 13, fontWeight: 700, background: '#F8FAFC', color: '#334155', border: '1px solid #CBD5E1' }}>
                                Costo: ${sd.costo_base.toFixed(2)}
                              </span>
                            )}
                            {sd.copago_estimado > 0 ? (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 12px', borderRadius: 99, fontSize: 13, fontWeight: 700, background: '#EFF6FF', color: '#1d4ed8', border: '1px solid #BFDBFE' }}>
                                💰 Tú pagas: ${sd.copago_estimado.toFixed(2)} {sd.moneda}
                              </span>
                            ) : (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 12px', borderRadius: 99, fontSize: 13, fontWeight: 700, background: '#D1FAE5', color: '#065F46', border: '1px solid #A7F3D0' }}>
                                🛡️ Cobertura Total (Sin Copago)
                              </span>
                            )}
                          </div>

                          {/* Map inline in chat */}
                          {(sd.hospitales_comparacion.some(h => h.lat !== null) || networkProviders.length > 0) && (
                            <div style={{ height: 320, borderRadius: 12, overflow: 'hidden', border: '1px solid #E2E8F0', marginTop: 2, boxShadow: '0 2px 8px rgba(15,23,42,.06)' }}>
                              <MiniMap
                                hospitals={sd.hospitales_comparacion}
                                networkProviders={networkProviders}
                                userLocation={userLocation ?? undefined}
                              />
                            </div>
                          )}
                        </motion.div>
                      )}
                    </div>
                  </motion.div>
                )
              })}
            </AnimatePresence>

            {/* Thinking */}
            <AnimatePresence>
              {loading && agentSteps.length > 0 && (
                <motion.div key="thinking" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }} className="msg-wrap">
                  <div className="msg-av"><Image src="/medibot-avatar.png" alt="" fill style={{ objectFit: 'cover' }} /></div>
                  <div className="msg-body"><AgentThinking steps={agentSteps} /></div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Typing */}
            <AnimatePresence>
              {loading && agentSteps.length === 0 && (
                <motion.div key="typing" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }} className="msg-wrap">
                  <div className="msg-av"><Image src="/medibot-avatar.png" alt="" fill style={{ objectFit: 'cover' }} /></div>
                  <div className="msg-body">
                    <div className="typing-bubble">
                      <div className="tdot"/><div className="tdot"/><div className="tdot"/>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div ref={bottomRef} />
          </div>
        </div>

        {/* Input */}
        <div className="input-bar">
          {!planId ? (
            <div style={{ padding: '20px', background: '#FEF2F2', borderRadius: 16, border: '2px dashed #FCA5A5', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, margin: '0 20px 16px' }}>
              <div style={{ color: '#b91c1c', fontWeight: 800, fontSize: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 20 }}>⚠️</span> Acción Requerida
              </div>
              <div style={{ color: '#dc2626', fontSize: 14, textAlign: 'center', maxWidth: 450, lineHeight: 1.5 }}>
                El chat está deshabilitado. Para estimar tus copagos y sugerir la red hospitalaria correcta, es <b>obligatorio</b> seleccionar tu aseguradora.
              </div>
              <motion.button 
                onClick={() => setShowPlanModal(true)}
                animate={{ scale: [1, 1.03, 1] }}
                transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
                style={{ background: '#EF4444', color: '#fff', border: 'none', padding: '14px 36px', borderRadius: 10, fontSize: 15, fontWeight: 700, cursor: 'pointer', boxShadow: '0 6px 16px rgba(239, 68, 68, 0.4)', marginTop: 8 }}
              >
                Elegir Aseguradora Ahora
              </motion.button>
            </div>
          ) : (
            <div className="input-row">
              <textarea ref={textareaRef} className="input-box" rows={1}
                value={input} onChange={e => setInput(e.target.value)} onKeyDown={handleKey}
                placeholder="Describe tus síntomas… (Enter para enviar, Shift+Enter para nueva línea)"
                disabled={loading}
                aria-label="Describe tus síntomas"
              />
              <button className="input-mic-btn" aria-label="Micrófono (próximamente)" title="Próximamente">
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"/>
                </svg>
              </button>
              <button className="input-send-btn" onClick={handleSend}
                disabled={loading || !input.trim()} aria-label="Enviar mensaje">
                <svg width="17" height="17" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
                </svg>
              </button>
            </div>
          )}
          <p className="input-hint">MediBot AI · Estimador de copago y cobertura · No reemplaza al médico</p>
        </div>
      </div>

      {/* ── RIGHT PANEL ───────────────────────────────────── */}
      <RightPanel data={structured} />

      {/* ── MODALS ─────────────────────────────────────────── */}
      <AnimatePresence>
        {showReset && <ConfirmReset onConfirm={handleReset} onCancel={() => setShowReset(false)} />}
      </AnimatePresence>
      <AnimatePresence>
        {showPlanModal && plans.length > 0 && (
          <PlanSelectorModal
            plans={plans}
            onSelect={id => { setPlanId(id); setShowPlanModal(false) }}
            onClose={() => setShowPlanModal(false)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}