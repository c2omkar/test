# ============================================================
#  Nifty PDH/PDL Short Strangle — Backtest
#
#  Strategy:
#    - Each day: note previous day High (PDH) & Low (PDL)
#    - Round PDH UP to nearest 50  → CE strike to SELL
#    - Round PDL DOWN to nearest 50 → PE strike to SELL
#    - Enter at 10:00 AM (OPEN price used as proxy)
#
#  Exit conditions (first one that triggers wins):
#    1. Individual leg SL : option rises 60% from entry
#    2. Cumulative SL     : combined P&L <= -Rs 2000 → exit both
#    3. Cumulative TGT    : combined P&L >= +Rs 2500 → exit both
#    4. Time exit         : 3:20 PM → exit at CLOSE price
#
#  Fixes vs previous version:
#    - Tries BOTH old and new NSE Bhav Copy URL formats (fixes 2025 data)
#    - Retries session if 403 received mid-run
#    - Added debug logging for skipped days
#
#  Run: python nifty_pdh_pdl_backtest.py
# ============================================================

import subprocess, sys
subprocess.check_call([sys.executable, "-m", "pip", "install",
                       "yfinance", "pandas", "numpy",
                       "matplotlib", "requests", "tqdm", "-q"])

import math, time, warnings, requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from io import BytesIO
from zipfile import ZipFile
from datetime import date, timedelta
from tqdm import tqdm
from collections import defaultdict

warnings.filterwarnings("ignore")
pd.set_option("display.float_format", "{:.2f}".format)

# ── CONFIG ────────────────────────────────────────────────────

CONFIG = {
    "ticker":           "NIFTY",
    "start_date":       date(2025, 1, 1),
    "end_date":         date(2026, 5, 12),
    "entry_hour":       10,
    "entry_minute":     0,
    "exit_hour":        15,
    "exit_minute":      20,    # square off at 3:20 PM
    "leg_sl_pct":       60,    # % per leg SL
    "cumulative_sl":    2000,  # Rs — exit ALL if combined loss hits this
    "cumulative_tgt":   2500,  # Rs — exit ALL if combined profit hits this
    "lots":             1,
    "lot_size":         75,    # 75 from Sep 2024 onwards
    "strike_gap":       50,
    "expiry_type":      "weekly",
    "sleep_sec":        0.3,   # delay between requests (increase if getting 403s)
}

# ── Helpers ───────────────────────────────────────────────────

def round_up_strike(price, gap=50):
    return math.ceil(price / gap) * gap

def round_down_strike(price, gap=50):
    return math.floor(price / gap) * gap

def make_session():
    """Create a fresh NSE session with cookies"""
    s = requests.Session()
    hdrs = {
        "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0.0.0 Safari/537.36",
        "Accept":          "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection":      "keep-alive",
    }
    try:
        s.get("https://www.nseindia.com", headers=hdrs, timeout=15)
        time.sleep(1)
        s.get("https://www.nseindia.com/market-data/securities-available-for-trading",
              headers=hdrs, timeout=10)
    except Exception:
        pass
    return s, {
        "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0.0.0 Safari/537.36",
        "Accept":          "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer":         "https://www.nseindia.com/",
        "X-Requested-With": "XMLHttpRequest",
    }

# ── Nifty OHLC ────────────────────────────────────────────────

def fetch_nifty_ohlc(start: date, end: date) -> pd.DataFrame:
    import yfinance as yf
    print("Fetching Nifty daily OHLC from Yahoo Finance...")
    df = yf.download(
        "^NSEI",
        start=start.strftime("%Y-%m-%d"),
        end=(end + timedelta(days=1)).strftime("%Y-%m-%d"),
        interval="1d",
        auto_adjust=True,
        progress=False,
    )
    if df.empty:
        raise ValueError("Could not download Nifty OHLC. Check internet.")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close"]].copy()
    df.index = pd.to_datetime(df.index).date
    df.index.name = "Date"
    df = df.sort_index()
    print(f"  Got {len(df)} trading days ({df.index[0]} to {df.index[-1]})")
    return df

# ── NSE Bhav Copy — tries both URL formats ────────────────────
#
#  NSE uses TWO different URL formats depending on the date:
#
#  OLD (works up to ~mid-2024):
#    .../DERIVATIVES/YYYY/MMM/fo{DD}{MMM}{YYYY}bhav.csv.zip
#
#  NEW (2024 onwards):
#    .../content/fo/BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip

def bhav_urls(d: date):
    dd   = d.strftime("%d")
    mm3  = d.strftime("%b").upper()
    yyyy = d.strftime("%Y")
    mm2  = d.strftime("%m")
    return [
        # New format (2024+) — try first for recent dates
        f"https://nsearchives.nseindia.com/content/fo/"
        f"BhavCopy_NSE_FO_0_0_0_{yyyy}{mm2}{dd}_F_0000.csv.zip",
        # Old format (pre-2024)
        f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/"
        f"{yyyy}/{mm3}/fo{dd}{mm3}{yyyy}bhav.csv.zip",
    ]

def parse_bhav_new(df: pd.DataFrame) -> pd.DataFrame:
    """Parse new-format Bhav Copy (2024+)"""
    df.columns = df.columns.str.strip()
    # New format columns: TckrSymb, XpryDt, OptnTp, StrkPric, OpnPric, HghPric, LwPric, ClsPric
    col_map = {
        "TckrSymb": "SYMBOL",
        "XpryDt":   "EXPIRY_DT",
        "OptnTp":   "OPTION_TYP",
        "StrkPric": "STRIKE_PR",
        "OpnPric":  "OPEN",
        "HghPric":  "HIGH",
        "LwPric":   "LOW",
        "ClsPric":  "CLOSE",
        "FinInstrmTp": "INSTRUMENT",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    # Filter Nifty options
    if "SYMBOL" in df.columns:
        df = df[df["SYMBOL"].astype(str).str.strip() == "NIFTY"].copy()
    if "INSTRUMENT" in df.columns:
        df = df[df["INSTRUMENT"].astype(str).str.strip().isin(["IO", "OPTIDX"])].copy()
    # Parse dates — new format uses YYYY-MM-DD
    if "EXPIRY_DT" in df.columns:
        df["EXPIRY_DT"] = pd.to_datetime(df["EXPIRY_DT"], errors="coerce")
    if "OPTION_TYP" in df.columns:
        df["OPTION_TYP"] = df["OPTION_TYP"].astype(str).str.strip().str.upper()
        # New format uses CE/PE directly
    for col in ["STRIKE_PR", "OPEN", "HIGH", "LOW", "CLOSE"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def parse_bhav_old(df: pd.DataFrame) -> pd.DataFrame:
    """Parse old-format Bhav Copy (pre-2024)"""
    df.columns = df.columns.str.strip()
    df = df[
        (df["SYMBOL"].str.strip()     == "NIFTY") &
        (df["INSTRUMENT"].str.strip() == "OPTIDX")
    ].copy()
    for col in ["STRIKE_PR", "OPEN", "HIGH", "LOW", "CLOSE"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["EXPIRY_DT"]  = pd.to_datetime(df["EXPIRY_DT"], format="%d-%b-%Y", errors="coerce")
    df["OPTION_TYP"] = df["OPTION_TYP"].str.strip().str.upper()
    return df

def fetch_option_bhav(trade_date: date, session, headers) -> pd.DataFrame:
    urls = bhav_urls(trade_date)
    for i, url in enumerate(urls):
        try:
            resp = session.get(url, headers=headers, timeout=20)
            if resp.status_code == 403:
                continue
            if resp.status_code != 200:
                continue
            with ZipFile(BytesIO(resp.content)) as z:
                raw = pd.read_csv(z.open(z.namelist()[0]))
            # Detect format by column names
            cols = [c.strip() for c in raw.columns]
            if "TckrSymb" in cols or "XpryDt" in cols:
                df = parse_bhav_new(raw)
            else:
                df = parse_bhav_old(raw)
            if not df.empty:
                return df
        except Exception:
            continue
    return pd.DataFrame()

def get_nearest_expiry(bhav: pd.DataFrame, trade_date: date, expiry_type: str):
    expiries = sorted([
        e for e in bhav["EXPIRY_DT"].dropna().unique()
        if pd.notna(e) and e.date() >= trade_date
    ])
    if not expiries:
        return None
    if expiry_type == "monthly":
        monthly = [e for e in expiries if e.day >= 25]
        return monthly[0] if monthly else expiries[0]
    return expiries[0]

def find_option(bhav, expiry, strike_target, opt_type, gap):
    for adj in [0, 1, -1, 2, -2]:
        strike = strike_target + adj * gap
        rows = bhav[
            (bhav["EXPIRY_DT"]  == expiry) &
            (bhav["STRIKE_PR"]  == strike) &
            (bhav["OPTION_TYP"] == opt_type)
        ]
        if not rows.empty and float(rows.iloc[0]["OPEN"]) > 0:
            return strike, rows.iloc[0]
    return None, None

# ── Exit simulation ───────────────────────────────────────────
#
#  Since Bhav Copy is end-of-day, we use:
#    OPEN  = entry price (10 AM proxy)
#    HIGH  = worst intraday price (used to check SL breach)
#    LOW   = best intraday price  (used to check TGT hit)
#    CLOSE = exit price for time exit (3:20 PM proxy)
#
#  Priority: Leg SL → Cumulative SL → Cumulative TGT → Time Exit

def simulate_exit(ce_entry, pe_entry, ce_row, pe_row,
                  leg_sl_pct, cum_sl, cum_tgt, lot_size, lots):
    unit        = lot_size * lots
    sl_mult     = 1 + leg_sl_pct / 100

    ce_sl_px    = round(ce_entry * sl_mult, 2)
    pe_sl_px    = round(pe_entry * sl_mult, 2)

    ce_high     = float(ce_row["HIGH"])
    pe_high     = float(pe_row["HIGH"])
    ce_low      = float(ce_row["LOW"])
    pe_low      = float(pe_row["LOW"])
    ce_close    = float(ce_row["CLOSE"])
    pe_close    = float(pe_row["CLOSE"])

    ce_exit_px  = None;  ce_reason = None
    pe_exit_px  = None;  pe_reason = None

    # 1. Individual leg SL
    if ce_high >= ce_sl_px:
        ce_exit_px = ce_sl_px;  ce_reason = "Leg SL"
    if pe_high >= pe_sl_px:
        pe_exit_px = pe_sl_px;  pe_reason = "Leg SL"

    # 2. Cumulative SL  (worst case for still-open legs = their HIGH)
    ce_worst = ce_exit_px if ce_exit_px else ce_high
    pe_worst = pe_exit_px if pe_exit_px else pe_high
    cum_pnl_worst = ((ce_entry - ce_worst) + (pe_entry - pe_worst)) * unit
    if cum_pnl_worst <= -cum_sl:
        if not ce_exit_px:
            ce_exit_px = ce_high;   ce_reason = "Cumulative SL"
        if not pe_exit_px:
            pe_exit_px = pe_high;   pe_reason = "Cumulative SL"

    # 3. Cumulative TGT (best case for still-open legs = their LOW)
    ce_best = ce_exit_px if ce_exit_px else ce_low
    pe_best = pe_exit_px if pe_exit_px else pe_low
    cum_pnl_best = ((ce_entry - ce_best) + (pe_entry - pe_best)) * unit
    if cum_pnl_best >= cum_tgt:
        if not ce_exit_px:
            ce_exit_px = ce_low;    ce_reason = "Cumulative TGT"
        if not pe_exit_px:
            pe_exit_px = pe_low;    pe_reason = "Cumulative TGT"

    # 4. Time exit 3:20 PM
    if not ce_exit_px:
        ce_exit_px = ce_close;  ce_reason = "Time Exit 3:20 PM"
    if not pe_exit_px:
        pe_exit_px = pe_close;  pe_reason = "Time Exit 3:20 PM"

    ce_pnl    = round((ce_entry - ce_exit_px) * unit, 2)
    pe_pnl    = round((pe_entry - pe_exit_px) * unit, 2)
    total_pnl = round(ce_pnl + pe_pnl, 2)

    return {
        "ce_sl_px":   round(ce_sl_px,   2),
        "pe_sl_px":   round(pe_sl_px,   2),
        "ce_exit_px": round(ce_exit_px, 2),
        "pe_exit_px": round(pe_exit_px, 2),
        "ce_reason":  ce_reason,
        "pe_reason":  pe_reason,
        "ce_pnl":     ce_pnl,
        "pe_pnl":     pe_pnl,
        "total_pnl":  total_pnl,
    }

# ── Main backtest loop ────────────────────────────────────────

def run_backtest(config: dict) -> pd.DataFrame:
    nifty   = fetch_nifty_ohlc(config["start_date"], config["end_date"])
    days    = list(nifty.index)
    session, headers = make_session()

    records     = []
    skip_log    = defaultdict(int)   # reason → count
    consecutive_403 = 0

    print(f"\nRunning backtest over {len(days)-1} trading days "
          f"({days[1]} to {days[-1]})...\n")

    for i in tqdm(range(1, len(days)), desc="Backtesting", ncols=72):
        today = days[i]
        prev  = days[i - 1]

        pdh        = float(nifty.loc[prev, "High"])
        pdl        = float(nifty.loc[prev, "Low"])
        prev_open  = float(nifty.loc[prev, "Open"])
        prev_close = float(nifty.loc[prev, "Close"])

        today_open  = float(nifty.loc[today, "Open"])
        today_close = float(nifty.loc[today, "Close"])
        today_high  = float(nifty.loc[today, "High"])
        today_low   = float(nifty.loc[today, "Low"])

        ce_strike_target = round_up_strike(pdh,  config["strike_gap"])
        pe_strike_target = round_down_strike(pdl, config["strike_gap"])

        time.sleep(config["sleep_sec"])
        bhav = fetch_option_bhav(today, session, headers)

        if bhav.empty:
            skip_log["no bhav data"] += 1
            consecutive_403 += 1
            # Refresh session after 5 consecutive failures
            if consecutive_403 >= 5:
                tqdm.write(f"  Refreshing NSE session after {consecutive_403} failures...")
                session, headers = make_session()
                consecutive_403  = 0
            continue

        consecutive_403 = 0
        expiry = get_nearest_expiry(bhav, today, config["expiry_type"])
        if expiry is None:
            skip_log["no expiry found"] += 1
            continue

        ce_strike_used, ce_row = find_option(bhav, expiry, ce_strike_target, "CE",
                                             config["strike_gap"])
        pe_strike_used, pe_row = find_option(bhav, expiry, pe_strike_target, "PE",
                                             config["strike_gap"])

        if ce_row is None:
            skip_log["CE strike not found"] += 1
            continue
        if pe_row is None:
            skip_log["PE strike not found"] += 1
            continue

        ce_entry = float(ce_row["OPEN"])
        pe_entry = float(pe_row["OPEN"])

        if ce_entry <= 0 or pe_entry <= 0:
            skip_log["zero entry price"] += 1
            continue

        ex = simulate_exit(
            ce_entry, pe_entry, ce_row, pe_row,
            config["leg_sl_pct"],
            config["cumulative_sl"],
            config["cumulative_tgt"],
            config["lot_size"],
            config["lots"],
        )

        records.append({
            "Date":             today,
            "Day_of_Week":      today.strftime("%A"),
            "Expiry":           expiry.date(),

            "Prev_Date":        prev,
            "Prev_Nifty_Open":  round(prev_open,  2),
            "Prev_Nifty_High":  round(pdh,        2),
            "Prev_Nifty_Low":   round(pdl,        2),
            "Prev_Nifty_Close": round(prev_close, 2),

            "Nifty_Open":       round(today_open,  2),
            "Nifty_High":       round(today_high,  2),
            "Nifty_Low":        round(today_low,   2),
            "Nifty_Close":      round(today_close, 2),

            "PDH_Rounded_CE":   ce_strike_target,
            "PDL_Rounded_PE":   pe_strike_target,
            "CE_Strike_Used":   ce_strike_used,
            "PE_Strike_Used":   pe_strike_used,

            "CE_Entry_Price":   round(ce_entry,      2),
            "CE_SL_Price":      ex["ce_sl_px"],
            "CE_Exit_Price":    ex["ce_exit_px"],
            "CE_Exit_Reason":   ex["ce_reason"],
            "CE_PnL":           ex["ce_pnl"],

            "PE_Entry_Price":   round(pe_entry,      2),
            "PE_SL_Price":      ex["pe_sl_px"],
            "PE_Exit_Price":    ex["pe_exit_px"],
            "PE_Exit_Reason":   ex["pe_reason"],
            "PE_PnL":           ex["pe_pnl"],

            "Total_PnL":        ex["total_pnl"],
            "Result":           "PROFIT" if ex["total_pnl"] >= 0 else "LOSS",
        })

    total_skipped = sum(skip_log.values())
    print(f"\n  Done: {len(records)} trades  |  {total_skipped} days skipped")
    if skip_log:
        print("  Skip reasons:")
        for reason, cnt in sorted(skip_log.items(), key=lambda x: -x[1]):
            print(f"    {reason:<28} : {cnt}")
    return pd.DataFrame(records)

# ── Summary ───────────────────────────────────────────────────

def print_summary(df: pd.DataFrame, config: dict):
    if df.empty:
        print("No trades to analyse.")
        return df

    df = df.copy()
    df["Cumulative_PnL"] = df["Total_PnL"].cumsum()

    total    = len(df)
    wins     = (df["Total_PnL"] > 0).sum()
    losses   = (df["Total_PnL"] < 0).sum()
    total_pl = df["Total_PnL"].sum()
    avg_win  = df[df["Total_PnL"] > 0]["Total_PnL"].mean()
    avg_loss = df[df["Total_PnL"] < 0]["Total_PnL"].mean()
    max_win  = df["Total_PnL"].max()
    max_loss = df["Total_PnL"].min()
    cum      = df["Cumulative_PnL"]
    max_dd   = (cum - cum.cummax()).min()

    reasons = pd.concat([
        df["CE_Exit_Reason"].value_counts(),
        df["PE_Exit_Reason"].value_counts()
    ]).groupby(level=0).sum().sort_values(ascending=False)

    print("\n" + "="*56)
    print("     NIFTY PDH/PDL SHORT STRANGLE — RESULTS")
    print("="*56)
    print(f"  Period          :  {df['Date'].iloc[0]}  to  {df['Date'].iloc[-1]}")
    print(f"  Leg SL          :  {config['leg_sl_pct']}%  per leg")
    print(f"  Cumulative SL   :  Rs {config['cumulative_sl']:,}")
    print(f"  Cumulative TGT  :  Rs {config['cumulative_tgt']:,}")
    print(f"  Time exit       :  {config['exit_hour']}:{config['exit_minute']:02d}")
    print("-"*56)
    print(f"  Total trades    :  {total}")
    print(f"  Win / Loss      :  {wins}W  /  {losses}L  ({wins/total*100:.1f}% win rate)")
    print(f"  Total P&L       :  Rs {total_pl:>12,.0f}")
    print(f"  Avg win         :  Rs {avg_win:>12,.0f}")
    print(f"  Avg loss        :  Rs {avg_loss:>12,.0f}")
    print(f"  Best day        :  Rs {max_win:>12,.0f}")
    print(f"  Worst day       :  Rs {max_loss:>12,.0f}")
    print(f"  Max drawdown    :  Rs {max_dd:>12,.0f}")
    print("-"*56)
    print("  Exit reason breakdown (leg count):")
    for reason, count in reasons.items():
        print(f"    {reason:<24} :  {count}")
    print("="*56)

    # Charts
    fig, axes = plt.subplots(3, 1, figsize=(15, 11))
    fig.suptitle(
        f"Nifty PDH/PDL Short Strangle  ({df['Date'].iloc[0]} to {df['Date'].iloc[-1]})\n"
        f"Leg SL {config['leg_sl_pct']}%  |  "
        f"Cum SL Rs {config['cumulative_sl']:,}  |  "
        f"Cum TGT Rs {config['cumulative_tgt']:,}  |  "
        f"Exit {config['exit_hour']}:{config['exit_minute']:02d}",
        fontsize=11, fontweight="bold"
    )
    dates = pd.to_datetime(df["Date"])

    ax1 = axes[0]
    ax1.plot(dates, df["Cumulative_PnL"], color="#1565c0", linewidth=1.5)
    ax1.fill_between(dates, df["Cumulative_PnL"], 0,
                     where=df["Cumulative_PnL"] >= 0, alpha=0.15, color="#1565c0")
    ax1.fill_between(dates, df["Cumulative_PnL"], 0,
                     where=df["Cumulative_PnL"] <  0, alpha=0.20, color="#c62828")
    ax1.axhline(0, color="gray", linewidth=0.8, linestyle="--")
    ax1.set_title("Cumulative P&L")
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"Rs {x:,.0f}"))
    ax1.grid(True, alpha=0.3)

    ax2 = axes[1]
    bar_colors = ["#2e7d32" if v >= 0 else "#c62828" for v in df["Total_PnL"]]
    ax2.bar(dates, df["Total_PnL"], color=bar_colors, width=1)
    ax2.axhline(0, color="gray", linewidth=0.8, linestyle="--")
    ax2.set_title("Daily P&L")
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"Rs {x:,.0f}"))
    ax2.grid(True, alpha=0.3, axis="y")

    drawdown = df["Cumulative_PnL"] - df["Cumulative_PnL"].cummax()
    ax3 = axes[2]
    ax3.fill_between(dates, drawdown, 0, color="#b71c1c", alpha=0.5)
    ax3.set_title("Drawdown")
    ax3.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"Rs {x:,.0f}"))
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("backtest_chart.png", dpi=150, bbox_inches="tight")
    plt.show()
    print("Chart saved  -->  backtest_chart.png")

    return df

# ── Export CSV ────────────────────────────────────────────────

def export_csv(df: pd.DataFrame):
    df_out = df.copy()
    df_out["Cumulative_PnL"] = df_out["Total_PnL"].cumsum()

    col_order = [
        "Date", "Day_of_Week", "Expiry",
        "Prev_Date",
        "Prev_Nifty_Open", "Prev_Nifty_High", "Prev_Nifty_Low", "Prev_Nifty_Close",
        "Nifty_Open", "Nifty_High", "Nifty_Low", "Nifty_Close",
        "PDH_Rounded_CE", "PDL_Rounded_PE", "CE_Strike_Used", "PE_Strike_Used",
        "CE_Entry_Price", "CE_SL_Price", "CE_Exit_Price", "CE_Exit_Reason", "CE_PnL",
        "PE_Entry_Price", "PE_SL_Price", "PE_Exit_Price", "PE_Exit_Reason", "PE_PnL",
        "Total_PnL", "Cumulative_PnL", "Result",
    ]
    df_out = df_out[[c for c in col_order if c in df_out.columns]]
    df_out.to_csv("backtest_results.csv", index=False)
    print("Trade log saved  -->  backtest_results.csv")
    try:
        from google.colab import files
        files.download("backtest_results.csv")
        files.download("backtest_chart.png")
    except ImportError:
        pass

# ── RUN ───────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 56)
    print("   NIFTY PDH/PDL SHORT STRANGLE BACKTEST")
    print(f"   {CONFIG['start_date']}  to  {CONFIG['end_date']}")
    print(f"   Leg SL    : {CONFIG['leg_sl_pct']}% per leg")
    print(f"   Cum SL    : Rs {CONFIG['cumulative_sl']:,}  (exit all)")
    print(f"   Cum TGT   : Rs {CONFIG['cumulative_tgt']:,}  (exit all)")
    print(f"   Time exit : {CONFIG['exit_hour']}:{CONFIG['exit_minute']:02d}")
    print(f"   Lots: {CONFIG['lots']}  |  Lot size: {CONFIG['lot_size']}")
    print("=" * 56 + "\n")

    results = run_backtest(CONFIG)

    if not results.empty:
        results = print_summary(results, CONFIG)
        export_csv(results)
        print("\nLast 10 trades:")
        preview = [
            "Date", "CE_Strike_Used", "PE_Strike_Used",
            "CE_Entry_Price", "PE_Entry_Price",
            "CE_Exit_Reason", "PE_Exit_Reason",
            "CE_PnL", "PE_PnL", "Total_PnL", "Cumulative_PnL",
        ]
        results["Cumulative_PnL"] = results["Total_PnL"].cumsum()
        print(results[preview].tail(10).to_string(index=False))
    else:
        print("\n  0 trades processed. Possible reasons:")
        print("  1. NSE is blocking requests — try increasing sleep_sec to 1.0 in CONFIG")
        print("  2. VPN active — disable it and retry")
        print("  3. Run during IST market hours for better NSE access")

# ── NOTES ─────────────────────────────────────────────────────
# URL FORMATS:
#   Old (pre-2024): .../DERIVATIVES/YYYY/MMM/fo{DD}{MMM}{YYYY}bhav.csv.zip
#   New (2024+):    .../content/fo/BhavCopy_NSE_FO_0_0_0_{YYYYMMDD}_F_0000.csv.zip
#   Script tries BOTH automatically.
#
# IF STILL GETTING 0 TRADES:
#   - Try running during IST market hours (9 AM - 5 PM)
#   - Increase sleep_sec from 0.3 to 1.0 in CONFIG
#   - Disable VPN if active
#   - NSE occasionally blocks non-Indian IPs
#
# DATA LIMITATION:
#   OPEN price = proxy for 10 AM entry (not exact)
#   HIGH/LOW   = used to detect SL/TGT breach intraday
#   CLOSE      = used for time exit price
#   For exact intraday simulation, paid 1-min data needed.
#
# LOT SIZE: 75 from Sep 2024. Use 50 for dates before Sep 2024.