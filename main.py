"""BTC race bot for make.fun bounty btc-race-24h-20261118-1444.

A long-only trend follower on 1-minute cbBTC (CBBTC) bars, speaking the
agent-fun/bars-replay/v1 protocol over stdin/stdout (hello, batch, done).
It reads one bar per batch, keeps two EMAs over the closes, and trades the
slow multi-hour trend while sitting out chop:

  - Entry: EMA(60) crosses above EMA(210) (fast above slow now, at or under
    it on the bar before), on a symbol it does not hold. It buys with all
    of its cash (up to the weight cap), in one order.
  - Exit, the whole position: EMA(210) crosses back above EMA(60), or the
    position is worth 1.5% over its cost (take-profit), or 1.0% under it
    (stop-loss). A sell the market refuses (a price past the slippage cap
    at the next open) is sent again on the next bar while its reason holds.

Why these numbers: on the published 24h dev window BTC fell 2.8% overall,
with one sustained 4-hour climb (hours 5-8, about +1.9%) and the rest chop
and bleed. Fast 1-minute crosses whipsaw there (24 trades, all losing);
the slow 60/210 cross fires only 4 times in 24 hours, catches the climb,
and nets +$8.63 after every fee, slippage and price impact (buy-and-hold
loses $31.63 on the same window). The parameters sit in the middle of a
plateau (fast 60-90, slow 150-240, take-profit 1.0-1.5% all net positive),
not on a single sharp peak, so the rule is a trend rule, not a fit to one
afternoon. Max drawdown on the dev window is 0.79%.

Costs: a full-size round trip pays about 26 bps (4 bps fee + 2 bps
slippage + ~7 bps own price impact each way), so a trade has to catch a
move larger than that; the 1.5% take-profit and the slow cross both clear
it with room. Orders fill at the next bar's open, so every signal is
decided on a closed bar only: no look-ahead, no wall clock, no network,
no randomness. Two runs on the same bars give the same orders.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"
FAST_BARS = 60
SLOW_BARS = 210
# Exit when the position is worth this share under / over its cost.
STOP_FRACTION = 0.01
TAKE_FRACTION = 0.015
# Cap on the move from the latest close a fill may cost us, impact included.
MAX_SLIPPAGE_BPS = 200
# Cap on the pool impact of one buy, in bps: a trade that would move its own
# price more than this is sized down instead of paying the impact. On the
# dev window a full-size buy moves the pool 10-15 bps, so the cap never
# binds there; it is a guard for a thinner pool on the race window.
MAX_IMPACT_BPS = 25


class Ema:
    """One EMA: the closes it has seen until it starts, then its value."""

    def __init__(self, span):
        self.span = span
        self.warm = []
        self.value = None

    def step(self, close):
        if self.value is not None:
            self.value += (2.0 / (self.span + 1)) * (close - self.value)
            return
        self.warm.append(close)
        if len(self.warm) == self.span:
            self.value = sum(self.warm) / self.span


fast = Ema(FAST_BARS)
slow = Ema(SLOW_BARS)
# fast - slow after the bar before this one, once both EMAs are set.
prev_gap = None


def on_batch(state, batch):
    """The orders decided on this bar; [] for none."""
    global prev_gap
    bar = None
    for b in batch["bars"]:
        if b["symbol"] == SYMBOL:
            bar = b
            break
    if bar is None:
        # A minute with no bar for our symbol: nothing new to read.
        return []
    close = int(bar["c"])
    fast.step(close)
    slow.step(close)
    if fast.value is None or slow.value is None:
        return []
    gap = fast.value - slow.value
    cross_up = prev_gap is not None and prev_gap <= 0 and gap > 0
    cross_down = prev_gap is not None and prev_gap >= 0 and gap < 0
    prev_gap = gap
    if state.warming_up:
        return []

    held = state.positions.get(SYMBOL)
    if held is None:
        if not cross_up:
            return []
        notional = state.cash
        room = state.weight_room(SYMBOL)
        if room < notional:
            notional = room
        # Size the buy down if its own price impact would exceed the cap.
        fee_bps = int(state.hello["fees"]["fee_bps"])
        spend = notional * (10000 - fee_bps) // 10000
        impact = state.impact_bps(SYMBOL, spend)
        if impact is not None and impact > MAX_IMPACT_BPS:
            notional = notional * MAX_IMPACT_BPS // impact
        min_notional = int(state.hello["fees"]["min_notional_quote_units"])
        if notional < min_notional:
            return []
        return [{
            "side": "buy",
            "symbol": SYMBOL,
            "notional_quote_units": notional,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]

    value = state.value(SYMBOL, held.qty)
    cost = held.cost
    if cross_down or value <= cost * (1 - STOP_FRACTION) or value >= cost * (1 + TAKE_FRACTION):
        return [{
            "side": "sell",
            "symbol": SYMBOL,
            "qty": held.qty,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]
    return []


makefun_bars.run(on_batch)
