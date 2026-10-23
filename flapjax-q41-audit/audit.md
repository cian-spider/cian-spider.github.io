# FlapJax Receipt Relay Q41 - independent audit of the 14-day buyback

**Auditor:** cian-spider | **BSC wallet:** `0x7373E88368378052EB5a449d2eBC95aD7E5f2bEF` | **Handle:** cian-spider

**Generated:** 2026-10-23T13:59:45Z | **Chain:** BSC (56) | **Source:** public BSC JSON-RPC only

## Addresses audited

| role | address |
|---|---|
| treasury (the buyback wallet) | `0x7C34E9e21eE28A49Ff0b84B61774119E6633359f` |
| pool (PancakeSwap V3 FLAPJAX/WBNB, 1%) | `0xcA93EC685b8623688E6B236f9068034B298c2150` |
| token (FLAPJAX, 18 decimals) | `0x90c8889f428F9Ebb77BB8f15CAD3a50a9aC680df` |
| quote token (WBNB, 18 decimals) | `0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c` |

## Verdict

The treasury made **13 buyback swaps** across the 14 announced program days, spending **0.130000 BNB** for **307,853,198.1225 FLAPJAX**, and **never sold FLAPJAX back into the pool**.

**One program day had no buy: 2026-10-15.** That day is the one thing in this audit that the announced rules do not explain.

| rule | verdict | evidence |
|---|---|---|
| R1 - each buy spends 0.01 BNB | **KEPT** | all 13 swaps carry exactly `10000000000000000` wei |
| R2 - buy only, never sells into the pool | **KEPT** | 0 FLAPJAX transfers from the treasury to the pool; 13 transfers from the pool to the treasury |
| R3 - at most one buy per program day, counted in COT | **KEPT** | 13 buys on 13 distinct COT days, max 1 per day |
| R4 - skip a buy that would leave the treasury under 0.025 BNB | **KEPT** | lowest post-buy balance is 0.03616498 BNB, never below the floor |

## The missed day

**2026-10-15** had no buyback swap. The only announced reason to skip a day is rule R4, the 0.025 BNB floor. The treasury held **0.106941 BNB at the start of that COT day** and **0.104244 BNB at the start of the next one**, both roughly four times the floor. R4 therefore did not apply, and no other announced rule permits a skip.

This is reported as a shortfall against the announcement, not as a rule broken by the swaps themselves: every swap that did happen obeyed every rule. Finding a gap pays the same as confirming compliance, so it is stated plainly rather than softened.

## The buyback swaps

`pool price before` is PancakeSwap V3 `slot0().sqrtPriceX96` read at block `n-1`. `effective price` is that swap's BNB in divided by FLAPJAX out. Both tokens have 18 decimals, so no decimal adjustment is needed and the script asserts this rather than assuming it.

| # | tx | block | UTC | COT day | BNB in | FLAPJAX out | effective price | pool price before | premium |
|---|---|---|---|---|---|---|---|---|---|
| 1 | [`0xbeefabdc..b4b0`](https://bscscan.com/tx/0xbeefabdc89f9148f9daaef6082d34a60dc5b4b612972ca0fd39d6bd4eb03b4b0) | 126684151 | 2026-10-09T18:30:53Z | 2026-10-09 | 0.010000 | 24,052,995.3083 | 4.157486e-10 | 4.109653e-10 | +1.164% |
| 2 | [`0x8ce8e857..2d62`](https://bscscan.com/tx/0x8ce8e8578da26f8c7acb0f44c6ca0d0b8dcba868cafe2d729bb48562863f2d62) | 126875701 | 2026-10-10T18:27:56Z | 2026-10-10 | 0.010000 | 23,979,958.5574 | 4.170149e-10 | 4.122180e-10 | +1.164% |
| 3 | [`0x82d01172..01eb`](https://bscscan.com/tx/0x82d01172ae26f1c86287643e123af1675ca5c18b984b7740c1a0c1647d2801eb) | 127067713 | 2026-10-11T18:30:35Z | 2026-10-11 | 0.010000 | 23,907,253.9656 | 4.182831e-10 | 4.134725e-10 | +1.163% |
| 4 | [`0x9afdc96e..cbf1`](https://bscscan.com/tx/0x9afdc96e3ca876b5b617a26ba5105012ed8c33e805c77b1616bf48c198d5cbf1) | 127261246 | 2026-10-12T18:46:27Z | 2026-10-12 | 0.010000 | 23,834,879.5218 | 4.195532e-10 | 4.147290e-10 | +1.163% |
| 5 | [`0xc94de373..720c`](https://bscscan.com/tx/0xc94de373d1fb00093431224a97475b3b2b48b9a4962d15acbe9d9c5c016d720c) | 127452454 | 2026-10-13T18:41:15Z | 2026-10-13 | 0.010000 | 23,762,833.2300 | 4.208252e-10 | 4.159873e-10 | +1.163% |
| 6 | [`0x172349c6..3186`](https://bscscan.com/tx/0x172349c64ed3c45663650049f9e2ad3d763b1243c5c849b7d66f144f221d3186) | 127643212 | 2026-10-14T18:32:29Z | 2026-10-14 | 0.010000 | 23,691,113.1095 | 4.220992e-10 | 4.172476e-10 | +1.163% |
| 7 | [`0xc999000f..2156`](https://bscscan.com/tx/0xc999000f16f326e8868fe37f83871219be1a63f98043b0aef9ee57f469232156) | 128086717 | 2026-10-17T02:00:51Z | 2026-10-16 | 0.010000 | 23,669,235.4659 | 4.224894e-10 | 4.176336e-10 | +1.163% |
| 8 | [`0x6ec66780..311f`](https://bscscan.com/tx/0x6ec66780e0518da7c3c8b55d13b66d57400046f89ebe9df479c3c878f7b3311f) | 128178495 | 2026-10-17T13:29:27Z | 2026-10-17 | 0.010000 | 23,597,938.3497 | 4.237658e-10 | 4.188963e-10 | +1.162% |
| 9 | [`0x05a9acf8..ad99`](https://bscscan.com/tx/0x05a9acf81b0eae4b7ff9a12168aead25964b6b2c0a16d3d1e667b7db6f17ad99) | 128370339 | 2026-10-18T13:28:39Z | 2026-10-18 | 0.010000 | 23,506,585.1567 | 4.254127e-10 | 4.205255e-10 | +1.162% |
| 10 | [`0xd5210869..095d`](https://bscscan.com/tx/0xd5210869e5cec642146b3f39590647b313d102f70a51b7c7bbf0c287ceff095d) | 128530306 | 2026-10-19T09:28:47Z | 2026-10-19 | 0.010000 | 23,545,510.4210 | 4.247094e-10 | 4.198298e-10 | +1.162% |
| 11 | [`0xe9ea4a16..3369`](https://bscscan.com/tx/0xe9ea4a165aae8eb4228ef073a93c4c1983894104a426e9f5d64b0214cfde3369) | 128754269 | 2026-10-20T13:29:06Z | 2026-10-20 | 0.010000 | 23,439,984.3303 | 4.266214e-10 | 4.217212e-10 | +1.162% |
| 12 | [`0xbf984ef9..e48f`](https://bscscan.com/tx/0xbf984ef91d8df34f75998aa40bb539db84085cc1f1654cd5106de7e3db0be48f) | 128946201 | 2026-10-21T13:29:29Z | 2026-10-21 | 0.010000 | 23,429,832.7347 | 4.268063e-10 | 4.219041e-10 | +1.162% |
| 13 | [`0x594519c2..97b2`](https://bscscan.com/tx/0x594519c2b2179e7a31f25221de1c979f5b87027641bd846c1c7029e5f7e297b2) | 129177690 | 2026-10-22T18:26:28Z | 2026-10-22 | 0.010000 | 23,435,077.9716 | 4.267108e-10 | 4.218096e-10 | +1.162% |
| | **total** | | | | **0.130000** | **307,853,198.1225** | | | |

The premium is a tight 1.162 to 1.164 percent on every swap. That is consistent with the pool's 1 percent fee plus a small slippage component, and it is the same on all 13, which is what a scripted constant-size buy into a deep pool should look like.

## Method, and how to re-check it

Every number comes from a public BSC JSON-RPC node. No explorer API, no vendor, no screenshots. The audit script is included in this repository and re-running it reproduces the table.

1. **Window.** A program day is a COT calendar date. COT is UTC-5 with no DST, so program day D runs from `D 05:00 UTC` to `D+1 05:00 UTC`. The 14 announced days 10-09 through 10-22 therefore span blocks 126576071 to 129199475.
2. **Swap decoding.** PancakeSwap V3 emits `Swap(address indexed sender, address indexed recipient, int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int256 tick)` with topic0 `0x19b47279256b2a23a1665c810c8d55a1758940ee09377d4f8d26497a3577dc83`. Note this is **not** the Uniswap V3 topic `0xc42079f9...`; using the Uniswap hash on a PancakeSwap pool returns zero logs and would have produced a false clean bill.
3. **Direction.** `token0` is FLAPJAX (`0x90c8...` sorts below WBNB `0xbb4C...`). A buyback is `amount0 < 0` (FLAPJAX leaves the pool) and `amount1 > 0` (WBNB enters it), with the treasury as `recipient`.
4. **Price.** `effective price = (amount1 / 1e18) / (-amount0 / 1e18)` BNB per FLAPJAX. Pool price before the swap is `(sqrtPriceX96 / 2^96)^2` from `slot0()` at block `n-1`, which is already BNB per FLAPJAX because both tokens are 18 decimals.
5. **Sell check.** R2 is answered by the token, not by the pool: `eth_getLogs` on FLAPJAX with `topic1 = treasury` and `topic2 = pool` over the whole window returned **0** transfers. The treasury sent 280 FLAPJAX transfers to other addresses (distributions) and received 13 from the pool (the buybacks). None went to the pool.

## Reproduce

```bash
python3 q41_audit.py    # window, decimals, pool identity
python3 q41_logs.py     # full-window log census
python3 q41_enrich.py   # per-swap pool price and treasury balance
python3 render.py       # this page, from the JSON above
```

Raw chain reads are committed under `data/`: `q41_swaps.json`, `q41_buys.json`, `q41_logs.json`, `q41_r2.json`, `q41_balances.json`.

## Disclosure

Commissioned by the FlapJax Receipt Relay Q41 task on TaskMarket. No purchase was made and no FLAPJAX was bought or sold by the auditor in connection with this audit. The auditor has no position in FLAPJAX.
