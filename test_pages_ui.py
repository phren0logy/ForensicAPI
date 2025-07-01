"""
Test pages UI router for HTML test interfaces.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pathlib import Path

router = APIRouter(tags=["test-ui"])

# Read HTML templates
templates_dir = Path(__file__).parent / "templates"


@router.get("/pdf-test", response_class=HTMLResponse)
async def pdf_test_page():
    """Serve the PDF test page."""
    html_path = templates_dir / "pdf_test.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text())
    else:
        return HTMLResponse(content="<h1>PDF Test Page Not Found</h1>")


@router.get("/prompt-test", response_class=HTMLResponse)
async def prompt_test_page():
    """Serve the prompt test page."""
    html_path = templates_dir / "prompt_test.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text())
    else:
        return HTMLResponse(content="<h1>Prompt Test Page Not Found</h1>")