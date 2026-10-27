#!/usr/bin/env python3
"""Preflight a paid x402 endpoint from the buyer's side, in one command.

Every check here is one a buyer performs implicitly, in this order, and stops at the
first thing that fails. That ordering is the point: a seller who only tests in a browser
passes checks 4 and 5 while failing 1, and concludes the endpoint works.

  1. Does the paid path answer a *machine*? Same URL, the default Python User-Agent and
     a curl one. 13 of the 24 largest sellers in the PayAI Bazaar return 403 to the
     former and 200 to the latter, so a Python buyer never sees a price.
  2. Is there a 402 challenge at all, and where is it? The Coinbase x402 README puts the
     `PaymentRequired` object in the `PAYMENT-REQUIRED` header; some servers put it in
     the body instead; a buyer must read both.
  3. Is the challenge payable? `accepts[]` needs a scheme, a CAIP-2 network with a
     reference, an integer amount, the token contract, the recipient, and for `exact`
     on EVM the EIP-712 domain name and version. A missing `extra.name` makes the
     payment unsignable, which looks like the server is broken when it is the buyer.
  4. Where the response headers matter: HSTS, CSP, ACAO, X-Content-Type-Options.
  5. The zone's email authentication, because a paid service sends receipts.

It never spends anything, never sends a payment, and never requests more than one path
on the target. `--json` gives the same result machine-readably.

Usage:
  python3 zero/x402server/preflight.py https://example.com/v1/thing
  python3 zero/x402server/preflight.py https://example.com/v1/thing --json
  python3 zero/x402server/preflight.py https://example.com/v1/thing --post '{"a":1}'
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse

sys.path.insert(0, __file__.rsplit("/", 1)[0])
try:
    import dnsaudit  # noqa: E402
except ImportError:
    # The single-file copy published for download sits next to nothing. The endpoint
    # checks are the point and they do not need it; the zone checks are skipped and the
    # report says so rather than pretending they passed.
    dnsaudit = None

BUYER_UA = "cian-preflight/1.0 (+https://cian-spider.github.io/work.html)"
LIB_UA = "Python-urllib/3.12"  # deliberately the default a lot of agent code sends

OK, WARN, FAIL = "ok", "warn", "fail"

# Suffixes where the zone belongs to the platform, not to the seller. Reporting
# "this domain cannot receive email" about netlify.app is exactly the false positive
# this repo already shipped once: a shared suffix is not the customer's zone.
SHARED_SUFFIXES = (".netlify.app", ".workers.dev", ".vercel.app", ".pages.dev",
                   ".github.io", ".fly.dev", ".onrender.com", ".herokuapp.com")


def _get(url: str, ua: str, method: str = "GET", body: bytes | None = None):
    req = urllib.request.Request(url, data=body, headers={"User-Agent": ua, "Accept": "*/*"}, method=method)
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, dict(r.headers), r.read(65536)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read(65536) or b""
    except Exception as e:
        return None, {}, str(e).encode()


def challenge(headers: dict, body: bytes):
    """Return (challenge dict, where it came from)."""
    h = {k.lower(): v for k, v in headers.items()}
    raw = h.get("payment-required") or h.get("x-payment")
    if raw:
        try:
            d = json.loads(base64.b64decode(raw))
            if d.get("accepts"):
                return d, "PAYMENT-REQUIRED header"
        except Exception:
            pass
    try:
        d = json.loads(body)
    except Exception:
        return None, "unparseable body and no readable header"
    if d.get("accepts"):
        return d, "response body"
    return (d, "body present but no accepts[]") if d else (None, "empty")


def payable(req: dict) -> list[tuple[str, str, str]]:
    """Check one `accepts` entry. Returns (level, id, detail) findings."""
    out = []
    scheme = req.get("scheme")
    net = str(req.get("network") or "")
    if scheme not in ("exact", "upto"):
        out.append((FAIL, "scheme", f"scheme is {scheme!r}; a buyer needs 'exact' or 'upto'"))
    if ":" not in net:
        out.append((WARN, "network_not_caip2",
                    f"network is {net!r}; CAIP-2 needs a namespace and reference, e.g. eip155:8453"))
    amount = req.get("amount")
    try:
        n = int(amount)
        if n <= 0:
            out.append((FAIL, "amount", f"amount is {amount!r}, which is not positive"))
    except Exception:
        out.append((FAIL, "amount", f"amount is {amount!r}, not an integer in atomic units"))
    if not str(req.get("asset") or "").strip():
        out.append((FAIL, "asset", "no asset (the token contract) is named"))
    if not str(req.get("payTo") or "").strip():
        out.append((FAIL, "payTo", "no payTo, so there is nowhere to send the payment"))
    extra = req.get("extra") or {}
    if str(scheme) == "exact" and net.startswith("eip155"):
        # EIP-3009 signing needs the token's EIP-712 domain, which the server must supply.
        if not extra.get("name") or not extra.get("version"):
            out.append((FAIL, "eip712_domain",
                        "extra.name and extra.version are missing, so an exact EVM payment cannot be signed"))
    if not str(req.get("resource") or "").strip():
        out.append((WARN, "resource", "no resource field; a buyer cannot bind the payment to a URL"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--post", metavar="BODY", help="send this JSON body as POST instead of GET")
    ap.add_argument("--no-dns", action="store_true")
    args = ap.parse_args()

    url = args.url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        print("pass a full http(s) URL", file=sys.stderr)
        return 2
    method = "POST" if args.post else "GET"
    body = args.post.encode() if args.post else None

    findings: list[tuple[str, str, str]] = []
    report: dict = {"url": url, "method": method, "checks": {}}

    # 1. machine reachability
    s_lib, _, b_lib = _get(url, LIB_UA, method, body)
    s_buyer, headers, resp = _get(url, BUYER_UA, method, body)
    report["checks"]["status"] = {"library_ua": s_lib, "buyer_ua": s_buyer}
    if s_lib == 403 and s_buyer in (200, 402, 405, 400):
        findings.append((FAIL, "ua_filtered",
                         f"{LIB_UA} gets 403 while a normal client gets {s_buyer}; "
                         "a Python buyer never sees the price"))
    elif s_buyer is None:
        findings.append((FAIL, "unreachable", resp.decode(errors="replace")[:160]))
        if args.json:
            print(json.dumps({**report, "findings": [{"level": a, "id": b, "detail": c} for a, b, c in findings]}, indent=1))
        return 1
    elif s_buyer >= 500:
        findings.append((FAIL, "server_error", f"HTTP {s_buyer}; the paid path is not serving"))
    elif s_buyer == 200:
        findings.append((WARN, "no_challenge", "HTTP 200 without a 402: either it is free or the paywall is off"))
    elif s_buyer not in (402,):
        findings.append((WARN, "unexpected_status",
                         f"HTTP {s_buyer}; a paid path normally answers 402 before payment"))

    # 2 and 3. the challenge and whether it can be paid
    if s_buyer == 402:
        ch, where = challenge(headers, resp)
        report["checks"]["challenge"] = {"source": where, "accepts": len((ch or {}).get("accepts") or [])}
        if not ch or not ch.get("accepts"):
            findings.append((FAIL, "no_accepts", f"402 but no usable accepts[] ({where})"))
        else:
            if where != "PAYMENT-REQUIRED header":
                findings.append((WARN, "challenge_not_in_header",
                                 f"challenge came from the {where}; the x402 README specifies the header, "
                                 "and a body-only challenge is invisible to a spec-following buyer"))
            for i, req in enumerate(ch.get("accepts") or []):
                for lvl, fid, det in payable(req):
                    findings.append((lvl, f"{fid}[{i}]", det))

    # 4. response headers worth an operator's attention
    h = {k.lower(): v for k, v in headers.items()}
    for hid, present, detail in (
        ("missing_strict_transport_security", "strict-transport-security", "no HSTS on the paid path"),
        ("missing_content_security_policy", "content-security-policy", "no CSP"),
        ("missing_x_content_type_options", "x-content-type-options", "no X-Content-Type-Options"),
    ):
        if present not in h:
            findings.append((WARN, hid, detail))
    if h.get("access-control-allow-origin") == "*":
        findings.append((WARN, "cors_wildcard", "any origin can call this paid endpoint from a browser"))

    # 5. the zone's email authentication, because a paid service sends receipts
    if args.no_dns or dnsaudit is None:
        findings.append((OK, "dns_skipped", "zone checks need dnsaudit.py beside this file; download it too if you want them"))
    else:
        host = parsed.netloc.split(":")[0].lower()
        if host.endswith(SHARED_SUFFIXES) or any(host == s.lstrip(".") for s in SHARED_SUFFIXES):
            # The zone holds thousands of unrelated customers. Its MX and DMARC say
            # nothing about this seller, so saying anything would be noise dressed up
            # as a finding.
            findings.append((OK, "dns_skipped_shared_platform",
                             f"{host} is on a shared platform suffix; its zone records are not yours"))
        else:
            try:
                d = dnsaudit.audit(host)
                report["checks"]["zone"] = d.get("zone")
                for f in d.get("findings") or []:
                    # Never a hard failure: a DNS record can be a deliberate choice, and
                    # it is the seller's call, not a precondition for taking a payment.
                    if f.get("severity") in ("critical", "high"):
                        findings.append((WARN, "dns:" + f["id"], f.get("detail", "")))
            except Exception as e:
                findings.append((WARN, "dns_skipped", str(e)[:120]))

    report["findings"] = [{"level": a, "id": b, "detail": c} for a, b, c in findings]
    report["verdict"] = ("fails" if any(a == FAIL for a, _, _ in findings)
                         else "warns" if any(a == WARN for a, _, _ in findings) else "clean")

    if args.json:
        print(json.dumps(report, indent=1))
    else:
        print(f"preflight {url}")
        for a, b, c in sorted(findings, key=lambda f: {"fail": 0, "warn": 1, "ok": 2}[f[0]]):
            print(f"  [{a:4s}] {b:34s} {c}")
        print(f"\nverdict: {report['verdict']}")
        if not findings:
            print("  nothing found by these checks. That is not a guarantee, it is the absence of these specific defects.")
    return 0 if report["verdict"] != "fails" else 1


if __name__ == "__main__":
    sys.exit(main())