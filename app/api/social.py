from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import APIRouter

from app.sources.platforms import PLATFORMS

router = APIRouter(prefix="/api", tags=["social"])

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
TIMEOUT = httpx.Timeout(8.0)
CONCURRENCY = 15


async def check_platform(client: httpx.AsyncClient, platform: dict,
                         username: str, sem: asyncio.Semaphore) -> dict[str, Any]:
    url = platform["url"].format(username)
    result = {"platform": platform["name"], "url": url, "status": "unknown"}

    async with sem:
        try:
            resp = await client.get(url, headers=HEADERS, follow_redirects=True)
        except (httpx.HTTPError, asyncio.TimeoutError):
            result["status"] = "error"
            return result

    method = platform["method"]
    if method == "status":
        if resp.status_code == 200:
            result["status"] = "found"
        elif resp.status_code == 404:
            result["status"] = "not_found"
    elif resp.status_code == 200:
        if method == "username_in_body":
            result["status"] = "found" if username.lower() in resp.text.lower() else "not_found"
        else:
            result["status"] = "not_found" if platform.get("absent_text", "") in resp.text else "found"

    return result


async def search_username(username: str) -> dict[str, Any]:
    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        results = await asyncio.gather(
            *(check_platform(client, p, username, sem) for p in PLATFORMS)
        )

    results.sort(key=lambda r: (r["status"] != "found", r["platform"].lower()))
    found = [r for r in results if r["status"] == "found"]
    return {
        "query": username,
        "type": "username",
        "checked": len(results),
        "found_count": len(found),
        "results": results,
    }


@router.get("/username/{username}")
async def username_endpoint(username: str) -> dict[str, Any]:
    return await search_username(username)
