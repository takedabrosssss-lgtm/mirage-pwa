# MIRAGE — Futures Paper Trading PWA

**Delivery status:** runnable first implementation for four private accounts. Paper trading only. The project contains no exchange API keys, private exchange endpoints, withdrawals, or real order placement.

## What is included

- Mobile-first dark MIRAGE interface based on the approved visual direction: black/graphite surfaces, white typography, geometric mark, rounded cards, restrained green performance accents, responsive layout and reduced-motion setting.
- Installable PWA shell for Android (manifest, service worker, app icons).
- Four pre-created accounts; public registration is not implemented. Passwords are PBKDF2-SHA256 hashes, sessions are server-side, and account data is scoped by user ID.
- Shared server-side scanner. Each account has its own balance, preferences, positions, history, risk settings and optional automatic paper-trading switch.
- Binance USDⓈ-M Futures public market data only: REST endpoints plus public WebSocket Mark Price / book ticker streams. Region access is checked; Spot is never used as a fallback.
- Long and Short paper positions, isolated-margin accounting, score-based 3x / 5x / 8x leverage (hard cap 8x), stop-distance sizing, risk caps, symbol quantity/price-step and minimum-notional filters from Futures exchangeInfo.
- Simulated bid/ask fills, configurable taker commission and slippage, spread-aware risk sizing, public funding-history reconciliation, partial TP1/TP2/TP3 closes (50% / 30% / remainder), break-even stop after TP1, Mark Price triggers, and estimated liquidation guard.
- PHANTOM status and audit events. New entries are blocked if REST market access is denied, quotes are stale, spread is too wide, or risk/margin checks fail.
- Publisher-attributed RSS news cards.
- Russian / English preference per account.

## Important boundaries — read before relying on it

This is a runnable first build, **not a finished production trading platform**. The scanner is a transparent rule-based technical model (EMA trend, RSI, MACD momentum proxy, ATR and volume participation), not a trained AI model. Full market-structure analysis (BOS/CHoCH, order blocks, FVG, liquidity), full multi-timeframe confluence, macroeconomic calendar, automated AI news-impact classification, push notifications, password-reset/admin UI, MFE/MAE tracking, strategy backtesting/research, and exact Binance maintenance-margin bracket liquidation are not implemented yet. The liquidation price is explicitly approximate.

**Stop/TP timing:** when the Binance public WebSocket is reachable, open positions are evaluated on incoming Mark Price / book updates, nominally around one-second cadence. REST polling is a slower fallback. This is a simulator, not an exchange-native stop order: prices can move between updates, network delivery can stall, and the app cannot protect a position while the market feed is unavailable. PHANTOM must be checked before interpreting results.

**Execution-cost assumptions:** default taker commission is 0.05% per side; simulated slippage is 2 bps. Both are assumptions, not fetched from a user's Binance account. Spread is derived from bid/ask and is not added again as a separate fee. The simulator does not reproduce order-book depth, queue priority, market impact, fee discounts, or account-specific fee tiers. Funding is reconciled from public funding history; if that endpoint is unavailable, the event is logged and reconciliation is delayed rather than fabricated.

**Leverage:** leverage affects initial margin and liquidation proximity, not the allowed cash-risk budget. Leverage is selected from signal quality: score 80–85 => 3x, 86–91 => 5x, 92+ => 8x. The simulator blocks a stop placed beyond its estimated liquidation threshold. Exchange maintenance brackets and exact liquidation fees are not reproduced.

**TP behaviour:** Mark Price triggers targets. Simulated exit fills use current Bid/Ask plus slippage. TP1 closes 50% of original quantity and moves the remaining stop to entry; TP2 closes 30% of original quantity; TP3 closes the remainder. If the Mark Price touches the stop, the remaining position is closed.

## Project layout

The runtime is intentionally compact:

- `app.py` — FastAPI application, authentication, account data, API routes and background loops.
- `trading.py` — deterministic paper-execution calculations.
- `market.py` — Binance USDⓈ-M public data adapter and rule-based scanner.
- `news.py` — RSS news adapter.
- `static/` — PWA interface, styles, manifest, service worker and icons.
- `tests/` — deterministic trading calculation tests.

`app.py` is the only application entry point. Do not run a second engine or a second web process against the same account database.

## Local run

Requirements: Python 3.11+ (Python 3.12 recommended).

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Windows PowerShell: Copy-Item .env.example .env
pytest -q
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1
```

Open `http://127.0.0.1:8000`.

Development-only accounts (change before sharing the app):

| Login | Password |
|---|---|
| `owner` | `ChangeMe-Owner-2026!` |
| `user2` | `ChangeMe-User2-2026!` |
| `user3` | `ChangeMe-User3-2026!` |
| `user4` | `ChangeMe-User4-2026!` |

Local SQLite data is stored in `data/mirage.db`. It is ignored by Git. Do not upload `.env`, database files, or real passwords.

## Publish for four users (manual GitHub + Render setup)

This project has **not** been deployed by this delivery. The following are publication instructions, not a claim that a host or region has already been tested.

### 1. Create a new private GitHub repository

1. Create a new private repository, for example `mirage-pwa`. Do not overwrite the old MIRAGE / Trading Intelligence repository.
2. Extract this ZIP on your computer.
3. Upload the contents of the extracted `MIRAGE` folder to the root of the new repository (not the ZIP file itself).
4. Do not upload `.env`, `data/`, `*.db`, or `*.sqlite*`.

### 2. Create persistent PostgreSQL storage

The production app requires PostgreSQL; it deliberately refuses SQLite in production because many free hosts have ephemeral filesystems. Create a PostgreSQL database with a provider of your choice (for example, a free-tier managed PostgreSQL provider if its current terms fit). Copy its connection string. Free-tier quotas, inactivity behaviour, backups and expiry policies change, so check the provider's current dashboard and terms before relying on it.

### 3. Create the Render web service

1. In Render, choose **New → Web Service**, connect GitHub and select the new `mirage-pwa` repository.
2. Choose a server region only after checking current provider availability. Start by testing a European region close to the users, but do not assume that proximity guarantees Binance API access. A previous Oregon-hosted test returned HTTP 451; the exact chosen region must be checked again.
3. Runtime: **Python**.
4. Build command: `pip install -r requirements.txt`.
5. Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1`.
6. Health check path: `/api/health`.
7. Add the environment variables below before deploying.

Required environment variables (set in the host dashboard, never commit secrets):

```text
APP_ENV=production
APP_SECRET=<random secret of at least 32 characters>
DATABASE_URL=<managed PostgreSQL connection string>
MARKET_REGION_LABEL=<chosen-market-access-region-label>
SERVER_REGION_LABEL=<actual-host-region-label>
BINANCE_FUTURES_BASE_URL=https://fapi.binance.com
BINANCE_FUTURES_WS_URL=wss://fstream.binance.com/market/stream?streams=!markPrice@arr@1s/!bookTicker/!ticker@arr
SCAN_UNIVERSE_SIZE=10
LOG_LEVEL=INFO
BOOTSTRAP_USERS_JSON=[{"username":"owner","password":"REPLACE_WITH_UNIQUE_PASSWORD_1","role":"admin","language":"ru"},{"username":"user2","password":"REPLACE_WITH_UNIQUE_PASSWORD_2","language":"ru"},{"username":"user3","password":"REPLACE_WITH_UNIQUE_PASSWORD_3","language":"ru"},{"username":"user4","password":"REPLACE_WITH_UNIQUE_PASSWORD_4","language":"ru"}]
```

Use four different passwords of at least 12 characters. Enter `BOOTSTRAP_USERS_JSON` as a single-line JSON value. The bootstrap variable is used only when the database has no users; it does not enable public registration. Once the database is initialized, changing this variable does not reset account passwords.

### 4. Verify region access before opening paper positions

After deployment, open `https://YOUR-SERVICE.onrender.com/api/health` and inspect:

- `market.ok` and `market.message` — public USDⓈ-M Futures REST access from the server region.
- `market.region` — the configured market-region label (it is a label, not independent geolocation proof).
- `server_region` — the region label you configured for the host.
- `engine.websocket.connected` — whether the public Mark Price / book stream is connected.

HTTP 403/451, timeouts, or a disconnected stream mean the feed is unavailable or degraded. In that state, new entries are blocked. Do not switch to Spot. If the chosen region is blocked, test another provider-permitted region and verify it again. The app does not automatically route around regional restrictions.

### 5. Install on Android

1. Open the deployed HTTPS URL in Chrome on each Android phone.
2. Sign in with that person's separate account.
3. Open Chrome's menu and choose **Install app** or **Add to Home screen**.
4. Repeat on the other phones using their own logins.

## Free-host limitation

A free web service may sleep when idle. If the server sleeps, its scanner and position manager stop running; the PWA cannot keep server-side trading logic alive while the phone is closed. This first publication setup is for interface and paper-engine validation while the service is awake, **not unattended 24/7 position management**. For continuous scanning and SL/TP management, an always-on server and persistent database will eventually be required. Do not enable unattended auto-paper trading on a sleeping service and assume it is monitoring positions continuously.

## Validation performed for this delivery

- Python syntax compilation for the runtime modules.
- `pytest -q`: 13 deterministic tests passed (trade fills, fees, funding direction, risk sizing, leverage, stop/target rules, quantity/price-step rounding, liquidation estimate).
- Local FastAPI smoke test: login, authenticated `/api/auth/me`, dashboard and health endpoints returned HTTP 200.

The smoke test used a temporary local database. It did **not** verify external Binance connectivity, production PostgreSQL, hosting-region access, or 24/7 operation.
