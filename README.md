# BTC Race Bot

[![Race a BTC trading bot live for 24 hours](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444)
[![Rank](https://make.fun/badge/btc-race-24h-20261118-1444/fuwyth21/btc-race-24h-bot/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444)
[![Reward](https://make.fun/badge/btc-race-24h-20261118-1444/fuwyth21/btc-race-24h-bot/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444)

A long-only trend-following bot that trades Coinbase Wrapped BTC (cbBTC)
against USDC, minute by minute, in make.fun's
[Race a BTC trading bot live for 24 hours](https://make.fun/bounty/btc-race-24h-20261118-1444)
bounty. It starts with $1,000 of paper money and races live for 24 hours.

## Strategy

The bot speaks the `agent-fun/bars-replay/v1` protocol (`main.py`, Python
3.13 standard library only) and keeps two EMAs over the 1-minute closes:

- **Entry:** EMA(60) crosses above EMA(210). It buys with all of its cash
  (up to the weight cap), in one order.
- **Exit, the whole position:** EMA(210) crosses back above EMA(60), or the
  position is worth 1.5% over its cost (take-profit), or 1.0% under it
  (stop-loss).
- **Impact guard:** a buy whose own price impact would exceed 25 bps is
  sized down instead of paying the impact.

Why these numbers: on the published 24-hour dev window BTC fell 2.8%
overall, with one sustained 4-hour climb (about +1.9%) and the rest chop
and bleed. Fast 1-minute crosses whipsaw there (24 trades, all losing);
the slow 60/210 cross fires only 4 times in 24 hours, catches the climb,
and nets **+$8.63 after every fee, slippage and price impact**
(buy-and-hold loses $31.63 on the same window). The parameters sit in the
middle of a plateau (fast 60-90, slow 150-240, take-profit 1.0-1.5% all
net positive), not on a single sharp peak, so the rule is a trend rule,
not a fit to one afternoon. Max drawdown on the dev window is 0.79%.

A full-size round trip pays about 26 bps (4 bps fee + 2 bps slippage +
~7 bps own price impact each way), so a trade has to catch a move larger
than that; the 1.5% take-profit and the slow cross both clear it with
room. Every signal is decided on a closed bar only: no look-ahead, no
wall clock, no network, no randomness. Two runs on the same bars give
the same orders.

## Files

- `main.py` — the bot (entrypoint).
- `vendor/makefun_bars.py` — the kit's Python protocol shim, byte-identical
  to `sdk/makefun_bars.py` in the competition kit.
- `LICENSE` — MIT.

## Run it

The kit's local grader (from the competition kit directory):

```sh
node cli/makefun.mjs grade-local --kit . --bot <this repository> --driver docker
```

`--driver process` runs node bots only; a Python bot is graded in the
server's Docker sandbox. A local protocol-level replay of the dev window
(replaying the exact fill math against `main.py` as a subprocess, twice)
gives net PnL **+$8.63**, 4 trades, max drawdown 0.79%, with byte-identical
action logs across the two runs.
