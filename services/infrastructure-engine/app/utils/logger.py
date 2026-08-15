import logging
import json
from app.config import settings

class StructuredSecretMasker(logging.Formatter):
    def format(self, record):
        message = record.getMessage()
        if settings.github_token and settings.github_token in message:
            message = message.replace(settings.github_token, "***MASKED_TOKEN***")
        
        log_obj = {
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }
        
        if hasattr(record, "runId"):
            log_obj["runId"] = record.runId
            
        return json.dumps(log_obj)

def get_logger(name: str):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredSecretMasker())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
