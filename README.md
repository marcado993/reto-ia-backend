<div align="center">

# MediBot
### Estimador Agéntico de Copago y Cobertura para el Paciente

*El paciente describe lo que siente. MediBot le dice a qué especialidad ir, cuánto va a pagar exactamente y a qué hospital de su red le conviene más — antes de salir de casa.*

<p>
  <img src="https://img.shields.io/badge/síntomas-en_español-059669?style=flat-square" alt="Síntomas en español" />
  <img src="https://img.shields.io/badge/especialidades-médicas-10b981?style=flat-square" alt="Especialidades médicas" />
  <img src="https://img.shields.io/badge/reglas-clínicas-dc2626?style=flat-square" alt="Reglas clínicas" />
  <img src="https://img.shields.io/badge/hospitales-con_coordenadas-f97316?style=flat-square" alt="Hospitales con coordenadas" />
  <img src="https://img.shields.io/badge/planes-de_seguro-3b82f6?style=flat-square" alt="Planes de seguro" />
</p>

<p>
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi" />
  <img src="https://img.shields.io/badge/Next.js-Frontend-000?style=flat-square&logo=nextdotjs" />
  <img src="https://img.shields.io/badge/PostgreSQL%20%2F%20SQLite-DB-336791?style=flat-square&logo=postgresql" />
  <img src="https://img.shields.io/badge/OpenRouter%20%2F%20Gemini-LLM-8b5cf6?style=flat-square" />
</p>

</div>

---

## Presentación

### El reto

> **Estimador Agéntico de Copago y Cobertura para el Paciente.**
> Un agente conversacional que ayude al paciente a entender su beneficio antes de atenderse. El paciente ingresa su síntoma, el agente sugiere la especialidad en el hospital y, cruzando datos con su plan de seguro, le indica exactamente cuánto será su copago y qué hospital de la red le conviene más económicamente.

### Nuestra solución, en una frase

Un **agente híbrido** (LLM + reglas clínicas + base de datos de planes y hospitales) que toma el síntoma en lenguaje coloquial, selecciona especialidad y servicio de primer contacto, calcula el **copago exacto** según el plan del paciente y devuelve un **comparador de hospitales** de su red — todo en una sola respuesta estructurada.

### Cómo cumplimos cada parte del reto

| Exigencia del reto | Cómo la cumple MediBot |
|---|---|
| *“El paciente ingresa su síntoma”* | Endpoint `POST /api/chat/` recibe texto libre en español. NLP + LLM normalizan a síntomas del catálogo (con sinónimos coloquiales). |
| *“El agente sugiere la especialidad”* | LLM propone especialidad → **Rule Engine** valida con reglas clínicas y eleva la urgencia si detecta una emergencia (la regla *siempre* gana al LLM en seguridad). |
| *“Cruzando datos con su plan de seguro”* | `CopagoService` lee el plan (IESS, ISSFA, Bupa, Saludsa, BMI…) y aplica copago fijo o porcentual sobre el costo base del servicio. |
| *“Indica exactamente cuánto será su copago”* | Respuesta estructurada con `costo_base`, `copago_estimado`, `desglose` y `moneda` — listo para mostrar en la UI. |
| *“Hospital de la red más económicamente conveniente”* | `HospitalService` filtra los hospitales por red del plan, calcula copago por hospital y los ordena por costo (con distancia geográfica si hay coordenadas). |

---

## Diagrama del flujo agéntico

Cada bloque numerado corresponde directamente a una exigencia del reto.

```text
                ┌───────────────────────────────────────────────┐
                │  Paciente describe su síntoma                 │
                │  ("me duele el pecho desde anoche")           │
                └───────────────────────┬───────────────────────┘
                                        │
                                        ▼
                            POST /api/chat/   (FastAPI)
                                        │
                                        ▼
                              ┌──────────────────┐
                              │  MedicalAgent    │
                              │  (orquestador)   │
                              └────────┬─────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
        ▼                              ▼                              ▼
 ╔════════════════╗           ╔════════════════╗            ╔════════════════╗
 ║ [1] Entender   ║           ║ [2] Sugerir    ║            ║ [3] Cruzar con ║
 ║   al paciente  ║           ║  especialidad  ║            ║   el plan de   ║
 ║                ║           ║   y urgencia   ║            ║     seguro     ║
 ╠════════════════╣           ╠════════════════╣            ╠════════════════╣
 ║ • LLM          ║           ║ • LLM propone  ║            ║ • CopagoService║
 ║   analyze_     ║           ║   especialidad ║            ║   lee el plan  ║
 ║   patient      ║           ║                ║            ║   del paciente ║
 ║ • NLP normaliza║           ║ • Rule Engine  ║            ║ • Aplica       ║
 ║   los síntomas ║           ║   valida y     ║            ║   copago fijo  ║
 ║   coloquiales  ║           ║   eleva la     ║            ║   o porcentual ║
 ║                ║           ║   urgencia (la ║            ║   sobre el     ║
 ║                ║           ║   regla manda  ║            ║   costo base   ║
 ║                ║           ║   en emergencia║            ║   del servicio ║
 ╚════════════════╝           ╚════════════════╝            ╚════════════════╝
        │                              │                              │
        └──────────────────────────────┼──────────────────────────────┘
                                       │
                                       ▼
                          ╔════════════════════════╗
                          ║ [4] Hospital más       ║
                          ║      conveniente       ║
                          ╠════════════════════════╣
                          ║ HospitalService        ║
                          ║ • Filtra por red       ║
                          ║   del plan             ║
                          ║ • Ordena por copago    ║
                          ║ • Considera distancia  ║
                          ║   si hay coordenadas   ║
                          ╚═══════════┬════════════╝
                                      │
                                      ▼
                ┌───────────────────────────────────────────────┐
                │  Respuesta estructurada al frontend           │
                │  • Especialidad + nivel de urgencia           │
                │  • Copago exacto + desglose de cobertura      │
                │  • Hospitales recomendados (ordenados)        │
                └───────────────────────────────────────────────┘
```

> El **Rule Engine** funciona como red de seguridad: si el LLM subestima una emergencia, la regla local eleva la urgencia y prioriza la especialidad correcta.

---

## Documentación

### Arquitectura

```
Paciente
   │
   ▼
Frontend (Next.js)  ──►  Backend API (FastAPI)
                              │
                              ├── MedicalAgent (orquestador)
                              ├── LLM Service (OpenRouter / Gemini)
                              ├── NLP Service (extracción de síntomas)
                              ├── Ontology Service (síntoma → especialidad)
                              ├── Rule Engine (urgencia + reglas clínicas)
                              ├── Copago Service (cálculo exacto)
                              ├── Hospital Service (búsqueda + comparativo)
                              └── PostgreSQL / SQLite (ontología y catálogo)
```

### Flujo paso a paso del agente

```
🔍 Analizando síntomas         → ✓ Identificados
🩺 Identificando condiciones    → ✓ 2 condiciones
👨‍⚕️ Sugiriendo especialidad     → ✓ Cardiología, Neumología
⚙️  Evaluando urgencia          → ✓ ALTA — Emergencia
💰 Calculando copago            → ✓ $6.00 USD
🏥 Buscando hospitales          → ✓ 3 opciones encontradas
```

### Datos sembrados

| Recurso | Detalle |
|---|---|
| **Síntomas** | Catálogo en español con sinónimos coloquiales |
| **Especialidades** | Cardiología, Neumología, Ginecología, Oncología, etc. |
| **Planes de seguro** | IESS (gratuito), ISSFA, Bupa 100/200, Saludsa Premium/Básico, BMI Gold |
| **Hospitales** | Con coordenadas reales (Quito, Guayaquil, Cuenca, Loja, etc.) |
| **Reglas clínicas** | Reglas de emergencia y de derivación por especialidad |
| **Servicios médicos** | Consultas, emergencias, hospitalización y procedimientos |

### API Endpoints

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/chat/` | `POST` | Chat con el agente — entrada principal del paciente |
| `/api/symptoms/` | `GET` | Listar síntomas del catálogo |
| `/api/health-plans/` | `GET` | Listar planes de seguro |
| `/api/health-plans/{id}` | `GET` | Detalle de plan |
| `/api/health-plans/copago` | `POST` | Calcular copago para una combinación plan + servicio |
| `/api/hospitals/` | `GET` | Listar hospitales |
| `/api/hospitals/search` | `POST` | Buscar hospitales por plan / especialidad |
| `/health` | `GET` | Health check |

Documentación interactiva (Swagger UI): [http://localhost:8000/docs](http://localhost:8000/docs)

### Inicio rápido

#### 1. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tu OPENROUTER_API_KEY (o GEMINI_API_KEY)
```

#### 2. Con Docker (full stack)

```bash
docker-compose up --build
docker-compose exec backend python3 scripts/seed_db.py
```

#### 3. Solo backend con Docker

```bash
cd backend
docker compose up --build
```

#### 4. Sin Docker (desarrollo local)

```bash
# Backend
cd backend
pip install -e .
python3 scripts/seed_db.py
uvicorn app.main:app --reload --port 8000

# Frontend (en otra terminal)
cd frontend
npm install
npm run dev
```

#### 5. Acceder

- **Frontend**: [http://localhost:3000](http://localhost:3000)
- **Backend API**: [http://localhost:8000/docs](http://localhost:8000/docs)

### Variables de entorno principales

| Variable | Por defecto | Descripción |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./medical_chatbot.db` | URL de la base de datos (Postgres en prod) |
| `OPENROUTER_API_KEY` | *(vacío)* | Key de OpenRouter — recomendado |
| `OPENROUTER_MODEL` | `openai/gpt-oss-20b:free` | Modelo a usar |
| `OPENROUTER_TIMEOUT` | `25.0` | Timeout por llamada al LLM (segundos) |
| `GEMINI_API_KEY` | *(vacío)* | Alternativa: Gemini directo |
| `CORS_ORIGINS` | `http://localhost:3000` | Origins permitidos (CSV) |
| `DEBUG` | `True` | Logs verbosos |

---

## Identidad visual

- **Marca**: MediBot — Asistente de Cobertura Médica
- **Colores**: Teal/Esmeralda (`#059669`, `#10b981`) primario · Slate secundario
- **Tipografía**: Inter (cuerpo) · JetBrains Mono (datos técnicos)
- **Logo**: Cruz médica con `+` estilizado
- **Layout**: Sidebar con plan de seguro · chat central · cards expandibles con copago y hospitales

## Principios de diseño (Heurísticas de Nielsen)

| Heurística | Implementación |
|---|---|
| **Visibilidad del estado** | Agent steps animados (“Analizando síntomas…” → ✓) |
| **Correspondencia con el mundo real** | Síntomas en lenguaje coloquial (“me duele el pecho”) |
| **Control y libertad** | Selector de plan visible, sugerencias de preguntas |
| **Consistencia** | Mismo color por nivel de urgencia, misma estructura de respuesta |
| **Prevención de errores** | Botón enviar deshabilitado si no se selecciona plan |
| **Reconocimiento > recuerdo** | Planes visibles en sidebar, chips de síntomas |
| **Flexibilidad** | Sugerencias clickeables (preguntas rápidas) |
| **Diseño minimal** | Una acción principal: escribir síntomas |
| **Recuperación de errores** | Mensaje claro en rojo ante errores de conexión |
| **Ayuda y documentación** | Disclaimer médico visible, sugerencias contextuales |
