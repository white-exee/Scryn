from __future__ import annotations

from typing import Any, Optional

import networkx as nx

from app.api.domain import lookup_domain
from app.api.enrich import enrich_email, enrich_phone
from app.api.social import search_username


def compute_score(modules: dict[str, Any]) -> tuple[int, dict[str, int]]:
    breakdown: dict[str, int] = {}

    if "username" in modules:
        breakdown["username_presence"] = min(modules["username"]["found_count"] * 6, 40)

    if "email" in modules:
        e = modules["email"]
        breakdown["email"] = (
            (5 if e["valid_format"] else 0)
            + (10 if e["deliverable_domain"] else 0)
            + (10 if e["gravatar"] else 0)
        )

    if "phone" in modules:
        breakdown["phone"] = 15 if modules["phone"].get("valid") else 0

    if "domain" in modules:
        d = modules["domain"]
        breakdown["domain"] = (
            (10 if not d["whois"].get("error") and d["whois"].get("registrar") else 0)
            + (5 if d["dns"].get("A") or d["dns"].get("NS") else 0)
            + (5 if d.get("subdomains") else 0)
        )

    return min(sum(breakdown.values()), 100), breakdown


def build_graph(target: str, modules: dict[str, Any]) -> dict[str, list]:
    g = nx.Graph()
    g.add_node(target, label=target, group="target")

    if "username" in modules:
        username = modules["username"]["query"]
        user_node = f"user:{username}"
        g.add_node(user_node, label=username, group="username")
        g.add_edge(target, user_node)
        for r in modules["username"]["results"]:
            if r["status"] == "found":
                node = f"profile:{r['platform']}"
                g.add_node(node, label=r["platform"], group="profile", url=r["url"])
                g.add_edge(user_node, node)

    if "email" in modules:
        e = modules["email"]
        email_node = f"email:{e['query']}"
        g.add_node(email_node, label=e["query"], group="email")
        g.add_edge(target, email_node)
        if e.get("domain"):
            g.add_node(f"domain:{e['domain']}", label=e["domain"], group="domain")
            g.add_edge(email_node, f"domain:{e['domain']}")
        if e.get("gravatar"):
            g.add_node("gravatar", label="Gravatar", group="profile")
            g.add_edge(email_node, "gravatar")

    if "phone" in modules:
        p = modules["phone"]
        label = p.get("e164", p["query"])
        phone_node = f"phone:{label}"
        g.add_node(phone_node, label=label, group="phone")
        g.add_edge(target, phone_node)
        if p.get("carrier"):
            g.add_node(f"carrier:{p['carrier']}", label=p["carrier"], group="meta")
            g.add_edge(phone_node, f"carrier:{p['carrier']}")

    if "domain" in modules:
        d = modules["domain"]
        domain_node = f"domain:{d['query']}"
        g.add_node(domain_node, label=d["query"], group="domain")
        g.add_edge(target, domain_node)
        for ns in d["dns"].get("NS", [])[:5]:
            g.add_node(f"ns:{ns}", label=ns, group="meta")
            g.add_edge(domain_node, f"ns:{ns}")

    nodes = [{"id": n, **g.nodes[n]} for n in g.nodes]
    edges = [{"from": a, "to": b} for a, b in g.edges]
    return {"nodes": nodes, "edges": edges}


async def run_scan(username: Optional[str] = None, email: Optional[str] = None,
                   phone: Optional[str] = None, domain: Optional[str] = None) -> dict[str, Any]:
    modules: dict[str, Any] = {}

    if username:
        modules["username"] = await search_username(username)
    if email:
        modules["email"] = enrich_email(email)
    if phone:
        modules["phone"] = enrich_phone(phone)
    if domain:
        modules["domain"] = lookup_domain(domain)

    if not modules:
        return {"error": "Provide at least one of: username, email, phone, domain."}

    target = username or email or phone or domain
    score, breakdown = compute_score(modules)
    return {
        "target": target,
        "modules": modules,
        "score": score,
        "score_breakdown": breakdown,
        "graph": build_graph(target, modules),
    }
