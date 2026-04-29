# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, user, association
from app.routers import templates, managers, audit

app = FastAPI(title="C&S Tool Hub")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(user.router, prefix="/api")
app.include_router(association.router, prefix="/api")
app.include_router(templates.router, prefix="/api")
app.include_router(managers.router, prefix="/api")
app.include_router(audit.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
