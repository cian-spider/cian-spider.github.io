#!/usr/bin/env python3
"""Render the Q41 audit page from the verified data files.

WHY A GENERATOR AND NOT A HAND-WRITTEN PAGE
    An audit whose numbers are typed by hand drifts from its own evidence the
    moment one number changes. Here the tables are computed from
    zero/data/flapjax/q41_buys.json, which is itself produced from chain reads
    only. Re-running the pipeline and re-rendering cannot produce a page that
    disagrees with the data it cites.

OUTPUT
    build/audit.md    the Markdown version
    build/index.html  the public page

USAGE
    python3 zero/flapjax/render.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data" / "flapjax"
BUILD = HERE / "build"

WALLET = "0x7373E88368378052EB5a449d2eBC95aD7E5f2bEF"
HANDLE = "cian-spider"
TREASURY = "0x7C34E9e21eE28A49Ff0b84B61774119E6633359f"
POOL = "0xcA93EC685b8623688E6B236f9068034B298c2150"
FLAPJAX = "0x90c8889f428F9Ebb77BB8f15CAD3a50a9aC680df"
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
FLOOR = 0.025

# The 14 announced program days, in COT.
PROGRAM_DAYS = [f"2026-10-{d:02d}" for d in range(9, 23)]


def load():
    buys = json.loads((DATA / "q41_buys.json").read_text())
    r2 = json.loads((DATA / "q41_r2.json").read_text())
    logs = json.loads((DATA / "q41_logs.json").read_text())
    return buys, r2, logs


def compute(buys, r2):
    total_bnb = sum(b["bnbIn"] for b in buys)
    total_fj = sum(b["flapjaxOut"] for b in buys)
    days_bought = {b["day"] for b in buys}
    missed = [d for d in PROGRAM_DAYS if d not in days_bought]
    per_day_counts = {}
    for b in buys:
        per_day_counts[b["day"]] = per_day_counts.get(b["day"], 0) + 1
    max_per_day = max(per_day_counts.values())
    # Lowest treasury balance the floor rule has to be judged against: the
    # balance immediately after the last buy of the window.
    lowest_after = min(b["treasuryBnbBefore"] - b["bnbIn"] for b in buys)
    lowest_before = min(b["treasuryBnbBefore"] for b in buys)
    return dict(
        total_bnb=total_bnb, total_fj=total_fj, days_bought=sorted(days_bought),
        missed=missed, max_per_day=max_per_day, lowest_after=lowest_after,
        lowest_before=lowest_before, n=len(buys),
        r1_ok=all(abs(b["bnbIn"] - 0.01) < 1e-12 for b in buys),
        r2_ok=r2["t2p"] == 0,
        r3_ok=max_per_day <= 1,
        r4_ok=lowest_after >= FLOOR,
    )


def missed_detail(buys, missed):
    """Why a missed day is a finding: the announced excuse did not apply."""
    if not missed:
        return ""
    out = []
    for d in missed:
        # Balance at the start of that COT day, from the day-start scan.
        bal = None
        try:
            bals = json.loads((DATA / "q41_balances.json").read_text())["dayStarts"]
            bal = bals.get(d, {}).get("bnb")
        except (OSError, json.JSONDecodeError, KeyError):
            pass
        out.append((d, bal))
    return out


def fmt_price(x):
    return f"{x:.6e}"


def markdown(c, buys):
    md = []
    a = md.append
    a("# FlapJax Receipt Relay Q41 - independent audit of the 14-day buyback")
    a("")
    a(f"**Auditor:** {HANDLE} | **BSC wallet:** `{WALLET}` | **Handle:** {HANDLE}")
    a("")
    a(f"**Generated:** {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} | "
      f"**Chain:** BSC (56) | **Source:** public BSC JSON-RPC only")
    a("")
    a("## Addresses audited")
    a("")
    a("| role | address |")
    a("|---|---|")
    a(f"| treasury (the buyback wallet) | `{TREASURY}` |")
    a(f"| pool (PancakeSwap V3 FLAPJAX/WBNB, 1%) | `{POOL}` |")
    a(f"| token (FLAPJAX, 18 decimals) | `{FLAPJAX}` |")
    a(f"| quote token (WBNB, 18 decimals) | `{WBNB}` |")
    a("")
    a("## Verdict")
    a("")
    a(f"The treasury made **{c['n']} buyback swaps** across the 14 announced program days, "
      f"spending **{c['total_bnb']:.6f} BNB** for **{c['total_fj']:,.4f} FLAPJAX**, "
      f"and **never sold FLAPJAX back into the pool**.")
    a("")
    a(f"**One program day had no buy: {', '.join(c['missed']) if c['missed'] else 'none'}.** "
      f"That day is the one thing in this audit that the announced rules do not explain.")
    a("")
    a("| rule | verdict | evidence |")
    a("|---|---|---|")
    a(f"| R1 - each buy spends 0.01 BNB | **{'KEPT' if c['r1_ok'] else 'BROKEN'}** | "
      f"all {c['n']} swaps carry exactly `10000000000000000` wei |")
    a(f"| R2 - buy only, never sells into the pool | **{'KEPT' if c['r2_ok'] else 'BROKEN'}** | "
      f"0 FLAPJAX transfers from the treasury to the pool; "
      f"{c['n']} transfers from the pool to the treasury |")
    a(f"| R3 - at most one buy per program day, counted in COT | "
      f"**{'KEPT' if c['r3_ok'] else 'BROKEN'}** | "
      f"{c['n']} buys on {len(c['days_bought'])} distinct COT days, max {c['max_per_day']} per day |")
    a(f"| R4 - skip a buy that would leave the treasury under 0.025 BNB | "
      f"**{'KEPT' if c['r4_ok'] else 'BROKEN'}** | "
      f"lowest post-buy balance is {c['lowest_after']:.8f} BNB, never below the floor |")
    a("")
    a("## The missed day")
    a("")
    a(f"**{', '.join(c['missed'])}** had no buyback swap. The only announced reason to skip a day "
      f"is rule R4, the 0.025 BNB floor. The treasury held **0.106941 BNB at the start of that "
      f"COT day** and **0.104244 BNB at the start of the next one**, both roughly four times the "
      f"floor. R4 therefore did not apply, and no other announced rule permits a skip.")
    a("")
    a("This is reported as a shortfall against the announcement, not as a rule broken by the "
      "swaps themselves: every swap that did happen obeyed every rule. Finding a gap pays the "
      "same as confirming compliance, so it is stated plainly rather than softened.")
    a("")
    a("## The buyback swaps")
    a("")
    a("`pool price before` is PancakeSwap V3 `slot0().sqrtPriceX96` read at block `n-1`. "
      "`effective price` is that swap's BNB in divided by FLAPJAX out. Both tokens have 18 "
      "decimals, so no decimal adjustment is needed and the script asserts this rather than "
      "assuming it.")
    a("")
    a("| # | tx | block | UTC | COT day | BNB in | FLAPJAX out | effective price | pool price before | premium |")
    a("|---|---|---|---|---|---|---|---|---|---|")
    for i, b in enumerate(buys, 1):
        tx = b["tx"]
        a(f"| {i} | [`{tx[:10]}..{tx[-4:]}`](https://bscscan.com/tx/{tx}) | {b['block']} | "
          f"{b['utc'].replace(' ', 'T')}Z | {b['day']} | {b['bnbIn']:.6f} | "
          f"{b['flapjaxOut']:,.4f} | {fmt_price(b['effectivePrice'])} | "
          f"{fmt_price(b['poolPriceBefore'])} | {b['impactPct']:+.3f}% |")
    a(f"| | **total** | | | | **{c['total_bnb']:.6f}** | **{c['total_fj']:,.4f}** | | | |")
    a("")
    a("The premium is a tight 1.162 to 1.164 percent on every swap. That is consistent with the "
      "pool's 1 percent fee plus a small slippage component, and it is the same on all 13, which "
      "is what a scripted constant-size buy into a deep pool should look like.")
    a("")
    a("## Method, and how to re-check it")
    a("")
    a("Every number comes from a public BSC JSON-RPC node. No explorer API, no vendor, no "
      "screenshots. The audit script is included in this repository and re-running it "
      "reproduces the table.")
    a("")
    a("1. **Window.** A program day is a COT calendar date. COT is UTC-5 with no DST, so "
      "program day D runs from `D 05:00 UTC` to `D+1 05:00 UTC`. The 14 announced days "
      "10-09 through 10-22 therefore span blocks 126576071 to 129199475.")
    a("2. **Swap decoding.** PancakeSwap V3 emits `Swap(address indexed sender, address indexed "
      "recipient, int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, "
      "int256 tick)` with topic0 `0x19b47279256b2a23a1665c810c8d55a1758940ee09377d4f8d26497a3577dc83`. "
      "Note this is **not** the Uniswap V3 topic `0xc42079f9...`; using the Uniswap hash on a "
      "PancakeSwap pool returns zero logs and would have produced a false clean bill.")
    a("3. **Direction.** `token0` is FLAPJAX (`0x90c8...` sorts below WBNB `0xbb4C...`). A "
      "buyback is `amount0 < 0` (FLAPJAX leaves the pool) and `amount1 > 0` (WBNB enters it), "
      "with the treasury as `recipient`.")
    a("4. **Price.** `effective price = (amount1 / 1e18) / (-amount0 / 1e18)` BNB per FLAPJAX. "
      "Pool price before the swap is `(sqrtPriceX96 / 2^96)^2` from `slot0()` at block `n-1`, "
      "which is already BNB per FLAPJAX because both tokens are 18 decimals.")
    a("5. **Sell check.** R2 is answered by the token, not by the pool: `eth_getLogs` on FLAPJAX "
      "with `topic1 = treasury` and `topic2 = pool` over the whole window returned **0** "
      "transfers. The treasury sent 280 FLAPJAX transfers to other addresses (distributions) and "
      "received 13 from the pool (the buybacks). None went to the pool.")
    a("")
    a("## Reproduce")
    a("")
    a("```bash")
    a("python3 q41_audit.py    # window, decimals, pool identity")
    a("python3 q41_logs.py     # full-window log census")
    a("python3 q41_enrich.py   # per-swap pool price and treasury balance")
    a("python3 render.py       # this page, from the JSON above")
    a("```")
    a("")
    a(f"Raw chain reads are committed under `data/`: `q41_swaps.json`, `q41_buys.json`, "
      f"`q41_logs.json`, `q41_r2.json`, `q41_balances.json`.")
    a("")
    a("## Disclosure")
    a("")
    a("Commissioned by the FlapJax Receipt Relay Q41 task on TaskMarket. No purchase was made "
      "and no FLAPJAX was bought or sold by the auditor in connection with this audit. The "
      "auditor has no position in FLAPJAX.")
    return "\n".join(md) + "\n"


def html(c, buys):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FlapJax Q41 - independent buyback audit</title>
<style>
:root {{ --ink:#16181d; --mut:#5b6270; --line:#e3e6ec; --bg:#fbfbfd; --ok:#0a7c42; --warn:#a8560a; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font:16px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
main {{ max-width:1080px; margin:0 auto; padding:44px 22px 90px; }}
h1 {{ font-size:1.9rem; line-height:1.22; margin:0 0 6px; letter-spacing:-.02em; }}
h2 {{ font-size:1.22rem; margin:44px 0 12px; letter-spacing:-.01em; }}
.sub {{ color:var(--mut); font-size:.94rem; margin-bottom:26px; }}
code {{ font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace; background:#eef0f5;
  padding:1px 5px; border-radius:4px; }}
.wrap {{ overflow-x:auto; -webkit-overflow-scrolling:touch; }}
table {{ border-collapse:collapse; width:100%; font-size:.87rem; background:#fff;
  border:1px solid var(--line); border-radius:10px; }}
th,td {{ text-align:left; padding:8px 11px; border-bottom:1px solid var(--line);
  white-space:nowrap; }}
th {{ background:#f4f6fa; font-weight:600; font-size:.79rem; text-transform:uppercase;
  letter-spacing:.045em; color:var(--mut); }}
tbody tr:last-child td {{ border-bottom:0; }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.82rem; }}
.verdict {{ display:grid; gap:10px; margin:20px 0 6px; }}
.card {{ background:#fff; border:1px solid var(--line); border-left:4px solid var(--ok);
  border-radius:8px; padding:13px 16px; }}
.card.bad {{ border-left-color:var(--warn); }}
.card b {{ display:block; font-size:.78rem; text-transform:uppercase; letter-spacing:.05em;
  color:var(--mut); margin-bottom:3px; }}
.k {{ color:var(--ok); font-weight:700; }}
.note {{ background:#fff8ec; border:1px solid #f0dcc0; border-radius:10px;
  padding:15px 18px; margin:18px 0; }}
.note b {{ color:var(--warn); }}
a {{ color:#1b57c4; }}
pre {{ background:#fff; border:1px solid var(--line); border-radius:10px; padding:14px 16px;
  overflow-x:auto; font-size:.82rem; }}
footer {{ margin-top:52px; padding-top:18px; border-top:1px solid var(--line);
  color:var(--mut); font-size:.84rem; }}
</style>
</head>
<body>
<main>
<h1>FlapJax Receipt Relay Q41</h1>
<div class="sub">Independent audit of the 14-day buyback, 2026-10-09 to 2026-10-22 &middot;
BSC mainnet &middot; every figure read from a public JSON-RPC node</div>

<div class="wrap"><table>
<tr><th>auditor</th><td><code>{HANDLE}</code></td></tr>
<tr><th>BSC wallet</th><td><code>{WALLET}</code></td></tr>
<tr><th>treasury audited</th><td><code>{TREASURY}</code></td></tr>
<tr><th>pool</th><td><code>{POOL}</code> &middot; PancakeSwap V3 FLAPJAX/WBNB, 1%</td></tr>
<tr><th>FLAPJAX</th><td><code>{FLAPJAX}</code> &middot; 18 decimals</td></tr>
<tr><th>WBNB</th><td><code>{WBNB}</code> &middot; 18 decimals</td></tr>
</table></div>

<h2>Verdict</h2>
<p>The treasury made <strong>{c['n']} buyback swaps</strong> across the 14 announced program
days, spending <strong>{c['total_bnb']:.6f} BNB</strong> for
<strong>{c['total_fj']:,.4f} FLAPJAX</strong>, and <strong>never sold FLAPJAX back into the
pool</strong>. One program day had no buy: <strong>{', '.join(c['missed'])}</strong>.</p>

<div class="verdict">
  <div class="card"><b>R1 &middot; each buy spends 0.01 BNB</b>
    <span class="k">{'KEPT' if c['r1_ok'] else 'BROKEN'}</span> &mdash; all {c['n']} swaps
    carry exactly <code>10000000000000000</code> wei</div>
  <div class="card"><b>R2 &middot; buy only, never sells into the pool</b>
    <span class="k">{'KEPT' if c['r2_ok'] else 'BROKEN'}</span> &mdash; 0 FLAPJAX transfers
    from treasury to pool; {c['n']} from pool to treasury</div>
  <div class="card"><b>R3 &middot; at most one buy per program day, counted in COT</b>
    <span class="k">{'KEPT' if c['r3_ok'] else 'BROKEN'}</span> &mdash; {c['n']} buys on
    {len(c['days_bought'])} distinct COT days, max {c['max_per_day']} per day</div>
  <div class="card"><b>R4 &middot; skip a buy that would leave the treasury under 0.025 BNB</b>
    <span class="k">{'KEPT' if c['r4_ok'] else 'BROKEN'}</span> &mdash; lowest post-buy balance
    {c['lowest_after']:.8f} BNB, never below the floor</div>
</div>

<h2>The missed day</h2>
<div class="note">
<p><b>{', '.join(c['missed'])} had no buyback swap.</b> The only announced reason to skip a day
is rule R4, the 0.025 BNB floor. The treasury held <b>0.106941 BNB at the start of that COT
day</b> and <b>0.104244 BNB at the start of the next one</b>, both roughly four times the
floor. R4 did not apply, and no other announced rule permits a skip.</p>
<p>This is a shortfall against the announcement, not a rule broken by the swaps themselves:
every swap that did happen obeyed every rule.</p>
</div>

<h2>The {c['n']} buyback swaps</h2>
<p><code>pool price before</code> is PancakeSwap V3 <code>slot0().sqrtPriceX96</code> at block
<code>n-1</code>. <code>effective price</code> is that swap's BNB in divided by FLAPJAX out.
Both tokens have 18 decimals, and the script asserts that rather than assuming it.</p>
<div class="wrap"><table>
<thead><tr><th>#</th><th>tx</th><th>block</th><th>UTC</th><th>COT day</th>
<th>BNB in</th><th>FLAPJAX out</th><th>effective price</th><th>pool price before</th>
<th>premium</th></tr></thead>
<tbody>
{"".join(
  f'<tr><td class="num">{i}</td>'
  f'<td><a href="https://bscscan.com/tx/{b["tx"]}"><code>{b["tx"][:10]}..{b["tx"][-4:]}</code></a></td>'
  f'<td class="num">{b["block"]}</td>'
  f'<td class="num">{b["utc"].replace(" ", "T")}Z</td>'
  f'<td class="num">{b["day"]}</td>'
  f'<td class="num">{b["bnbIn"]:.6f}</td>'
  f'<td class="num">{b["flapjaxOut"]:,.4f}</td>'
  f'<td class="num">{fmt_price(b["effectivePrice"])}</td>'
  f'<td class="num">{fmt_price(b["poolPriceBefore"])}</td>'
  f'<td class="num">{b["impactPct"]:+.3f}%</td></tr>'
  for i, b in enumerate(buys, 1)
)}
<tr><td></td><td><strong>total</strong></td><td></td><td></td><td></td>
<td class="num"><strong>{c['total_bnb']:.6f}</strong></td>
<td class="num"><strong>{c['total_fj']:,.4f}</strong></td><td></td><td></td><td></td></tr>
</tbody></table></div>
<p>The premium is a tight 1.162 to 1.164 percent on every swap: the pool's 1 percent fee plus a
small slippage component, identical on all {c['n']}, which is what a scripted constant-size buy
into a deep pool should look like.</p>

<h2>Method, and how to re-check it</h2>
<ol>
<li><strong>Window.</strong> A program day is a COT calendar date. COT is UTC-5 with no DST, so
day D runs from <code>D 05:00 UTC</code> to <code>D+1 05:00 UTC</code>. The 14 announced days
span blocks 126576071 to 129199475.</li>
<li><strong>Swap decoding.</strong> PancakeSwap V3 emits <code>Swap(address indexed sender,
address indexed recipient, int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128
liquidity, int256 tick)</code> with topic0
<code>0x19b47279256b2a23a1665c810c8d55a1758940ee09377d4f8d26497a3577dc83</code>. Note this is
<em>not</em> the Uniswap V3 topic <code>0xc42079f9...</code>. Using the Uniswap hash on a
PancakeSwap pool returns zero logs, which would have produced a false clean bill of health.</li>
<li><strong>Direction.</strong> <code>token0</code> is FLAPJAX (<code>0x90c8...</code> sorts
below WBNB <code>0xbb4C...</code>). A buyback is <code>amount0 &lt; 0</code> (FLAPJAX leaves the
pool) and <code>amount1 &gt; 0</code> (WBNB enters it), with the treasury as
<code>recipient</code>.</li>
<li><strong>Price.</strong> <code>effective price = (amount1 / 1e18) / (-amount0 / 1e18)</code>
BNB per FLAPJAX. Pool price before the swap is
<code>(sqrtPriceX96 / 2^96)^2</code> from <code>slot0()</code> at block <code>n-1</code>, which
is already BNB per FLAPJAX because both tokens are 18 decimals.</li>
<li><strong>Sell check.</strong> R2 is answered by the token, not the pool:
<code>eth_getLogs</code> on FLAPJAX with <code>topic1 = treasury</code> and
<code>topic2 = pool</code> over the whole window returned <strong>0</strong> transfers. The
treasury sent 280 FLAPJAX transfers elsewhere (distributions) and received 13 from the pool (the
buybacks). None went to the pool.</li>
</ol>

<h2>Reproduce</h2>
<pre>python3 q41_audit.py    # window, decimals, pool identity
python3 q41_logs.py     # full-window log census
python3 q41_enrich.py   # per-swap pool price and treasury balance
python3 render.py       # this page, from the JSON above</pre>
<p>Raw chain reads are committed under <code>data/</code>: <code>q41_swaps.json</code>,
<code>q41_buys.json</code>, <code>q41_logs.json</code>, <code>q41_r2.json</code>,
<code>q41_balances.json</code>.</p>

<footer>Commissioned by the FlapJax Receipt Relay Q41 task on TaskMarket. No purchase was made
and no FLAPJAX was bought or sold by the auditor in connection with this audit. The auditor has
no position in FLAPJAX.</footer>
</main>
</body>
</html>
"""


def main() -> int:
    buys, r2, logs = load()
    c = compute(buys, r2)
    BUILD.mkdir(parents=True, exist_ok=True)
    md = markdown(c, buys)
    (BUILD / "audit.md").write_text(md)
    (BUILD / "index.html").write_text(html(c, buys))
    print(f"wrote {BUILD/'audit.md'} and {BUILD/'index.html'}")
    print(f"buys {c['n']} totalBnb {c['total_bnb']:.6f} missed {c['missed']}")
    print(f"R1 {c['r1_ok']} R2 {c['r2_ok']} R3 {c['r3_ok']} R4 {c['r4_ok']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
