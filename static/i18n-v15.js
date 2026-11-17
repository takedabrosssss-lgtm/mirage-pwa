/* MIRAGE v1.5 complete UI locale layer. No framework or third-party request. */
(() => {
  'use strict';

  const RU_EN = {
    'Добро пожаловать':'Welcome back',
    'Войдите в свой аккаунт MIRAGE':'Sign in to your MIRAGE account',
    'Логин':'Username', 'Ваш логин':'Your username', 'Пароль':'Password', 'Ваш пароль':'Your password',
    'Войти в MIRAGE':'Sign in to MIRAGE', 'Пропустить':'Skip', 'Далее':'Continue',
    'Перейти ко входу':'Go to sign in', 'Главная':'Home', 'Сканер':'Scanner', 'Аналитика':'Analytics',
    'Торговля':'Trading', 'Ещё':'More', 'Инициализация MIRAGE':'Initializing MIRAGE',
    'Обзор портфеля':'Portfolio overview', 'Рыночная аналитика и автоматическое Paper Trading':'Market intelligence and automated paper trading',
    'Рынок':'Market', 'Рост':'Gainers', 'Падение':'Losers', 'Объём':'Volume', 'Все активы':'All assets',
    'Состояние MIRAGE':'MIRAGE system status', 'Сканер торговых возможностей':'Trading opportunity scanner',
    'Автоматическая торговля':'Automated trading', 'Включена для этого счёта':'Enabled for this account',
    'Выключена в настройках':'Disabled in settings', 'Настроить':'Configure',
    'Время сканирования':'Last scan', 'Последние сигналы':'Latest signals', 'Сканер анализирует рынок':'Scanner is analysing the market',
    'Портфель':'Portfolio', 'Позиции':'Positions', 'Открытые позиции':'Open positions', 'История':'History',
    'Открытых позиций пока нет':'No open positions yet', 'История сделок пока пуста':'Trade history is empty',
    'Открыть Paper':'Open paper trade', 'Открыть аналитику':'Open analytics', 'Закрыть позицию':'Close position',
    'Закрыть':'Close', 'Открытые':'Open', 'Закрытые':'Closed', 'Баланс':'Balance',
    'Начальный капитал':'Initial capital', 'Свободная маржа':'Free margin', 'Совокупный открытый риск':'Total open risk',
    'Нереализованный P&L':'Unrealized P&L', 'Пока нет закрытых сделок':'No closed trades yet',
    'Результат по стратегиям':'Performance by strategy', 'Разбивка по стратегиям будет рассчитана автоматически.':'Strategy breakdown will appear automatically.',
    'Пока нет подтверждённых сигналов':'No qualified signals yet', 'Квалифицированные сигналы':'Qualified signals',
    'Ручная проверка обновляет сигналы и не открывает сделки.':'Manual scan refreshes signals and never opens trades.',
    'Проверить сейчас':'Scan now', 'Перейти к сканеру':'Open scanner', 'Настройки':'Settings',
    'Ручной анализ по тому же алгоритму, что использует автоматический сканер.':'Manual analysis uses the same model as the automatic scanner.',
    'Введите символ контракта':'Enter contract symbol', 'Таймфрейм':'Timeframe', 'Запустить анализ':'Run analysis',
    'Анализировать':'Analyse', 'Квалифицированный сетап не найден':'No qualified setup found',
    'Система не будет предлагать сделку без полного подтверждения условий.':'MIRAGE will not suggest a trade without full condition confirmation.',
    'Анализ':'Analysis', 'Анализ рынка':'Market analysis', 'Новости':'News', 'Новости рынка':'Market news',
    'Информационный фон. Новости не являются торговым сигналом.':'Market context. News is not a trading signal.',
    'Открыть источник':'Open source', 'Откройте источник для полного материала.':'Open the source for the full story.',
    'Лента временно недоступна':'Feed temporarily unavailable',
    'Заголовки не генерируются и не подменяются вымышленными новостями.':'Headlines are never fabricated or replaced with invented stories.',
    'PHANTOM Protocol':'PHANTOM Protocol', 'Защита сделок':'Trade protection', 'Защита и журнал событий':'Protection and event log',
    'Проверки протокола':'Protocol checks', 'Журнал событий':'Event log', 'Критических событий нет':'No critical events',
    'Все изменения состояния будут записываться сюда.':'All system-state changes will be recorded here.',
    'Настройки сохранены':'Settings saved', 'Добро пожаловать в MIRAGE':'Welcome to MIRAGE',
    'Сессия завершена. Войдите снова.':'Your session has expired. Please sign in again.',
    'Завершение сеанса…':'Signing out…', 'Выйти из аккаунта':'Sign out', 'Выйти из аккаунта MIRAGE':'Sign out of MIRAGE',
    'Сервер не подтвердил завершение сеанса':'The server did not confirm sign-out',
    'Не удалось загрузить раздел':'Could not load this section', 'Повторить':'Try again',
    'Формат чисел':'Language', 'Русский':'Russian', 'English':'English', 'Предпочтения':'Preferences',
    'Уведомления':'Notifications', 'Важные события, входы и блокировки PHANTOM.':'Important events, entries and PHANTOM blocks.',
    'Уменьшить анимации':'Reduce motion', 'Отключить часть переходов интерфейса.':'Reduce interface transitions and animations.',
    'Вид интерфейса':'Interface appearance', 'Минималистичный вид':'Minimal interface', 'Расширенные данные':'Advanced information',
    'Режим меняет только визуальное отображение. Все расчёты, фильтры и функции продолжают работать.':'This changes the visual theme only. All calculations, filters and functions remain active.',
    'Параметры личного виртуального фьючерсного счёта.':'Personal virtual futures account settings.',
    'Автоматические входы выключены':'Automatic entries are disabled',
    'Автоматические входы проходят отдельные лимиты защиты':'Automatic entries must pass separate safety limits',
    'MIRAGE самостоятельно сканирует рынок и открывает подходящие позиции без ручного подтверждения.':'MIRAGE scans the market and opens qualified paper positions without manual confirmation.',
    'Только виртуальные сделки. Реальные ордера Binance не поддерживаются и не отправляются.':'Virtual trades only. No real Binance orders are supported or submitted.',
    'Контроль риска':'Risk management', 'Риск на сделку':'Risk per trade', 'Максимум открытых позиций':'Maximum open positions',
    'Лимит до 10 позиций. Реальное число одновременно открытых сделок дополнительно ограничивается совокупным денежным риском. Плечо до 8x выбирается по качеству сигнала.':'Up to 10 positions. The actual number of concurrent trades is also limited by total account risk. Leverage up to 8x is selected by signal quality.',
    'Подключение данных':'Market data connection', 'Фильтр качества не пройден':'Quality filter not passed',
    'Сканер рынка':'Market scanner', 'Анализирует бессрочные USDT-контракты Binance по модели исходного Telegram-бота.':'Analyses Binance USDT perpetual contracts with the MIRAGE hybrid intelligence engine.',
    'Сканер активен':'Scanner active', 'Анализ рынка':'Market analysis',
    'Закрытые свечи · индикаторы · фильтр S/A · защита от повторных сигналов.':'Closed candles · indicators · S/A filter · duplicate-signal protection.',
    'Сетапы цикла':'Setups this cycle', 'Сохранено':'Saved', 'Автовходы':'Auto entries',
    'Автоматические входы проходят отдельные лимиты защиты':'Automatic entries pass separate risk and safety checks',
    'Автоматические входы выключены':'Automatic entries are disabled',
    'Стратегические горизонты':'Strategy models', 'Фильтры отбора исходной системы':'Hybrid signal selection and confirmation',
    'Пробой диапазона · импульс объёма':'Range breakout · volume impulse', 'Откат к EMA20 · подтверждение MACD':'EMA pullback · MACD confirmation',
    'Направление тренда · ADX':'Trend direction · ADX', 'Старший тренд · импульс и DI':'Higher-timeframe trend · momentum and DI',
    'Пробой диапазона':'Range breakout', 'Откат к':'Pullback to', 'Старший тренд':'Higher-timeframe trend',
    'Статистика виртуального счёта':'Virtual account statistics',
    'Кривая капитала учитывает все реальные изменения виртуального баланса, включая ручное закрытие. Win Rate и качество стратегии исключают ручные выходы.':'The equity curve includes all changes to the virtual balance, including manual exits. Win rate and strategy metrics exclude manual exits.',
    'Кривая капитала':'Equity curve', 'Результаты':'Results', 'Закрытых сделок':'Closed trades',
    'Прибыльных сделок':'Winning trades', 'Убыточных сделок':'Losing trades', 'Максимальная просадка':'Maximum drawdown',
    'Пока нет подтверждённых сигналов':'No qualified signals yet',
    'Это нормально: система не открывает сделки, если фильтры направления, EMA, ADX и объёма не совпадают. Автоматический поиск продолжится на сервере.':'This is expected: MIRAGE does not trade when direction, EMA, ADX and volume filters do not align. Automatic scanning continues on the server.',
    'Качество от 80/100':'Quality score 80/100 or higher',
    'Качество от 86/100':'Quality score 86/100 or higher',
    'Фильтры направления, EMA, ADX и объёма':'Direction, EMA, ADX and volume filters',
    'Без ручных выходов':'Manual exits excluded', 'Ручные закрытия остаются в реальной кривой баланса.':'Manual closes remain reflected in the account equity curve.',
    'Ручные выходы':'Manual exits', 'Источник':'Source', 'Проверка':'Check',
    'Рост':'Gainers', 'Падение':'Losers', 'Объём':'Volume',
    'ОЖИДАНИЕ ПОТОКА':'WAITING FOR FEED', 'АКТИВЕН':'ACTIVE', 'ОГРАНИЧЕН':'DEGRADED',
    'ЗАБЛОКИРОВАН':'BLOCKED', 'ЗАПУСК':'STARTING', 'НЕИЗВЕСТНО':'UNKNOWN',
    'АКТИВЕН':'ACTIVE', 'ЗАБЛОКИРОВАН':'BLOCKED', 'ОГРАНИЧЕН':'DEGRADED',
    'Верхний уровень':'Overview', 'ВЕРХНИЙ УРОВЕНЬ':'OVERVIEW', 'Общий виртуальный капитал':'Total virtual capital',
    'ОБЩИЙ ВИРТУАЛЬНЫЙ КАПИТАЛ':'TOTAL VIRTUAL CAPITAL', 'Последние сигналы':'Latest signals',
    'Сканер торговых возможностей':'Trading opportunity scanner', 'MARKET INTELLIGENCE ENGINE':'MARKET INTELLIGENCE ENGINE',
    'КОНТРОЛЬ':'CONTROL', 'Настроить':'Configure', 'Модули':'Modules', 'Инструменты мониторинга и управления системой.':'System monitoring and control tools.',
    'Интеллект':'Intelligence', 'Анализ отдельного контракта':'Analyse an individual contract',
    'Информационный контекст рынка':'Market context', 'Риск, автоматизация и вид':'Risk, automation and appearance',
    'Сделки, уровни, комиссии':'Trades, levels and fees', 'Система анализирует только закрытые свечи. Сетап ниже 80/100 или без независимого подтверждения не допускается к открытию позиции.':'MIRAGE analyses closed candles only. Setups below the quality threshold or without independent confirmation cannot become positions.',
    'Эквити счёта':'Account equity', 'Свободная':'Available', 'Проверить отдельный контракт':'Analyse a contract',
    'Нереализованный':'Unrealized', 'Открыть':'Open', 'Закрыто':'Closed', 'Позиция открыта':'Position opened',
    'Позиция закрыта':'Position closed', 'MARKET INTELLIGENCE · RISK CONTROL · PAPER EXECUTION':'MARKET INTELLIGENCE · RISK CONTROL · PAPER EXECUTION',
    'Поступают актуальные фьючерсные котировки…':'Waiting for live futures quotes…',
    'График загрузится с данными рынка':'The chart will appear when market data arrives',
    'Нет достаточной истории для графика':'Not enough history to draw a chart',
    'Последние':'Last', 'закрытых свечей':'closed candles', 'записей':'events',
    'Рынок без догадок':'See beyond the market', 'Сначала защита капитала':'Capital protection first', 'Сначала Paper Trading':'Paper trading first',
    'Рынок — это больше, чем движение цены. MIRAGE анализирует его структуру.':'Markets are more than price movements. MIRAGE analyses their structure.',
    'Многоуровневый анализ, торговые стратегии и интеллектуальный отбор сигналов.':'Multi-timeframe analysis, specialised strategies and intelligent signal selection.',
    'Контроль рисков, защита капитала и продуманное исполнение сделок.':'Risk controls, capital protection and disciplined trade execution.',
    'MIRAGE анализирует реальные данные Binance USDⓈ-M и использует только закрытые свечи. Сигнал не означает гарантированную прибыль.':'MIRAGE analyses live Binance USDⓈ-M market data and uses closed candles only. A signal never guarantees profit.',
    'PHANTOM проверяет качество потока данных. Дневной лимит убытка, пауза после серии потерь и запрет очереди старых сигналов ограничивают новые входы.':'PHANTOM verifies data integrity. Daily loss limits, a losing-streak cooldown and expired-signal protection restrict new entries.',
    'Все сделки виртуальные. Комиссии, спред, проскальзывание и funding учитываются в расчётах. Реальные ордера отключены.':'All trades are simulated. Fees, spread, slippage and funding are included in calculations. Real orders are disabled.',
    'Breakout Intelligence':'Интеллект пробоев', 'Mean Reversion':'Возврат к среднему', 'Trend Pullback':'Откат по тренду',
    'Trend Following':'Следование тренду', 'Momentum Intelligence':'Импульсная стратегия',
    'Break above the 20-bar range':'Пробой максимума 20 свечей', 'Break below the 20-bar range':'Пробой минимума 20 свечей',
    'Participation confirmed by volume':'Объём подтверждает движение', 'Momentum and trend aligned':'Импульс и тренд согласованы',
    'Pullback tested the EMA20 area':'Коррекция протестировала зону EMA20', 'Closed candle reclaimed EMA20':'Закрытая свеча вернулась выше EMA20',
    'Momentum resumed with the trend':'Импульс возобновился в сторону тренда', 'Closed candle rejected EMA20':'Закрытая свеча отвергла EMA20',
    'Momentum resumed to the downside':'Импульс возобновился вниз', 'Positive multi-bar price acceleration':'Положительное ускорение цены на нескольких свечах',
    'MACD histogram expanding':'Гистограмма MACD расширяется', 'Volume confirms momentum':'Объём подтверждает импульс',
    'Negative multi-bar price acceleration':'Отрицательное ускорение цены на нескольких свечах',
    'MACD histogram expanding downward':'Гистограмма MACD расширяется вниз', 'EMA20 / EMA50 trend structure aligned':'Структура EMA20 / EMA50 согласована',
    'Price holds above EMA20':'Цена удерживается выше EMA20', 'ADX and MACD confirm trend strength':'ADX и MACD подтверждают силу тренда',
    'Price holds below EMA20':'Цена удерживается ниже EMA20', 'Lower Bollinger band rejection':'Отбой от нижней полосы Боллинджера',
    'RSI shows stretched downside':'RSI указывает на чрезмерное снижение', 'MACD momentum begins to recover':'Импульс MACD начинает восстанавливаться',
    'Upper Bollinger band rejection':'Отбой от верхней полосы Боллинджера', 'RSI shows stretched upside':'RSI указывает на чрезмерный рост',
    'MACD momentum begins to fade':'Импульс MACD начинает ослабевать',
    'Сигнал не означает гарантированную прибыль.':'A signal does not guarantee profit.',
    'Автоматические входы выключены':'Automatic entries are disabled', 'Сохранено':'Saved',
    'Контракт':'Contract', 'Анализирует рынок':'Analysing the market', 'Автовходы':'Auto entries',
    'Режим меняет только визуальное отображение. Все расчёты, фильтры и функции продолжают работать.':'This mode changes the visual appearance only. Calculations, filters and features remain active.'
,

    'Включите автоматическую торговлю, чтобы MIRAGE самостоятельно открывал позиции.':'Enable automated trading to let MIRAGE open qualified positions.',
    'MIRAGE самостоятельно откроет позицию после появления подходящего сетапа и прохождения PHANTOM.':'MIRAGE will open a position only after a qualified setup passes PHANTOM.',
    'Закрытые Paper-сделки с комиссиями и funding появятся здесь.':'Closed paper trades, including fees and funding, will appear here.',
    'Свободная isolated margin после резерва открытых позиций':'Free isolated margin after open-position reservations',
    'ЭКВИТИ СЧЁТА':'ACCOUNT EQUITY', 'Открытые позиции':'Open positions', 'Свободная маржа':'Free margin',
    'Открытые':'Open', 'История':'History', 'План выхода':'Exit plan', 'Завершена':'Completed',
    'Проверить отдельный контракт':'Analyse an individual contract',
    'Дополнительный анализ — не требуется для автоматической торговли.':'Additional analysis is not required for automated trading.',
    'Контракт':'Contract', '15 минут · Scalping':'15 minutes · Scalping', '1 час · Intraday':'1 hour · Intraday',
    '4 часа · Swing':'4 hours · Swing', '1 день · Position':'1 day · Position',
    'Система анализирует только закрытые свечи. Сетап ниже 80/100 или без независимого подтверждения не допускается к открытию позиции.':'Only closed candles are analysed. Setups below 86/100 or without independent confirmation cannot become positions.',
    'Система не будет предлагать сделку без полного подтверждения условий.':'MIRAGE will not suggest a trade without full condition confirmation.',
    'Анализ отдельного контракта':'Analyse an individual contract', 'Запустить анализ':'Run analysis',
    'Квалифицированный сетап не найден':'No qualified setup found',
    'Система анализирует только закрытые свечи.':'The engine analyses closed candles only.',
    'Закрытые свечи · индикаторы · фильтр S/A · защита от повторных сигналов.':'Closed candles · indicators · S/A filter · duplicate-signal protection.',
    'Сканирование завершено:':'Scan complete:', 'кандидатов':'candidates', 'новых сигналов':'new signals',
    'Сделки, уровни, комиссии':'Trades, levels and fees', 'Открыть Paper позицию':'Open paper position',
    'Открыть Paper':'Open paper trade', 'Paper-позиция открыта':'Paper position opened',
    'Paper-позиция закрыта':'Paper position closed', 'Закрыть Paper-позицию по текущим рыночным Bid/Ask?':'Close the paper position at the current market Bid/Ask?',
    'Автоматические входы проходят отдельные лимиты защиты':'Automatic entries must pass separate safety limits',
    'Риск, автоматизация и вид':'Risk, automation and appearance',
    'ВЕРХНИЙ УРОВЕНЬ':'OVERVIEW', 'Система':'System', 'Место':'Place', 'Время':'Time',
    'Защита капитала':'Capital protection', 'Нет подтверждённых сигналов':'No qualified signals',
    'Включить':'Enable', 'Выключить':'Disable', 'Открыть источник':'Open source',
    'Пока нет подтверждённых сигналов':'No qualified signals yet',
    'Сигнал не означает гарантированную прибыль.':'A signal does not guarantee profit.',
    'Сначала':'First', 'Прибыльных сделок':'Winning trades', 'Убыточных сделок':'Losing trades',
    'Average Trade':'Average trade', 'Win Rate стратегии':'Strategy win rate', 'Profit Factor':'Profit factor',
    'Начальный уровень':'Initial level', 'Результат':'Result', 'Сигналы':'Signals', 'Условия':'Conditions',
    'Статистика':'Statistics', 'Виртуальный счёт':'Paper account', 'Сохранить':'Save',
    'Ручная проверка обновляет сигналы и не открывает сделки.':'Manual scan refreshes signals and never opens trades.',
    'PHANTOM проверяет качество потока данных. Дневной лимит убытка, пауза после серии потерь и запрет очереди старых сигналов ограничивают новые входы.':'PHANTOM validates data integrity. Daily loss limits, a losing-streak cooldown and expired-signal protection restrict new entries.',
    'Контроль состояния данных, допуска к новым входам и сопровождения открытых позиций.':'Monitors data integrity, new-entry permission and open-position management.',
    'Новые входы блокируются, пока не восстановлены надёжные данные.':'New entries remain blocked until reliable data is restored.',
    'REST и оба live-потока свежие. Допуск новых Paper-входов может быть разрешён.':'REST and both live feeds are fresh. New paper entries may be permitted.',
    'Проверки протокола':'Protocol checks', 'Журнал событий':'Event log',
    'MARKET INTELLIGENCE ENGINE':'MARKET INTELLIGENCE ENGINE', 'Рыночная аналитика и автоматическое Paper Trading':'Market intelligence and automated paper trading',
    'Отключить часть переходов интерфейса.':'Reduce interface transitions and animations.',
    'Нереализованный P&L':'Unrealized P&L', 'Свободная':'Available',
    'Сканер торговых возможностей':'Trading opportunity scanner',
    'Доходность':'Performance', 'Риск на сделку':'Risk per trade',
    'Максимум открытых позиций':'Maximum open positions', 'Режим меняет только визуальное отображение. Все расчёты, фильтры и функции продолжают работать.':'This mode changes visual appearance only. All calculations, filters and features remain active.',
    'Новые карточки появятся после прохождения фильтров качества S/A и PHANTOM.':'New cards appear only after passing the S/A quality and PHANTOM checks.',
    'последних':'latest', 'Качество от 80/100':'Quality score 86/100 or higher',
    'Комиссии · funding · ручные выходы':'Fees · funding · manual exits', 'Закрытые сделки':'Closed trades',
    'Начальный капитал':'Initial capital', 'Результат по стратегиям':'Strategy performance',
    'Проверить отдельный контракт':'Analyse a contract', 'Ручной анализ':'Manual analysis',
    'Автоматическая торговля':'Automated trading', 'Плечо':'Leverage', 'Выбрать':'Select',
    'Неизвестно':'Unknown', 'Ожидание данных':'Waiting for data', 'Откройте раздел':'Open section',
    'Рыночные сигналы':'Market signals', 'Нереализованный P&L':'Unrealized P&L',
    'Уровень качества':'Quality score', 'Внимание':'Attention', 'Выход':'Exit',
    'Система анализирует рынок':'The system is analysing the market', 'Запуск':'Starting',
    'Активен':'Active', 'Заблокирован':'Blocked', 'Ограничен':'Degraded'

  };

  const PHRASES = [
    ['Система не будет предлагать сделку без полного подтверждения условий.','MIRAGE will not suggest a trade without full confirmation.'],
    ['Только виртуальные сделки. Реальные биржевые ордера отключены.','Virtual trades only. Real exchange orders are disabled.'],
    ['Не удалось выйти:','Could not sign out:'],
    ['Не удалось прочитать уровни Take Profit','Could not read Take Profit levels'],
    ['Открыть Paper','Open paper trade'],
    ['закрытых сделок','closed trades'], ['прибыльных из','winning out of'],
    ['Сканирование завершено:','Scan complete:'], ['Новые входы блокируются','New entries are blocked'],
    ['Закрытые свечи','Closed candles'], ['EMA подтверждает рост','EMA confirms upside'],
    ['EMA подтверждает снижение','EMA confirms downside'], ['Откат к EMA20','Pullback to EMA20'],
    ['Подтверждение MACD','MACD confirmation'], ['Старший тренд','Higher-timeframe trend'],
    ['Объём выше среднего','Volume above average'], ['Объём ниже среднего','Volume below average'],
    ['Время сканирования','Last scan'], ['Проверки протокола','Protocol checks'],
    ['Состояние рынка','Market state'], ['Аналитика виртуального счёта','Virtual account analytics'],
    ['Проверка…','Scanning…'], ['активирован','activated'], ['Сканер уже выполняет цикл. Дождитесь его завершения.','The scanner is already running. Please wait for it to finish.'],
    ['Повторный ручной запуск будет доступен через','Manual scan will be available again in'],
    ['качество от 80/100','quality 86/100+'], ['Последний скан','Last scan'],
    ['Качество от 80/100','Quality score 86/100 or higher'], ['Поток источников','Source feed'],
    ['Загрузка','Loading'], ['Идёт анализ','Analysis in progress'], ['Ожидание данных','Waiting for data']
  ];
  const EN_RU = Object.fromEntries(Object.entries(RU_EN).map(([ru,en]) => [en,ru]));
  let currentLanguage = 'ru';
  let applying = false;

  function translateText(raw, language) {
    const value = raw.replace(/\u00a0/g, ' ');
    const trimmed = value.trim();
    if (!trimmed) return raw;
    if (language === 'en' && /^\d+[мчд]$/.test(trimmed)) return trimmed.replace('м','m').replace('ч','h').replace('д','d');
    if (language === 'ru' && /^\d+[mhd]$/.test(trimmed)) return trimmed.replace('m','м').replace('h','ч').replace('d','д');
    if (language === 'en') {
      if (RU_EN[trimmed]) return value.replace(trimmed, RU_EN[trimmed]);
      let out = value;
      for (const [ru,en] of PHRASES) out = out.split(ru).join(en);
      return out;
    }
    if (EN_RU[trimmed]) return value.replace(trimmed, EN_RU[trimmed]);
    let out = value;
    for (const [ru,en] of PHRASES) out = out.split(en).join(ru);
    return out;
  }

  function translateAttributes(element) {
    for (const attr of ['placeholder','title','aria-label','aria-valuetext']) {
      const value = element.getAttribute?.(attr);
      if (value) {
        const translated = translateText(value, currentLanguage);
        if (translated !== value) element.setAttribute(attr, translated);
      }
    }
  }

  function translateNode(node) {
    if (!node || applying) return;
    if (node.nodeType === Node.TEXT_NODE) {
      const parent = node.parentElement;
      if (!parent || parent.closest('script,style,code,pre,svg,input,textarea,select,option')) return;
      const value = node.nodeValue || '';
      const translated = translateText(value, currentLanguage);
      if (translated !== value) {
        applying = true;
        node.nodeValue = translated;
        applying = false;
      }
      return;
    }
    if (node.nodeType === Node.ELEMENT_NODE) {
      if (node.matches('script,style,code,pre,svg,input,textarea,select')) return;
      translateAttributes(node);
      const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
      const texts = [];
      while (walker.nextNode()) texts.push(walker.currentNode);
      texts.forEach(translateNode);
      node.querySelectorAll?.('[placeholder],[title],[aria-label],[aria-valuetext]').forEach(translateAttributes);
    }
  }

  function setLanguage(language) {
    currentLanguage = language === 'en' ? 'en' : 'ru';
    document.documentElement.lang = currentLanguage;
    document.documentElement.dataset.language = currentLanguage;
    try { localStorage.setItem('mirage-language', currentLanguage); } catch (_) {}
    translateNode(document.body);
    updateIntroLabels();
  }

  function updateIntroLabels() {
    const intervalSelect = document.querySelector('#analyze-interval');
    if (intervalSelect) {
      let option = intervalSelect.querySelector('option[value="30m"]');
      if (!option) { option = document.createElement('option'); option.value = '30m'; intervalSelect.insertBefore(option, intervalSelect.querySelector('option[value="1h"]')); }
      const optionText = currentLanguage === 'en' ? '30 minutes · Range' : '30 минут · Флэт';
      if (option.textContent !== optionText) option.textContent = optionText;
    }
    const version = document.querySelector('.settings-version');
    if (version) { const updated = version.textContent.replace('MIRAGE v1.4.1', 'MIRAGE v1.5.0'); if (version.textContent !== updated) version.textContent = updated; }
    const scannerMeta = [...document.querySelectorAll('.section-head p')].find(x => x.textContent.includes('80/100'));
    if (scannerMeta) { const updated = currentLanguage === 'en' ? scannerMeta.textContent.replace('качество от 80/100', 'quality 86/100+') : scannerMeta.textContent.replace('quality 86/100+', 'качество от 86/100'); if (scannerMeta.textContent !== updated) scannerMeta.textContent = updated; }
    const note = document.querySelector('.analysis-form-panel .form-note');
    if (note) { const noteText = currentLanguage === 'en' ? 'Only closed candles are analysed. Setups below 86/100 or without independent confirmation cannot become positions.' : 'Система анализирует только закрытые свечи. Сетап ниже 86/100 или без независимого подтверждения не допускается к открытию позиции.'; if (note.textContent !== noteText) note.textContent = noteText; }
    const label = document.querySelector('.onboarding-progress-label');
    if (label) { const active = document.querySelectorAll('.onboarding-dots i.active').length ? [...document.querySelectorAll('.onboarding-dots i')].findIndex(x => x.classList.contains('active')) + 1 : 1; const next = currentLanguage === 'en' ? `MIRAGE INTRODUCTION · 0${active} / 03` : `ВВЕДЕНИЕ MIRAGE · 0${active} / 03`; if (label.textContent !== next) label.textContent = next; }
    const cards = [...document.querySelectorAll('.strategy-card')];
    if (!cards.length) return;
    const items = currentLanguage === 'en' ? [
      ['15m','SCALPING','Breakout Intelligence','20-bar range break · volume and trend confirmation'],
      ['30m','SCALPING','Mean Reversion','Range market · Bollinger rejection and RSI recovery'],
      ['1h','INTRADAY','Trend Pullback','EMA20 retest · MACD momentum recovery'],
      ['4h','SWING','Trend Following','Trend structure · ADX and higher-timeframe alignment'],
      ['1d','POSITION','Momentum Intelligence','Multi-bar acceleration · weekly trend confirmation']
    ] : [
      ['15m','SCALPING','Интеллект пробоев','Пробой 20 свечей · подтверждение объёмом и трендом'],
      ['30m','SCALPING','Возврат к среднему','Флэтовый рынок · отбой от Bollinger и разворот RSI'],
      ['1h','INTRADAY','Откат по тренду','Тест EMA20 · восстановление импульса MACD'],
      ['4h','SWING','Следование тренду','Структура тренда · ADX и подтверждение старшими ТФ'],
      ['1d','POSITION','Импульсная стратегия','Ускорение нескольких свечей · подтверждение недельным трендом']
    ];
    while (cards.length < items.length) {
      const clone = cards[cards.length - 1].cloneNode(true);
      clone.dataset.v15Added = 'true';
      cards[0].parentElement.appendChild(clone);
      cards.push(clone);
    }
    cards.forEach((card, index) => {
      const item = items[index];
      if (!item) return;
      const [tf,group,model,description] = item;
      const indexNode = card.querySelector('.strategy-index');
      const timeNode = card.querySelector('.strategy-time');
      const strong = card.querySelector('strong');
      const modelNode = card.querySelector('b');
      const desc = card.querySelector('p');
      if (indexNode && indexNode.textContent !== `0${index+1}`) indexNode.textContent = `0${index+1}`;
      if (timeNode && timeNode.textContent !== tf) timeNode.textContent = tf;
      if (strong && strong.textContent !== group) strong.textContent = group;
      if (modelNode && modelNode.textContent !== model) modelNode.textContent = model;
      if (desc && desc.textContent !== description) desc.textContent = description;
    });
  }

  async function refreshLanguageFromAccount() {
    try {
      const response = await fetch('/api/settings', {credentials:'same-origin',cache:'no-store'});
      if (!response.ok) return;
      const settings = await response.json();
      setLanguage(settings.language || 'ru');
    } catch (_) { /* Login screen may be unauthenticated. */ }
  }

  // Upgrade the already-onboarded installation once; thereafter the app's
  // existing completion flag is respected and onboarding does not repeat.
  try {
    if (!localStorage.getItem('mirage-onboarding-v15-migrated')) {
      localStorage.removeItem('mirage-onboarding-v14');
      localStorage.setItem('mirage-onboarding-v15-migrated', '1');
    }
  } catch (_) {}

  document.addEventListener('change', event => {
    if (event.target?.id === 'setting-language') setLanguage(event.target.value);
  }, true);

  document.addEventListener('submit', event => {
    if (event.target?.id === 'login-form') setTimeout(refreshLanguageFromAccount, 900);
  }, true);

  // Observe new sections, cards, toasts and modal text produced by the existing renderer.
  const observer = new MutationObserver(records => {
    for (const record of records) {
      if (record.type === 'characterData') translateNode(record.target);
      for (const node of record.addedNodes || []) translateNode(node);
      if (record.type === 'attributes' && record.target.nodeType === 1) translateAttributes(record.target);
    }
    updateIntroLabels();
  });
  observer.observe(document.body, {subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['placeholder','title','aria-label','aria-valuetext','data-art']});

  // Keep dates/localized numerals consistent with the selected locale.
  const originalToLocaleString = Date.prototype.toLocaleString;
  Date.prototype.toLocaleString = function(locales, options) {
    if (currentLanguage === 'en' && (!locales || locales === 'ru-RU')) return originalToLocaleString.call(this, 'en-US', options);
    if (currentLanguage === 'ru' && (!locales || locales === 'en-US')) return originalToLocaleString.call(this, 'ru-RU', options);
    return originalToLocaleString.call(this, locales, options);
  };

  // Full-screen introduction supports natural left/right swipes on touch devices.
  let touchStartX = 0;
  document.addEventListener('touchstart', event => {
    if (!event.target.closest('#onboarding-screen')) return;
    touchStartX = event.changedTouches?.[0]?.clientX || 0;
  }, {passive:true});
  document.addEventListener('touchend', event => {
    if (!event.target.closest('#onboarding-screen') || !touchStartX) return;
    const endX = event.changedTouches?.[0]?.clientX || 0;
    const delta = endX - touchStartX;
    touchStartX = 0;
    if (Math.abs(delta) > 55) {
      if (delta < 0) document.querySelector('#onboarding-next')?.click();
      else {
        try {
          if (typeof onboardingIndex === 'number' && onboardingIndex > 0 && typeof renderOnboarding === 'function') {
            onboardingIndex -= 1;
            renderOnboarding();
          }
        } catch (_) {}
      }
    }
  }, {passive:true});

  const appVisibility = new MutationObserver(() => {
    const shell = document.querySelector('#app-shell');
    if (shell && !shell.classList.contains('hidden')) refreshLanguageFromAccount();
  });
  const shell = document.querySelector('#app-shell');
  if (shell) appVisibility.observe(shell, {attributes:true,attributeFilter:['class']});

  // Restore the last chosen locale immediately; the authenticated account
  // then remains the source of truth and synchronises it across devices.
  let storedLanguage = 'ru';
  try { storedLanguage = localStorage.getItem('mirage-language') || 'ru'; } catch (_) {}
  setLanguage(storedLanguage);
  refreshLanguageFromAccount();
})();
