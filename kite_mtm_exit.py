"""
Kite Connect — Total MTM Exit Monitor
======================================
Monitors the combined MTM (unrealised P&L) of 2 open positions
(CE leg + PE leg of a short strangle) and exits both when the
total MTM hits the configured target or stop-loss.

Setup:
  pip install kiteconnect

Usage:
  1. Fill CONFIG below with your API key, access token, and strikes.
  2. Run:  python kite_mtm_exit.py
"""

import time
from datetime import datetime

try:
    from kiteconnect import KiteConnect
except ImportError:
    raise SystemExit("Install kiteconnect first:  pip install kiteconnect")

# ── CONFIG ────────────────────────────────────────────────────────────────────

CONFIG = {
    # Kite API credentials
    "api_key":      "your_api_key_here",
    "access_token": "your_access_token_here",

    # Your 2 open positions (tradingsymbol exactly as shown in Kite positions)
    # Example: "NIFTY2552222500CE"
    "ce_symbol":    "NIFTY2552222500CE",   # <-- replace
    "pe_symbol":    "NIFTY2552221800PE",   # <-- replace

    # Exchange for F&O (NFO for Nifty/BankNifty options)
    "exchange":     "NFO",

    # Exit thresholds (in Rs, total across both legs)
    "total_target": 2500,    # exit both if combined MTM profit >= this
    "total_sl":     -2000,   # exit both if combined MTM loss   <= this

    # Polling interval in seconds
    "poll_interval": 5,

    # Order type for exit ("MARKET" recommended for quick exit)
    "order_type":   "MARKET",
    "product":      "MIS",   # MIS for intraday, NRML for overnight
}

# ── HELPERS ───────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}]  {msg}")


def get_position_mtm(positions: list, symbol: str, exchange: str) -> float | None:
    """Return unrealised P&L for a specific symbol, or None if not found."""
    for pos in positions:
        if pos["tradingsymbol"] == symbol and pos["exchange"] == exchange:
            # 'pnl' = total day P&L (unrealised + realised for the day)
            # Use 'unrealised' for open MTM only
            return float(pos.get("unrealised", pos.get("pnl", 0)))
    return None


def place_exit_order(kite: KiteConnect, symbol: str, exchange: str,
                     quantity: int, product: str, order_type: str) -> str:
    """Place a BUY order to exit a short option position."""
    order_id = kite.place_order(
        variety=KiteConnect.VARIETY_REGULAR,
        exchange=exchange,
        tradingsymbol=symbol,
        transaction_type=KiteConnect.TRANSACTION_TYPE_BUY,
        quantity=quantity,
        order_type=order_type,
        product=product,
        price=None,          # None = market price
        validity=KiteConnect.VALIDITY_DAY,
    )
    return order_id


def get_open_quantity(positions: list, symbol: str, exchange: str) -> int:
    """Return net short quantity (absolute) for a position."""
    for pos in positions:
        if pos["tradingsymbol"] == symbol and pos["exchange"] == exchange:
            qty = int(pos.get("quantity", 0))
            # quantity is negative for short positions
            return abs(qty)
    return 0

# ── MAIN MONITOR LOOP ─────────────────────────────────────────────────────────

def run(config: dict):
    kite = KiteConnect(api_key=config["api_key"])
    kite.set_access_token(config["access_token"])

    ce_sym  = config["ce_symbol"]
    pe_sym  = config["pe_symbol"]
    exch    = config["exchange"]
    target  = config["total_target"]
    sl      = config["total_sl"]
    poll    = config["poll_interval"]

    log(f"Starting MTM monitor")
    log(f"  CE : {ce_sym}")
    log(f"  PE : {pe_sym}")
    log(f"  Target : Rs {target:,}  |  SL : Rs {sl:,}")
    log(f"  Polling every {poll}s  —  press Ctrl+C to stop\n")

    exited = False

    while not exited:
        try:
            raw       = kite.positions()
            day_pos   = raw.get("day", [])

            ce_mtm = get_position_mtm(day_pos, ce_sym, exch)
            pe_mtm = get_position_mtm(day_pos, pe_sym, exch)

            if ce_mtm is None:
                log(f"WARNING: CE position '{ce_sym}' not found in positions.")
            if pe_mtm is None:
                log(f"WARNING: PE position '{pe_sym}' not found in positions.")

            if ce_mtm is None or pe_mtm is None:
                time.sleep(poll)
                continue

            total_mtm = ce_mtm + pe_mtm
            log(f"MTM  CE={ce_mtm:+,.0f}  PE={pe_mtm:+,.0f}  "
                f"TOTAL={total_mtm:+,.0f}  "
                f"(target {target:+,} | sl {sl:+,})")

            if total_mtm >= target:
                log(f"TARGET HIT ({total_mtm:+,.0f} >= {target:,}) — exiting both legs...")
                trigger = "TARGET"
            elif total_mtm <= sl:
                log(f"STOP-LOSS HIT ({total_mtm:+,.0f} <= {sl:,}) — exiting both legs...")
                trigger = "STOP-LOSS"
            else:
                time.sleep(poll)
                continue

            # Place exit orders
            for sym in [ce_sym, pe_sym]:
                qty = get_open_quantity(day_pos, sym, exch)
                if qty <= 0:
                    log(f"  {sym}: no open quantity, skipping.")
                    continue
                try:
                    oid = place_exit_order(
                        kite, sym, exch, qty,
                        config["product"], config["order_type"]
                    )
                    log(f"  EXIT order placed for {sym}  qty={qty}  order_id={oid}")
                except Exception as e:
                    log(f"  ERROR placing exit for {sym}: {e}")

            log(f"\nBoth legs exit orders sent ({trigger}). Monitor stopped.")
            exited = True

        except KeyboardInterrupt:
            log("Stopped by user.")
            break
        except Exception as e:
            log(f"ERROR: {e}  — retrying in {poll}s...")
            time.sleep(poll)


if __name__ == "__main__":
    run(CONFIG)
