from fastapi import FastAPI

app = FastAPI(title="dependency-engine")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "dependency-engine"}
