from fastapi import FastAPI

app = FastAPI(title="developer-enginer")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "developer-enginer"}
