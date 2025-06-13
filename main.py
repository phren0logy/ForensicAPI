from fastapi import FastAPI

from routes.compose_prompt import router as compose_router
from routes.pdf_to_markdown import router as pdf_router
from routes.root import router as root_router
from test_pages_ui import router as test_pages_router

app = FastAPI()

app.include_router(root_router)
app.include_router(pdf_router)
app.include_router(compose_router)
app.include_router(test_pages_router)
