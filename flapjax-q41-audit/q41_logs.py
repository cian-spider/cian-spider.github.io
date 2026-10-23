#!/usr/bin/env python3
"""Full-window log census for the FlapJax Q41 audit.

WHY THIS EXISTS SEPARATELY FROM q41_audit.py
    q41_audit.py asked the named pool "who swapped" and got zero, while the
    treasury's nonce moved from 30 to 376 across the same window. A zero that
    contradicts a nonce delta is not an answer, it is a broken question. So
    this asks the token instead: every FLAPJAX Transfer in the window, plus
    every WBNB Transfer touching the treasury. The token is the ground truth
    for "did the treasury buy or sell", independent of which venue it used.

WHAT IT WRITES
    zero/data/flapjax/q41_logs.json
      flapjaxTransfers  every Transfer on the FLAPJAX token in the window
      wbnbToTreasury    WBNB in, to the treasury
      wbnbFromTreasury  WBNB out, from the treasury
      poolLogs          every log on the pool named in the brief
    plus a small summary printed to stdout.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from q41_audit import (  # noqa: E402
    FLAPJAX, OUT_DIR, POOL, TREASURY, WBNB, block_at, block_ts, rpc, utc,
)

TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
STEP = 49000
OUT_PATH = OUT_DIR / "q41_logs.json"

START_TS = 1791522000   # 2026-10-09 05:00:00 UTC = 10-09 00:00 COT
END_TS = 1792645200     # 2026-10-22 05:00:00 UTC = 10-22 00:00 COT


def scan(addr: str | None, topics: list, frm: int, to: int, label: str) -> list:
    out, start, n = [], frm, 0
    while start <= to:
        end = min(start + STEP - 1, to)
        params = {"fromBlock": hex(start), "toBlock": hex(end)}
        if addr:
            params["address"] = addr
        if topics:
            params["topics"] = topics
        for attempt in range(4):
            try:
                out.extend(rpc("eth_getLogs", [params]))
                break
            except RuntimeError as e:
                if attempt == 3:
                    raise
                print(f"  retry {label} {start}-{end}: {e}", flush=True)
                time.sleep(2 + attempt * 3)
        start = end + 1
        n += 1
        if n % 10 == 0:
            print(f"  {label}: {n} chunks, {len(out)} logs", flush=True)
    print(f"  {label}: DONE {len(out)} logs over {n} chunks", flush=True)
    return out


def pad(addr: str) -> str:
    return "0x" + "0" * 24 + addr[2:].lower()


def decode_transfer(lg: dict) -> dict:
    return {
        "token": lg["address"],
        "from": "0x" + lg["topics"][1][-40:],
        "to": "0x" + lg["topics"][2][-40:],
        "value": int(lg["data"], 16),
        "block": int(lg["blockNumber"], 16),
        "tx": lg["transactionHash"],
        "logIndex": int(lg["logIndex"], 16),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    head = int(rpc("eth_blockNumber", []), 16)
    lo = head - 4_000_000
    frm = block_at(START_TS, lo, head)
    to = block_at(END_TS, lo, head)
    print(f"head {head} window blocks {frm}..{to} ({to - frm})", flush=True)
    print(f"{utc(block_ts(frm))} .. {utc(block_ts(to))}", flush=True)

    print("1/4 all FLAPJAX transfers in window", flush=True)
    fj = scan(FLAPJAX, [TRANSFER], frm, to, "flapjax")

    print("2/4 WBNB transfers to treasury", flush=True)
    w_in = scan(WBNB, [TRANSFER, None, pad(TREASURY)], frm, to, "wbnb-in")

    print("3/4 WBNB transfers from treasury", flush=True)
    w_out = scan(WBNB, [TRANSFER, pad(TREASURY)], frm, to, "wbnb-out")

    print("4/4 all logs on the named pool", flush=True)
    pool = scan(POOL, [], frm, to, "pool")

    data = {
        "generatedAt": utc(int(time.time())),
        "head": head,
        "window": {"fromBlock": frm, "toBlock": to,
                   "startTs": START_TS, "endTs": END_TS,
                   "startUtc": utc(START_TS), "endUtc": utc(END_TS)},
        "flapjaxTransfers": [decode_transfer(l) for l in fj],
        "wbnbToTreasury": [decode_transfer(l) for l in w_in],
        "wbnbFromTreasury": [decode_transfer(l) for l in w_out],
        "poolLogs": [{"block": int(l["blockNumber"], 16),
                      "tx": l["transactionHash"],
                      "topic0": l["topics"][0],
                      "nTopics": len(l["topics"])} for l in pool],
    }
    OUT_PATH.write_text(json.dumps(data, indent=1))
    print(f"wrote {OUT_PATH}", flush=True)

    # ---- summary
    tr = data["flapjaxTransfers"]
    print()
    print(f"FLAPJAX transfers in window: {len(tr)}")
    if tr:
        print(f"  total moved: {sum(t['value'] for t in tr) / 1e18:,.2f} FLAPJAX")
        senders = Counter(t["from"] for t in tr)
        recips = Counter(t["to"] for t in tr)
        print(f"  distinct senders {len(senders)}, distinct recipients {len(recips)}")
        print("  top senders:")
        for a, c in senders.most_common(6):
            print(f"    {a} {c}")
        print("  top recipients:")
        for a, c in recips.most_common(6):
            print(f"    {a} {c}")
        print(f"  treasury appears as sender {senders.get(TREASURY.lower(), 0)}, "
              f"as recipient {recips.get(TREASURY.lower(), 0)}")
        byday = Counter()
        for t in tr:
            byday[time.strftime("%Y-%m-%d", time.gmtime(block_ts(t["block"]) - 5 * 3600))] += 1
        print("  transfers per COT day:")
        for d in sorted(byday):
            print(f"    {d} {byday[d]}")
    print()
    print(f"WBNB to treasury: {len(data['wbnbToTreasury'])}, "
          f"from treasury: {len(data['wbnbFromTreasury'])}")
    print(f"logs on named pool: {len(data['poolLogs'])}")
    if data["poolLogs"]:
        print("  topic0 counts:", Counter(p["topic0"][:20] for p in data["poolLogs"]).most_common())
    return 0


if __name__ == "__main__":
    sys.exit(main())
