from fastapi import FastAPI

app = FastAPI(title="documentation-engine")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "documentation-engine"}
