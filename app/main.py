from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from app.api import domain, enrich, social
from app.core.correlate import run_scan
from app.web import router as web_router

app = FastAPI(
    title="Scryn",
    version="0.1.0",
    description="Identity Intelligence & OSINT Analyzer — public sources only.",
)

app.include_router(social.router)
app.include_router(enrich.router)
app.include_router(domain.router)
app.include_router(web_router)


class ScanRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    domain: Optional[str] = None


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "scryn", "version": "0.1.0"}


@app.post("/api/scan")
async def scan(req: ScanRequest):
    return await run_scan(req.username, req.email, req.phone, req.domain)
