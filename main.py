from fastapi import FastAPI

from routes.compose_prompt import router as compose_router
from routes.extraction import router as extraction_router
from routes.root import router as root_router
from routes.segmentation import router as segmentation_router
from routes.anonymization import router as anonymization_router
from routes.filtering import router as filtering_router
from test_pages_ui import router as test_pages_router

app = FastAPI()

app.include_router(root_router)
app.include_router(compose_router)
app.include_router(extraction_router)
app.include_router(segmentation_router)
app.include_router(anonymization_router, prefix="/anonymization")
app.include_router(filtering_router)
app.include_router(test_pages_router)
