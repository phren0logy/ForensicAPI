import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.datastructures import UploadFile as FastAPIUploadFile
import json

router = APIRouter()

logger = logging.getLogger(__name__)

@router.post("/compose-prompt", response_class=PlainTextResponse)
async def compose_prompt(request: Request):
    logger.info("/compose-prompt endpoint called")
    """
    Accepts a multipart/form-data request with:
    - A 'mapping' JSON field: {"tag1": "string or filename", ...}
    - Optional files: each with their field name matching a tag or filename in the mapping.
    For each tag, if a file is uploaded for the value, use its contents; otherwise, use the string directly.
    """
    form = await request.form()
    mapping_json = form.get("mapping")
    if mapping_json is None:
        logger.warning("No mapping field provided in form data")
        raise HTTPException(status_code=400, detail="Missing 'mapping' field in form data.")
    try:
        mapping = json.loads(mapping_json)
    except Exception:
        raise HTTPException(status_code=400, detail="'mapping' field is not valid JSON.")
    composed_sections = []
    instructions_section = None
    for tag, value in mapping.items():
        file_obj = form.get(value)
        if isinstance(file_obj, FastAPIUploadFile):
            file_bytes = await file_obj.read()
            content = file_bytes.decode("utf-8", errors="replace")
        else:
            content = value
        wrapped = f"<{tag}>\n{content}\n</{tag}>"
        if tag.lower() == "instructions":
            instructions_section = wrapped
        else:
            composed_sections.append(wrapped)
    if instructions_section:
        combined = f"{instructions_section}\n\n" + "\n\n".join(composed_sections) + f"\n\n{instructions_section}"
    else:
        combined = "\n\n".join(composed_sections)
    logger.info("Prompt composition complete")
    return combined
