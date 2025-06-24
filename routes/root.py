import logging
from datetime import datetime
from fastapi import APIRouter

router = APIRouter()

logger = logging.getLogger(__name__)

@router.get("/")
def read_root():
    logger.info("Root endpoint called")
    return {
        "message": (
            "FastAPI reusable prototyping app. Available endpoints: "
            "\n- GET / : This message."
            "\n- GET /health : Health check endpoint."
            "\n- POST /extract : PDF extraction endpoint with Azure Document Intelligence."
            "\n- POST /segment : Document segmentation endpoint."
            "\n- POST /segment-filtered : Combined filtering and segmentation endpoint."
            "\n- POST /anonymize-azure-di : PII anonymization for Azure DI output."
            "\n- POST /compose-prompt : Composes a prompt from a mapping and optional uploaded files. "
            "Send a multipart/form-data request with a 'mapping' JSON field and optional files. Returns a composed prompt with each section wrapped in XML tags."
        )
    }

@router.get("/health")
def health_check():
    logger.info("Health check endpoint called")
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }
