from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A modular SaaS billing backend.",
)


@app.get("/", tags=["Health"])
def root():
    return {
        "application": settings.app_name,
        "status": "running",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy"}
