from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from app.core.correlate import run_scan

ACCENTS = {
    "green": "\033[92m", "amber": "\033[93m", "red": "\033[91m", "cyan": "\033[96m",
    "magenta": "\033[95m", "blue": "\033[94m", "white": "\033[97m", "mono": "\033[97m",
}

G = "\033[92m"
D = "\033[90m"
H = "\033[97m"
R = "\033[91m"
B = "\033[1m"
X = "\033[0m"


def set_theme(name: str) -> None:
    global G, D, H, R, B, X
    if name == "none":
        G = D = H = R = B = X = ""
        return
    G = ACCENTS.get(name, ACCENTS["green"])
    if name == "mono":
        D = "\033[90m"


BANNER = r"""
 ___  ___ _ __ _   _ _ __
/ __|/ __| '__| | | | '_ \
\__ \ (__| |  | |_| | | | |
|___/\___|_|   \__, |_| |_|
               |___/"""


def enable_colors() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            k.SetConsoleMode(k.GetStdHandle(-11), 7)
        except Exception:
            pass


def flag(b) -> str:
    return f"{G}yes{X}" if b else f"{D}no{X}"


def bar(score: int) -> str:
    n = round(score / 5)
    return G + "█" * n + X + D + "█" * (20 - n) + X


def print_map(data: dict) -> None:
    m = data["modules"]
    rows = []
    if "username" in m:
        rows.append(("username", f"{m['username']['found_count']} profiles"))
    if "email" in m:
        e = m["email"]
        rows.append(("email", f"{e['query']}  mx={'yes' if e['deliverable_domain'] else 'no'}"))
    if "phone" in m:
        p = m["phone"]
        rows.append(("phone", f"{p.get('e164') or p['query']}  {p.get('region') or ''}".strip()))
    if "domain" in m:
        d = m["domain"]
        extra = f"{len(d['dns'].get('NS', []))} ns"
        if d.get("subdomains"):
            extra += f", {len(d['subdomains'])} subdomains"
        rows.append(("domain", f"{d['query']}  {extra}"))

    print(f"{H}{data['target']}{X}")
    for i, (k, v) in enumerate(rows):
        branch = "└─ " if i == len(rows) - 1 else "├─ "
        print(f"{D}{branch}{X}{k} {D}{v}{X}")


def print_report(data: dict) -> None:
    print(f"{G}{BANNER}{X}")
    print(f"{B}scryn{X} {D}v0.1 — identity recon · public sources only{X}\n")

    if data.get("error"):
        print(f"{R}[!] {data['error']}{X}")
        return

    m = data["modules"]
    print(f"{D}[*] target: {X}{data['target']}\n")

    if "username" in m:
        u = m["username"]
        found = [r for r in u["results"] if r["status"] == "found"]
        print(f"{D}── username ── {X}{u['query']} {D}({u['found_count']}/{u['checked']}){X}")
        if found:
            for r in found:
                print(f"  {G}[+]{X} {r['platform']:<13}{D}{r['url']}{X}")
        else:
            print(f"  {D}[-] no profiles matched{X}")
        print()

    if "email" in m:
        e = m["email"]
        print(f"{D}── email ── {X}{e['query']}")
        print(f"  valid={flag(e['valid_format'])}  mx={flag(e['deliverable_domain'])}  gravatar={flag(e['gravatar'])}")
        if e["mx_records"]:
            print(f"  {D}mx:{X} " + ", ".join(e["mx_records"]))
        gp = e.get("gravatar_profile")
        if gp:
            loc = f"  {D}{gp['location']}{X}" if gp.get("location") else ""
            print(f"  {D}gravatar:{X} {H}{gp.get('display_name') or '?'}{X}{loc}")
            for a in gp["accounts"][:8]:
                print(f"    {G}↳{X} {(a['service'] or '?'):<12}{D}{a['url']}{X}")
        print()

    if "phone" in m:
        p = m["phone"]
        print(f"{D}── phone ── {X}{p['query']}")
        print(f"  valid={flag(p.get('valid'))}  region={H}{p.get('region') or '-'}{X}  "
              f"carrier={H}{p.get('carrier') or '-'}{X}  type={p.get('line_type') or '-'}")
        print()

    if "domain" in m:
        dm = m["domain"]
        print(f"{D}── domain ── {X}{dm['query']}")
        print(f"  {D}registrar{X} {dm['whois'].get('registrar') or '-'}")
        for t, v in dm["dns"].items():
            if not v:
                continue
            if t == "TXT" and len(v) > 3:
                print(f"  {D}txt  {X} {len(v)} records {D}(use --json for full){X}")
            else:
                print(f"  {D}{t.lower():<5}{X} " + ", ".join(v))
        es = dm.get("email_security", {})
        print(f"  {D}spf  {X} {flag(es.get('spf'))} {D}{es.get('spf_policy') or ''}{X}   "
              f"{D}dmarc{X} {flag(es.get('dmarc'))} {D}{es.get('dmarc_policy') or ''}{X}")
        subs = dm.get("subdomains", [])
        if subs:
            print(f"  {D}subs {X} {len(subs)} subdomains (crt.sh)")
            for s in subs[:8]:
                print(f"    {G}·{X} {s}")
            if len(subs) > 8:
                print(f"    {D}… +{len(subs) - 8} more (use --json){X}")
        print()

    print(f"{D}── map ──{X}")
    print_map(data)
    print()

    print(f"{H}confidence {data['score']}/100{X}  " + bar(data["score"]))
    bd = data["score_breakdown"]
    if bd:
        print(f"{D}" + "  ".join(f"{k} +{v}" for k, v in bd.items()) + X)
    print()


def build_markdown(data: dict) -> str:
    if data.get("error"):
        return f"# Scryn report\n\n> {data['error']}\n"
    m = data["modules"]
    out = [f"# Scryn report: `{data['target']}`", "", f"**Confidence:** {data['score']}/100  "]
    out.append("`" + "  ".join(f"{k} +{v}" for k, v in data["score_breakdown"].items()) + "`\n")
    if "username" in m:
        u = m["username"]
        out.append(f"## Username — {u['query']} ({u['found_count']}/{u['checked']})\n")
        for r in u["results"]:
            if r["status"] == "found":
                out.append(f"- [{r['platform']}]({r['url']})")
        out.append("")
    if "email" in m:
        e = m["email"]
        out.append(f"## Email — {e['query']}\n")
        out.append(f"- valid: {e['valid_format']} | mx: {e['deliverable_domain']} | gravatar: {e['gravatar']}")
        gp = e.get("gravatar_profile")
        if gp:
            out.append(f"- gravatar: **{gp.get('display_name') or '?'}**")
            for a in gp["accounts"]:
                out.append(f"  - {a['service']}: {a['url']}")
        out.append("")
    if "phone" in m:
        p = m["phone"]
        out.append(f"## Phone — {p['query']}\n")
        out.append(f"- valid: {p.get('valid')} | region: {p.get('region')} | carrier: {p.get('carrier')} | type: {p.get('line_type')}\n")
    if "domain" in m:
        dm = m["domain"]
        es = dm.get("email_security", {})
        out.append(f"## Domain — {dm['query']}\n")
        out.append(f"- registrar: {dm['whois'].get('registrar')}")
        out.append(f"- spf: {es.get('spf')} ({es.get('spf_policy')}) | dmarc: {es.get('dmarc')} ({es.get('dmarc_policy')})")
        subs = dm.get("subdomains", [])
        if subs:
            out.append(f"- subdomains ({len(subs)}):")
            out.extend(f"  - {s}" for s in subs)
        out.append("")
    return "\n".join(out)


def report_to_text(data: dict) -> str:
    import contextlib
    import io
    set_theme("none")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print_report(data)
    return buf.getvalue()


def write_output(data: dict, path: str) -> None:
    ext = path.rsplit(".", 1)[-1].lower()
    if ext == "json":
        content = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    elif ext in ("md", "markdown"):
        content = build_markdown(data)
    else:
        content = report_to_text(data)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"[+] report written: {path}")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    common.add_argument("--no-color", action="store_true")
    common.add_argument("--color", default="green", choices=list(ACCENTS) + ["none"])
    common.add_argument("--output", "-o", metavar="FILE", help="save report (.json/.md/.txt)")

    epilog = (
        "examples:\n"
        "  scryn --username torvalds\n"
        "  scryn --username torvalds --domain example.com\n"
        "  scryn username torvalds\n"
        "  scryn email jane@example.com\n"
        "  scryn --username torvalds --color amber -o report.md\n"
        "\noptions (any command): --json  --output FILE  --color NAME  --no-color"
    )
    parser = argparse.ArgumentParser(
        prog="scryn",
        description="Scryn - public-source identity intelligence.",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
    )
    for target in ("username", "email", "phone", "domain"):
        parser.add_argument(f"--{target}")

    sub = parser.add_subparsers(dest="cmd", metavar="COMMAND")
    helps = {
        "username": "find a username across the calibrated platforms",
        "email": "enrich an email (format, MX, Gravatar + linked accounts)",
        "phone": "enrich a phone number (region, carrier, type)",
        "domain": "domain recon (WHOIS, DNS, subdomains, SPF/DMARC)",
    }
    for name in ("username", "email", "phone", "domain"):
        p = sub.add_parser(name, parents=[common], help=helps[name])
        p.add_argument("value")

    scan = sub.add_parser("scan", parents=[common], help="combine several identifiers")
    for target in ("username", "email", "phone", "domain"):
        scan.add_argument(f"--{target}")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.cmd in ("username", "email", "phone", "domain"):
        kwargs = {args.cmd: args.value}
    else:
        kwargs = {k: getattr(args, k, None) for k in ("username", "email", "phone", "domain")}

    if not any(kwargs.values()):
        parser.print_help()
        return

    data = asyncio.run(run_scan(**kwargs))

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        enable_colors()
        set_theme("none" if args.no_color else args.color)
        print_report(data)

    if args.output:
        write_output(data, args.output)


if __name__ == "__main__":
    main()
