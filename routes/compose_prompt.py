import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.datastructures import UploadFile as FastAPIUploadFile # Used for type hinting and FastAPI specifics
from starlette.datastructures import UploadFile as StarletteUploadFile # Used for isinstance with request.form()
import json

router = APIRouter()

logger = logging.getLogger(__name__)

# NOTE: When processing `await request.form()` directly, items that are file uploads
# appear as `starlette.datastructures.UploadFile` instances. 
# While `fastapi.datastructures.UploadFile` is an alias for the Starlette one,
# `isinstance` checks against `fastapi.datastructures.UploadFile` can fail
# in certain contexts (e.g., during testing with TestClient).
# Therefore, for reliable type checking of items from `request.form()`, 
# we use `isinstance` with `starlette.datastructures.UploadFile`.

@router.post("/compose-prompt", response_class=PlainTextResponse)
async def compose_prompt(request: Request):
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
    actual_uploaded_files = {
        key: form_item
        for key, form_item in form.items()
        if isinstance(form_item, StarletteUploadFile)  # Check against Starlette's UploadFile
    }

    composed_sections = []
    instructions_section = None
    for tag, name_or_literal_content in mapping.items():
        content_to_use = None
        if name_or_literal_content in actual_uploaded_files:
            uploaded_file_object = actual_uploaded_files[name_or_literal_content]
            file_bytes = await uploaded_file_object.read()
            content_to_use = file_bytes.decode("utf-8", errors="replace")
        else:
            content_to_use = name_or_literal_content
        
        wrapped = f"<{tag}>\n{content_to_use}\n</{tag}>"
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
