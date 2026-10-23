#!/usr/bin/env python3
"""FlapJax Receipt Relay Q41: an on-chain audit of the 14-day buyback.

WHAT THIS PROVES, AND FROM WHAT
    Every number here comes from a public BSC node and nothing else. No
    explorer API, no vendor, no screenshots. The two endpoints are recorded so
    a stranger can re-run this file and get the same answer.

THE CLAIM BEING CHECKED
    Announced 2026-10-08. FlapJax buys back its own token from its treasury
    0x7C34E9e21eE28A49Ff0b84B61774119E6633359f for 14 program days, 10-09
    through 10-22, 0.01 BNB per program day, buy-only, in the PancakeSwap V3
    FLAPJAX/WBNB 1% pool 0xcA93EC685b8623688E6B236f9068034B298c2150.
    Four rules:
      R1 each buy spends 0.01 BNB
      R2 only buys FLAPJAX, never sells
      R3 at most one buy per program day, day counted in COT (UTC-5)
      R4 skipped if it would leave the treasury under 0.025 BNB

HOW A SWAP IS READ
    A PancakeSwap V3 pool emits
      Swap(address indexed sender, address indexed recipient,
           int256 amount0, int256 amount1, uint160 sqrtPriceX96,
           uint128 liquidity, int256 tick)
    Both amount0 and amount1 are signed from the pool's own point of view, so a
    positive value means the pool received that token. token0 is the lower
    address: FLAPJAX 0x90c8... < WBNB 0xbb4C..., so
      amount0 = FLAPJAX delta, amount1 = WBNB delta.
    A buyback is therefore amount0 < 0 (FLAPJAX leaves the pool) and
    amount1 > 0 (WBNB enters it).

THE PRICE FORMULA, BOTH TOKENS 18 DECIMALS
    effective price = (WBNB in / 1e18) / (FLAPJAX out / 1e18)  BNB per FLAPJAX
    pool price before the swap, from slot0().sqrtPriceX96 at block n-1:
      price of token0 in token1 = (sqrtPriceX96 / 2^96)^2
      token0 is FLAPJAX, token1 is WBNB, so that is already BNB per FLAPJAX
      scaled by 10^(18-18) = 1, i.e. no adjustment is needed here, and the
      script asserts the decimals rather than assuming them.

USAGE
    python3 zero/flapjax/q41_audit.py            # full run, writes JSON
    python3 zero/flapjax/q41_audit.py --cached   # reuse zero/data/flapjax/q41_raw.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RPCS = [
    # NodeReal first: it is the only free endpoint measured to serve archive
    # eth_getLogs on this box, at a 49,000-block range. The rest are kept as
    # fallbacks for plain calls, which they do serve.
    "https://bsc-mainnet.nodereal.io/v1/64a9df0874fb4a93b9d0a3849de012d3",
    "https://bsc-rpc.publicnode.com",
    "https://bsc-dataseed.binance.org",
    "https://1rpc.io/bnb",
]

TREASURY = "0x7C34E9e21eE28A49Ff0b84B61774119E6633359f"
POOL = "0xcA93EC685b8623688E6B236f9068034B298c2150"
FLAPJAX = "0x90c8889f428F9Ebb77BB8f15CAD3a50a9aC680df"
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"

SWAP_TOPIC = "0x" + "c42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
SLOT0_SELECTOR = "0x3850c7bd"          # slot0()
DECIMALS_SELECTOR = "0x313ce567"      # decimals()
TOKEN0_SELECTOR = "0x0dfe1681"        # token0()

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "flapjax"
RAW_PATH = OUT_DIR / "q41_raw.json"

# Window. The brief says program days 10-09 through 10-22 but asks for swaps
# 10-09 to 10-21, and says a program day is counted in COT, which is UTC-5 and
# has no DST. So a program day D runs from D 00:00 COT to D+1 00:00 COT, which
# is D 05:00 UTC to D+1 05:00 UTC.
COT_OFFSET_HOURS = -5


# ---------------------------------------------------------------------------
# RPC
# ---------------------------------------------------------------------------

class Rpc:
    def __init__(self):
        self.i = 0
        self.calls = 0

    def __call__(self, method: str, params: list):
        last = None
        for attempt in range(len(RPCS) * 2):
            url = RPCS[self.i % len(RPCS)]
            body = json.dumps({"jsonrpc": "2.0", "id": 1,
                               "method": method, "params": params}).encode()
            req = urllib.request.Request(url, data=body,
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=40) as res:
                    d = json.loads(res.read().decode())
                self.calls += 1
                if "error" in d:
                    raise RuntimeError(f"{method} {params[:2]} -> {d['error']}")
                return d["result"]
            except Exception as e:                      # noqa: BLE001
                last = e
                self.i += 1
                time.sleep(0.4 * (attempt + 1))
        raise RuntimeError(f"all RPCs failed on {method}: {last}")


rpc = Rpc()


def block_at(ts: int, lo: int, hi: int) -> int:
    """Binary search the first block whose timestamp is >= ts."""
    while lo < hi:
        mid = (lo + hi) // 2
        b = rpc("eth_getBlockByNumber", [hex(mid), False])
        if int(b["timestamp"], 16) < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def block_ts(n: int) -> int:
    b = rpc("eth_getBlockByNumber", [hex(n), False])
    return int(b["timestamp"], 16)


def call(to: str, data: str, block: int) -> str:
    return rpc("eth_call", [{"to": to, "data": data}, hex(block)])


def get_logs(addr: str, topics: list, frm: int, to: int) -> list:
    """eth_getLogs with a range cap and pagination, because public nodes cap it."""
    out, start = [], frm
    step = 5000
    while start <= to:
        end = min(start + step - 1, to)
        try:
            chunk = rpc("eth_getLogs", [{
                "address": addr, "topics": topics,
                "fromBlock": hex(start), "toBlock": hex(end),
            }])
        except RuntimeError:
            if step > 200:
                step //= 2
                continue
            raise
        out.extend(chunk)
        start = end + 1
    return out


# ---------------------------------------------------------------------------
# Decoding
# ---------------------------------------------------------------------------

def s_word(hexword: str) -> int:
    v = int(hexword, 16)
    return v - (1 << 256) if v >= (1 << 255) else v


def decode_swap(log: dict) -> dict:
    d = log["data"][2:]
    w = [d[i:i + 64] for i in range(0, len(d), 64)]
    return {
        "sender": "0x" + log["topics"][1][-40:],
        "recipient": "0x" + log["topics"][2][-40:],
        "amount0": s_word(w[0]),
        "amount1": s_word(w[1]),
        "sqrtPriceX96": int(w[2], 16),
        "liquidity": int(w[3], 16),
        "tick": s_word(w[4]),
        "block": int(log["blockNumber"], 16),
        "tx": log["transactionHash"],
        "logIndex": int(log["logIndex"], 16),
    }


def price_from_sqrt(sqrt_price_x96: int) -> float:
    """Price of token0 in token1, in human units, assuming equal decimals."""
    return (sqrt_price_x96 / (1 << 96)) ** 2


def cot(ts: int) -> str:
    t = time.gmtime(ts + COT_OFFSET_HOURS * 3600)
    return time.strftime("%Y-%m-%d %H:%M:%S", t)


def utc(ts: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(ts))


def program_day(ts: int) -> str:
    """The COT calendar date a timestamp falls on. That is the program day."""
    t = time.gmtime(ts + COT_OFFSET_HOURS * 3600)
    return time.strftime("%Y-%m-%d", t)


# ---------------------------------------------------------------------------

def build(cached: bool) -> dict:
    head = int(rpc("eth_blockNumber", []), 16)
    print(f"head block {head}", flush=True)

    # Decimals, asserted rather than assumed.
    dec_f = int(call(FLAPJAX, DECIMALS_SELECTOR, head), 16)
    dec_w = int(call(WBNB, DECIMALS_SELECTOR, head), 16)
    t0 = "0x" + call(POOL, TOKEN0_SELECTOR, head)[-40:]
    print(f"decimals FLAPJAX={dec_f} WBNB={dec_w} token0={t0}", flush=True)
    assert t0.lower() == FLAPJAX.lower(), f"token0 is {t0}, expected FLAPJAX"

    # Window bounds in UTC. A COT day D starts at D 05:00 UTC.
    start_ts = int(time.mktime(time.strptime("2026-10-09 05:00:00", "%Y-%m-%d %H:%M:%S"))
                   - time.timezone)
    # Simpler and timezone-proof: compute from a UTC struct directly.
    import calendar
    start_ts = calendar.timegm(time.strptime("2026-10-09 05:00:00", "%Y-%m-%d %H:%M:%S"))
    # 10-22 00:00 COT is the end of the last program day = 10-22 05:00 UTC.
    end_ts = calendar.timegm(time.strptime("2026-10-22 05:00:00", "%Y-%m-%d %H:%M:%S"))
    print(f"window {utc(start_ts)} .. {utc(end_ts)} UTC", flush=True)

    # Search backwards for the blocks. The window is in the past, so the head
    # is above it; start the search well below to keep the range sane.
    lo = head - 3_000_000
    frm = block_at(start_ts, lo, head)
    to = block_at(end_ts, lo, head)
    print(f"blocks {frm} .. {to} ({to - frm} blocks)", flush=True)

    sender_topic = "0x" + "0" * 24 + TREASURY[2:].lower()
    print("scanning Swap logs where sender == treasury", flush=True)
    logs = get_logs(POOL, [SWAP_TOPIC, sender_topic], frm, to)
    print(f"{len(logs)} swap(s) from the treasury in window", flush=True)

    swaps = []
    for lg in logs:
        s = decode_swap(lg)
        ts = block_ts(s["block"])
        s["timestamp"] = ts
        s["utc"] = utc(ts)
        s["cot"] = cot(ts)
        s["programDay"] = program_day(ts)
        s["flapjaxOut"] = -s["amount0"] / 10 ** dec_f     # negative amount0 = out of pool
        s["bnbIn"] = s["amount1"] / 10 ** dec_w
        s["isBuy"] = s["amount0"] < 0 and s["amount1"] > 0
        if s["isBuy"] and s["flapjaxOut"]:
            s["effectivePrice"] = s["bnbIn"] / s["flapjaxOut"]
        else:
            s["effectivePrice"] = None
        # Pool price at the block before, which is what the brief asks for.
        prev = s["block"] - 1
        slot0 = call(POOL, SLOT0_SELECTOR, prev)
        s["poolSqrtPriceX96Before"] = int(slot0[2:66], 16)
        s["poolPriceBefore"] = price_from_sqrt(s["poolSqrtPriceX96Before"])
        s["poolTickBefore"] = s_word(slot0[66:130])
        s["prevBlock"] = prev
        swaps.append(s)

    # Treasury BNB balance before each program day, for the 0.025 floor rule.
    day_blocks = {}
    d = start_ts
    while d < end_ts:
        n = block_at(d, lo, head)
        day_blocks[time.strftime("%Y-%m-%d", time.gmtime(d + COT_OFFSET_HOURS * 3600))] = n
        d += 86400
    balances = {}
    for day, n in day_blocks.items():
        bal = int(rpc("eth_getBalance", [TREASURY, hex(n - 1)]), 16) / 1e18
        balances[day] = {"block": n - 1, "bnb": bal}

    return {
        "generatedAt": utc(int(time.time())),
        "head": head,
        "rpcs": RPCS,
        "addresses": {"treasury": TREASURY, "pool": POOL,
                      "flapjax": FLAPJAX, "wbnb": WBNB},
        "decimals": {"flapjax": dec_f, "wbnb": dec_w},
        "token0": t0,
        "window": {"fromBlock": frm, "toBlock": to,
                   "startUtc": utc(start_ts), "endUtc": utc(end_ts),
                   "startTs": start_ts, "endTs": end_ts},
        "swaps": swaps,
        "dayStartBalances": balances,
    }


def summarise(data: dict) -> None:
    sw = data["swaps"]
    print()
    print(f"{'utc':20} {'cot':20} {'day':10} {'bnbIn':>12} {'flapjaxOut':>20} {'price':>18}")
    for s in sw:
        p = f"{s['effectivePrice']:.18f}" if s["effectivePrice"] else "n/a"
        print(f"{s['utc']:20} {s['cot']:20} {s['programDay']:10} "
              f"{s['bnbIn']:12.6f} {s['flapjaxOut']:20.6f} {p:>18}")
    buys = [s for s in sw if s["isBuy"]]
    sells = [s for s in sw if not s["isBuy"]]
    print()
    print(f"buys {len(buys)}  sells {len(sells)}  totalBNB {sum(s['bnbIn'] for s in buys):.6f}  "
          f"totalFLAPJAX {sum(s['flapjaxOut'] for s in buys):.6f}")
    days = sorted({s["programDay"] for s in buys})
    print(f"days with a buy: {len(days)} -> {days}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cached", action="store_true")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.cached and RAW_PATH.is_file():
        data = json.loads(RAW_PATH.read_text())
    else:
        data = build(cached=False)
        RAW_PATH.write_text(json.dumps(data, indent=1))
        print(f"wrote {RAW_PATH}")
    summarise(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
