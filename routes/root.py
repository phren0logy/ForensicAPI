from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def read_root():
    return {
        "message": (
            "FastAPI reusable prototyping app. Available endpoints: "
            "\n- GET / : This message."
            "\n- POST /pdf-to-markdown : Converts an uploaded PDF to Markdown using Azure Document Intelligence. "
            "Send a multipart/form-data request with a single file field named 'file' (PDF file). Returns extracted Markdown as plain text."
            "\n- POST /compose-prompt : Composes a prompt from a mapping and optional uploaded files. "
            "Send a multipart/form-data request with a 'mapping' JSON field and optional files. Returns a composed prompt with each section wrapped in XML tags."
        )
    }
