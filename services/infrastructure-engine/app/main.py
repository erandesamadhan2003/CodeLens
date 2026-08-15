from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="infrastructure-engine")

app.include_router(router, prefix="/internal")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "infrastructure-engine"}
