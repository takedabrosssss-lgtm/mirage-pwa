const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];
const state = {
  user:null, settings:{}, page:'home', market:{items:[],market:{}}, dashboard:null,
  signals:[], trades:[], tradeStatus:'OPEN', analytics:null, news:null, phantom:null,
  mode:localStorage.getItem('mirage-mode') || 'STEALTH', marketFilter:'gainers', pollTimer:null
};

const ICONS = {
  home:'<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/><path d="M9 21v-6h6v6"/>',
  'scan-line':'<path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"/><path d="M7 12h10"/><path d="M7 8h10M7 16h10"/>',
  'chart-no-axes-combined':'<path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-5 5"/><path d="M15 9h4v4"/>',
  'arrow-left-right':'<path d="M17 3 21 7l-4 4"/><path d="M3 7h18"/><path d="m7 21-4-4 4-4"/><path d="M21 17H3"/>',
  'layers-3':'<path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/>',
  user:'<path d="M20 21a8 8 0 0 0-16 0"/><circle cx="12" cy="8" r="4"/>',
  lock:'<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 1 1 8 0v3"/>',
  'arrow-right':'<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
  'chevrons-up-down':'<path d="m7 15 5 5 5-5"/><path d="m7 9 5-5 5 5"/>',
  activity:'<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  shield:'<path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/>',
  wallet:'<rect x="3" y="5" width="18" height="15" rx="3"/><path d="M3 8h15a3 3 0 0 1 3 3v1h-5a2 2 0 0 0 0 4h5"/><path d="M16 14h.01"/>',
  'trending-up':'<path d="m3 17 6-6 4 4 8-9"/><path d="M15 6h6v6"/>',
  'trending-down':'<path d="m3 7 6 6 4-4 8 9"/><path d="M15 18h6v-6"/>',
  bitcoin:'<path d="M9 4h6a3 3 0 0 1 0 6H9zm0 6h7a3.5 3.5 0 0 1 0 7H9z"/><path d="M11 2v20M15 2v2M15 20v2"/>',
  ethereum:'<path d="m12 2 6 10-6 4-6-4 6-10Z"/><path d="m6 14 6 8 6-8-6 4-6-4Z"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  zap:'<path d="m13 2-3 9h7l-6 11 2-9H6l7-11Z"/>',
  'arrow-up-right':'<path d="M7 17 17 7"/><path d="M7 7h10v10"/>',
  'arrow-down-right':'<path d="M7 7 17 17"/><path d="M7 17h10V7"/>',
  search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  settings:'<path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"/><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.6a8 8 0 0 1-1.5.9l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.5-.9l-1.7.6-1.4-2.4 1.4-1.1a7 7 0 0 1 0-1.8l-1.4-1.1 1.4-2.4 1.7.6a8 8 0 0 1 1.5-.9l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.5.9l1.7-.6 1.4 2.4-1.4 1.1a7 7 0 0 1 0 1.8Z"/>',
  newspaper:'<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M7 8h5M7 12h10M7 16h10M16 8h1"/>',
  'brain-circuit':'<path d="M12 18V5a3 3 0 0 0-6 0 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 6 3Z"/><path d="M12 18V5a3 3 0 0 1 6 0 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-6 3Z"/><path d="M8 8h.01M8 13h.01M16 8h.01M16 13h.01"/>',
  'chevron-right':'<path d="m9 18 6-6-6-6"/>',
  'circle-check':'<circle cx="12" cy="12" r="9"/><path d="m8 12 2.5 2.5L16 9"/>',
  'alert-triangle':'<path d="m10.3 3.9-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3.1l-8-14a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/>',
  'refresh-cw':'<path d="M20 7v5h-5"/><path d="M4 17v-5h5"/><path d="M5.5 9A7 7 0 0 1 18 6l2 1M4 17l2 1a7 7 0 0 0 12.5-3"/>',
  close:'<path d="m18 6-12 12M6 6l12 12"/>',
  'external-link':'<path d="M14 3h7v7M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  eye:'<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  'eye-off':'<path d="m3 3 18 18M10.6 10.6a2 2 0 0 0 2.8 2.8"/><path d="M9.9 5.2A10.7 10.7 0 0 1 12 5c6.5 0 10 7 10 7a16 16 0 0 1-3.1 3.9M6.2 6.2C3.5 8 2 12 2 12s3.5 7 10 7c1 0 2-.2 2.9-.5"/>',
  'bar-chart-3':'<path d="M3 3v18h18"/><rect x="7" y="12" width="3" height="6" rx=".5"/><rect x="13" y="8" width="3" height="10" rx=".5"/><rect x="19" y="4" width="2" height="14" rx=".5"/>',
  gauge:'<path d="M12 14 16 8"/><path d="M3.3 17a9 9 0 1 1 17.4 0"/><path d="M7 17h10"/>',
  'arrow-down-left':'<path d="M17 7 7 17"/><path d="M17 17H7V7"/>',
  'radio-tower':'<path d="M12 18v4"/><path d="M8.5 14.5a5 5 0 0 1 7 0"/><path d="M5.2 11.2a9.5 9.5 0 0 1 13.6 0"/><path d="M2 8a14 14 0 0 1 20 0"/><circle cx="12" cy="18" r="1"/>',
  'target':'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="M12 2v2M22 12h-2M12 22v-2M2 12h2"/>',
  'sparkles':'<path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z"/><path d="m19 15 .9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z"/><path d="m5 2 .7 1.3L7 4l-1.3.7L5 6l-.7-1.3L3 4l1.3-.7L5 2Z"/>'
};
function icon(name, cls=''){return `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name]||ICONS.activity}</svg>`}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function n(v,d=2){return Number(v||0).toLocaleString(state.settings.language==='en'?'en-US':'ru-RU',{minimumFractionDigits:d,maximumFractionDigits:d})}
function money(v,d=2){return `${Number(v||0)<0?'−':''}$ ${n(Math.abs(Number(v||0)),d)}`}
function pct(v,d=2){return `${Number(v||0)>=0?'+':''}${n(v,d)}%`}
function timeAgo(ts){if(!ts)return '—';const minutes=Math.max(0,Math.floor(Date.now()/1000-Number(ts))/60);return minutes<60?`${Math.floor(minutes)}м`:minutes<1440?`${Math.floor(minutes/60)}ч`:`${Math.floor(minutes/1440)}д`}
function fmtPrice(v){const x=Number(v||0);return n(x,x>=1000?2:x>=1?4:6)}
function toast(message,type='ok'){const root=$('#toast-root');const el=document.createElement('div');el.className=`toast ${type}`;el.innerHTML=`<span class="toast-mark">${icon(type==='error'?'alert-triangle':'circle-check')}</span><span>${esc(message)}</span>`;root.append(el);setTimeout(()=>el.remove(),3800)}
async function api(path,options={}){
  const res=await fetch(path,{credentials:'same-origin',headers:{'Content-Type':'application/json',...(options.headers||{})},...options});
  let data={};try{data=await res.json()}catch{}
  if(!res.ok){if(res.status===401){showLogin();throw new Error('Сессия завершена. Войдите снова.')}throw new Error(data.detail||`HTTP ${res.status}`)}return data;
}
function showLogin(){state.user=null;stopPolling();$('#app-shell').classList.add('hidden');$('#login-screen').classList.remove('hidden')}
function showApp(){ $('#login-screen').classList.add('hidden');$('#app-shell').classList.remove('hidden');$('#profile-initial').textContent=(state.user.username||'U').slice(0,1).toUpperCase();applyMode(); }
function applyMode(){document.body.dataset.mode=state.mode;document.body.classList.toggle('reduce-motion',!!state.settings.reduced_motion);$('#mode-label').textContent=state.mode==='STEALTH'?'STEALTH MODE':'SPECTRE MODE';$('.mode-indicator')?.classList.toggle('expert',state.mode==='SPECTRE')}
function setMode(){state.mode=state.mode==='STEALTH'?'SPECTRE':'STEALTH';localStorage.setItem('mirage-mode',state.mode);applyMode();toast(state.mode==='STEALTH'?'STEALTH MODE активирован':'SPECTRE MODE активирован')}
async function refreshBasics(){const [dash,marketData]=await Promise.all([api('/api/dashboard'),api('/api/market/overview')]);state.dashboard=dash;state.market=marketData;state.settings=state.settings||{};return [dash,marketData]}
function marketHealthy(){return !!state.market.market?.ok}
function scannerState(){return state.dashboard?.engine?.scanner||'BOOTING'}
function liveState(){const ws=state.dashboard?.engine?.websocket||{};return !!ws.market_connected&&!!ws.public_connected}
function statusLabel(value){const map={ACTIVE:'АКТИВЕН',DEGRADED:'ОГРАНИЧЕН',BLOCKED:'ЗАБЛОКИРОВАН',WAITING_FOR_TICKERS:'ОЖИДАНИЕ ПОТОКА',BOOTING:'ЗАПУСК'};return map[value]||value||'НЕИЗВЕСТНО'}
function statusTone(value){return value==='ACTIVE'?'good':(['DEGRADED','WAITING_FOR_TICKERS','BOOTING'].includes(value)?'warn':'bad')}
function coinMeta(symbol){const key=(symbol||'').replace('USDT','');const map={BTC:'coin-btc',ETH:'coin-eth',BNB:'coin-bnb',SOL:'coin-sol',XRP:'coin-xrp',ADA:'coin-ada',DOGE:'coin-doge',AVAX:'coin-avax',LINK:'coin-link',LTC:'coin-ltc'};return [key,map[key]||'coin-default']}
function coinGlyph(key){const shapes={BTC:'<path d="M9 4h6a3 3 0 0 1 0 6H9zm0 6h7a3 3 0 0 1 0 6H9z"/><path d="M11 2v20M15 2v2M15 20v2"/>',ETH:'<path d="m12 2 7 10-7 4-7-4 7-10Z"/><path d="m5 14 7 8 7-8-7 4-7-4Z"/>',BNB:'<path d="m12 2 4 4-4 4-4-4 4-4Zm7 7 4 4-4 4-4-4 4-4ZM5 9l4 4-4 4-4-4 4-4Zm7 7 4 4-4 4-4-4 4-4Zm0-7 3 3-3 3-3-3 3-3Z"/>',SOL:'<path d="M5 6h14l-3 3H2l3-3Zm0 5h14l-3 3H2l3-3Zm0 5h14l-3 3H2l3-3Z"/>',XRP:'<path d="M5 4h2l5 5 5-5h2l-6 6a1.5 1.5 0 0 1-2 0L5 4Zm0 16h2l5-5 5 5h2l-6-6a1.5 1.5 0 0 0-2 0l-6 6Z"/>',ADA:'<circle cx="12" cy="12" r="1.7"/><circle cx="12" cy="5" r="1.2"/><circle cx="12" cy="19" r="1.2"/><circle cx="5" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/><circle cx="7" cy="7" r=".8"/><circle cx="17" cy="7" r=".8"/><circle cx="7" cy="17" r=".8"/><circle cx="17" cy="17" r=".8"/>',DOGE:'<path d="M6 4h6a8 8 0 1 1 0 16H6V4Zm4 4v8h2a4 4 0 1 0 0-8h-2Z"/><path d="M4 11h9"/>',AVAX:'<path d="M12 3 22 21H2L12 3Zm0 6-3.3 6h6.6L12 9Z"/>',LINK:'<path d="M8 8 5 10a4 4 0 0 0 0 7l3 2m8-11 3 2a4 4 0 0 1 0 7l-3 2M9 12l6-4m-6 8 6-4"/>',LTC:'<path d="M8 3h4l-3 10 7-3-1 4-7 3-1 4H3l1.5-5L3 17l1-3 2-1 2-10Z"/>'};return shapes[key]||'<path d="m12 3 8 5v8l-8 5-8-5V8l8-5Z"/><path d="m8 12 4-3 4 3-4 3-4-3Z"/>'}
function logoCoin(symbol){const [key,cls]=coinMeta(symbol);return `<span class="coin-mark ${cls}"><svg viewBox="0 0 24 24" aria-hidden="true">${coinGlyph(key)}</svg></span>`}
function linePath(values,width=600,height=150,pad=4){
  if(!values||values.length<2)return '';
  const clean=values.map(Number).filter(Number.isFinite);if(clean.length<2)return '';
  const min=Math.min(...clean),max=Math.max(...clean),range=max-min||Math.abs(max)||1;
  return clean.map((v,i)=>`${pad+(i/(clean.length-1))*(width-pad*2)},${height-pad-((v-min)/range)*(height-pad*2)}`).join(' ');
}
function chartSvg(values,{width=600,height=150,cls='equity-line',fill=true}={}){
  if(!values||values.length<2)return `<div class="chart-empty">Нет достаточной истории для графика</div>`;
  const points=linePath(values,width,height,5);const first=points.split(' ')[0],last=points.split(' ').at(-1);
  const area=fill?`<polygon class="chart-fill" points="${points} ${last.split(',')[0]},${height} ${first.split(',')[0]},${height}"/>`:'';
  return `<svg class="data-chart ${cls}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-label="Market chart"><defs><linearGradient id="chartFade" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity=".22"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs><path class="chart-grid" d="M0 ${height*.25}H${width}M0 ${height*.5}H${width}M0 ${height*.75}H${width}"/>${area}<polyline class="${cls}-path" points="${points}"/><circle class="chart-last" cx="${last.split(',')[0]}" cy="${last.split(',')[1]}" r="3.4"/></svg>`;
}
function miniSpark(symbol){const v=(symbol||'').split('').reduce((a,c)=>a+c.charCodeAt(0),0);const vals=Array.from({length:22},(_,i)=>Math.sin((i+v)*.7)*.35+Math.cos((i+v)*.21)*.25+i*.018);return `<svg class="mini-spark" viewBox="0 0 90 26" preserveAspectRatio="none"><polyline points="${linePath(vals,90,26,2)}"/></svg>`}
function sectionHead(title,meta='',action=''){return `<div class="section-head"><div><h2>${title}</h2>${meta?`<p>${meta}</p>`:''}</div>${action}</div>`}
function buttonIcon(name,action,label,cls=''){return `<button class="icon-btn ${cls}" data-action="${action}" aria-label="${label}" type="button">${icon(name)}</button>`}

async function navigate(page){
  state.page=page;$$('.nav-item').forEach(b=>b.classList.toggle('active',b.dataset.page===page));
  const root=$('#page-content');root.classList.add('page-leaving');
  await new Promise(resolve=>setTimeout(resolve,80));root.innerHTML=`<div class="loading-screen"><span class="loader-orbit"></span><span>Загрузка ${esc(page)}</span></div>`;root.classList.remove('page-leaving');root.classList.add('page-entering');
  try{
    const renderers={home:renderHome,scanner:renderScanner,analytics:renderAnalytics,trading:renderTrading,more:renderMore,news:renderNews,intelligence:renderIntelligence,phantom:renderPhantom,settings:renderSettings};
    await (renderers[page]||renderHome)(root);
  }catch(e){root.innerHTML=`<div class="error-panel">${icon('alert-triangle')}<h3>Не удалось загрузить раздел</h3><p>${esc(e.message)}</p><button class="btn" data-action="retry">Повторить</button></div>`}
  root.scrollTo?.(0,0);window.scrollTo({top:0,behavior:'smooth'});setTimeout(()=>root.classList.remove('page-entering'),420);
}
function navTo(page){navigate(page).catch(e=>toast(e.message,'error'))}

async function renderHome(root){
  const [basics, signalList] = await Promise.all([refreshBasics(),api('/api/signals?limit=5').catch(()=>[])]);
  const dash=basics[0], md=basics[1], signals=signalList||[];
  state.signals=signals;const balance=Number(dash.balance||10000),equity=Number(dash.equity||balance),unreal=Number(dash.unrealized_pnl||0);
  const items=[...(md.items||[])];let active=[...items];
  if(state.marketFilter==='gainers')active=active.filter(x=>Number(x.change_pct||0)>=0).sort((a,b)=>(b.change_pct||0)-(a.change_pct||0));
  if(state.marketFilter==='losers')active=active.filter(x=>Number(x.change_pct||0)<0).sort((a,b)=>(a.change_pct||0)-(b.change_pct||0));
  if(state.marketFilter==='trending')active.sort((a,b)=>(b.quote_volume||0)-(a.quote_volume||0));
  let candles=[];try{const data=await api('/api/market/klines?symbol=BTCUSDT&interval=15m');candles=(data.rows||[]).filter(r=>Number(r[6])<Date.now()).slice(-48).map(r=>Number(r[4]));}catch{}
  const btc=items.find(x=>x.symbol==='BTCUSDT');const scanner=scannerState();const ws=liveState();
  root.innerHTML=`
    <div class="home-intro"><div><div class="eyebrow">ВЕРХНИЙ УРОВЕНЬ · USDⓈ-M PERPETUALS</div><h1>Обзор портфеля</h1><p>Рыночная аналитика и автоматическое Paper Trading</p></div><span class="live-pill ${ws?'live':'warn'}"><i></i>${ws?'LIVE FEED':'FEED CHECK'}</span></div>
    <section class="hero-balance card-glass">
      <div class="hero-orbit orbit-one"></div><div class="hero-orbit orbit-two"></div><div class="hero-balance-top"><span class="overline">ОБЩИЙ ВИРТУАЛЬНЫЙ КАПИТАЛ</span><span class="paper-chip">${icon('shield')} PAPER ONLY</span></div>
      <div class="hero-balance-value">${money(equity)}</div>
      <div class="hero-balance-bottom"><div class="balance-delta ${unreal>=0?'positive':'negative'}"><span>${unreal>=0?'▲':'▼'}</span>${money(Math.abs(unreal))}<small>Нереализованный P&L</small></div><div class="balance-sub">Баланс ${money(balance)}</div></div>
      <div class="hero-wave"><svg viewBox="0 0 600 110" preserveAspectRatio="none"><path class="wave-back" d="M0 78 C70 64 70 88 135 61 S204 42 248 54 S315 84 358 42 S420 18 460 43 S520 4 600 19"/><path class="wave-front" d="M0 86 C68 76 78 89 135 71 S205 50 248 64 S315 88 358 54 S420 31 460 53 S520 20 600 29"/></svg></div>
      <div class="balance-foot"><span>${icon('wallet')} Счёт ${esc(state.user?.username||'owner')}</span><span>${icon('activity')} ${dash.open_positions||0} открытых позиций</span></div>
    </section>

    <div class="quick-grid">
      <button class="quick-card" data-page="scanner"><span class="quick-icon">${icon('scan-line')}</span><strong>Сканер</strong><small>Рыночные сигналы</small></button>
      <button class="quick-card" data-page="trading"><span class="quick-icon">${icon('arrow-left-right')}</span><strong>Торговля</strong><small>Открытые позиции</small></button>
      <button class="quick-card" data-page="analytics"><span class="quick-icon">${icon('chart-no-axes-combined')}</span><strong>Аналитика</strong><small>Результаты</small></button>
      <button class="quick-card" data-page="phantom"><span class="quick-icon">${icon('shield')}</span><strong>PHANTOM</strong><small>Защита сделок</small></button>
    </div>

    <div class="home-grid">
      <section class="panel market-panel">
        <div class="panel-heading"><div><div class="eyebrow">MARKET PULSE</div><h2>Рынок</h2></div><button class="text-action" data-page="scanner">Все активы ${icon('arrow-right')}</button></div>
        <div class="market-chart-head"><div><span class="symbol-big">BTC/USDT</span><small>Bitcoin · 15m</small></div><div class="market-chart-price"><strong>${btc?money(btc.mark||btc.last_price,2):'—'}</strong><span class="${Number(btc?.change_pct||0)>=0?'positive':'negative'}">${btc?pct(btc.change_pct):'Ожидание данных'}</span></div></div>
        ${chartSvg(candles,{width:600,height:150,cls:'market-line'})}
        <div class="chart-foot"><span>${icon('clock')} ${candles.length?`Последние ${candles.length} закрытых свечей`:'График загрузится с данными рынка'}</span><span class="chart-source">BINANCE USDⓈ-M</span></div>
        <div class="market-filters"><button class="pill ${state.marketFilter==='gainers'?'active':''}" data-filter="gainers">Рост</button><button class="pill ${state.marketFilter==='losers'?'active':''}" data-filter="losers">Падение</button><button class="pill ${state.marketFilter==='trending'?'active':''}" data-filter="trending">Объём</button></div>
        <div class="asset-list">${active.slice(0,5).map((x,i)=>assetRow(x,i)).join('')||`<div class="subtle-empty">Поступают актуальные фьючерсные котировки…</div>`}</div>
      </section>
      <section class="panel system-panel">
        <div class="panel-heading"><div><div class="eyebrow">SYSTEM STATUS</div><h2>Состояние MIRAGE</h2></div><span class="status-ring ${statusTone(scanner)}">${icon(scanner==='ACTIVE'?'circle-check':'activity')}</span></div>
        <div class="system-status-main"><strong class="${statusTone(scanner)}">${statusLabel(scanner)}</strong><small>Сканер торговых возможностей</small></div>
        <div class="system-checks">
          <div class="system-check"><span>${icon('activity')} Binance REST</span><b class="${marketHealthy()?'good':'bad'}">${marketHealthy()?'ONLINE':'CHECK'}</b></div>
          <div class="system-check"><span>${icon('radio-tower')||icon('activity')} Live WebSocket</span><b class="${ws?'good':'warn'}">${ws?'CONNECTED':'DEGRADED'}</b></div>
          <div class="system-check"><span>${icon('shield')} PHANTOM</span><b class="${state.dashboard?.engine?.scanner==='ACTIVE'&&ws?'good':'warn'}">${ws?'GUARDED':'PROTECTIVE'}</b></div>
          <div class="system-check"><span>${icon('zap')} Paper execution</span><b class="good">ENABLED</b></div>
        </div>
        <div class="auto-trade-strip"><span class="auto-indicator ${state.settings.auto_trade?'on':''}"></span><div><strong>Автоматическая торговля</strong><small>${state.settings.auto_trade?'Включена для этого счёта':'Выключена в настройках'}</small></div><button class="text-action" data-page="settings">Настроить ${icon('arrow-right')}</button></div>
        <div class="system-foot"><span>Время сканирования</span><strong>${dash.engine?.last_scan?new Date(dash.engine.last_scan*1000).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'}):'—'}</strong></div>
      </section>
    </div>

    <section class="panel recent-panel">
      <div class="panel-heading"><div><div class="eyebrow">SIGNAL INTELLIGENCE</div><h2>Последние сигналы</h2></div><button class="text-action" data-page="scanner">Сканер ${icon('arrow-right')}</button></div>
      ${state.signals.length?state.signals.slice(0,3).map(signalCard).join(''):`<div class="scanner-idle"><div class="radar-mini"><span></span><i></i><b></b></div><div><strong>Сканер анализирует рынок</strong><p>Новые карточки появятся после прохождения фильтров качества S/A и PHANTOM.</p></div></div>`}
    </section>
    <div class="disclaimer-line">${icon('shield')} MIRAGE работает только в Paper Trading. Реальные биржевые ордера отключены.</div>`;
}
function assetRow(x,i){const change=Number(x.change_pct||0),price=Number(x.mark||x.last_price||0),symbol=x.symbol||'';return `<div class="asset-row"><div class="asset-identity">${logoCoin(symbol)}<div><strong>${esc(symbol.replace('USDT',''))}</strong><small>${esc(symbol)} PERP</small></div></div><div class="asset-price"><strong>${price?money(price,price>100?2:4):'—'}</strong><small>Mark Price</small></div><div class="asset-move ${change>=0?'positive':'negative'}"><strong>${change>=0?'▲':'▼'} ${n(Math.abs(change),2)}%</strong><small>24H</small></div><div class="asset-spark">${miniSpark(symbol)}</div></div>`}

function signalCard(s){const side=s.side==='SHORT'?'SHORT':'LONG',ind=s.indicators||{},gate=ind.quality_gate||{};const score=Number(s.score||0);return `<article class="signal-card-v2"><div class="signal-main"><div class="signal-coin">${logoCoin(s.symbol)}</div><div class="signal-name"><div><strong>${esc(s.symbol)}</strong><span class="side-pill ${side.toLowerCase()}">${side==='LONG'?'▲ LONG':'▼ SHORT'}</span></div><small>${esc(s.strategy)} · ${esc(s.interval)} · ${timeAgo(s.created_at)}</small></div><div class="signal-quality"><strong>${score}</strong><small>QUALITY</small></div></div><div class="signal-level-row"><div><small>ENTRY</small><b>${fmtPrice(s.entry)}</b></div><div><small>STOP LOSS</small><b>${fmtPrice(s.stop)}</b></div><div><small>TP1</small><b>${fmtPrice((s.targets||[])[0])}</b></div><div><small>TP2 / TP3</small><b>${fmtPrice((s.targets||[])[1])} / ${fmtPrice((s.targets||[])[2])}</b></div></div><div class="signal-meta-row"><span>${icon('gauge')} Grade ${esc(s.grade||'—')}</span><span>${icon('activity')} RSI ${n(ind.rsi,1)}</span><span>${icon('bar-chart-3')} ADX ${n(ind.adx?.adx,1)}</span><span>${icon('zap')} ATR ${fmtPrice(ind.atr)}</span></div>${(ind.strategy_reasons||[]).length?`<div class="signal-reasons">${(ind.strategy_reasons||[]).slice(0,3).map(x=>`<span>${icon('circle-check')}${esc(x)}</span>`).join('')}</div>`:''}<div class="signal-card-foot"><span class="signal-valid">${icon('shield')} ${gate.passed===false?'Фильтр качества не пройден':'S/A · подтверждённый сетап'}</span><button class="btn btn-quiet small-btn" data-action="open-signal" data-symbol="${esc(s.symbol)}" data-side="${side}" data-strategy="${esc(s.strategy)}" data-interval="${esc(s.interval)}" data-score="${score}" data-stop="${s.stop}" data-tps="${esc(JSON.stringify(s.targets||[]))}">Открыть Paper ${icon('arrow-up-right')}</button></div></article>`}

async function renderScanner(root){
  await refreshBasics();const signals=await api('/api/signals?limit=60');state.signals=signals||[];const engine=state.dashboard?.engine||{},scanner=engine.scanner||'BOOTING';
  const strategies=[['SCALPING','15m','Breakout','Пробой диапазона · импульс объёма'],['INTRADAY','1h','EMA Pullback','Откат к EMA20 · подтверждение MACD'],['SWING','4h','Trend Following','Направление тренда · ADX'],['POSITION','1d','Trend Following','Старший тренд · импульс и DI']];
  root.innerHTML=`<div class="page-intro"><div><div class="eyebrow">MARKET INTELLIGENCE ENGINE</div><h1>Сканер рынка</h1><p>Анализирует бессрочные USDT-контракты Binance по модели исходного Telegram-бота.</p></div><span class="status-pill ${statusTone(scanner)}"><i></i>${statusLabel(scanner)}</span></div>
    <section class="scanner-hero panel"><div class="scanner-visual"><div class="radar-ring ring-a"></div><div class="radar-ring ring-b"></div><div class="radar-ring ring-c"></div><div class="radar-sweep"></div><div class="radar-core">${icon('scan-line')}</div><span class="radar-node node-a"></span><span class="radar-node node-b"></span><span class="radar-node node-c"></span></div><div class="scanner-summary"><div class="eyebrow">AUTONOMOUS SCAN</div><h2>${scanner==='ACTIVE'?'Сканер активен':'Анализ рынка'}</h2><p>${engine.last_error?esc(engine.last_error):'Закрытые свечи · индикаторы · фильтр S/A · защита от повторных сигналов.'}</p><div class="scanner-stats"><div><strong>${engine.scan_candidates??0}</strong><small>Сетапы цикла</small></div><div><strong>${engine.signals_saved??0}</strong><small>Сохранено</small></div><div><strong>${engine.auto_positions_opened??0}</strong><small>Автовходы</small></div></div></div></section>
    <div class="scanner-control-row"><div class="auto-exec-state"><span class="auto-indicator ${state.settings.auto_trade?'on':''}"></span><div><strong>${state.settings.auto_trade?'AUTO PAPER EXECUTION ON':'AUTO PAPER EXECUTION OFF'}</strong><small>${state.settings.auto_trade?'Сигналы открывают позиции автоматически':'Включите автоматическую торговлю в настройках'}</small></div></div><button class="btn btn-outline" data-page="settings">Настройки ${icon('arrow-right')}</button></div>
    ${sectionHead('Стратегические горизонты','Фильтры отбора исходной системы')}
    <div class="strategy-grid">${strategies.map(([name,tf,model,desc],i)=>`<div class="strategy-card"><div class="strategy-card-top"><span class="strategy-index">0${i+1}</span><span class="strategy-time">${tf}</span></div><strong>${name}</strong><b>${model}</b><p>${desc}</p><div class="strategy-card-bottom"><span>${icon('activity')} Binance Futures</span><span class="strategy-active">${icon('circle-check')} ENABLED</span></div></div>`).join('')}</div>
    ${sectionHead('Квалифицированные сигналы',`${state.signals.length} последних · Grade S/A · качество от 80/100`)}
    <div class="signal-feed">${state.signals.map(signalCard).join('')||`<div class="empty-scanner panel"><div class="empty-radar">${icon('scan-line')}</div><h3>Пока нет подтверждённых сигналов</h3><p>Это нормально: система не открывает сделки, если фильтры направления, EMA, ADX и объёма не совпадают. Автоматический поиск продолжится на сервере.</p><div class="empty-checks"><span>${icon('circle-check')} Закрытые свечи</span><span>${icon('circle-check')} EMA / RSI / MACD</span><span>${icon('circle-check')} ADX / DI / объём</span></div></div>`}</div>`;
}

async function renderTrading(root){
  const [dash,open,closed]=await Promise.all([refreshBasics(),api('/api/trades?status=OPEN'),api('/api/trades?status=CLOSED')]);state.trades=state.tradeStatus==='OPEN'?open:closed;
  const d=dash[0];
  root.innerHTML=`<div class="page-intro"><div><div class="eyebrow">EXECUTION & POSITION CONTROL</div><h1>Торговля</h1><p>Binance USDⓈ-M Futures · Isolated Margin · Paper execution only</p></div><span class="paper-chip">${icon('shield')} PAPER ONLY</span></div>
    <div class="trading-summary"><div class="panel account-summary"><small>ЭКВИТИ СЧЁТА</small><strong>${money(d.equity)}</strong><span class="${Number(d.unrealized_pnl||0)>=0?'positive':'negative'}">${Number(d.unrealized_pnl||0)>=0?'+':''}${money(d.unrealized_pnl)} unrealized</span><div class="summary-sub">Balance ${money(d.balance)}</div></div><div class="panel account-stat"><div><span>${icon('activity')}</span><small>Открытые позиции</small></div><strong>${d.open_positions||0}<em> / ${state.settings.max_positions||3}</em></strong><div class="summary-sub">${money(d.open_risk||0)} open risk</div></div><div class="panel account-stat"><div><span>${icon('wallet')}</span><small>Свободная маржа</small></div><strong>${money(Math.max(0,(d.balance||0)-((d.open_notional||0)/3)))}</strong><div class="summary-sub">Оценка при 3x · не биржевой margin balance</div></div></div>
    <div class="trade-tabs"><button class="pill ${state.tradeStatus==='OPEN'?'active':''}" data-trade-status="OPEN">Открытые <b>${open.length}</b></button><button class="pill ${state.tradeStatus==='CLOSED'?'active':''}" data-trade-status="CLOSED">История <b>${closed.length}</b></button></div>
    <div class="trade-list">${state.trades.map(tradeCard).join('')||`<div class="empty-trades panel"><div class="empty-trade-icon">${icon(state.tradeStatus==='OPEN'?'arrow-left-right':'chart-no-axes-combined')}</div><h3>${state.tradeStatus==='OPEN'?'Открытых позиций пока нет':'История сделок пока пуста'}</h3><p>${state.tradeStatus==='OPEN'?(state.settings.auto_trade?'MIRAGE самостоятельно откроет позицию после появления подходящего сетапа и прохождения PHANTOM.':'Включите автоматическую торговлю, чтобы MIRAGE самостоятельно открывал позиции.'):'Закрытые Paper-сделки с комиссиями и funding появятся здесь.'}</p><button class="btn btn-outline" data-page="${state.tradeStatus==='OPEN'?'scanner':'analytics'}">${state.tradeStatus==='OPEN'?'Перейти к сканеру':'Открыть аналитику'} ${icon('arrow-right')}</button></div>`}</div>
    <section class="manual-intel panel"><div class="manual-art">${icon('brain-circuit')}</div><div><div class="eyebrow">MANUAL INTELLIGENCE</div><h3>Проверить отдельный контракт</h3><p>Дополнительный анализ — не требуется для автоматической торговли.</p></div><button class="btn btn-outline" data-page="intelligence">Анализировать ${icon('arrow-right')}</button></section>`;
}
function tradeCard(t){const isOpen=t.status==='OPEN',net=Number(t.realized_net||0),side=t.side==='SHORT'?'SHORT':'LONG';const targets=t.targets||[];return `<article class="position-card panel"><div class="position-head"><div class="position-title">${logoCoin(t.symbol)}<div><strong>${esc(t.symbol)} <span class="side-pill ${side.toLowerCase()}">${side}</span></strong><small>${esc(t.strategy)} · ${t.leverage}x isolated · ${timeAgo(t.opened_at)}</small></div></div><div class="position-pnl ${net>=0?'positive':'negative'}">${net>=0?'+':''}${money(net)}<small>${isOpen?'Realized P&L':'Net result'}</small></div></div>
  <div class="position-levels"><div><small>ENTRY</small><strong>${fmtPrice(t.entry)}</strong></div><div><small>${isOpen?'MARK PRICE':'EXIT STATUS'}</small><strong>${isOpen?fmtPrice(state.market.items?.find(x=>x.symbol===t.symbol)?.mark):esc(t.close_reason||'CLOSED')}</strong></div><div><small>STOP LOSS</small><strong>${fmtPrice(t.stop)}</strong></div><div><small>REMAINING</small><strong>${n(t.remaining_qty,5)}</strong></div></div>
  <div class="position-progress"><span class="progress-track"><i style="width:${Math.max(0,Math.min(100,(1-(Number(t.remaining_qty||0)/Math.max(Number(t.qty||1),1e-12)))*100))}%"></i></span><span>${isOpen?'План выхода':'Завершена'}</span></div>
  <div class="position-meta"><span>${icon('wallet')} Margin ${money(t.margin)}</span><span>${icon('activity')} Risk ${money(t.risk_amount)}</span><span>${icon('zap')} Fees ${money(Number(t.entry_fee||0)+Number(t.exit_fee||0))}</span><span>${icon('clock')} Funding ${money(t.funding_pnl)}</span></div>
  <div class="position-targets">${targets.map((tp,i)=>`<span class="${(t.target_hits||[]).includes(i)?'hit':''}"><small>TP${i+1}</small><b>${fmtPrice(tp)}</b></span>`).join('')}</div>
  <div class="position-foot"><span class="position-state ${isOpen?'open':'closed'}"><i></i>${isOpen?'OPEN POSITION':`CLOSED · ${esc(t.close_reason||'—')}`}</span>${isOpen?`<button class="btn btn-quiet small-btn" data-action="close-trade" data-id="${t.id}">Закрыть позицию</button>`:`<small>${t.closed_at?new Date(t.closed_at*1000).toLocaleString('ru-RU'):''}</small>`}</div></article>`}

async function renderAnalytics(root){
  await refreshBasics();const a=await api('/api/analytics');state.analytics=a;const vals=(a.equity_curve||[]).map(x=>Number(x.equity));
  root.innerHTML=`<div class="page-intro"><div><div class="eyebrow">PERFORMANCE INTELLIGENCE</div><h1>Аналитика</h1><p>Результаты закрытых Paper-сделок за вычетом комиссий и funding.</p></div><span class="paper-chip">${icon('chart-no-axes-combined')} ACCOUNT</span></div>
    <div class="analytics-hero panel"><div><small>NET P&L</small><strong class="${a.net_pnl>=0?'positive':'negative'}">${a.net_pnl>=0?'+':''}${money(a.net_pnl)}</strong><span>${a.closed} закрытых сделок</span></div><div class="analytics-orbit">${icon('chart-no-axes-combined')}<b>${n(a.win_rate,1)}%</b><small>WIN RATE</small></div></div>
    <div class="metric-grid-v2"><div class="metric-tile panel"><small>Win Rate</small><strong>${n(a.win_rate,1)}%</strong><span>${a.wins} прибыльных</span></div><div class="metric-tile panel"><small>Profit Factor</small><strong>${n(a.profit_factor,2)}</strong><span>Gross profit / loss</span></div><div class="metric-tile panel"><small>Average Trade</small><strong>${money(a.avg_trade)}</strong><span>Средняя net-сделка</span></div><div class="metric-tile panel"><small>Закрытые позиции</small><strong>${a.closed}</strong><span>${a.losses} убыточных</span></div></div>
    <section class="panel chart-panel-v2"><div class="panel-heading"><div><div class="eyebrow">EQUITY CURVE</div><h2>Кривая капитала</h2></div><span class="chart-caption">${a.closed} точки</span></div>${vals.length>1?chartSvg(vals,{width:720,height:190,cls:'equity-line'}):`<div class="chart-no-history"><div>${icon('chart-no-axes-combined')}</div><strong>График появится после первой закрытой сделки</strong><span>Исторические значения не подменяются демонстрационными данными.</span></div>`}<div class="chart-foot"><span>Начальный капитал $10,000</span><span>Net of fees & funding</span></div></section>
    <section class="panel strategy-performance"><div class="panel-heading"><div><div class="eyebrow">STRATEGY BREAKDOWN</div><h2>Результат по стратегиям</h2></div></div>${Object.keys(a.by_strategy||{}).length?Object.entries(a.by_strategy).map(([k,v])=>`<div class="strategy-performance-row"><div><strong>${esc(k)}</strong><small>Paper futures</small></div><b class="${v>=0?'positive':'negative'}">${v>=0?'+':''}${money(v)}</b></div>`).join(''):`<div class="chart-no-history compact"><strong>Пока нет закрытых сделок</strong><span>Разбивка по стратегиям будет рассчитана автоматически.</span></div>`}</section>`;
}

async function renderIntelligence(root){
  root.innerHTML=`<div class="page-intro"><div><div class="eyebrow">TECHNICAL RESEARCH</div><h1>Интеллект</h1><p>Ручной анализ по тому же алгоритму, что использует автоматический сканер.</p></div><span class="paper-chip">${icon('brain-circuit')} RULE-BASED</span></div>
    <section class="panel analysis-form-panel"><div class="analysis-form-art">${icon('scan-line')}</div><div class="form-grid-v2"><label>Контракт<input id="analyze-symbol" value="BTCUSDT" autocapitalize="characters" spellcheck="false"></label><label>Таймфрейм<select id="analyze-interval"><option value="15m">15 минут · Scalping</option><option value="1h" selected>1 час · Intraday</option><option value="4h">4 часа · Swing</option><option value="1d">1 день · Position</option></select></label><button class="btn primary full" id="analyze-button">Запустить анализ ${icon('arrow-right')}</button></div><p class="form-note">Система анализирует только закрытые свечи. Сетап ниже 80/100 или без независимого подтверждения не допускается к открытию позиции.</p></section><div id="analysis-result"></div>`;
}
async function runAnalysis(){
  const symbol=$('#analyze-symbol')?.value.trim().toUpperCase(),interval=$('#analyze-interval')?.value,root=$('#analysis-result');if(!symbol){toast('Введите символ контракта','error');return}
  root.innerHTML=`<div class="panel analysis-loading"><span class="loader-orbit"></span><strong>Анализ ${esc(symbol)}</strong><small>EMA · RSI · MACD · ATR · ADX · объём</small></div>`;
  try{const r=await api(`/api/analyze?symbol=${encodeURIComponent(symbol)}&interval=${interval}`);root.innerHTML=`<article class="analysis-result panel"><div class="analysis-result-head"><div>${logoCoin(r.symbol)}<div><strong>${esc(r.symbol)} <span class="side-pill ${r.side.toLowerCase()}">${r.side}</span></strong><small>${esc(r.strategy)} · ${r.interval}</small></div></div><div class="signal-quality"><strong>${r.score}</strong><small>QUALITY / 100</small></div></div><div class="analysis-level-grid"><div><small>ENTRY</small><b>${fmtPrice(r.entry)}</b></div><div><small>STOP LOSS</small><b>${fmtPrice(r.stop)}</b></div><div><small>TP1</small><b>${fmtPrice(r.tps[0])}</b></div><div><small>TP2</small><b>${fmtPrice(r.tps[1])}</b></div><div><small>TP3</small><b>${fmtPrice(r.tps[2])}</b></div></div><div class="indicator-grid"><div><small>RSI 14</small><b>${n(r.rsi,1)}</b></div><div><small>ADX</small><b>${n(r.adx?.adx,1)}</b></div><div><small>EMA 20</small><b>${fmtPrice(r.ema20)}</b></div><div><small>EMA 50</small><b>${fmtPrice(r.ema50)}</b></div><div><small>MACD</small><b>${n(r.macd?.histogram,4)}</b></div><div><small>VOLUME RATIO</small><b>${n(r.volume_ratio,2)}x</b></div></div><div class="signal-reasons">${(r.reasons||[]).map(x=>`<span>${icon('circle-check')}${esc(x)}</span>`).join('')}</div><div class="analysis-result-foot"><span class="signal-valid">${icon('shield')} Qualified S/A setup</span><button class="btn btn-outline" data-action="open-analysis" data-symbol="${esc(r.symbol)}" data-side="${r.side}" data-strategy="${r.strategy}" data-interval="${r.interval}" data-score="${r.score}" data-stop="${r.stop}" data-tps="${esc(JSON.stringify(r.tps))}">Открыть Paper позицию ${icon('arrow-up-right')}</button></div></article>`}
  catch(e){root.innerHTML=`<div class="analysis-no-setup panel"><div>${icon('alert-triangle')}</div><strong>Квалифицированный сетап не найден</strong><p>${esc(e.message)}</p><small>Система не будет предлагать сделку без полного подтверждения условий.</small></div>`}
}

async function renderNews(root){const d=await api('/api/news').catch(e=>({items:[],status:e.message}));state.news=d;root.innerHTML=`<div class="page-intro"><div><div class="eyebrow">MARKET CONTEXT</div><h1>Новости</h1><p>Информационный фон. Новости не являются торговым сигналом.</p></div><span class="paper-chip">${icon('newspaper')} NEWS FEED</span></div><section class="panel news-top"><div class="news-symbol">${icon('newspaper')}</div><div><strong>Новости рынка</strong><p>${esc(d.status||'Поток источников')}</p></div></section><div class="news-feed">${(d.items||[]).map(x=>`<article class="news-card panel"><div class="news-card-meta"><span>${esc(x.source||'MARKET SOURCE')}</span><span>${esc(x.published||'')}</span></div><h3>${esc(x.title)}</h3><p>${esc(x.summary||'Откройте источник для полного материала.')}</p><a href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">Открыть источник ${icon('external-link')}</a></article>`).join('')||`<div class="chart-no-history panel"><div>${icon('newspaper')}</div><strong>Лента временно недоступна</strong><span>Заголовки не генерируются и не подменяются вымышленными новостями.</span></div>`}</div>`}

async function renderPhantom(root){const p=await api('/api/phantom');state.phantom=p;const active=p.state==='ACTIVE';root.innerHTML=`<div class="page-intro"><div><div class="eyebrow">INDEPENDENT SAFETY LAYER</div><h1>PHANTOM Protocol</h1><p>Контроль состояния данных, допуска к новым входам и сопровождения открытых позиций.</p></div><span class="status-pill ${active?'good':'warn'}"><i></i>${active?'PROTECTION ACTIVE':'PROTECTIVE MODE'}</span></div><section class="phantom-hero panel"><div class="phantom-emblem">${icon('shield')}</div><div><div class="eyebrow">CURRENT PROTECTION STATE</div><h2 class="${active?'good':'warn'}">${active?'ACTIVE':'PROTECTIVE'}</h2><p>${active?'REST и оба live-потока свежие. Допуск новых Paper-входов может быть разрешён.':'Новые входы блокируются, пока не восстановлены надёжные данные.'}</p></div></section><section class="panel phantom-checks"><div class="panel-heading"><div><div class="eyebrow">SYSTEM VALIDATION</div><h2>Проверки протокола</h2></div></div>${(p.checks||[]).map((x,i)=>`<div class="phantom-check-row"><span class="check-index">0${i+1}</span><div class="check-copy"><strong>${esc(x.name)}</strong><small>${esc(x.detail||'')}</small></div><span class="check-state ${x.ok?'good':'warn'}">${x.ok?icon('circle-check'):icon('alert-triangle')}</span></div>`).join('')}</section><section class="panel audit-panel"><div class="panel-heading"><div><div class="eyebrow">AUDIT TRAIL</div><h2>Журнал событий</h2></div><span class="chart-caption">${(p.events||[]).length} записей</span></div>${(p.events||[]).map(x=>`<div class="audit-row"><span class="audit-dot ${esc((x.severity||'').toLowerCase())}"></span><div><strong>${esc(x.category)} · ${esc(x.severity)}</strong><p>${esc(x.message)}</p><small>${new Date(x.created_at*1000).toLocaleString('ru-RU')}</small></div></div>`).join('')||`<div class="chart-no-history compact"><strong>Критических событий нет</strong><span>Все изменения состояния будут записываться сюда.</span></div>`}</section>`}

async function renderSettings(root){await refreshBasics();const s=state.settings;root.innerHTML=`<div class="page-intro"><div><div class="eyebrow">PERSONAL CONFIGURATION</div><h1>Настройки</h1><p>Параметры личного виртуального фьючерсного счёта.</p></div><span class="paper-chip">${icon('settings')} CONTROL</span></div>
  <section class="panel settings-account"><div class="account-avatar">${esc((state.user?.username||'U').slice(0,1).toUpperCase())}</div><div><strong>${esc(state.user?.username||'')}</strong><small>${esc(state.user?.role||'user').toUpperCase()} · PRIVATE ACCOUNT</small></div><span class="account-capital">${money(state.dashboard?.balance||10000)}</span></section>
  <section class="panel settings-section"><div class="settings-section-head"><div><div class="eyebrow">EXECUTION MODE</div><h2>Автоматическая торговля</h2></div><span class="status-pill ${s.auto_trade?'good':'warn'}"><i></i>${s.auto_trade?'ENABLED':'DISABLED'}</span></div><div class="settings-toggle-row"><div><strong>Automatic Paper Trading</strong><p>MIRAGE самостоятельно сканирует рынок и открывает подходящие позиции без ручного подтверждения.</p></div><label class="toggle"><input id="setting-auto" type="checkbox" ${s.auto_trade?'checked':''}><span></span></label></div><div class="safety-note">${icon('shield')} Только виртуальные сделки. Реальные ордера Binance не поддерживаются и не отправляются.</div></section>
  <section class="panel settings-section"><div class="eyebrow">RISK MANAGEMENT</div><h2>Контроль риска</h2><div class="range-setting"><div><strong>Риск на сделку</strong><b id="risk-value">${n(s.risk_pct||1,2)}%</b></div><input id="setting-risk" type="range" min="0.25" max="2" step="0.25" value="${s.risk_pct||1}"><div class="range-labels"><span>0.25%</span><span>2.00%</span></div></div><div class="range-setting"><div><strong>Совокупный открытый риск</strong><b id="risk-cap-value">${n(s.max_total_risk_pct||3,1)}%</b></div><input id="setting-risk-cap" type="range" min="1" max="5" step="0.5" value="${s.max_total_risk_pct||3}"><div class="range-labels"><span>1%</span><span>5%</span></div></div><div class="range-setting"><div><strong>Максимум открытых позиций</strong><b id="positions-value">${s.max_positions||3}</b></div><input id="setting-positions" type="range" min="1" max="3" step="1" value="${s.max_positions||3}"><div class="range-labels"><span>1</span><span>3</span></div></div><p class="form-note">Плечо выбирается по качеству сигнала до 8x и не увеличивает бюджет риска. Позиции открываются с isolated margin.</p></section>
  <section class="panel settings-section"><div class="eyebrow">INTERFACE</div><h2>Вид интерфейса</h2><div class="mode-choice"><button class="mode-option ${state.mode==='STEALTH'?'selected':''}" data-mode="STEALTH"><span>${icon('eye')}</span><strong>STEALTH MODE</strong><small>Минималистичный вид</small></button><button class="mode-option ${state.mode==='SPECTRE'?'selected':''}" data-mode="SPECTRE"><span>${icon('brain-circuit')}</span><strong>SPECTRE MODE</strong><small>Расширенные данные</small></button></div><p class="form-note">Режим меняет только визуальное отображение. Все расчёты, фильтры и функции продолжают работать.</p></section>
  <section class="panel settings-section"><div class="eyebrow">EXPERIENCE</div><h2>Предпочтения</h2><div class="settings-toggle-row"><div><strong>Уведомления</strong><p>Важные события, входы и блокировки PHANTOM.</p></div><label class="toggle"><input id="setting-notify" type="checkbox" ${s.notifications?'checked':''}><span></span></label></div><div class="settings-toggle-row"><div><strong>Уменьшить анимации</strong><p>Отключить часть переходов интерфейса.</p></div><label class="toggle"><input id="setting-motion" type="checkbox" ${s.reduced_motion?'checked':''}><span></span></label></div></section>
  <section class="panel settings-section"><div class="eyebrow">MARKET CONNECTION</div><h2>Подключение данных</h2><div class="connection-row"><span>Binance USDⓈ-M REST</span><b class="${marketHealthy()?'good':'warn'}">${marketHealthy()?'CONNECTED':'CHECK'}</b></div><div class="connection-row"><span>Mark Price WebSocket</span><b class="${state.dashboard?.engine?.websocket?.market_connected?'good':'warn'}">${state.dashboard?.engine?.websocket?.market_connected?'CONNECTED':'OFFLINE'}</b></div><div class="connection-row"><span>Bid / Ask WebSocket</span><b class="${state.dashboard?.engine?.websocket?.public_connected?'good':'warn'}">${state.dashboard?.engine?.websocket?.public_connected?'CONNECTED':'OFFLINE'}</b></div><div class="connection-row"><span>Source</span><b class="connection-source">${esc(s.language||'ru').toUpperCase()} · ${esc(state.market.market?.region||'')}</b></div></section>
  <button class="btn logout-btn" id="logout-button">${icon('external-link')} Выйти из аккаунта</button><div class="settings-version">MIRAGE v1.2 · USDⓈ-M FUTURES · PAPER ONLY</div>`;
}
function renderMore(root){root.innerHTML=`<div class="page-intro"><div><div class="eyebrow">MIRAGE SUITE</div><h1>Ещё</h1><p>Инструменты мониторинга и управления системой.</p></div><span class="paper-chip">${icon('layers-3')} MODULES</span></div><div class="more-grid-v2"><button class="more-card panel" data-page="intelligence"><span>${icon('brain-circuit')}</span><strong>Интеллект</strong><small>Анализ отдельного контракта</small>${icon('chevron-right','more-arrow')}</button><button class="more-card panel" data-page="news"><span>${icon('newspaper')}</span><strong>Новости</strong><small>Информационный контекст рынка</small>${icon('chevron-right','more-arrow')}</button><button class="more-card panel" data-page="phantom"><span>${icon('shield')}</span><strong>PHANTOM</strong><small>Защита и журнал событий</small>${icon('chevron-right','more-arrow')}</button><button class="more-card panel" data-page="settings"><span>${icon('settings')}</span><strong>Настройки</strong><small>Риск, автоматизация и вид</small>${icon('chevron-right','more-arrow')}</button><button class="more-card panel" data-page="analytics"><span>${icon('chart-no-axes-combined')}</span><strong>Аналитика</strong><small>Статистика виртуального счёта</small>${icon('chevron-right','more-arrow')}</button><button class="more-card panel" data-page="trading"><span>${icon('arrow-left-right')}</span><strong>Позиции</strong><small>Сделки, уровни, комиссии</small>${icon('chevron-right','more-arrow')}</button></div><section class="panel about-panel"><div class="about-mark"><svg class="logo-mark" viewBox="0 0 100 100"><path d="M50 7 83 26 83 60 64 72 64 43 50 51 36 43 36 72 17 60 17 26 50 7Z"/><path d="M50 7 50 24 72 37M50 24 28 37M50 51 50 91"/></svg></div><div><strong>MIRAGE</strong><p>Private trading intelligence. Futures paper execution. No real exchange orders.</p></div></section>`}

async function openPaperTrade(data){
  let targets=[];try{targets=JSON.parse(data.tps||'[]')}catch{}
  if(targets.length!==3){toast('Не удалось прочитать уровни Take Profit','error');return}
  if(!confirm(`Открыть ${data.side} ${data.symbol} в PAPER режиме? Автоматическая торговля уже работает отдельно.`))return;
  try{await api('/api/trades/open',{method:'POST',body:JSON.stringify({symbol:data.symbol,side:data.side,strategy:data.strategy,interval:data.interval,score:Number(data.score),stop:Number(data.stop),tp1:Number(targets[0]),tp2:Number(targets[1]),tp3:Number(targets[2])})});toast('Paper-позиция открыта');state.tradeStatus='OPEN';await navigate('trading')}
  catch(e){toast(e.message,'error')}
}
async function patchSettings(patch){try{state.settings=await api('/api/settings',{method:'PATCH',body:JSON.stringify(patch)});toast('Настройки сохранены');return true}catch(e){toast(e.message,'error');return false}}

// Global event delegation keeps controls functional across animated page swaps.
document.addEventListener('click',async e=>{
  const nav=e.target.closest('[data-page]');if(nav){navTo(nav.dataset.page);return}
  const filter=e.target.closest('[data-filter]');if(filter){state.marketFilter=filter.dataset.filter;await navigate('home');return}
  const tab=e.target.closest('[data-trade-status]');if(tab){state.tradeStatus=tab.dataset.tradeStatus;await navigate('trading');return}
  const mode=e.target.closest('[data-mode]');if(mode){state.mode=mode.dataset.mode;localStorage.setItem('mirage-mode',state.mode);applyMode();await navigate('settings');return}
  const action=e.target.closest('[data-action]');if(action){const a=action.dataset.action;
    if(a==='open-signal'||a==='open-analysis')await openPaperTrade(action.dataset);
    if(a==='close-trade'){if(!confirm('Закрыть Paper-позицию по текущим рыночным Bid/Ask?'))return;try{await api(`/api/trades/${action.dataset.id}/close`,{method:'POST'});toast('Paper-позиция закрыта');await navigate('trading')}catch(err){toast(err.message,'error')}}
    if(a==='retry')await navigate(state.page);
  }
  if(e.target.closest('#mode-toggle'))setMode();
  if(e.target.closest('#profile-btn'))navTo('settings');
  if(e.target.closest('#analyze-button'))runAnalysis();
  if(e.target.closest('#logout-button')){try{await api('/api/auth/logout',{method:'POST'})}catch{}showLogin()}
});

document.addEventListener('input',e=>{
  if(e.target.id==='setting-risk')$('#risk-value').textContent=`${n(e.target.value,2)}%`;
  if(e.target.id==='setting-risk-cap')$('#risk-cap-value').textContent=`${n(e.target.value,1)}%`;
  if(e.target.id==='setting-positions')$('#positions-value').textContent=e.target.value;
});
document.addEventListener('change',async e=>{
  const id=e.target.id;let patch={};
  if(id==='setting-auto')patch.auto_trade=e.target.checked;
  if(id==='setting-risk')patch.risk_pct=Number(e.target.value);
  if(id==='setting-risk-cap')patch.max_total_risk_pct=Number(e.target.value);
  if(id==='setting-positions')patch.max_positions=Number(e.target.value);
  if(id==='setting-notify')patch.notifications=e.target.checked;
  if(id==='setting-motion')patch.reduced_motion=e.target.checked;
  if(Object.keys(patch).length){const ok=await patchSettings(patch);if(ok){state.settings={...state.settings,...patch};applyMode();if(id==='setting-auto')await navigate(state.page)}}
});

$('#login-form').addEventListener('submit',async e=>{e.preventDefault();const button=$('#login-button');button.disabled=true;$('#login-error').textContent='';try{const result=await api('/api/auth/login',{method:'POST',body:JSON.stringify({username:$('#login-user').value,password:$('#login-pass').value})});state.user=result.user;const me=await api('/api/auth/me');state.settings=me.settings||{};showApp();await navigate('home');startPolling();toast('Добро пожаловать в MIRAGE')}catch(err){$('#login-error').textContent=err.message}finally{button.disabled=false}});

function stopPolling(){if(state.pollTimer){clearInterval(state.pollTimer);state.pollTimer=null}}
function startPolling(){stopPolling();state.pollTimer=setInterval(async()=>{if(!state.user)return;try{await refreshBasics();if(state.page==='home')await renderHome($('#page-content'));else if(state.page==='trading'&&state.tradeStatus==='OPEN')await renderTrading($('#page-content'));}catch{}},15000)}
async function boot(){document.querySelectorAll('[data-icon]').forEach(el=>{const name=el.dataset.icon;el.outerHTML=icon(name,el.className||'')});if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js',{updateViaCache:'none'}).then(reg=>reg.update()).catch(()=>{})}applyMode();try{const me=await api('/api/auth/me');state.user=me.user;state.settings=me.settings||{};showApp();await navigate('home');startPolling()}catch{showLogin()}}
boot();
