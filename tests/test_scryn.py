import asyncio

import pytest

from app.api.domain import _dmarc_policy, _spf_all
from app.api.enrich import EMAIL_RE, enrich_phone
from app.api.social import search_username
from app.core.correlate import build_graph, compute_score
from app.sources.platforms import PLATFORMS


def test_platforms_wellformed():
    assert len(PLATFORMS) >= 20
    names = set()
    for p in PLATFORMS:
        assert "{}" in p["url"]
        assert p["method"] in ("status", "message", "username_in_body")
        if p["method"] == "message":
            assert p.get("absent_text")
        names.add(p["name"])
    assert len(names) == len(PLATFORMS)


@pytest.mark.parametrize("email,ok", [
    ("a@b.com", True),
    ("john.doe+tag@sub.example.org", True),
    ("bad", False),
    ("a@b", False),
    ("@b.com", False),
    ("a b@c.com", False),
])
def test_email_regex(email, ok):
    assert bool(EMAIL_RE.match(email)) is ok


def test_phone_valid():
    r = enrich_phone("+33612345678")
    assert r["valid"] is True
    assert r["country_code"] == 33
    assert r["line_type"] == "mobile"


def test_phone_invalid():
    assert enrich_phone("12").get("valid") is False


@pytest.mark.parametrize("record,expected", [
    ("v=spf1 include:x -all", "-all"),
    ("v=spf1 ~all", "~all"),
    ("v=spf1 include:y", None),
])
def test_spf_all(record, expected):
    assert _spf_all(record) == expected


@pytest.mark.parametrize("record,expected", [
    ("v=DMARC1; p=reject; rua=mailto:x", "reject"),
    ("v=DMARC1; p=none", "none"),
    ("v=DMARC1;", None),
])
def test_dmarc_policy(record, expected):
    assert _dmarc_policy(record) == expected


def test_scoring_username_capped():
    mods = {"username": {"found_count": 10, "checked": 23, "query": "x", "results": []}}
    score, bd = compute_score(mods)
    assert bd["username_presence"] == 40
    assert score == 40


def test_scoring_full_capped_at_100():
    mods = {
        "username": {"found_count": 20, "checked": 23, "query": "x", "results": []},
        "email": {"valid_format": True, "deliverable_domain": True, "gravatar": True},
        "phone": {"valid": True},
        "domain": {"whois": {"registrar": "R"}, "dns": {"A": ["1.2.3.4"]}, "subdomains": ["a.x"]},
    }
    score, bd = compute_score(mods)
    assert bd["email"] == 25
    assert bd["phone"] == 15
    assert bd["domain"] == 20
    assert score == 100


def test_build_graph_only_found_profiles():
    mods = {"username": {"query": "x", "results": [
        {"platform": "GitHub", "url": "u1", "status": "found"},
        {"platform": "GitLab", "url": "u2", "status": "not_found"},
    ]}}
    g = build_graph("x", mods)
    groups = {n["group"] for n in g["nodes"]}
    labels = {n["label"] for n in g["nodes"]}
    assert "target" in groups and "profile" in groups
    assert "GitHub" in labels
    assert "GitLab" not in labels


@pytest.mark.network
def test_no_false_positives_live():
    result = asyncio.run(search_username("zzqx-nope-9f3k1x-notarealuser-7788"))
    assert result["found_count"] == 0
