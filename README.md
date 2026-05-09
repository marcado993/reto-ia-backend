# MediBot — Estimador Agéntico de Copago y Cobertura

<p align="center">
  <img src="https://img.shields.io/badge/síntomas-90-green" alt="90 síntomas" />
  <img src="https://img.shields.io/badge/especialidades-26-blue" alt="26 especialidades" />
  <img src="https://img.shields.io/badge/reglas_clínicas-31-red" alt="31 reglas" />
  <img src="https://img.shields.io/badge/hospitales-25-orange" alt="25 hospitales" />
</p>

Un agente conversacional que ayuda al paciente a entender su beneficio antes de atenderse. El paciente ingresa su síntoma, el agente sugiere la especialidad, cruza datos con su plan de seguro, indica exactamente cuánto será su copago y qué hospital de la red le conviene más económicamente.

## Identidad Visual

- **Marca**: MediBot — Asistente de Cobertura Médica
- **Colores**: Teal/Esmeralda (#059669, #10b981) como color primario, Slate para secundarios
- **Tipografía**: Inter ( cuerpo), JetBrains Mono (datos técnicos)
- **Logo**: Cruz médica + "+" stylized
- **Diseño**: Sidebar con plan de seguro, chat central, cards expandibles

## Principios de Diseño (Nielsen)

| Heurística | Implementación |
|---|---|
| **Visibilidad del estado** | Agent steps animados ("Analizando síntomas..." → ✓) |
| **Correspondencia sistema-mundo real** | Síntomas en lenguaje coloquial ("me duele el pecho" |
| **Control y libertad** | Selector de plan visible, sugerencias de preguntas |
| **Consistencia** | Mismo color para mismas urgencias, misma estructura de respuesta |
| **Prevención de errores** | Botón enviar deshabilitado si no se selecciona plan |
| **Reconocimiento > recuerdo** | Planes visibles en sidebar, chips de síntomas |
| **Flexibilidad** | Sugerencias clickeables (preguntas rápidas) |
| **Diseño minimal** | Una acción principal (escribir síntomas), info progresiva |
| **Recuperación de errores** | Mensaje claro en rojo ante errores de conexión |
| **Ayuda y documentación** | Disclaimer médico visible, sugerencias contextuales |

## Arquitectura

```
Paciente → Frontend (Next.js) → Backend API (FastAPI)
                                    ├── Agente Conversacional (GPT-4o + Tools)
                                    ├── NLP Service (extracción de síntomas)
                                    ├── Ontology Service (síntomas → especialidades)
                                    ├── Rule Engine (urgencia + reglas clínicas)
                                    ├── Copago Service (cálculo exacto de copago)
                                    ├── Hospital Service (búsqueda + mapa comparativo)
                                    └── PostgreSQL / SQLite (datos + ontología)
```

## Flujo del Agente (Affordances Visuales)

```
 🔍 Analizando síntomas          → ✓ Identificados
 🩺 Identificando condiciones     → ✓ 2 condiciones
 👨‍⚕️ Sugiriendo especialidad     → ✓ Cardiología, Neumología
 ⚙️  Evaluando urgencia           → ✓ ALTA — Emergencia
 💰 Calculando copago             → ✓ $6.00 USD
 🏥 Buscando hospitales           → ✓ 3 opciones encontradas
```

## Inicio Rápido

### 1. Configurar variables de entorno
```bash
cp .env.example .env
# Editar .env con tu OPENAI_API_KEY
```

### 2. Levantar servicios con Docker
```bash
docker-compose up --build
docker-compose exec backend python3 scripts/seed_db.py
```

### 3. Sin Docker (desarrollo local)
```bash
# Backend
cd backend
pip install --break-system-packages -e .
python3 scripts/seed_db.py
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### 4. Acceder
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs

## Datos

| Recurso | Cantidad | Detalle |
|---------|----------|---------|
| **Síntomas** | 90 | Con sinónimos coloquiales en español |
| **Especialidades** | 26 | Cardiología, Neumología, Ginecología, Oncología, etc. |
| **Planes de seguro** | 7 | IESS (gratuito), ISSFA, Bupa 100/200, Saludsa Premium/Básico, BMI Gold |
| **Hospitales** | 25 | Con coordenadas reales (Quito, Guayaquil, Cuenca, Loja, etc.) |
| **Reglas clínicas** | 31 | 10 de emergencia, reglas de derivación por especialidad |
| **Servicios médicos** | 14 | Consultas por especialidad, emergencias, hospitalización |

## API Endpoints

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `POST /api/chat/` | POST | Chat con el agente |
| `GET /api/symptoms/` | GET | Listar síntomas |
| `GET /api/health-plans/` | GET | Listar planes de seguro |
| `GET /api/health-plans/{id}` | GET | Detalle de plan |
| `POST /api/health-plans/copago` | POST | Calcular copago |
| `GET /api/hospitals/` | GET | Listar hospitales |
| `POST /api/hospitals/search` | POST | Buscar hospitales por plan/especialidad |
| `GET /health` | GET | Health check |