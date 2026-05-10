const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'

// ── Chat ──────────────────────────────────────────────────────
export interface SendMessageParams {
  message: string
  sessionId: string | null
  planId: number | null
  age?: number | null
  gender?: 'male' | 'female' | null
  userLat?: number | null
  userLon?: number | null
}

export async function sendMessage({ message, sessionId, planId, age, gender, userLat, userLon }: SendMessageParams) {
  const body: Record<string, unknown> = { message, session_id: sessionId, plan_id: planId }
  if (age)    body.age    = age
  if (gender) body.gender = gender
  if (userLat != null) body.user_lat = userLat
  if (userLon != null) body.user_lon = userLon

  const res = await fetch(`${API_BASE}/chat/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Error de conexión' }))
    throw new Error(err.detail || `Error ${res.status}`)
  }
  return res.json()
}

// ── Session history ───────────────────────────────────────────
export async function getSession(sessionId: string) {
  const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

// ── Health Plans ──────────────────────────────────────────────
export async function fetchHealthPlans() {
  const res = await fetch(`${API_BASE}/health-plans/`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export async function fetchPlanDetails(planId: number) {
  const res = await fetch(`${API_BASE}/health-plans/${planId}`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

// ── Hospitals ─────────────────────────────────────────────────
export async function fetchHospitals(network?: string, zone?: string) {
  const params = new URLSearchParams()
  if (network) params.set('network', network)
  if (zone)    params.set('zone', zone)
  const res = await fetch(`${API_BASE}/hospitals/?${params}`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

export async function searchHospitals(planId: number, specialty?: string, urgency?: string, userLat?: number, userLon?: number) {
  const res = await fetch(`${API_BASE}/hospitals/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan_id: planId, specialty, urgency: urgency || 'media', user_lat: userLat, user_lon: userLon, limit: 3 }),
  })
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json()
}

// ── Providers (red de la aseguradora) ─────────────────────────
export async function fetchProvidersByPlan(planId: number) {
  const res = await fetch(`${API_BASE}/providers/by-plan/${planId}`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json() as Promise<{
    plan_id: number
    plan_name: string
    provider_network: string
    aseguradora: string | null
    providers: import('./types').NetworkProvider[]
    count: number
    note?: string
  }>
}

// ── Health check ──────────────────────────────────────────────
export async function healthCheck() {
  const res = await fetch(process.env.NEXT_PUBLIC_API_URL?.replace('/api', '') || 'http://localhost:8000/health')
  return res.ok
}