from __future__ import annotations

from typing import Any

import dns.resolver
import httpx
import whois
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["domain"])

RECORD_TYPES = ("A", "AAAA", "MX", "NS", "TXT", "CNAME")
UA = {"User-Agent": "scryn-osint/0.1"}


def dns_records(domain: str) -> dict[str, list[str]]:
    records: dict[str, list[str]] = {}
    for rtype in RECORD_TYPES:
        try:
            answers = dns.resolver.resolve(domain, rtype, lifetime=5)
            records[rtype] = sorted(str(r).strip('"').rstrip(".") for r in answers)
        except Exception:
            records[rtype] = []
    return records


def whois_info(domain: str) -> dict[str, Any]:
    try:
        w = whois.whois(domain)
    except Exception as exc:
        return {"error": str(exc)}

    def first(value):
        return value[0] if isinstance(value, list) and value else value

    def iso(value):
        value = first(value)
        return value.isoformat() if hasattr(value, "isoformat") else value

    return {
        "registrar": w.registrar,
        "creation_date": iso(w.creation_date),
        "expiration_date": iso(w.expiration_date),
        "updated_date": iso(w.updated_date),
        "name_servers": sorted({str(n).lower() for n in (w.name_servers or [])}),
        "emails": sorted({str(e).lower() for e in (w.emails or [])}) if w.emails else [],
        "country": w.country,
    }


def subdomains(domain: str, limit: int = 150) -> list[str]:
    try:
        resp = httpx.get(f"https://crt.sh/?q=%25.{domain}&output=json", headers=UA, timeout=20.0)
        if resp.status_code != 200:
            return []
        rows = resp.json()
    except Exception:
        return []
    out = set()
    for row in rows:
        for name in str(row.get("name_value", "")).splitlines():
            name = name.strip().lstrip("*.").lower()
            if name.endswith("." + domain) and name != domain:
                out.add(name)
    return sorted(out)[:limit]


def _spf_all(record: str) -> str | None:
    for token in record.split():
        if token.lower().endswith("all"):
            return token
    return None


def _dmarc_policy(record: str) -> str | None:
    for token in record.replace(";", " ").split():
        if token.lower().startswith("p="):
            return token.split("=", 1)[1]
    return None


def email_security(domain: str, txt_records: list[str]) -> dict[str, Any]:
    spf = next((t for t in txt_records if t.lower().startswith("v=spf1")), None)
    dmarc = None
    try:
        for r in dns.resolver.resolve("_dmarc." + domain, "TXT", lifetime=5):
            value = str(r).strip('"')
            if value.lower().startswith("v=dmarc1"):
                dmarc = value
                break
    except Exception:
        pass
    return {
        "spf": bool(spf),
        "spf_policy": _spf_all(spf) if spf else None,
        "dmarc": bool(dmarc),
        "dmarc_policy": _dmarc_policy(dmarc) if dmarc else None,
    }


def lookup_domain(domain: str) -> dict[str, Any]:
    domain = domain.strip().lower().replace("https://", "").replace("http://", "").strip("/")
    dns = dns_records(domain)
    return {
        "query": domain,
        "type": "domain",
        "whois": whois_info(domain),
        "dns": dns,
        "subdomains": subdomains(domain),
        "email_security": email_security(domain, dns.get("TXT", [])),
    }


@router.get("/domain/{domain}")
async def domain_endpoint(domain: str) -> dict[str, Any]:
    return lookup_domain(domain)
