from fastapi import FastAPI

app = FastAPI(title="infrastructure-engine")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "infrastructure-engine"}
