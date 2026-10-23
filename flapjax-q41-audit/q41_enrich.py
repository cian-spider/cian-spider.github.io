#!/usr/bin/env python3
"""Enrich the Q41 buy rows with the pool price before each swap.

WHY THIS IS A SEPARATE STEP
    The log scan is expensive and already done; the per-buy enrichment is 39
    extra calls, and the free archive endpoint this box uses drops DNS under
    rapid sequential queries. Splitting them means a DNS failure costs seconds
    instead of redoing the whole scan. Rows are written after every success, so
    an interrupt resumes rather than restarts.

WRITES
    zero/data/flapjax/q41_buys.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from q41_audit import (  # noqa: E402
    POOL, TREASURY, OUT_DIR, price_from_sqrt, program_day, rpc, utc,
)

BUYS_PATH = OUT_DIR / "q41_buys.json"
SWAPS_PATH = OUT_DIR / "q41_swaps.json"
SLOT0 = "0x3850c7bd"


def retry(fn, what: str, tries: int = 12):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:                      # noqa: BLE001
            last = e
            time.sleep(min(1.5 * (1.4 ** i), 20))
    raise RuntimeError(f"gave up on {what} after {tries}: {last}")


def main() -> int:
    swaps = json.loads(SWAPS_PATH.read_text())
    buys = sorted(
        [s for s in swaps if (s.get("recip") or "").lower() == TREASURY.lower()],
        key=lambda x: x["block"],
    )
    print(f"{len(buys)} treasury buy(s)", flush=True)

    done = {}
    if BUYS_PATH.is_file():
        try:
            done = {r["block"]: r for r in json.loads(BUYS_PATH.read_text())}
        except (OSError, json.JSONDecodeError):
            done = {}

    rows = []
    for i, b in enumerate(buys, 1):
        blk = b["block"]
        if blk in done:
            rows.append(done[blk])
            print(f"{i}/{len(buys)} block {blk} cached", flush=True)
            continue
        prev = blk - 1
        s0 = retry(lambda: rpc("eth_call", [{"to": POOL, "data": SLOT0}, hex(prev)]),
                   f"slot0 {prev}")
        sqrt = int(s0[2:66], 16)
        pool_price = price_from_sqrt(sqrt)
        fj = -b["a0"] / 1e18
        bnb = b["a1"] / 1e18
        eff = bnb / fj if fj else None
        bal = retry(lambda: int(rpc("eth_getBalance", [TREASURY, hex(prev)]), 16),
                    f"balance {prev}") / 1e18
        row = {
            "block": blk, "prevBlock": prev, "utc": b["utc"], "cot": b["cot"],
            "day": b["day"], "tx": b["tx"], "bnbIn": bnb, "flapjaxOut": fj,
            "effectivePrice": eff, "poolPriceBefore": pool_price,
            "sqrtPriceX96Before": sqrt, "treasuryBnbBefore": bal,
            "impactPct": (eff / pool_price - 1) * 100 if pool_price else None,
        }
        rows.append(row)
        BUYS_PATH.write_text(json.dumps(rows, indent=1))
        print(f"{i}/{len(buys)} block {blk} {row['utc']} {row['day']} "
              f"bnb {bnb:.6f} fj {fj:,.2f} eff {eff:.18f} "
              f"pool {pool_price:.18f} impact {row['impactPct']:+.3f}%", flush=True)

    BUYS_PATH.write_text(json.dumps(rows, indent=1))
    print()
    print(f"total BNB {sum(r['bnbIn'] for r in rows):.6f}")
    print(f"total FLAPJAX {sum(r['flapjaxOut'] for r in rows):,.4f}")
    print(f"distinct COT days {len({r['day'] for r in rows})}")
    print(f"wrote {BUYS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
