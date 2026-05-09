TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "extract_symptoms",
            "description": "Extrae y normaliza sintomas medicos del texto del paciente en espanol",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Texto del paciente describiendo sus sintomas",
                    }
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_ontology",
            "description": "Consulta las relaciones entre sintomas, enfermedades y especialidades medicas en la base de conocimiento",
            "parameters": {
                "type": "object",
                "properties": {
                    "symptoms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de sintomas normalizados",
                    }
                },
                "required": ["symptoms"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_urgency",
            "description": "Evalua el nivel de urgencia basado en combinaciones de sintomas y reglas clinicas",
            "parameters": {
                "type": "object",
                "properties": {
                    "symptoms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de sintomas normalizados",
                    },
                    "severity_notes": {
                        "type": "string",
                        "description": "Notas sobre la severidad descrita por el paciente",
                    },
                },
                "required": ["symptoms"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_copago",
            "description": "Calcula el copago estimado segun el plan de seguro y tipo de servicio medico",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "integer",
                        "description": "ID del plan de seguro del paciente",
                    },
                    "service_type": {
                        "type": "string",
                        "enum": ["consulta", "emergencia", "hospitalizacion"],
                        "description": "Tipo de servicio medico",
                    },
                    "specialty": {
                        "type": "string",
                        "description": "Especialidad medica",
                    },
                },
                "required": ["plan_id", "service_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_hospital",
            "description": "Busca hospitales de la red del seguro con menor copago para la especialidad requerida",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "integer",
                        "description": "ID del plan de seguro",
                    },
                    "specialty": {
                        "type": "string",
                        "description": "Especialidad medica requerida",
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["baja", "media", "alta"],
                        "description": "Nivel de urgencia",
                    },
                    "user_lat": {
                        "type": "number",
                        "description": "Latitud del paciente (opcional)",
                    },
                    "user_lon": {
                        "type": "number",
                        "description": "Longitud del paciente (opcional)",
                    },
                },
                "required": ["plan_id", "specialty"],
            },
        },
    },
]