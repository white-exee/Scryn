from __future__ import annotations

import hashlib
import re
from typing import Any

import dns.resolver
import httpx
import phonenumbers
from fastapi import APIRouter, Query
from phonenumbers import carrier, geocoder, number_type, PhoneNumberType

router = APIRouter(prefix="/api", tags=["enrich"])

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

LINE_TYPES = {
    PhoneNumberType.MOBILE: "mobile",
    PhoneNumberType.FIXED_LINE: "fixed_line",
    PhoneNumberType.FIXED_LINE_OR_MOBILE: "fixed_or_mobile",
    PhoneNumberType.VOIP: "voip",
    PhoneNumberType.TOLL_FREE: "toll_free",
}


def mx_records(domain: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5)
        return sorted(str(r.exchange).rstrip(".") for r in answers)
    except Exception:
        return []


def _gravatar_hash(email: str) -> str:
    return hashlib.md5(email.strip().lower().encode()).hexdigest()


def has_gravatar(email: str) -> bool:
    try:
        resp = httpx.get(f"https://www.gravatar.com/avatar/{_gravatar_hash(email)}?d=404", timeout=6.0)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


def gravatar_profile(email: str) -> dict[str, Any] | None:
    try:
        resp = httpx.get(f"https://gravatar.com/{_gravatar_hash(email)}.json",
                         headers={"User-Agent": "scryn-osint/0.1"}, timeout=6.0)
        if resp.status_code != 200:
            return None
        entry = (resp.json().get("entry") or [{}])[0]
    except Exception:
        return None
    accounts = [
        {"service": a.get("shortname") or a.get("name"), "url": a.get("url")}
        for a in entry.get("accounts", []) if a.get("url")
    ]
    name = entry.get("displayName")
    if not name and isinstance(entry.get("name"), dict):
        name = entry["name"].get("formatted")
    if not (name or accounts or entry.get("currentLocation")):
        return None
    return {"display_name": name, "location": entry.get("currentLocation"), "accounts": accounts}


def enrich_email(email: str) -> dict[str, Any]:
    email = email.strip()
    valid = bool(EMAIL_RE.match(email))
    domain = email.split("@", 1)[1] if "@" in email else None
    mx = mx_records(domain) if (valid and domain) else []
    profile = gravatar_profile(email) if valid else None
    return {
        "query": email,
        "type": "email",
        "valid_format": valid,
        "domain": domain,
        "mx_records": mx,
        "deliverable_domain": bool(mx),
        "gravatar": bool(profile) or (has_gravatar(email) if valid else False),
        "gravatar_profile": profile,
    }


def enrich_phone(raw: str) -> dict[str, Any]:
    out: dict[str, Any] = {"query": raw, "type": "phone", "valid": False}
    try:
        parsed = phonenumbers.parse(raw, None)
    except phonenumbers.NumberParseException as exc:
        out["error"] = str(exc)
        return out

    out["valid"] = phonenumbers.is_valid_number(parsed)
    out["possible"] = phonenumbers.is_possible_number(parsed)
    out["e164"] = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    out["international"] = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    out["country_code"] = parsed.country_code
    out["region"] = geocoder.description_for_number(parsed, "en") or None
    out["carrier"] = carrier.name_for_number(parsed, "en") or None
    out["line_type"] = LINE_TYPES.get(number_type(parsed), "unknown")
    return out


@router.get("/email")
async def email_endpoint(value: str = Query(...)):
    return enrich_email(value)


@router.get("/phone")
async def phone_endpoint(value: str = Query(...)):
    return enrich_phone(value)
