from fastapi import FastAPI

app = FastAPI(title="Uganda National Grid API", version="1.0.0")

@app.get("/")
def root():
    return {
        "service": "Uganda National Grid API",
        "status": "online",
        "phase": 2
    }

@app.get("/health")
def health():
    return {"status": "healthy"}
