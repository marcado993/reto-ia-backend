import logging
from datetime import datetime

logger = logging.getLogger("medical_chatbot.audit")


def log_audit(session_id: str, action: str, details: dict):
    logger.info(
        "AUDIT",
        extra={
            "session_id": str(session_id),
            "action": action,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )