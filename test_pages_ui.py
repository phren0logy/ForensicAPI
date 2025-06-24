import httpx
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/pdf-test", response_class=HTMLResponse)
async def pdf_test_form(request: Request):
    return templates.TemplateResponse(
        "pdf_test.html", {"request": request, "result": None}
    )


@router.post("/pdf-test", response_class=HTMLResponse)
async def pdf_test_submit(request: Request, file: UploadFile = File(...)):
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            "http://127.0.0.1:8000/extract",
            files={"file": (file.filename, await file.read(), "application/pdf")},
        )
        result = resp.json()
    return templates.TemplateResponse(
        "pdf_test.html", {"request": request, "result": result}
    )


@router.get("/prompt-test", response_class=HTMLResponse)
async def prompt_test_form(request: Request):
    return templates.TemplateResponse(
        "prompt_test.html", {"request": request, "result": None}
    )


@router.post("/prompt-test", response_class=HTMLResponse)
async def prompt_test_submit(
    request: Request,
    document: str = Form(""),
    transcript: str = Form(""),
    manual: str = Form(""),
    instructions: str = Form(""),
):
    import json

    mapping = {
        "document": document,
        "transcript": transcript,
        "manual": manual,
        "instructions": instructions,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "http://127.0.0.1:8000/compose-prompt",
            data={"mapping": json.dumps(mapping)},
        )
        result = resp.text
    return templates.TemplateResponse(
        "prompt_test.html", {"request": request, "result": result}
    )
