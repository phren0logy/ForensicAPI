from fastapi import FastAPI
from routes.root import router as root_router
from routes.pdf_to_markdown import router as pdf_router
from routes.compose_prompt import router as compose_router

app = FastAPI()


