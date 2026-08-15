from fastapi import FastAPI

app = FastAPI(title="security-engine")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "security-engine"}
