"""
Static description of the Stock Price Refresh pipeline
(.github/workflows/daily-stock-prices.yml).

Documents what stock_prices.py does: fetching current prices and 1-day change
for tracked biopharma companies via yfinance, then patching the live companies
row and inserting a history record for trend tracking.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "stock_prices",
    "workflow_name": "Stock Price Refresh",
    "workflow_file": ".github/workflows/daily-stock-prices.yml",
    "schedule": "Daily 14:00 UTC (10:00 AM ET) — after US market open, so intraday prices are available",
    "entrypoint": "scripts/sync/stock_prices.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Daily market data refresh that fetches current stock prices and 1-day "
        "percentage change for every tracked public biopharma company, then writes "
        "two records per company: a patch to the live `companies` row "
        "(`stock_price`, `stock_change`, `last_price_update`) for instant dashboard "
        "display, and an insert into `stock_price_history` for trend tracking. "
        "Uses `yfinance` for batch price download. Companies without a `ticker` in "
        "the database fall back to a hard-coded `TICKER_MAP`; companies with neither "
        "are skipped and logged. The script is a single-file, no-LLM, no-CT.gov "
        "workflow — purely market data plumbing."
    ),
    "dot": r"""
digraph {
    rankdir=TB
    bgcolor="transparent"
    fontcolor="#e8ecf2"

    node [
        shape=box,
        style="rounded,filled",
        fillcolor="#dbe9fb",
        color="#5b8def",
        fontcolor="#111827",
        fontname="Helvetica",
        fontsize=12,
        margin="0.18,0.12"
    ]

    edge [
        color="#5b6b7d",
        fontcolor="#e8ecf2",
        fontname="Helvetica",
        fontsize=10,
        arrowsize=0.8
    ]

    entry [
        label="stock_prices.py\n(entrypoint - __main__)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    companies_in [
        label="Supabase\ncompanies\n(id, name, ticker - read all)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    ticker_map [
        label="TICKER_MAP\n(hard-coded fallback\n~20 biopharma tickers)",
        fillcolor="#f3f0e0",
        color="#9a8a3b",
        fontcolor="#111827",
        fontsize=11
    ]

    yfinance [
        label="yfinance\nbatch download\n(2d period, 1d interval)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    subgraph cluster_loop {
        label="Per company with a ticker"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        upsert_price [label="upsert_price()\npatch companies row\n+ insert history record"]
    }

    companies_out [
        label="Supabase\ncompanies\n(stock_price, stock_change,\nlast_price_update patched)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    history_out [
        label="Supabase\nstock_price_history\n(price_usd, change_1d_pct,\nrecorded_at, source inserted)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    stdout [
        label="stdout\nper-company price log\n(name, ticker, price, change%)",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> companies_in [label="  get_companies()", style="bold", color="#c9890a", fontcolor="#c9890a"]
    companies_in -> ticker_map [label="  fallback if no ticker\nin db"]
    ticker_map -> yfinance [label="  ticker list"]
    companies_in -> yfinance [label="  ticker list\n(if in db)", style="bold", color="#c9890a", fontcolor="#c9890a"]
    yfinance -> upsert_price [label="  price + change_pct per ticker"]
    upsert_price -> companies_out [label="  sb_patch", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    upsert_price -> history_out [label="  sb_post", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    upsert_price -> stdout [label="  logs each company"]
}
""",
    "io_dot": r"""
digraph {
    rankdir=LR
    bgcolor="transparent"
    fontcolor="#e8ecf2"

    node [
        shape=box,
        style="rounded,filled",
        fontname="Helvetica",
        fontsize=11,
        margin="0.16,0.1"
    ]

    edge [
        color="#5b6b7d",
        fontcolor="#e8ecf2",
        fontname="Helvetica",
        fontsize=10,
        arrowsize=0.8
    ]

    subgraph cluster_in {
        label="Inputs - what comes in, and from where"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        sb_in [label="Supabase\ncompanies (id, name, ticker)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        yf_in [label="yfinance\n(Yahoo Finance API)\nbatch 2-day OHLCV", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Stock Price\nRefresh",
        shape=ellipse,
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827",
        fontsize=12
    ]

    subgraph cluster_out {
        label="Outputs - what goes out, and to where"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        companies_out [label="Supabase\ncompanies\n(stock_price, stock_change,\nlast_price_update)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        history_out [label="Supabase\nstock_price_history\n(price_usd, change_1d_pct,\nrecorded_at, source)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\nper-company log", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sb_in -> pipeline
    yf_in -> pipeline
    pipeline -> companies_out
    pipeline -> history_out
    pipeline -> stdout_out
}
""",
    "io": {
        "reads": [
            {
                "name": "companies",
                "kind": "Supabase table",
                "via": "get_companies() → _db.sb_get('companies', {'select': 'id,name,ticker'})",
                "desc": (
                    "Fetches all company rows with just the three fields needed to build "
                    "the ticker-to-company map: `id` (for the downstream PATCH), `name` "
                    "(for fallback lookup in `TICKER_MAP`), and `ticker` (stored in the "
                    "database if previously set). Companies without either a `ticker` "
                    "column value or a matching name in `TICKER_MAP` are logged as "
                    "'No ticker for X — skipping' and excluded from the download."
                ),
                "scope": (
                    "One query, all rows, narrow column projection. Typically 50–150 "
                    "company rows. No filtering — every company in the catalog is "
                    "checked for a ticker."
                ),
            },
            {
                "name": "yfinance (Yahoo Finance API)",
                "kind": "External library / API",
                "via": "fetch_prices(tickers) → yf.download(ticker_str, period='2d', interval='1d')",
                "desc": (
                    "Batch-downloads 2 days of daily OHLCV data for all tickers in one "
                    "call via `yf.download()` with `group_by='ticker'` and "
                    "`auto_adjust=True`. The 2-day window provides today's close and "
                    "yesterday's close — enough to compute the 1-day percentage change. "
                    "For single-ticker runs (when only one company has a ticker), "
                    "the DataFrame structure differs (`data['Close']` instead of "
                    "`data[ticker]['Close']`) and is handled as a special case."
                ),
                "scope": (
                    "One `yf.download()` call per run, regardless of the number of "
                    "tickers. Tickers are space-joined into a single string. "
                    "Per-ticker parse errors are caught and logged without aborting "
                    "the run — a bad ticker for one company doesn't block updates for "
                    "the others."
                ),
            },
        ],
        "cleaning": (
            "**Two fallback layers prevent missing tickers from crashing the run.** "
            "First, the `ticker` column in `companies` is preferred; if absent, "
            "`TICKER_MAP` is checked by exact company name. If neither matches, the "
            "company is skipped. "
            "**The yfinance download is wrapped in a broad try/except**: a failed bulk "
            "download returns an empty dict, so no per-company writes occur — but the "
            "script exits cleanly rather than with an unhandled exception. "
            "**Per-ticker parse errors** (malformed DataFrame shape for that ticker) "
            "are caught individually and logged, so one bad ticker doesn't block "
            "others. "
            "A 0.1-second sleep between `upsert_price()` calls is the only rate-limiting "
            "— yfinance is client-side and the Supabase REST API is the limiting factor."
        ),
        "writes": [
            {
                "name": "companies",
                "kind": "Supabase table",
                "via": "upsert_price() → _db.sb_patch('companies', {stock_price, stock_change, last_price_update}, {id: eq.<company_id>})",
                "desc": (
                    "Patches three columns on the matching `companies` row: "
                    "`stock_price` (current close in USD, rounded to 2 dp), "
                    "`stock_change` (1-day percentage change, rounded to 2 dp), and "
                    "`last_price_update` (current UTC timestamp as ISO string). "
                    "This is the live-data field the dashboard reads for the "
                    "market-data panel alongside each company's profile."
                ),
                "scope": (
                    "One PATCH per company with a resolved ticker and a downloaded "
                    "price. Typically 15–25 companies per run. The patch is "
                    "non-destructive — only the three price fields are touched."
                ),
            },
            {
                "name": "stock_price_history",
                "kind": "Supabase table",
                "via": "upsert_price() → _db.sb_post('stock_price_history', {company_id, ticker, price_usd, change_1d_pct, recorded_at, source})",
                "desc": (
                    "Inserts one history record per company per run: `company_id`, "
                    "`ticker`, `price_usd`, `change_1d_pct`, `recorded_at` (UTC ISO), "
                    "and `source='yfinance'`. If `market_cap` was available it is "
                    "included as `market_cap_usd`. The history table accumulates one "
                    "row per company per day and is used for trend charting. "
                    "A failed insert here is non-fatal — logged as a warning, "
                    "but the main `companies` patch is not rolled back."
                ),
                "scope": (
                    "One INSERT per company per run. Accumulates over time — "
                    "no upsert/dedup, so re-running on the same day produces a "
                    "duplicate history record (acceptable for trend data)."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Helpers",
            "note": "Three functions defined at module level, called from the __main__ block.",
            "groups": [
                [
                    {
                        "function": "log(msg)",
                        "lines": 3,
                        "desc": (
                            "Prints a timestamped log line to stdout using the current UTC "
                            "time formatted as `[HH:MM:SS]`. Used throughout for progress "
                            "tracking in the GitHub Actions log."
                        ),
                    }
                ],
                [
                    {
                        "function": "fetch_prices(tickers)",
                        "lines": 48,
                        "desc": (
                            "Imports `yfinance` at call time (graceful ImportError fallback "
                            "if not installed). Calls `yf.download()` with all tickers in "
                            "one batch, `period='2d'`, `interval='1d'`, `auto_adjust=True`, "
                            "`threads=True`. Iterates each ticker to extract `closes`, "
                            "computes 1-day percentage change from `iloc[-2]` and `iloc[-1]`, "
                            "and builds a `{ticker: {price, change_pct}}` dict. "
                            "Single-ticker runs handled as a special case (flat DataFrame). "
                            "Returns an empty dict on any download error."
                        ),
                    }
                ],
                [
                    {
                        "function": "get_companies()",
                        "lines": 3,
                        "desc": (
                            "Fetches all company rows from Supabase selecting only "
                            "`id`, `name`, and `ticker` — the minimum needed to build "
                            "the ticker-to-company map."
                        ),
                    },
                    {
                        "function": "upsert_price(company_id, ticker, price, change_pct, market_cap=None)",
                        "lines": 29,
                        "desc": (
                            "Two-write function: first patches `stock_price`, `stock_change`, "
                            "and `last_price_update` on the `companies` row via `_db.sb_patch()`. "
                            "Then inserts a `stock_price_history` record via `_db.sb_post()`. "
                            "The history insert failure is non-fatal — a warning is logged but "
                            "the function returns True regardless, since the live price "
                            "update already succeeded."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main block",
            "note": "No main() function — execution logic lives directly in the __main__ guard.",
            "groups": [
                [
                    {
                        "function": "__main__ block",
                        "lines": 38,
                        "desc": (
                            "Logs the run header, calls `get_companies()`, checks for an empty "
                            "result (exits cleanly). Builds `ticker_to_company` by preferring "
                            "the database `ticker` column, falling back to `TICKER_MAP` by "
                            "name. Calls `fetch_prices()` with the full ticker list. "
                            "Iterates `ticker_to_company` — for each ticker with a price, "
                            "calls `upsert_price()` and logs the result; tickers without "
                            "a price are logged as 'No price data'. Sleeps 0.1 s between "
                            "writes. Logs a final 'Updated N / M companies' summary."
                        ),
                    }
                ],
            ],
        },
    ],
}
