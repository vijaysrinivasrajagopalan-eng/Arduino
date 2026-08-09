
from urllib import response

import yfinance as yf
import pandas as pd
from fredapi import Fred
import os
import requests
from bs4 import BeautifulSoup

# ── FRED API key — set as environment variable ────────────────────────────────
# Export in your terminal before running:
#   export FRED_API_KEY="your_key_here"
# Or create a .env file and load with python-dotenv
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")


# ═════════════════════════════════════════════════════════════════════════════
# ← YOUR CODE — GOLD PRICE
# ═════════════════════════════════════════════════════════════════════════════
def get_gold_price() -> float:
    url = "https://www.kitco.com/charts/gold"  # Replace with a valid gold price website
    # Send a GET request to the website
    response = requests.get(url)
    # Check if the request was successful
    if response.status_code == 200:
    # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
    
        # Find the element containing the gold price (update the selector based on the website's structure)
    gold_price = soup.find('span', class_='TickerOverlay_pricePill__2zn5G')
    # ── STUB — replace with your scraper ──────────────────────────────────
    return float(gold_price.text.strip().replace(',', ''))  # Must return float: gold price in USD per troy ounce.
    # ── END STUB ──────────────────────────────────────────────────────────


# ═════════════════════════════════════════════════════════════════════════════
# ← YOUR CODE — OIL PRICE (Brent crude)
# ═════════════════════════════════════════════════════════════════════════════
def get_oil_price() -> float:
    """
    Return current Brent crude oil price in USD per barrel as a float.

    If you already have an oil scraper — plug it in here.
    If not — the fallback below uses yfinance (BZ=F ticker).
    Uncomment the fallback and delete the raise if you want automatic fetching.
    """
    # ── FALLBACK via yfinance — uncomment if you don't have a scraper ─────
    ticker = yf.Ticker("BZ=F")
    hist   = ticker.history(period="2d")
    if hist.empty:
        raise ValueError("Oil price fetch failed — BZ=F returned empty data")
    return float(hist["Close"].iloc[-1])
    # ── END FALLBACK ──────────────────────────────────────────────────────

    # ── STUB — replace with your scraper if you have one ──────────────────
    # raise NotImplementedError(
    #     "Replace get_oil_price() in data_sources.py with your scraper. "
    #     "Must return float: Brent crude in USD per barrel."
    # )
    # ── END STUB ──────────────────────────────────────────────────────────


# ═════════════════════════════════════════════════════════════════════════════
# READY TO RUN — VIX
# ═════════════════════════════════════════════════════════════════════════════
def get_vix() -> float:
    """
    Returns current VIX level from CBOE via Yahoo Finance.
    Ticker: ^VIX
    """
    ticker = yf.Ticker("^VIX")
    hist   = ticker.history(period="2d")
    if hist.empty:
        raise ValueError("VIX fetch failed — ^VIX returned empty data")
    return float(hist["Close"].iloc[-1])


# ═════════════════════════════════════════════════════════════════════════════
# READY TO RUN — YIELD CURVE (10yr minus 2yr)
# ═════════════════════════════════════════════════════════════════════════════
def get_yield_curve() -> float:
    """
    Returns US yield curve spread: 10-year minus 2-year Treasury yield.
    Positive = normal. Negative = inverted = recession warning.

    Tickers:
        ^TNX = 10-year US Treasury yield
        ^IRX = 13-week T-bill (proxy for 2yr when 2yr data unavailable)

    Note: Yahoo Finance doesn't have a clean 2yr ticker.
    We use FRED for the 2yr if API key is available, else use ^IRX as proxy.
    """
    # 10yr yield
    t10  = yf.Ticker("^TNX")
    h10  = t10.history(period="2d")
    if h10.empty:
        raise ValueError("10yr Treasury fetch failed")
    y10  = float(h10["Close"].iloc[-1])

    # 2yr yield — prefer FRED, fall back to ^IRX proxy
    if FRED_API_KEY:
        try:
            fred = Fred(api_key=FRED_API_KEY)
            series = fred.get_series("DGS2", observation_start="2025-01-01")
            y2 = float(series.dropna().iloc[-1])
        except Exception:
            y2 = _get_irx_proxy()
    else:
        y2 = _get_irx_proxy()

    return round(y10 - y2, 4)


def _get_irx_proxy() -> float:
    """13-week T-bill rate as 2yr proxy when FRED key unavailable."""
    t2  = yf.Ticker("^IRX")
    h2  = t2.history(period="2d")
    if h2.empty:
        raise ValueError("2yr Treasury proxy fetch failed")
    return float(h2["Close"].iloc[-1])


# ═════════════════════════════════════════════════════════════════════════════
# READY TO RUN — TED SPREAD
# ═════════════════════════════════════════════════════════════════════════════
def get_ted_spread() -> float:
    """
    TED Spread = 3-month LIBOR/SOFR rate minus 3-month T-bill rate.
    Measures banking system stress. Normal < 0.5%. Crisis > 1%.

    Uses FRED series:
        DTB3    = 3-month T-bill rate
        SOFR    = Secured Overnight Financing Rate (LIBOR replacement)

    Requires FRED_API_KEY environment variable.
    Set it with: export FRED_API_KEY="your_key"
    """
    if not FRED_API_KEY:
        raise EnvironmentError(
            "FRED_API_KEY not set. "
            "Get a free key at fred.stlouisfed.org and set: "
            "export FRED_API_KEY='your_key'"
        )

    fred   = Fred(api_key=FRED_API_KEY)
    start  = "2025-01-01"

    tbill  = fred.get_series("DTB3",  observation_start=start).dropna()
    sofr   = fred.get_series("SOFR",  observation_start=start).dropna()

    if tbill.empty or sofr.empty:
        raise ValueError("TED spread data unavailable from FRED")

    ted = float(sofr.iloc[-1]) - float(tbill.iloc[-1])
    return round(ted, 4)


# ═════════════════════════════════════════════════════════════════════════════
# READY TO RUN — USD/INR
# ═════════════════════════════════════════════════════════════════════════════
def get_usdinr() -> dict:
    """
    Returns dict with current rate and 30-day rate of change.
    Rate of change matters more than absolute level for crisis detection.

    Returns:
        {
            "rate"       : float  — current USD/INR spot rate
            "change_30d" : float  — % change over last 30 days
            "change_5d"  : float  — % change over last 5 days (velocity)
        }
    """
    ticker = yf.Ticker("USDINR=X")
    hist   = ticker.history(period="35d")

    if hist.empty or len(hist) < 5:
        raise ValueError("USD/INR fetch failed — insufficient data")

    current   = float(hist["Close"].iloc[-1])
    price_30d = float(hist["Close"].iloc[0])
    price_5d  = float(hist["Close"].iloc[-5])

    return {
        "rate"       : round(current, 4),
        "change_30d" : round(((current - price_30d) / price_30d) * 100, 3),
        "change_5d"  : round(((current - price_5d)  / price_5d)  * 100, 3),
    }
