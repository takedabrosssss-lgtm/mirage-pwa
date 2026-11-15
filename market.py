"""Public Binance USDⓈ-M data adapter and transparent rule-based scanner.
No private credentials and no order endpoints are used.
"""
from __future__ import annotations
import asyncio, time
from dataclasses import dataclass
from typing import Any
import httpx

@dataclass
class MarketStatus:
    ok: bool = False
    checked_at: float = 0.0
    region: str = "not-set"
    base_url: str = "https://fapi.binance.com"
    message: str = "Not checked yet"
    latency_ms: int | None = None

class BinanceUM:
    def __init__(self, base_url: str, region: str):
        self.base_url = base_url.rstrip("/")
        self.status = MarketStatus(region=region, base_url=self.base_url)
        self._sem = asyncio.Semaphore(6)
        self.symbol_filters: dict[str, dict[str, float]] = {}
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=5.0),
                                        headers={"User-Agent": "MIRAGE-Paper/1.0"})

    async def close(self):
        await self.client.aclose()

    async def get(self, path: str, params: dict | None = None):
        async with self._sem:
            r = await self.client.get(self.base_url + path, params=params)
            if r.status_code in (403, 451):
                self.status.ok = False
                self.status.message = f"Binance denied public API access (HTTP {r.status_code}) from this server region"
                raise RuntimeError(self.status.message)
            r.raise_for_status()
            return r.json()

    async def check(self):
        start = time.perf_counter()
        try:
            await self.get("/fapi/v1/time")
            await self.get("/fapi/v1/exchangeInfo")
            self.status.ok = True
            self.status.message = "Public USDⓈ-M Futures market data reachable"
            self.status.latency_ms = int((time.perf_counter() - start) * 1000)
        except Exception as exc:
            self.status.ok = False
            msg = str(exc)
            self.status.message = msg[:220] or exc.__class__.__name__
            self.status.latency_ms = None
        self.status.checked_at = time.time()
        return self.status

    async def book_mark(self, symbol: str):
        book, mark = await asyncio.gather(
            self.get("/fapi/v1/ticker/bookTicker", {"symbol": symbol}),
            self.get("/fapi/v1/premiumIndex", {"symbol": symbol}),
        )
        return {
            "symbol": symbol, "bid": float(book["bidPrice"]), "ask": float(book["askPrice"]),
            "mark": float(mark["markPrice"]), "last_funding_rate": float(mark["lastFundingRate"]),
            "next_funding_time": int(mark["nextFundingTime"]), "time": int(mark.get("time", book.get("time", 0)))
        }

    async def klines(self, symbol: str, interval: str, limit: int = 120):
        return await self.get("/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit})

    async def tickers(self):
        return await self.get("/fapi/v1/ticker/24hr")

    async def funding_history(self, symbol: str, start_ms: int, end_ms: int):
        return await self.get("/fapi/v1/fundingRate", {"symbol": symbol, "startTime": start_ms,
                                                        "endTime": end_ms, "limit": 100})

    async def universe(self, limit: int = 12):
        info, tickers = await asyncio.gather(self.get("/fapi/v1/exchangeInfo"), self.tickers())
        allowed = set()
        for item in info["symbols"]:
            if not (item.get("status") == "TRADING" and item.get("contractType") == "PERPETUAL"
                    and item.get("quoteAsset") == "USDT"):
                continue
            allowed.add(item["symbol"])
            filters = {f.get("filterType"): f for f in item.get("filters", [])}
            lot = filters.get("LOT_SIZE", {})
            price = filters.get("PRICE_FILTER", {})
            notional = filters.get("MIN_NOTIONAL", filters.get("NOTIONAL", {}))
            self.symbol_filters[item["symbol"]] = {
                "step_size": float(lot.get("stepSize", 0.001)),
                "min_qty": float(lot.get("minQty", 0.001)),
                "min_notional": float(notional.get("notional", notional.get("minNotional", 5))),
                "tick_size": float(price.get("tickSize", 0.01)),
            }
        ranked = [t for t in tickers if t.get("symbol") in allowed]
        ranked.sort(key=lambda t: float(t.get("quoteVolume", 0)), reverse=True)
        return [t["symbol"] for t in ranked[:limit]]


def _ema(values: list[float], period: int) -> float:
    if len(values) < period: return sum(values) / max(1, len(values))
    k = 2 / (period + 1)
    out = sum(values[:period]) / period
    for x in values[period:]: out = x * k + out * (1-k)
    return out

def _rsi(values: list[float], period: int = 14) -> float:
    changes = [values[i] - values[i-1] for i in range(1, len(values))]
    tail = changes[-period:]
    gains = sum(max(0, x) for x in tail) / max(1, period)
    losses = sum(max(0, -x) for x in tail) / max(1, period)
    if losses == 0: return 100.0
    return 100 - 100 / (1 + gains / losses)

def _atr(rows: list[list], period: int = 14) -> float:
    tr = []
    for i in range(1, len(rows)):
        h, l, prev = float(rows[i][2]), float(rows[i][3]), float(rows[i-1][4])
        tr.append(max(h-l, abs(h-prev), abs(l-prev)))
    return sum(tr[-period:]) / max(1, min(period, len(tr)))

def analyze_klines(symbol: str, interval: str, strategy: str, rows: list[list]) -> dict | None:
    if len(rows) < 60: return None
    closes = [float(r[4]) for r in rows[:-1]]  # ignore still-forming candle
    vols = [float(r[5]) for r in rows[:-1]]
    if len(closes) < 55: return None
    price = closes[-1]
    ema20, ema50 = _ema(closes, 20), _ema(closes, 50)
    rsi = _rsi(closes)
    macd = _ema(closes, 12) - _ema(closes, 26)
    prev_macd = _ema(closes[:-1], 12) - _ema(closes[:-1], 26)
    hist = macd - prev_macd
    atr = _atr(rows[:-1])
    avg_vol = sum(vols[-20:]) / 20
    vol_ratio = vols[-1] / avg_vol if avg_vol > 0 else 1
    long_score = 50
    short_score = 50
    if price > ema20 > ema50: long_score += 18
    if price < ema20 < ema50: short_score += 18
    if rsi >= 52 and rsi <= 70: long_score += 12
    if rsi <= 48 and rsi >= 30: short_score += 12
    if hist > 0: long_score += 10
    if hist < 0: short_score += 10
    if vol_ratio >= 1.15:
        if closes[-1] >= closes[-2]: long_score += 8
        else: short_score += 8
    if price > max(closes[-21:-1]): long_score += 8
    if price < min(closes[-21:-1]): short_score += 8
    if atr <= 0 or price <= 0: return None
    side = "LONG" if long_score >= short_score else "SHORT"
    score = max(long_score, short_score)
    entry = price
    distance = max(atr * 1.5, price * 0.002)
    if side == "LONG": stop, tps = entry-distance, [entry+distance, entry+2*distance, entry+3*distance]
    else: stop, tps = entry+distance, [entry-distance, entry-2*distance, entry-3*distance]
    return {"symbol": symbol, "interval": interval, "strategy": strategy, "side": side,
            "score": min(100, score), "grade": "S" if score >= 92 else "A" if score >= 80 else "B",
            "entry": entry, "stop": stop, "tps": tps, "rsi": rsi, "atr": atr,
            "ema20": ema20, "ema50": ema50, "volume_ratio": vol_ratio,
            "created_at": int(time.time())}

async def scan_market(api: BinanceUM, symbols_limit: int = 10):
    symbols = await api.universe(symbols_limit)
    jobs = []
    mapping = [("15m", "SCALPING"), ("1h", "INTRADAY"), ("4h", "SWING"), ("1d", "POSITION")]
    async def one(symbol, interval, strategy):
        try:
            rows = await api.klines(symbol, interval, 100)
            return analyze_klines(symbol, interval, strategy, rows)
        except Exception:
            return None
    for symbol in symbols:
        for interval, strategy in mapping:
            jobs.append(one(symbol, interval, strategy))
    results = await asyncio.gather(*jobs)
    return [r for r in results if r and r["score"] >= 80]
