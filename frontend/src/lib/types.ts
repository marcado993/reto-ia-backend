export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  structuredData?: StructuredResponse
  agentSteps?: AgentStep[]
  isThinking?: boolean
}

export interface AgentStep {
  id: string
  label: string
  icon: string
  status: 'pending' | 'active' | 'done'
  detail?: string
}

export interface StructuredResponse {
  sintomas: string[]
  urgencia: 'baja' | 'media' | 'alta'
  especialidades_sugeridas: string[]
  plan_seguro: string
  copago_estimado: number
  moneda: string
  hospital_recomendado: HospitalRecommendation | null
  hospitales_comparacion: HospitalRecommendation[]
  desglose_cobertura: string
}

export interface HospitalRecommendation {
  nombre: string
  tipo: string
  red: string
  costo_consulta: number
  copago_paciente: number
  lat: number | null
  lon: number | null
  distancia_km: number | null
}

export interface SymptomBadge {
  name: string
  normalized: string
  severity: 'baja' | 'media' | 'alta'
}

export interface HealthPlan {
  id: number
  name: string
  type: string
  is_public: boolean
  provider_network: string
  copago_consulta_usd: number | null
  copago_emergencia_usd: number | null
  copago_pct: number | null
  deductible_usd: number
}

export const URGENCY_CONFIG = {
  baja: { label: 'Baja', color: 'green', icon: '✓', pulse: false, bgClass: 'urgency-baja' },
  media: { label: 'Media', color: 'amber', icon: '⚡', pulse: false, bgClass: 'urgency-media' },
  alta: { label: 'ALTA — Emergencia', color: 'red', icon: '🚨', pulse: true, bgClass: 'urgency-alta' },
} as const

export const SPECIALTY_ICONS: Record<string, string> = {
  'cardiologia': '🫀',
  'neumologia': '🫁',
  'neurologia': '🧠',
  'medicina_interna': '🩺',
  'gastroenterologia': '🫃',
  'emergencias': '🚑',
  'dermatologia': '🩹',
  'ortopedia': '🦴',
  'urologia': '🫘',
  'psiquiatria': '🧘',
  'cirugia_general': '🔪',
  'infectologia': '🦠',
  'reumatologia': '🦴',
  'otorrinolaringologia': '👂',
  'endocrinologia': '🔬',
  'hematologia': '🩸',
  'oftalmologia': '👁️',
  'odontologia': '🦷',
  'ginecologia': '👶',
  'cirugia_vascular': '🫀',
  'alergologia': '🤧',
  'hepatologia': '🫁',
  'oncologia': '🎗️',
  'nutricion': '🥗',
  'geriatria': '👴',
  'pediatria': '🍼',
  'psicologia': '💭',
}

export const AGENT_STEP_ICONS: Record<string, string> = {
  'analyze': '🔍',
  'symptoms': '🩺',
  'specialty': '👨‍⚕️',
  'urgency': '⚙️',
  'copago': '💰',
  'hospital': '🏥',
}