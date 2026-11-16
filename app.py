from __future__ import annotations
import os, json, time, asyncio, secrets, hashlib, hmac, logging, statistics
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import websockets
from sqlalchemy import create_engine, String, Integer, Float, Text, ForeignKey, select, desc
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session as DBSession

from market import BinanceUM, scan_market, analyze_klines
from news import NewsService
from trading import (Quote, entry_fill, exit_fill, calculate_position_size, gross_pnl, fee,
                     funding_cost, leverage_for_score, validate_trade_plan, target_quantity,
                     approximate_liquidation_price, round_to_step)

ROOT = Path(__file__).parent
STATIC = ROOT / "static"
LOG = logging.getLogger("mirage")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
APP_ENV = os.getenv("APP_ENV", "development").lower()
APP_SECRET = os.getenv("APP_SECRET", "")
if APP_ENV == "production" and len(APP_SECRET) < 32:
    raise RuntimeError("APP_SECRET must be a random secret of at least 32 characters in production")
if not APP_SECRET:
    APP_SECRET = secrets.token_urlsafe(48)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'mirage.db'}")
if APP_ENV == "production" and DATABASE_URL.startswith("sqlite"):
    raise RuntimeError("Production requires persistent PostgreSQL via DATABASE_URL; SQLite on free web filesystems is ephemeral")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
os.makedirs(ROOT / "data", exist_ok=True)
engine = create_engine(DATABASE_URL, pool_pre_ping=True,
                       connect_args={"check_same_thread":False} if DATABASE_URL.startswith("sqlite") else {})
DBLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20), default="user")
    language: Mapped[str] = mapped_column(String(5), default="ru")
    balance: Mapped[float] = mapped_column(Float, default=10000.0)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda:int(time.time()))

class UserSession(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[int] = mapped_column(Integer, index=True)

class UserSettings(Base):
    __tablename__ = "user_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")

class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    side: Mapped[str] = mapped_column(String(8))
    strategy: Mapped[str] = mapped_column(String(20))
    interval: Mapped[str] = mapped_column(String(10), default="15m")
    score: Mapped[int] = mapped_column(Integer, default=80)
    grade: Mapped[str] = mapped_column(String(3), default="A")
    entry_price: Mapped[float] = mapped_column(Float)
    initial_qty: Mapped[float] = mapped_column(Float)
    remaining_qty: Mapped[float] = mapped_column(Float)
    leverage: Mapped[int] = mapped_column(Integer)
    initial_margin: Mapped[float] = mapped_column(Float)
    risk_amount: Mapped[float] = mapped_column(Float)
    stop_price: Mapped[float] = mapped_column(Float)
    targets_json: Mapped[str] = mapped_column(Text)
    target_hits_json: Mapped[str] = mapped_column(Text, default="[]")
    entry_fee: Mapped[float] = mapped_column(Float, default=0.0)
    exit_fee_total: Mapped[float] = mapped_column(Float, default=0.0)
    gross_realized: Mapped[float] = mapped_column(Float, default=0.0)
    funding_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(12), default="OPEN", index=True)
    opened_at: Mapped[int] = mapped_column(Integer, index=True)
    closed_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_funding_time: Mapped[int] = mapped_column(Integer, default=0)
    close_reason: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    side: Mapped[str] = mapped_column(String(8))
    strategy: Mapped[str] = mapped_column(String(20))
    interval: Mapped[str] = mapped_column(String(10))
    score: Mapped[int] = mapped_column(Integer)
    grade: Mapped[str] = mapped_column(String(3))
    entry: Mapped[float] = mapped_column(Float)
    stop: Mapped[float] = mapped_column(Float)
    targets_json: Mapped[str] = mapped_column(Text)
    indicators_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[int] = mapped_column(Integer, index=True)
    state: Mapped[str] = mapped_column(String(16), default="ACTIVE")

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(12))
    message: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[int] = mapped_column(Integer, default=lambda:int(time.time()), index=True)

Base.metadata.create_all(engine)

DEFAULT_SETTINGS = {
    "language":"ru", "auto_trade":False, "risk_pct":1.0, "max_total_risk_pct":3.0,
    "max_positions":3, "taker_fee":0.0005, "slippage_bps":2.0,
    "max_spread_bps":12.0, "strategies":["SCALPING","INTRADAY","SWING","POSITION"],
    "notifications":True, "reduced_motion":False, "sound":False
}

def _pbkdf(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310000)
    return "pbkdf2_sha256$310000$" + salt.hex() + "$" + digest.hex()

def _verify(password: str, stored: str) -> bool:
    try:
        _, rounds, salt_hex, digest_hex = stored.split("$")
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)).hex()
        return hmac.compare_digest(check, digest_hex)
    except Exception: return False

def add_audit(db, category, severity, message, user_id=None):
    db.add(AuditEvent(user_id=user_id, category=category, severity=severity,
                      message=message[:500], created_at=int(time.time())))

def get_settings(db, user_id: int) -> dict:
    row = db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if not row:
        row = UserSettings(user_id=user_id, payload=json.dumps(DEFAULT_SETTINGS))
        db.add(row); db.commit(); db.refresh(row)
    try: out = {**DEFAULT_SETTINGS, **json.loads(row.payload)}
    except Exception: out = DEFAULT_SETTINGS.copy()
    return out

def put_settings(db, user_id: int, data: dict):
    row = db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if not row:
        row = UserSettings(user_id=user_id, payload="{}")
        db.add(row)
    row.payload = json.dumps(data)
    db.commit()

def bootstrap_users():
    with DBLocal() as db:
        if db.scalar(select(User.id).limit(1)) is not None: return
        raw = os.getenv("BOOTSTRAP_USERS_JSON", "").strip()
        if raw:
            users = json.loads(raw)
            if not isinstance(users, list) or len(users) != 4:
                raise RuntimeError("BOOTSTRAP_USERS_JSON must contain exactly four user objects")
        elif APP_ENV == "development":
            users = [
                {"username":"owner","password":"ChangeMe-Owner-2026!","role":"admin"},
                {"username":"user2","password":"ChangeMe-User2-2026!"},
                {"username":"user3","password":"ChangeMe-User3-2026!"},
                {"username":"user4","password":"ChangeMe-User4-2026!"},
            ]
            LOG.warning("Development demo accounts created. Change their passwords before any shared deployment.")
        else:
            raise RuntimeError("Set BOOTSTRAP_USERS_JSON with exactly four accounts before production startup")
        for item in users:
            username, password = str(item["username"]).strip(), str(item["password"])
            if len(password) < 12 or not username:
                raise RuntimeError("Every bootstrap account needs a username and password of at least 12 characters")
            user = User(username=username, password_hash=_pbkdf(password), role=item.get("role","user"),
                        language=item.get("language","ru"), balance=10000.0)
            db.add(user); db.flush()
            settings = DEFAULT_SETTINGS.copy(); settings["language"] = user.language
            db.add(UserSettings(user_id=user.id, payload=json.dumps(settings)))
        db.commit()

bootstrap_users()

BINANCE_BASE = os.getenv("BINANCE_FUTURES_BASE_URL", "https://fapi.binance.com")
MARKET_REGION = os.getenv("MARKET_REGION_LABEL", "not-set")
SERVER_REGION = os.getenv("SERVER_REGION_LABEL", "not-reported")
market = BinanceUM(BINANCE_BASE, MARKET_REGION)
news = NewsService()
market_cache: dict[str, dict] = {}
market_event: asyncio.Event | None = None
ws_state = {"connected":False,"last_message":0,"last_error":"Not connected"}
ticker_cache: dict[str, dict] = {}
last_scan: int = 0
engine_state = {"scanner":"BOOTING", "last_scan":0, "last_error":"", "positions":"STARTING"}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global market_event
    market_event = asyncio.Event()
    tasks = [asyncio.create_task(background_loop()), asyncio.create_task(websocket_market_loop())]
    yield
    for task in tasks: task.cancel()
    for task in tasks:
        try: await task
        except asyncio.CancelledError: pass
    await market.close(); await news.close()

app = FastAPI(title="MIRAGE Paper Trading", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

class LoginBody(BaseModel): username: str; password: str
class TradeBody(BaseModel):
    symbol: str = Field(min_length=3, max_length=30)
    side: str
    strategy: str = "MANUAL"
    interval: str = "15m"
    score: int = Field(default=80, ge=80, le=100)
    stop: float = Field(gt=0)
    tp1: float = Field(gt=0); tp2: float = Field(gt=0); tp3: float = Field(gt=0)
class SettingsBody(BaseModel):
    language: str | None = None
    auto_trade: bool | None = None
    risk_pct: float | None = Field(default=None, ge=0.25, le=2.0)
    max_total_risk_pct: float | None = Field(default=None, ge=1.0, le=5.0)
    max_positions: int | None = Field(default=None, ge=1, le=10)
    notifications: bool | None = None
    reduced_motion: bool | None = None
    sound: bool | None = None
    strategies: list[str] | None = None


def current_user(request: Request, db: DBSession = Depends(lambda: DBLocal())):
    # Explicit session lifecycle to avoid leaking a SQLAlchemy session per request.
    token = request.cookies.get("mirage_session")
    if not token: raise HTTPException(401, "Authentication required")
    row = db.scalar(select(UserSession).where(UserSession.token_hash == hashlib.sha256(token.encode()).hexdigest(),
                                               UserSession.expires_at > int(time.time())))
    if not row: raise HTTPException(401, "Session expired")
    user = db.get(User, row.user_id)
    if not user: raise HTTPException(401, "Account unavailable")
    return user

# Dependency with deterministic session close.
def db_dependency():
    db = DBLocal()
    try: yield db
    finally: db.close()

# Replace dependency wrapper with the managed generator dependency.
def auth_user(request: Request, db: DBSession = Depends(db_dependency)) -> User:
    token = request.cookies.get("mirage_session")
    if not token: raise HTTPException(401, "Authentication required")
    digest = hashlib.sha256(token.encode()).hexdigest()
    row = db.scalar(select(UserSession).where(UserSession.token_hash == digest, UserSession.expires_at > int(time.time())))
    if not row: raise HTTPException(401, "Session expired")
    user = db.get(User, row.user_id)
    if not user: raise HTTPException(401, "Account unavailable")
    return user

@app.get("/")
def index(): return FileResponse(STATIC / "index.html")

@app.get("/manifest.webmanifest")
def manifest(): return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")

@app.get("/sw.js")
def service_worker(): return FileResponse(STATIC / "sw.js", media_type="application/javascript")

@app.post("/api/auth/login")
def login(body: LoginBody, response: Response, db: DBSession = Depends(db_dependency)):
    user = db.scalar(select(User).where(User.username == body.username.strip()))
    if not user or not _verify(body.password, user.password_hash):
        add_audit(db, "AUTH", "WARNING", f"Failed login for username {body.username[:60]}")
        db.commit(); raise HTTPException(401, "Invalid username or password")
    token = secrets.token_urlsafe(40)
    db.add(UserSession(user_id=user.id, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                       expires_at=int(time.time()) + 60*60*24*14))
    add_audit(db, "AUTH", "INFO", "User signed in", user.id); db.commit()
    response.set_cookie("mirage_session", token, httponly=True, secure=APP_ENV == "production",
                        samesite="lax", max_age=60*60*24*14, path="/")
    return {"user":user_public(user)}

def user_public(user):
    return {"id":user.id,"username":user.username,"role":user.role,"language":user.language}

@app.get("/api/auth/me")
def me(user: User = Depends(auth_user), db: DBSession = Depends(db_dependency)):
    return {"user":user_public(user), "settings":get_settings(db,user.id)}

@app.post("/api/auth/logout")
def logout(request: Request, response: Response, db: DBSession = Depends(db_dependency), user: User = Depends(auth_user)):
    token = request.cookies.get("mirage_session", "")
    db.query(UserSession).filter(UserSession.token_hash == hashlib.sha256(token.encode()).hexdigest()).delete()
    db.commit(); response.delete_cookie("mirage_session", path="/")
    return {"ok":True}

@app.get("/api/health")
def health():
    return {"ok":True,"app":"MIRAGE","version":"1.0.0","server_region":SERVER_REGION,
            "market":market.status.__dict__,"engine":{**engine_state,"websocket":ws_state},
            "server_time":int(time.time()),"paper_only":True,"real_orders_enabled":False}

@app.get("/api/settings")
def settings_get(user: User = Depends(auth_user), db: DBSession = Depends(db_dependency)):
    return get_settings(db,user.id)

@app.patch("/api/settings")
def settings_patch(body: SettingsBody, user: User = Depends(auth_user), db: DBSession = Depends(db_dependency)):
    s = get_settings(db,user.id); updates = body.model_dump(exclude_none=True)
    if "language" in updates and updates["language"] not in {"ru","en"}: raise HTTPException(400,"Language must be ru or en")
    if "strategies" in updates:
        allowed = {"SCALPING","INTRADAY","SWING","POSITION"}
        if not set(updates["strategies"]).issubset(allowed): raise HTTPException(400,"Unknown strategy")
    s.update(updates); put_settings(db,user.id,s)
    if "language" in updates: user.language = updates["language"]
    db.commit(); return s

@app.get("/api/market/overview")
def market_overview(user: User = Depends(auth_user)):
    items=[]
    for symbol, q in market_cache.items():
        items.append({**q, **ticker_cache.get(symbol, {}), "symbol":symbol})
    return {"items":items, "market":market.status.__dict__, "updated_at":int(time.time())}

@app.get("/api/market/klines")
async def market_klines(symbol: str, interval: str = "1h", user: User = Depends(auth_user)):
    if interval not in {"1m","5m","15m","30m","1h","4h","1d","1w"}: raise HTTPException(400,"Unsupported interval")
    try: return {"symbol":symbol,"interval":interval,"rows":await market.klines(symbol.upper(),interval,100)}
    except Exception as exc: raise HTTPException(503,f"Market data unavailable: {str(exc)[:140]}")

@app.get("/api/analyze")
async def analyze_symbol(symbol: str, interval: str = "1h", user: User = Depends(auth_user)):
    symbol = symbol.upper()
    if not symbol.endswith("USDT") or interval not in {"15m","1h","4h","1d"}:
        raise HTTPException(400,"Use a USDT perpetual and one of 15m, 1h, 4h, 1d")
    if not market.status.ok: raise HTTPException(503,"Binance Futures market data is unavailable from this server region")
    try:
        rows = await market.klines(symbol, interval, 120)
        result = analyze_klines(symbol, interval, "MANUAL", rows)
        if not result: raise HTTPException(422,"Not enough market history to analyze this symbol")
        return result
    except HTTPException: raise
    except Exception as exc: raise HTTPException(503,f"Analysis failed: {str(exc)[:140]}")

@app.get("/api/signals")
def signals(limit: int = 60, user: User = Depends(auth_user), db: DBSession = Depends(db_dependency)):
    rows = db.scalars(select(Signal).order_by(desc(Signal.created_at)).limit(min(max(limit,1),100))).all()
    return [signal_public(x) for x in rows]

def signal_public(s):
    return {"id":s.id,"symbol":s.symbol,"side":s.side,"strategy":s.strategy,"interval":s.interval,
            "score":s.score,"grade":s.grade,"entry":s.entry,"stop":s.stop,
            "targets":json.loads(s.targets_json),"indicators":json.loads(s.indicators_json),"created_at":s.created_at,"state":s.state}

@app.get("/api/trades")
def trades(status: str = "ALL", user: User = Depends(auth_user), db: DBSession = Depends(db_dependency)):
    q = select(Trade).where(Trade.user_id == user.id)
    if status in ("OPEN","CLOSED"): q = q.where(Trade.status == status)
    rows = db.scalars(q.order_by(desc(Trade.opened_at)).limit(250)).all()
    return [trade_public(t) for t in rows]

def trade_public(t):
    net = t.gross_realized - t.entry_fee - t.exit_fee_total + t.funding_pnl
    return {"id":t.id,"symbol":t.symbol,"side":t.side,"strategy":t.strategy,"interval":t.interval,
            "score":t.score,"grade":t.grade,"entry":t.entry_price,"qty":t.initial_qty,"remaining_qty":t.remaining_qty,
            "leverage":t.leverage,"margin":t.initial_margin,"risk_amount":t.risk_amount,"stop":t.stop_price,
            "targets":json.loads(t.targets_json),"target_hits":json.loads(t.target_hits_json),
            "entry_fee":t.entry_fee,"exit_fee":t.exit_fee_total,"gross_realized":t.gross_realized,
            "funding_pnl":t.funding_pnl,"realized_net":net,"status":t.status,"opened_at":t.opened_at,
            "closed_at":t.closed_at,"close_reason":t.close_reason,
            "liquidation_estimate":approximate_liquidation_price(t.side,t.entry_price,t.leverage)}

def get_quote_from_cache(symbol: str) -> Quote:
    q = market_cache.get(symbol)
    if not q or time.time() - q.get("book_received_at", q.get("received_at",0)) > 5 or time.time() - q.get("mark_received_at", q.get("received_at",0)) > 5:
        raise HTTPException(503, f"Fresh bid/ask or Mark Price for {symbol} is unavailable; new entries are blocked")
    quote = Quote(q["bid"],q["ask"],q["mark"],q.get("time",0));
    try: quote.validate()
    except ValueError as e: raise HTTPException(503,str(e))
    return quote

def active_trades(db, user_id):
    return db.scalars(select(Trade).where(Trade.user_id==user_id, Trade.status=="OPEN")).all()

def open_trade(db, user: User, plan: dict, quote_data: dict, settings: dict):
    if not market.status.ok: raise ValueError("Market data region check failed; entries are disabled")
    symbol, side = plan["symbol"], plan["side"]
    cached = market_cache.get(symbol)
    if not cached or time.time()-cached.get("book_received_at",cached.get("received_at",0))>5 or time.time()-cached.get("mark_received_at",cached.get("received_at",0))>5:
        raise ValueError("Market quote is stale; entries are disabled")
    quote = Quote(quote_data["bid"],quote_data["ask"],quote_data["mark"],quote_data.get("time",0))
    quote.validate()
    if quote.spread_bps > float(settings["max_spread_bps"]): raise ValueError(f"Spread too wide ({quote.spread_bps:.1f} bps)")
    score = int(plan.get("score",80)); leverage = leverage_for_score(score)
    if leverage == 0: raise ValueError("Signal below quality gate (minimum 80/100)")
    entry = entry_fill(side, quote, float(settings["slippage_bps"]))
    filters = market.symbol_filters.get(symbol)
    if not filters:
        raise ValueError("Exchange symbol filters are unavailable; entry blocked")
    tick = filters["tick_size"]
    stop_mode = "down" if side == "LONG" else "up"
    target_mode = "up" if side == "LONG" else "down"
    stop = round_to_step(float(plan["stop"]), tick, stop_mode)
    targets = [round_to_step(float(x), tick, target_mode) for x in plan["targets"]]
    validate_trade_plan(side, entry, stop, targets)
    liquidation = approximate_liquidation_price(side, entry, leverage)
    if (side == "LONG" and stop <= liquidation) or (side == "SHORT" and stop >= liquidation):
        raise ValueError("Stop loss is beyond the estimated liquidation price; reduce leverage or widen margin")
    open_positions = active_trades(db,user.id)
    if len(open_positions) >= int(settings["max_positions"]): raise ValueError("Maximum simultaneous positions reached")
    free_balance = user.balance - sum(t.initial_margin * (t.remaining_qty/t.initial_qty) for t in open_positions)
    if free_balance <= 0: raise ValueError("No free isolated margin")
    active_risk = sum(t.risk_amount * (t.remaining_qty/t.initial_qty) for t in open_positions)
    risk_cap = user.balance * float(settings["max_total_risk_pct"]) / 100
    risk_budget = user.balance * float(settings["risk_pct"]) / 100
    if active_risk + risk_budget > risk_cap + 1e-8: raise ValueError("Aggregate open-risk limit would be exceeded")
    size = calculate_position_size(balance=user.balance,risk_pct=float(settings["risk_pct"]),
        entry_price=entry,stop_price=stop,side=side,leverage=leverage,free_balance=free_balance,
        fee_rate=float(settings["taker_fee"]),spread_bps=quote.spread_bps,
        slippage_bps=float(settings["slippage_bps"]),quantity_step=filters["step_size"])
    if size.quantity < filters["min_qty"] or size.quantity * entry < filters["min_notional"]:
        raise ValueError("Position is below Binance USD-M minimum quantity/notional for this symbol")
    entry_fee = fee(size.quantity*entry,float(settings["taker_fee"]))
    user.balance -= entry_fee  # entry fee is debited immediately; do not deduct it again at close
    now = int(time.time())
    t = Trade(user_id=user.id,symbol=symbol,side=side,strategy=plan.get("strategy","MANUAL"),
        interval=plan.get("interval","15m"),score=score,grade="S" if score>=92 else "A",
        entry_price=entry,initial_qty=size.quantity,remaining_qty=size.quantity,leverage=leverage,
        initial_margin=size.margin_required,risk_amount=size.estimated_stop_loss,stop_price=stop,
        targets_json=json.dumps(targets),target_hits_json="[]",entry_fee=entry_fee,
        opened_at=now,last_funding_time=now)
    db.add(t); db.flush()
    add_audit(db,"PAPER_TRADE","INFO",f"Opened {side} {symbol} {leverage}x; isolated margin; no exchange order",user.id)
    db.commit(); db.refresh(t)
    return t

@app.post("/api/trades/open")
def manual_open(body: TradeBody, user: User = Depends(auth_user), db: DBSession = Depends(db_dependency)):
    symbol=body.symbol.upper()
    if not symbol.endswith("USDT"): raise HTTPException(400,"Only USDT-margined perpetual symbols are supported")
    s=get_settings(db,user.id)
    quote=get_quote_from_cache(symbol)
    try:
        t=open_trade(db,user,{"symbol":symbol,"side":body.side.upper(),"strategy":body.strategy.upper(),
            "interval":body.interval,"score":body.score,"stop":body.stop,"targets":[body.tp1,body.tp2,body.tp3]},
            {"bid":quote.bid,"ask":quote.ask,"mark":quote.mark,"time":quote.timestamp_ms},s)
        return trade_public(t)
    except (ValueError, KeyError) as e: db.rollback(); raise HTTPException(400,str(e))

@app.post("/api/trades/{trade_id}/close")
def close_manual(trade_id: int, user: User = Depends(auth_user), db: DBSession = Depends(db_dependency)):
    t=db.scalar(select(Trade).where(Trade.id==trade_id,Trade.user_id==user.id,Trade.status=="OPEN"))
    if not t: raise HTTPException(404,"Open paper position not found")
    q=get_quote_from_cache(t.symbol); s=get_settings(db,user.id)
    close_position_part(db,t,user,t.remaining_qty,exit_fill(t.side,q,float(s["slippage_bps"])),"MANUAL")
    db.commit(); return trade_public(t)

def close_position_part(db, t: Trade, user: User, qty: float, price: float, reason: str):
    qty=min(max(0.0,qty),t.remaining_qty)
    if qty <= 0: return
    s=get_settings(db,user.id)
    close_fee=fee(qty*price,float(s["taker_fee"]))
    gross=gross_pnl(t.side,t.entry_price,price,qty)
    user.balance += gross - close_fee
    t.gross_realized += gross; t.exit_fee_total += close_fee
    t.remaining_qty=max(0.0,t.remaining_qty-qty)
    if t.remaining_qty <= t.initial_qty*1e-9:
        t.remaining_qty=0.0; t.status="CLOSED"; t.closed_at=int(time.time()); t.close_reason=reason
    add_audit(db,"EXECUTION","INFO",f"{reason} {t.symbol}: qty {qty:.8f} at {price:.8f}; gross {gross:.4f}; exit fee {close_fee:.4f}",user.id)

def process_position(db, t: Trade, user: User, qdata: dict):
    mark=float(qdata["mark"]); quote=Quote(qdata["bid"],qdata["ask"],mark,qdata.get("time",0)); quote.validate()
    s=get_settings(db,user.id); slip=float(s["slippage_bps"]); targets=json.loads(t.targets_json); hits=set(json.loads(t.target_hits_json))
    # Mark Price triggers; execution uses current Bid/Ask plus slippage.
    liquidation = approximate_liquidation_price(t.side, t.entry_price, t.leverage)
    liquidated = mark <= liquidation if t.side == "LONG" else mark >= liquidation
    if liquidated:
        liq_quote = Quote(qdata["bid"], qdata["ask"], mark, qdata.get("time", 0))
        close_position_part(db, t, user, t.remaining_qty,
                            exit_fill(t.side, liq_quote, slip), "LIQUIDATION_ESTIMATE")
        add_audit(db, "PHANTOM", "CRITICAL", f"Estimated liquidation threshold touched for {t.symbol}", user.id)
        return
    stop_hit = mark <= t.stop_price if t.side=="LONG" else mark >= t.stop_price
    if stop_hit:
        close_position_part(db,t,user,t.remaining_qty,exit_fill(t.side,quote,slip),"SL")
        return
    for idx,target in enumerate(targets):
        if idx in hits or t.status!="OPEN": continue
        touched = mark >= target if t.side=="LONG" else mark <= target
        if touched:
            qty=target_quantity(t.initial_qty,t.remaining_qty,idx)
            close_position_part(db,t,user,qty,exit_fill(t.side,quote,slip),f"TP{idx+1}")
            hits.add(idx); t.target_hits_json=json.dumps(sorted(hits))
            if idx == 0 and t.status == "OPEN":
                # After TP1, protect the remainder at break-even (entry price).
                t.stop_price = t.entry_price
    
funding_check_cache: dict[int, float] = {}
async def apply_funding(db, t: Trade, user: User, now_ms: int):
    if t.status!="OPEN": return
    if time.time() - funding_check_cache.get(t.id, 0) < 30: return
    funding_check_cache[t.id] = time.time()
    start=max(t.last_funding_time+1,t.opened_at)
    try: rows=await market.funding_history(t.symbol,start,now_ms)
    except Exception as e:
        add_audit(db,"FUNDING","WARNING",f"Funding history unavailable for {t.symbol}: {str(e)[:100]}",user.id); return
    for row in rows:
        ft=int(row["fundingTime"])
        if ft<=t.last_funding_time or ft>now_ms or ft<t.opened_at: continue
        mark=float(row.get("markPrice") or t.entry_price); rate=float(row["fundingRate"])
        cost=funding_cost(t.side,t.remaining_qty*mark,rate)
        pnl=-cost; user.balance += pnl; t.funding_pnl += pnl; t.last_funding_time=ft
        add_audit(db,"FUNDING","INFO",f"{t.symbol} funding {rate*100:.5f}% => {pnl:+.4f} USDT",user.id)

@app.get("/api/dashboard")
def dashboard(user: User = Depends(auth_user), db: DBSession = Depends(db_dependency)):
    positions=active_trades(db,user.id)
    unrealized=0.0; notional=0.0; open_risk=0.0
    for t in positions:
        q=market_cache.get(t.symbol)
        if q:
            close_px=q["bid"] if t.side=="LONG" else q["ask"]
            s = get_settings(db,user.id)
            unrealized += gross_pnl(t.side,t.entry_price,close_px,t.remaining_qty) - fee(t.remaining_qty*close_px,float(s["taker_fee"]))
            notional += t.remaining_qty*q["mark"]
        open_risk += t.risk_amount*(t.remaining_qty/t.initial_qty)
    closed=db.scalars(select(Trade).where(Trade.user_id==user.id,Trade.status=="CLOSED")).all()
    net_closed=[x.gross_realized-x.entry_fee-x.exit_fee_total+x.funding_pnl for x in closed]
    return {"balance":user.balance,"equity":user.balance+unrealized,"unrealized_pnl":unrealized,
            "open_positions":len(positions),"open_notional":notional,"open_risk":open_risk,
            "total_closed":len(closed),"realized_net":sum(net_closed),
            "market":market.status.__dict__,"engine":{**engine_state,"websocket":ws_state},
            "recent_signals": [signal_public(x) for x in db.scalars(select(Signal).order_by(desc(Signal.created_at)).limit(5)).all()]}

@app.get("/api/analytics")
def analytics(user: User = Depends(auth_user), db: DBSession = Depends(db_dependency)):
    rows=db.scalars(select(Trade).where(Trade.user_id==user.id,Trade.status=="CLOSED").order_by(Trade.closed_at)).all()
    vals=[t.gross_realized-t.entry_fee-t.exit_fee_total+t.funding_pnl for t in rows]
    wins=[v for v in vals if v>0]; losses=[v for v in vals if v<0]
    gross_profit=sum(wins); gross_loss=abs(sum(losses))
    equity=10000.0; curve=[]
    for value,t in zip(vals,rows): equity += value; curve.append({"time":t.closed_at,"equity":round(equity,2)})
    return {"closed":len(vals),"wins":len(wins),"losses":len(losses),"win_rate":len(wins)/len(vals)*100 if vals else 0,
            "profit_factor":gross_profit/gross_loss if gross_loss else (gross_profit if gross_profit else 0),
            "net_pnl":sum(vals),"gross_profit":gross_profit,"gross_loss":gross_loss,
            "avg_trade":statistics.mean(vals) if vals else 0,"equity_curve":curve,
            "by_strategy":{k:round(sum((t.gross_realized-t.entry_fee-t.exit_fee_total+t.funding_pnl) for t in rows if t.strategy==k),2)
                           for k in {t.strategy for t in rows}}}

@app.get("/api/news")
async def get_news(user: User = Depends(auth_user)):
    return await news.get()

@app.get("/api/phantom")
def phantom(user: User = Depends(auth_user), db: DBSession = Depends(db_dependency)):
    events=db.scalars(select(AuditEvent).where((AuditEvent.user_id==user.id)|(AuditEvent.user_id==None))
                      .order_by(desc(AuditEvent.created_at)).limit(40)).all()
    return {"state":"PROTECTIVE" if (not market.status.ok or time.time()-market.status.checked_at>900) else "ACTIVE",
            "checks":[{"name":"REST market data","ok":market.status.ok,"detail":market.status.message},
                      {"name":"Live mark/book stream","ok":ws_state["connected"],"detail":ws_state["last_error"] or ("Last message " + str(ws_state["last_message"]))},
                      {"name":"Paper-only execution","ok":True,"detail":"No exchange order endpoints are implemented"},
                      {"name":"Risk gate","ok":True,"detail":"Per-user risk and margin checks enabled"},
                      {"name":"Duplicate guard","ok":True,"detail":"Symbol/side/strategy deduplication enabled"}],
            "events":[{"category":e.category,"severity":e.severity,"message":e.message,"created_at":e.created_at} for e in events]}

async def refresh_market_quotes():
    if not hasattr(refresh_market_quotes, "last_ticker_refresh") or time.time()-refresh_market_quotes.last_ticker_refresh > 60:
        try:
            rows = await market.tickers()
            for row in rows:
                if row.get("symbol", "").endswith("USDT"):
                    ticker_cache[row["symbol"]] = {"change_pct":float(row.get("priceChangePercent",0)),
                        "quote_volume":float(row.get("quoteVolume",0)), "last_price":float(row.get("lastPrice",0))}
            refresh_market_quotes.last_ticker_refresh = time.time()
        except Exception: pass
    symbols=set()
    with DBLocal() as db:
        for t in db.scalars(select(Trade).where(Trade.status=="OPEN")).all(): symbols.add(t.symbol)
    symbols.update(list(market_cache.keys())[:12])
    if not symbols and market.status.ok:
        try: symbols.update(await market.universe(12))
        except Exception: pass
    async def one(sym):
        cached = market_cache.get(sym, {})
        # WebSocket marks are 1-second and book tickers are real-time. REST is a guarded fallback.
        book_age = time.time() - cached.get("book_received_at", 0)
        mark_age = time.time() - cached.get("mark_received_at", 0)
        if book_age < 4 and mark_age < 4: return
        try:
            data=await market.book_mark(sym); now=time.time()
            data["received_at"]=now; data["book_received_at"]=now; data["mark_received_at"]=now
            market_cache[sym]=data
            if market_event: market_event.set()
        except Exception as e:
            if sym in market_cache: market_cache[sym]["stale"]=True
    await asyncio.gather(*(one(x) for x in list(symbols)[:30]))

async def websocket_market_loop():
    """Low-latency public mark/book streams; reconnects automatically after network interruptions."""
    url=os.getenv("BINANCE_FUTURES_WS_URL", "wss://fstream.binance.com/market/stream?streams=!markPrice@arr@1s/!bookTicker/!ticker@arr")
    while True:
        try:
            async with websockets.connect(url, ping_interval=180, ping_timeout=600, close_timeout=8, max_size=8*1024*1024) as ws:
                ws_state["connected"]=True; ws_state["last_error"]=""
                async for raw in ws:
                    try:
                        msg=json.loads(raw); stream=msg.get("stream",""); payload=msg.get("data",msg)
                        items=payload if isinstance(payload,list) else [payload]
                        now=time.time()
                        for p in items:
                            symbol=p.get("s","")
                            if not symbol or not symbol.endswith("USDT") or p.get("st",1)!=1: continue
                            if "markPrice" in p.get("e","") or ("p" in p and "r" in p and "T" in p):
                                q=market_cache.setdefault(symbol,{"symbol":symbol})
                                q["mark"]=float(p["p"]); q["last_funding_rate"]=float(p.get("r",0)); q["next_funding_time"]=int(p.get("T",0))
                                q["mark_received_at"]=now; q["received_at"]=now
                            elif p.get("e")=="bookTicker" or ("b" in p and "a" in p and "s" in p):
                                q=market_cache.setdefault(symbol,{"symbol":symbol})
                                q["bid"]=float(p["b"]); q["ask"]=float(p["a"]); q["book_received_at"]=now; q["received_at"]=now
                            elif p.get("e")=="24hrTicker" or "P" in p and "c" in p and "q" in p:
                                ticker_cache[symbol]={"change_pct":float(p.get("P",0)),"quote_volume":float(p.get("q",0)),"last_price":float(p.get("c",0))}
                        ws_state["last_message"]=int(now)
                        if market_event: market_event.set()
                    except Exception:
                        continue
        except asyncio.CancelledError: raise
        except Exception as exc:
            ws_state["connected"]=False; ws_state["last_error"]=str(exc)[:180]
            await asyncio.sleep(5)
        finally:
            ws_state["connected"]=False

async def run_scan():
    global last_scan
    if not market.status.ok: return
    try:
        candidates=await scan_market(market, int(os.getenv("SCAN_UNIVERSE_SIZE","10")))
        with DBLocal() as db:
            for item in candidates:
                existing=db.scalar(select(Signal).where(Signal.symbol==item["symbol"],Signal.side==item["side"],
                    Signal.strategy==item["strategy"],Signal.created_at>int(time.time())-1800).limit(1))
                if existing: continue
                row=Signal(symbol=item["symbol"],side=item["side"],strategy=item["strategy"],interval=item["interval"],
                    score=item["score"],grade=item["grade"],entry=item["entry"],stop=item["stop"],
                    targets_json=json.dumps(item["tps"]),
                    indicators_json=json.dumps({k:item[k] for k in ("rsi","atr","ema20","ema50","volume_ratio")}),
                    created_at=item["created_at"],state="ACTIVE")
                db.add(row); db.flush()
                # Each account independently chooses whether scanner signals may open paper positions.
                for u in db.scalars(select(User)).all():
                    s=get_settings(db,u.id)
                    if not s["auto_trade"] or item["strategy"] not in s["strategies"]: continue
                    duplicate=db.scalar(select(Trade.id).where(Trade.user_id==u.id,Trade.symbol==item["symbol"],
                        Trade.side==item["side"],Trade.strategy==item["strategy"],Trade.status=="OPEN").limit(1))
                    if duplicate: continue
                    try:
                        q=market_cache.get(item["symbol"])
                        if not q or time.time()-q.get("book_received_at",q.get("received_at",0))>5 or time.time()-q.get("mark_received_at",q.get("received_at",0))>5: continue
                        open_trade(db,u,{"symbol":item["symbol"],"side":item["side"],"strategy":item["strategy"],
                            "interval":item["interval"],"score":item["score"],"stop":item["stop"],"targets":item["tps"]},q,s)
                    except Exception as e:
                        add_audit(db,"PHANTOM","WARNING",f"Auto entry blocked {item['symbol']}: {str(e)[:130]}",u.id)
                db.commit()
        last_scan=int(time.time()); engine_state["last_scan"]=last_scan
        engine_state["scanner"]="ACTIVE"; engine_state["last_error"]=""
    except Exception as exc:
        engine_state["scanner"]="DEGRADED"; engine_state["last_error"]=str(exc)[:220]
        with DBLocal() as db: add_audit(db,"MARKET","ERROR",f"Scanner failed: {str(exc)[:200]}"); db.commit()

async def manage_open_positions():
    now_ms=int(time.time()*1000)
    with DBLocal() as db:
        trades=db.scalars(select(Trade).where(Trade.status=="OPEN")).all()
        for t in trades:
            user=db.get(User,t.user_id)
            if not user: continue
            q=market_cache.get(t.symbol)
            if not q or time.time()-q.get("book_received_at",q.get("received_at",0))>5 or time.time()-q.get("mark_received_at",q.get("received_at",0))>5: continue
            try:
                await apply_funding(db,t,user,now_ms)
                if t.status=="OPEN": process_position(db,t,user,q)
            except Exception as exc:
                add_audit(db,"PHANTOM","ERROR",f"Position guard error {t.symbol}: {str(exc)[:120]}",user.id)
        db.commit()

async def background_loop():
    next_check=0; next_scan=0; last_manage=0
    while True:
        try:
            now=time.time()
            if now>=next_check:
                await market.check(); next_check=now+300
            await refresh_market_quotes()
            # Evaluate all open positions at least once a second when the live stream is healthy.
            if market.status.ok or ws_state["connected"]:
                if now-last_manage >= 1:
                    engine_state["positions"]="ACTIVE" if ws_state["connected"] else "REST_FALLBACK"
                    await manage_open_positions(); last_manage=time.time()
                if market.status.ok and now>=next_scan:
                    await run_scan(); next_scan=now+180
            else:
                engine_state["scanner"]="BLOCKED"; engine_state["positions"]="MARKET_DATA_UNAVAILABLE"
            if market_event:
                try: await asyncio.wait_for(market_event.wait(), timeout=1.0); market_event.clear()
                except asyncio.TimeoutError: pass
            else: await asyncio.sleep(1)
        except asyncio.CancelledError: raise
        except Exception as exc:
            LOG.exception("Background loop recovered from error")
            engine_state["last_error"]=str(exc)[:220]
            await asyncio.sleep(2)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app",host="0.0.0.0",port=int(os.getenv("PORT","8000")),reload=APP_ENV=="development")
