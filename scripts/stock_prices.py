#!/usr/bin/env python3
"""
Stock Price Updater — GitHub Actions edition
Fetches current prices + 1-day change for tracked biopharma companies
using yfinance and upserts to Supabase `companies` table.
Runs 6 AM ET daily (10:00 UTC), after market open.
"""

import os, json, datetime, time
import requests

# ── Credentials ─────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}


def log(msg):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ── Ticker map: company name → Yahoo Finance ticker ─────────────────────────
# Mapped to companies in the Supabase `companies` table
TICKER_MAP = {
    "Roche":               "RHHBY",
    "AstraZeneca":         "AZN",
    "Sanofi":              "SNY",
    "Regeneron":           "REGN",
    "AbbVie":              "ABBV",
    "Johnson & Johnson":   "JNJ",
    "Pfizer":              "PFE",
    "Amgen":               "AMGN",
    "Bristol Myers Squibb":"BMY",
    "Lilly":               "LLY",
    "Merck":               "MRK",
    "GSK":                 "GSK",
    "Novartis":            "NVS",
    "Takeda":              "TAK",
    "UCB":                 "UCBJY",
    "argenx":              "ARGX",
    "Protagonist":         "PTGX",
    "Prometheus":          "RXDX",
    "Roivant":             "ROIV",
    "Inhibrx":             "INBX",
}


def fetch_prices(tickers):
    """Fetch prices via yfinance. Returns dict: ticker → {price, change_pct}."""
    try:
        import yfinance as yf
    except ImportError:
        log("yfinance not installed — skipping price fetch")
        return {}

    results = {}
    if not tickers:
        return results

    # Batch download for efficiency
    ticker_str = " ".join(tickers)
    log(f"Downloading prices for {len(tickers)} tickers…")
    try:
        data = yf.download(
            ticker_str,
            period="2d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )

        for ticker in tickers:
            try:
                if len(tickers) == 1:
                    closes = data["Close"]
                else:
                    closes = data[ticker]["Close"]

                closes = closes.dropna()
                if len(closes) >= 2:
                    prev  = float(closes.iloc[-2])
                    curr  = float(closes.iloc[-1])
                    chg   = round((curr - prev) / prev * 100, 2) if prev else 0.0
                    results[ticker] = {"price": round(curr, 2), "change_pct": chg}
                elif len(closes) == 1:
                    curr = float(closes.iloc[-1])
                    results[ticker] = {"price": round(curr, 2), "change_pct": 0.0}
            except Exception as e:
                log(f"  Parse error for {ticker}: {e}")
    except Exception as e:
        log(f"yfinance download error: {e}")

    return results


def get_companies():
    """Fetch all companies from Supabase."""
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/companies",
            headers=SB_HEADERS,
            params={"select": "id,name,ticker"},
        )
        return r.json()
    except Exception as e:
        log(f"Companies fetch error: {e}")
        return []


def upsert_price(company_id, ticker, price, change_pct, market_cap=None):
    """Update stock_price and stock_change on the company row, and write a history record."""
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"

    # 1. Patch the live companies row (existing behaviour)
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/companies",
        headers={**SB_HEADERS, "Prefer": "return=minimal"},
        params={"id": f"eq.{company_id}"},
        json={
            "stock_price":       price,
            "stock_change":      change_pct,
            "last_price_update": datetime.datetime.utcnow().isoformat(),
        },
    )
    if r.status_code not in (200, 201, 204):
        log(f"  Update error for company {company_id}: {r.status_code} {r.text[:100]}")
        return False

    # 2. Insert into stock_price_history for trend tracking
    hist_payload = {
        "company_id":    company_id,
        "ticker":        ticker,
        "price_usd":     price,
        "change_1d_pct": change_pct,
        "recorded_at":   now_iso,
        "source":        "yfinance",
    }
    if market_cap is not None:
        hist_payload["market_cap_usd"] = market_cap

    rh = requests.post(
        f"{SUPABASE_URL}/rest/v1/stock_price_history",
        headers={**SB_HEADERS, "Prefer": "return=minimal"},
        json=hist_payload,
        timeout=10,
    )
    if rh.status_code not in (200, 201, 204):
        log(f"  History insert warning for {ticker}: {rh.status_code} {rh.text[:80]}")
        # Non-fatal: the main update already succeeded

    return True


# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log(f"=== Stock Price Updater — {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} ===")

    companies = get_companies()
    if not companies:
        log("No companies found in Supabase — done.")
        raise SystemExit(0)

    log(f"Found {len(companies)} companies in Supabase")

    # Build ticker list from Supabase data (prefer db ticker col, fallback to map)
    ticker_to_company = {}
    for co in companies:
        ticker = co.get("ticker") or TICKER_MAP.get(co["name"])
        if ticker:
            ticker_to_company[ticker] = co
        else:
            log(f"  No ticker for: {co['name']} — skipping")

    if not ticker_to_company:
        log("No tickers to fetch — done.")
        raise SystemExit(0)

    prices = fetch_prices(list(ticker_to_company.keys()))

    updated = 0
    for ticker, co in ticker_to_company.items():
        if ticker in prices:
            p = prices[ticker]
            if upsert_price(co["id"], ticker, p["price"], p["change_pct"], p.get("market_cap")):
                log(f"  {co['name']} ({ticker}): ${p['price']} ({p['change_pct']:+.2f}%)")
                updated += 1
        else:
            log(f"  No price data for {co['name']} ({ticker})")
        time.sleep(0.1)

    log(f"Updated {updated} / {len(ticker_to_company)} companies")
    log("=== Stock prices complete ===")
