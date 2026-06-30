#!/usr/bin/env python3
"""Reachability checker — the seed of automated monitoring.

For each catalog entry, probes source.canonical_url and reports whether the
declared `status` still matches reality. Read-only.

User-Agent is built from almanac.config.yml (slug + homepage) so agencies can see
who is checking. Three refinements keep the monitor from crying wolf at bot defenses:

  1. Browser-UA retry. A block code (401/403/406/429) triggers one retry with a
     common browser User-Agent — some hosts only sniff the UA.
  2. Headless fallback (opt-in). Many federal hosts (BLS, Census, Congress.gov,
     SEC, GAO) sit behind CDN bot protection (JS challenge + TLS fingerprinting)
     that no curl can satisfy — a 403 there is not a 404. When `--headless` is on
     (or `reachability.headless: true` in almanac.config.yml) a real headless
     Chromium is tried for blocked URLs; if it loads the page, the source is
     verified `ok via headless`. This needs Playwright (see requirements-headless.txt);
     if it is not installed the checker degrades gracefully to rung 3.
  3. Blocked != dead. If every rung still hits a block code, the source is
     reported as *blocked / unverifiable* — NOT flagged as an outage. The headless
     rung only ever *upgrades* a blocked source to ok; it never newly flags one as
     dead. Only genuine failures (404, 5xx, connection/timeout) flag an entry.

Uses curl for reliable wall-clock timeouts.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog"
CONFIG = ROOT / "almanac.config.yml"
DEFAULT_TIMEOUT = 12
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
BLOCK_CODES = {401, 403, 406, 429}


def _config() -> dict:
    if CONFIG.exists():
        return yaml.safe_load(CONFIG.read_text()) or {}
    return {}


def _user_agent() -> str:
    cfg = _config()
    slug = cfg.get("slug") or "almanac"
    homepage = cfg.get("homepage") or ""
    contact = f" (+{homepage})" if homepage else ""
    return f"{slug}-link-checker/0.1{contact}"


def _headless_default() -> bool:
    """Whether the headless fallback is enabled by config (CI reads the same flag)."""
    reach = _config().get("reachability") or {}
    return bool(reach.get("headless", False))


UA = _user_agent()


def _curl(url: str, timeout: float, ua: str) -> tuple[int | None, str]:
    cmd = ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}",
           "--max-time", str(int(timeout)), "-A", ua, "-L", url]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5, check=False)
    except subprocess.TimeoutExpired:
        return None, f"timeout>{timeout + 5}s"
    if proc.returncode != 0 and not proc.stdout.strip().isdigit():
        err = (proc.stderr or proc.stdout or "curl failed").strip().splitlines()[-1]
        return None, err[:120]
    raw = proc.stdout.strip()
    if not raw.isdigit():
        return None, raw or "no status code"
    return int(raw), ""


def _probe_headless(url: str, timeout: float) -> tuple[int | None, str]:
    """Load the URL in a real headless Chromium — beats JS/TLS bot challenges curl can't.

    Returns (status, note). status is None when the headless rung could not run
    (Playwright missing) or could not reach the page; callers must treat a None or
    non-2xx/3xx result as *still blocked*, never as a dead-link flag.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, "playwright not installed (see requirements-headless.txt)"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=BROWSER_UA)
                resp = page.goto(url, wait_until="domcontentloaded",
                                 timeout=int(timeout * 1000))
                return (resp.status if resp else None), ""
            finally:
                browser.close()
    except Exception as exc:  # navigation timeout, challenge wall, launch failure
        return None, f"headless {type(exc).__name__}"


def _probe(url: str, timeout: float, headless: bool = False) -> tuple[int | None, str]:
    """Probe with the almanac UA; retry as a browser, then (opt-in) as headless Chromium."""
    if not shutil.which("curl"):
        raise SystemExit("check_links.py requires curl on PATH")
    code, note = _curl(url, timeout, UA)
    if code in BLOCK_CODES:
        bcode, bnote = _curl(url, timeout, BROWSER_UA)
        if bcode is not None and bcode < 400:
            return bcode, f"ok via browser-UA (almanac-UA got {code})"
        c = bcode if bcode is not None else code
        if c in BLOCK_CODES:
            # curl can't beat CDN bot protection; try a real headless browser.
            if headless:
                hcode, hnote = _probe_headless(url, timeout)
                if hcode is not None and hcode < 400:
                    return hcode, f"ok via headless (curl got {c})"
                detail = f"; {hnote}" if hnote else ""
                return c, f"blocked by bot protection ({c}) — headless unverified{detail}"
            return c, f"blocked by bot protection ({c}) — cannot auto-verify"
        return c, bnote or f"http {c}"
    return code, note


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SEC",
                    help=f"per-request timeout in seconds (default: {DEFAULT_TIMEOUT})")
    ap.add_argument("--headless", action=argparse.BooleanOptionalAction,
                    default=_headless_default(),
                    help="verify CDN-bot-blocked sources with a headless browser "
                         "(needs Playwright; defaults to reachability.headless in config)")
    args = ap.parse_args()

    report = []
    problems = 0
    for path in sorted(CATALOG.glob("*.yaml")):
        entry = yaml.safe_load(path.read_text())
        url = entry.get("source", {}).get("canonical_url")
        declared = entry.get("status")
        code, note = _probe(url, args.timeout, headless=args.headless)
        blocked = code in BLOCK_CODES
        reachable = code is not None and code < 400
        # Dead = a definitive failure (404 / 5xx / connection / timeout).
        # A host that merely blocks our bot is unverifiable, not dead.
        dead = (not reachable) and (not blocked)
        flagged = declared in ("live", "frozen") and dead
        if flagged:
            problems += 1
        report.append({"id": entry.get("id"), "url": url, "declared_status": declared,
                       "http": code, "reachable": reachable, "blocked": blocked,
                       "flagged": flagged, "note": note})

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for r in report:
            mark = "FLAG" if r["flagged"] else ("blok" if r["blocked"] else ("ok  " if r["reachable"] else "warn"))
            print(f"[{mark}] {r['id']:34} status={r['declared_status']:8} http={r['http']}  {r['note']}")
        print(f"\n{problems} entr{'y' if problems == 1 else 'ies'} declared live/frozen but unreachable")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
