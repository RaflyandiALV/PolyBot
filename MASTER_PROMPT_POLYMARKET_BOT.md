# MASTER PROMPT — POLYMARKET TRADING BOT
# Untuk: AI Agent di CLI / Antigravity IDE
# Dari: Rafly — Developer, BINUS University
# Tujuan: Implementasi full bot dari nol, biaya $0, paper trading dulu

---

Kamu adalah senior Python developer dan quant engineer. Tugasmu adalah membangun
sebuah Polymarket trading bot secara lengkap dari awal di local machine saya.
Ikuti SEMUA instruksi di bawah ini secara berurutan, jangan skip satu pun.
Jangan berasumsi — kalau ada yang ambigu, tanya dulu sebelum menulis kode.

---

## CONTEXT HARDWARE (WAJIB DIPAHAMI SEBELUM MULAI)

Device saya:
- Laptop  : Asus Vivobook 14 Pro OLED
- CPU     : AMD Ryzen 5 5500H (6 core, 12 thread, max 4.4GHz)
- GPU     : RTX 3050 Mobile (4GB VRAM) — JANGAN dipakai untuk AI inference
- RAM     : 8GB DDR4
- OS      : Windows 11 (asumsikan ini, kecuali saya bilang lain)
- Koneksi : WiFi rumah (latency 20-80ms ke internet)

Implikasi teknis yang WAJIB kamu hormati:
1. DILARANG menjalankan LLM lokal apapun (Llama, Mistral, dll).
   Alasan: 4GB VRAM tidak cukup untuk model yang akurat untuk trading.
2. DILARANG strategi HFT atau lag arbitrage.
   Alasan: WiFi rumah latency 20-80ms, kalah jauh dari server colocated.
3. RAM 8GB berarti total memory usage bot harus di bawah 400MB.
   Jangan load library besar yang tidak perlu.
4. Bot harus bisa survive laptop sleep/restart tanpa kehilangan state.
   Semua state wajib di-persist ke disk setiap setelah perubahan.
5. Jangan pernah open Chrome atau aplikasi berat saat bot jalan.

---

## STRATEGI TRADING (WAJIB DIPAHAMI SEBELUM MENULIS KODE)

Strategi yang dipakai: NEWS-BASED EDGE TRADING
Bukan HFT, bukan lag arbitrage, bukan local ML model.

Logika inti:
  Berita breaking masuk
    → Bot kumpulkan berita dari RSS + NewsAPI (gratis)
    → Kirim ke Claude API di cloud (bukan lokal) untuk analisis
    → Claude API mengestimasi probabilitas event
    → Bandingkan dengan harga di Polymarket
    → Kalau gap (edge) > 12%: pertimbangkan entry
    → Hitung bet size pakai Half-Kelly Criterion
    → Eksekusi (atau simulasi di paper trading)
    → Log semua keputusan untuk evaluasi

Laptop hanya sebagai "remote control":
  - Kumpul data (ringan, CPU)
  - Kirim ke cloud API (network call)
  - Terima keputusan (JSON response)
  - Eksekusi order (API call ke Polymarket)
  Semua komputasi berat ada di server Anthropic, bukan laptop.

Framework quant yang diimplementasikan (dari Gojo.ether playbook):
  1. Base Rate   → prior probabilitas sebelum analisis berita
  2. Bayes       → update probabilitas saat berita baru masuk (via Claude API)
  3. EV          → Expected Value = (ai_prob - market_price) × potential_payout - fee
  4. Kelly       → bet size = Half-Kelly, max 15% bankroll per trade
  5. KL-Diverge  → versi sederhana: monitor 2-3 market berkorelasi saja

Mode operasi: PAPER TRADING (simulasi, tidak ada uang nyata)
Semua eksekusi order adalah simulasi sampai saya bilang go-live.
Ini berarti biaya = $0 (tidak ada API call ke Polymarket yang berbayar,
tidak ada Claude API call kecuali saat mode paper trading dijalankan dengan flag --live-ai).

---

## STRUKTUR FOLDER YANG HARUS DIBUAT

Buat folder project di direktori kerja saat ini dengan struktur PERSIS ini:

```
polymarket-bot/
│
├── .env                        ← credentials (JANGAN commit ke git)
├── .env.example                ← template kosong untuk dokumentasi
├── .gitignore
├── requirements.txt
├── README.md
│
├── data/
│   ├── news/
│   │   ├── raw_news.json       ← semua berita yang dikumpulkan
│   │   └── processed_news.json ← berita yang sudah dianalisis AI
│   ├── markets/
│   │   └── active_markets.json ← daftar market Polymarket aktif
│   └── survival/
│       ├── state.json          ← balance dan posisi aktif saat ini
│       └── log.json            ← history semua trade dan keputusan
│
├── collector/
│   ├── __init__.py
│   ├── rss_collector.py        ← ambil berita dari RSS feed (gratis)
│   ├── newsapi_collector.py    ← ambil berita dari NewsAPI (gratis tier)
│   └── market_collector.py     ← ambil harga dan daftar market dari Polymarket
│
├── engine/
│   ├── __init__.py
│   ├── base_rate.py            ← database prior probabilitas per kategori
│   ├── ai_analyzer.py          ← kirim berita ke Claude API, terima probabilitas
│   ├── ev_calculator.py        ← hitung Expected Value + fee
│   ├── kelly_sizer.py          ← hitung bet size pakai Half-Kelly
│   └── decision_engine.py      ← gabungkan semua engine, output BUY/SKIP
│
├── risk/
│   ├── __init__.py
│   ├── survival_engine.py      ← "Survive or Die" logic, track bankroll
│   └── checklist.py            ← 6 pre-execution validation checks
│
├── execution/
│   ├── __init__.py
│   ├── paper_trader.py         ← simulasi eksekusi (paper trading)
│   └── live_trader.py          ← eksekusi nyata via Polymarket CLOB API
│
├── monitoring/
│   ├── __init__.py
│   └── telegram_alert.py       ← kirim alert ke Telegram (gratis)
│
├── utils/
│   ├── __init__.py
│   ├── logger.py               ← logging terpusat
│   └── sleep_prevention.py     ← cegah laptop sleep saat bot jalan
│
└── main.py                     ← entry point utama
```

---

## DETAIL IMPLEMENTASI PER FILE

Implementasikan SEMUA file di bawah ini. Jangan ada yang dilewati.
Setiap file harus production-quality: ada error handling, ada logging, ada docstring.

---

### FILE: requirements.txt

```
requests==2.31.0
feedparser==6.0.10
python-dotenv==1.0.0
schedule==1.2.0
anthropic==0.20.0
py-clob-client==0.14.0
```

TIDAK BOLEH ada library lain. Setiap tambahan library harus ada justifikasi
kenapa diperlukan dan tidak bisa diganti dengan stdlib Python.

---

### FILE: .env.example

```
# Polymarket API (ambil dari polymarket.com → Settings → API Keys)
POLY_API_KEY=your_api_key_here
POLY_API_SECRET=your_api_secret_here
POLY_PASSPHRASE=your_passphrase_here
POLY_PRIVATE_KEY=your_proxy_wallet_private_key_here

# Anthropic Claude API (ambil dari console.anthropic.com)
# Untuk paper trading mode: isi MOCK_AI=true maka tidak ada API call
ANTHROPIC_API_KEY=your_anthropic_api_key_here
MOCK_AI=true

# NewsAPI (gratis di newsapi.org, 100 req/hari)
NEWS_API_KEY=your_newsapi_key_here

# Telegram Bot (opsional, untuk alert — gratis)
# Buat bot via @BotFather di Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Paper Trading Config
PAPER_TRADING=true
STARTING_BALANCE=1000.0
DAILY_TARGET_PCT=0.25
```

---

### FILE: .gitignore

```
.env
data/
__pycache__/
*.pyc
.pytest_cache/
venv/
```

---

### FILE: utils/logger.py

Logger terpusat. Semua modul import dari sini.
Format log: [TIMESTAMP] [LEVEL] [MODULE] message
Output ke console DAN ke file data/bot.log secara bersamaan.
Gunakan stdlib `logging` saja, tidak perlu library eksternal.

---

### FILE: utils/sleep_prevention.py

Implementasikan fungsi `prevent_sleep()` dan `allow_sleep()`.
Di Windows: gunakan `ctypes.windll.kernel32.SetThreadExecutionState`
dengan flag `ES_CONTINUOUS | ES_SYSTEM_REQUIRED (0x80000002)`.
Di Linux/Mac: gunakan subprocess call ke `caffeinate` atau `systemd-inhibit`.
Detect OS otomatis dengan `platform.system()`.
Fungsi ini dipanggil di main.py saat bot start.

---

### FILE: collector/rss_collector.py

Kumpulkan berita dari RSS feed gratis berikut ini (hardcode list ini):

```python
RSS_FEEDS = {
    "Reuters Top News":      "https://feeds.reuters.com/reuters/topNews",
    "Reuters Business":      "https://feeds.reuters.com/reuters/businessNews",
    "BBC World":             "http://feeds.bbci.co.uk/news/world/rss.xml",
    "BBC Business":          "http://feeds.bbci.co.uk/news/business/rss.xml",
    "CNBC Top News":         "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "CoinDesk":              "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Cointelegraph":         "https://cointelegraph.com/rss",
    "Politico":              "https://rss.politico.com/politics-news.xml",
    "Al Jazeera":            "https://www.aljazeera.com/xml/rss/all.xml",
}
```

Setiap artikel yang dikumpulkan harus distandarisasi ke format ini:
```python
{
    "id": str,           # sha256 dari URL, untuk deduplication
    "source": "rss",
    "feed_name": str,
    "title": str,
    "description": str,
    "url": str,
    "published_at": str, # ISO 8601 UTC
    "collected_at": str, # ISO 8601 UTC
    "analyzed": False,   # akan di-update engine setelah dianalisis
}
```

Implementasikan deduplication berdasarkan field `id` (hash URL).
Jangan simpan artikel yang lebih lama dari 24 jam.
Wrap setiap feed fetch di try-except — kalau satu feed error, lanjut ke feed lain.
Jangan crash karena satu feed down.

---

### FILE: collector/newsapi_collector.py

Gunakan NewsAPI free tier (100 request/hari — HEMAT penggunaannya).

Topik yang di-query (hardcode):
```python
TOPICS = [
    "Federal Reserve interest rates",
    "US election 2026",
    "Bitcoin price prediction",
    "Ukraine Russia ceasefire",
    "US economy GDP",
    "crypto regulation SEC",
    "artificial intelligence regulation",
    "oil price OPEC",
]
```

PENTING: Implement rate limiting. Hitung penggunaan harian dan simpan ke
`data/newsapi_usage.json`. Kalau sudah 80 request hari ini, berhenti query NewsAPI
dan fallback ke RSS saja. Reset counter setiap tengah malam UTC.

Format artikel sama seperti RSS collector, dengan tambahan field `"topic": str`.

---

### FILE: collector/market_collector.py

Ambil daftar market aktif dari Polymarket CLOB API.
Endpoint: `GET https://clob.polymarket.com/markets`

Untuk setiap market, simpan:
```python
{
    "condition_id": str,      # ID unik market
    "question": str,          # pertanyaan market
    "category": str,          # kategori (politics, crypto, sports, dll)
    "end_date": str,          # tanggal resolusi
    "volume": float,          # total volume dalam USDC
    "best_ask_yes": float,    # harga terbaik untuk beli YES
    "best_bid_yes": float,    # harga terbaik untuk jual YES
    "best_ask_no": float,     # harga terbaik untuk beli NO
    "liquidity": float,       # total likuiditas di order book
    "last_updated": str,      # ISO 8601 UTC
}
```

Filter: HANYA simpan market dengan:
- `volume >= 10000` (likuiditas cukup)
- `end_date` dalam 7 hari ke depan (relevan untuk news-based trading)
- `active == True`

Simpan ke `data/markets/active_markets.json`.
Update setiap 30 menit via scheduler.

---

### FILE: engine/base_rate.py

Ini adalah "Step 0" dari integrated framework.
Sebelum analisis berita, bot harus tahu base rate historis per kategori.

Implementasikan dictionary ini sebagai konstanta (hardcode — ini data riset):

```python
BASE_RATES = {
    # Politik
    "politics_incumbent_win":       0.67,  # incumbent menang pemilu
    "politics_challenger_win":      0.33,  # challenger menang pemilu
    "politics_primary_frontrunner": 0.72,  # frontrunner menang primary
    "politics_impeachment":         0.08,  # impeachment berhasil
    
    # Ekonomi / Fed
    "fed_rate_cut":                 0.35,  # Fed cut rates di meeting ini
    "fed_rate_hike":                0.25,  # Fed hike rates di meeting ini
    "fed_rate_hold":                0.40,  # Fed hold rates di meeting ini
    "economic_beat_consensus":      0.42,  # data ekonomi beat ekspektasi
    "economic_miss_consensus":      0.35,  # data ekonomi miss ekspektasi
    
    # Geopolitik
    "ceasefire_after_negotiation":  0.58,  # gencatan senjata setelah negosiasi
    "ceasefire_broken":             0.45,  # gencatan senjata gagal
    "sanctions_implemented":        0.62,  # sanksi diimplementasikan
    
    # Crypto
    "btc_breakout_up":              0.45,  # BTC breakout ke atas dari range
    "btc_breakdown_down":           0.35,  # BTC breakdown ke bawah
    "btc_stays_range":              0.20,  # BTC tetap di range
    "crypto_regulation_strict":     0.40,  # regulasi crypto ketat
    "crypto_regulation_lenient":    0.35,  # regulasi crypto longgar
    
    # Default kalau kategori tidak dikenali
    "unknown":                      0.50,
}

def get_base_rate(category: str) -> float:
    """Return base rate untuk kategori market."""
    return BASE_RATES.get(category, BASE_RATES["unknown"])

def classify_market(question: str) -> str:
    """
    Klasifikasikan pertanyaan market ke kategori base rate.
    Gunakan keyword matching sederhana, tidak perlu ML.
    
    Contoh:
    "Will Fed cut rates in March?" → "fed_rate_cut"
    "Will Ukraine ceasefire hold?" → "ceasefire_after_negotiation"
    "Will BTC reach $100K?"        → "btc_breakout_up"
    """
    question_lower = question.lower()
    
    # Implementasikan keyword matching di sini
    # Setiap kategori punya list keyword yang di-check
    # Return kategori pertama yang match
    # Fallback ke "unknown" kalau tidak ada yang match
```

---

### FILE: engine/ai_analyzer.py

Ini adalah JANTUNG dari bot. Kirim berita + context market ke Claude API,
terima estimasi probabilitas yang terstruktur.

Model yang dipakai: `claude-sonnet-4-5` (bukan Opus — terlalu mahal untuk 
iterative analysis; bukan Haiku — kurang akurat untuk financial reasoning).

PENTING — Cost control:
- MOCK_AI=true di .env berarti tidak ada API call sama sekali
- Return dummy response untuk paper trading gratis
- Hanya buat API call saat MOCK_AI=false

Prompt yang dikirim ke Claude (implementasikan PERSIS ini):

```python
SYSTEM_PROMPT = """
Kamu adalah quantitative analyst untuk prediction market. Tugasmu adalah
mengestimasi probabilitas suatu event terjadi berdasarkan berita terbaru
dan data yang diberikan.

Kamu HARUS merespons HANYA dengan JSON valid, tidak ada teks lain,
tidak ada markdown, tidak ada penjelasan di luar JSON.

Format respons yang WAJIB diikuti:
{
  "probability": float,        // 0.0 sampai 1.0
  "confidence": "LOW" | "MEDIUM" | "HIGH",
  "reasoning": string,         // maksimal 3 kalimat
  "key_factors": [string],     // maksimal 3 faktor terpenting
  "time_sensitivity": "HOURS" | "DAYS" | "WEEKS"
}

Rules:
- probability harus antara 0.05 dan 0.95 (tidak boleh 0 atau 1)
- confidence HIGH hanya kalau ada bukti kuat dan konsisten
- confidence LOW kalau berita ambigu atau contradictory
- reasoning harus spesifik, bukan generik
- Jangan pernah berikan rekomendasi BUY/SELL — hanya estimasi probabilitas
"""

USER_PROMPT_TEMPLATE = """
MARKET QUESTION: {question}
CURRENT MARKET PRICE (crowd belief): {market_price} ({market_price_pct}%)
BASE RATE (historical): {base_rate} ({base_rate_pct}%)
MARKET CATEGORY: {category}
RESOLVES: {end_date}

RELEVANT NEWS (last 6 hours):
{news_summary}

Berdasarkan informasi di atas, estimasi probabilitas bahwa market ini
akan resolve TRUE (YES). Pertimbangkan base rate historis sebagai prior,
lalu update berdasarkan berita terbaru (Bayesian reasoning).
"""
```

Implementasikan retry logic: kalau API call gagal, coba 3 kali dengan
exponential backoff (1s, 2s, 4s). Kalau masih gagal setelah 3 kali,
return None dan log error. JANGAN crash bot karena satu API call gagal.

Implementasikan response parsing yang robust: kalau JSON tidak valid atau
field yang dibutuhkan tidak ada, return None dan log warning.

---

### FILE: engine/ev_calculator.py

Hitung Expected Value dengan BENAR termasuk transaction fee Polymarket.

```python
POLYMARKET_FEE = 0.02  # 2% dari profit

def calculate_ev(
    ai_probability: float,
    market_price: float,    # harga saat ini di market (0.0 - 1.0)
    stake: float,           # berapa USDC yang akan dipertaruhkan
    side: str               # "YES" atau "NO"
) -> dict:
    """
    Hitung Expected Value dengan fee.
    
    Untuk BUY YES di harga 0.40:
    - Kalau menang: dapat $1.00 per share, profit = (1/0.40 - 1) × stake
    - Kalau kalah: kehilangan stake
    - Fee: 2% dari profit saja (bukan dari total)
    
    Returns dict dengan:
    - ev_raw: EV sebelum fee
    - ev_net: EV setelah fee (ini yang dipakai untuk keputusan)
    - edge: selisih ai_probability vs market implied probability
    - profitable: True kalau ev_net > 0
    """
    
    # Kalau side = "NO", flip probabilitas
    if side == "NO":
        ai_probability = 1 - ai_probability
        market_price = 1 - market_price
    
    # Potential profit per unit stake
    potential_profit = stake * (1 / market_price - 1)
    
    # EV tanpa fee
    ev_raw = (ai_probability * potential_profit) + \
             ((1 - ai_probability) * (-stake))
    
    # Fee hanya dari profit (bukan dari loss)
    fee = potential_profit * POLYMARKET_FEE
    
    # EV bersih
    ev_net = ev_raw - (ai_probability * fee)
    
    # Edge = selisih probabilitas
    edge = ai_probability - market_price
    
    return {
        "ev_raw": round(ev_raw, 4),
        "ev_net": round(ev_net, 4),
        "edge": round(edge, 4),
        "edge_pct": round(edge * 100, 2),
        "profitable": ev_net > 0,
        "fee_cost": round(ai_probability * fee, 4),
    }
```

---

### FILE: engine/kelly_sizer.py

Implementasikan Half-Kelly dengan uncertainty adjustment.

```python
def calculate_bet_size(
    ai_probability: float,
    market_price: float,
    bankroll: float,
    confidence: str,         # "LOW", "MEDIUM", "HIGH" dari AI
    kelly_fraction: float = 0.5  # default Half-Kelly
) -> dict:
    """
    Hitung ukuran bet optimal.
    
    Uncertainty multiplier berdasarkan confidence:
    - HIGH:   1.0  (pakai full Half-Kelly)
    - MEDIUM: 0.5  (pakai Quarter-Kelly)
    - LOW:    0.0  (SKIP, jangan bet)
    
    Hard limits yang tidak boleh dilanggar:
    - Maximum 15% bankroll per trade
    - Minimum bet: $5 (di bawah ini tidak worth the fee)
    - Kalau bankroll < $50: maximum 10% per trade
    """
    
    # Kalau confidence LOW, langsung return 0
    if confidence == "LOW":
        return {"bet_size": 0, "reason": "Confidence too low, skipping"}
    
    # Kelly formula: f* = (p*b - q) / b
    # b = net payout ratio = (1/market_price) - 1
    p = ai_probability
    q = 1 - ai_probability
    b = (1 / market_price) - 1
    
    if b <= 0:
        return {"bet_size": 0, "reason": "Invalid odds"}
    
    kelly_full = (p * b - q) / b
    
    # Kalau Kelly negatif, jangan bet
    if kelly_full <= 0:
        return {"bet_size": 0, "reason": "Negative Kelly, no edge"}
    
    # Apply fraction
    kelly_adjusted = kelly_full * kelly_fraction
    
    # Apply uncertainty multiplier
    uncertainty_multiplier = {"HIGH": 1.0, "MEDIUM": 0.5}.get(confidence, 0)
    kelly_adjusted *= uncertainty_multiplier
    
    # Calculate raw bet size
    raw_bet = bankroll * kelly_adjusted
    
    # Apply hard limits
    max_bet = bankroll * (0.10 if bankroll < 50 else 0.15)
    min_bet = 5.0
    
    final_bet = max(min_bet, min(raw_bet, max_bet))
    
    # Final check: jangan bet kalau melebihi bankroll
    final_bet = min(final_bet, bankroll * 0.95)
    
    return {
        "bet_size": round(final_bet, 2),
        "kelly_full_pct": round(kelly_full * 100, 2),
        "kelly_applied_pct": round(kelly_adjusted * 100, 2),
        "bankroll_pct": round(final_bet / bankroll * 100, 2),
        "reason": f"Half-Kelly × {uncertainty_multiplier} uncertainty multiplier",
    }
```

---

### FILE: risk/checklist.py

6 pertanyaan wajib sebelum setiap eksekusi.
SEMUA harus True, kalau ada satu False → SKIP trade, log alasannya.

```python
def pre_execution_checklist(
    trade_data: dict,
    bankroll: float,
    active_positions: int
) -> dict:
    """
    Validasi 6 checkpoint sebelum eksekusi.
    
    trade_data harus mengandung:
    - ev_net: float
    - edge_pct: float
    - confidence: str
    - bet_size: float
    - base_rate: float (tidak boleh None)
    - market_volume: float
    - hours_to_resolution: float
    
    Returns:
    - passed: bool (True kalau semua lolos)
    - checks: dict berisi hasil setiap checkpoint
    - failed_checks: list nama checkpoint yang gagal
    """
    
    checks = {
        "ev_positive":        trade_data["ev_net"] > 0,
        "edge_sufficient":    trade_data["edge_pct"] > 12.0,   # min 12% edge
        "confidence_ok":      trade_data["confidence"] != "LOW",
        "position_size_safe": trade_data["bet_size"] <= bankroll * 0.15,
        "market_liquid":      trade_data["market_volume"] >= 10_000,
        "not_overexposed":    active_positions < 3,             # max 3 posisi aktif
    }
    
    failed = [name for name, passed in checks.items() if not passed]
    
    return {
        "passed": len(failed) == 0,
        "checks": checks,
        "failed_checks": failed,
    }
```

---

### FILE: risk/survival_engine.py

Implementasikan "Survive or Die" system sesuai spesifikasi berikut.

State yang disimpan di `data/survival/state.json`:
```json
{
  "balance": 1000.0,
  "day_number": 1,
  "day_start_balance": 1000.0,
  "target_balance": 1250.0,
  "active_positions": [],
  "last_updated": "ISO8601",
  "total_trades": 0,
  "winning_trades": 0
}
```

Setiap posisi aktif dalam `active_positions` menyimpan:
```json
{
  "position_id": "uuid",
  "market_id": "condition_id",
  "question": "string",
  "side": "YES atau NO",
  "entry_price": 0.40,
  "shares": 250.0,
  "cost": 100.0,
  "ai_probability": 0.72,
  "edge_pct": 20.0,
  "opened_at": "ISO8601",
  "status": "OPEN"
}
```

Log harian di `data/survival/log.json` — append-only, JANGAN overwrite:
```json
[
  {
    "date": "2026-03-22",
    "day_number": 1,
    "starting_balance": 1000.0,
    "ending_balance": 1150.0,
    "target_balance": 1250.0,
    "target_achieved": false,
    "trades_today": [...],
    "death": false
  }
]
```

Kondisi "DEATH" (sistem mati):
- Balance turun di bawah $10
- Saat death: log entry dengan `"death": true`, print summary statistik
  (berapa hari bertahan, win rate, max balance dicapai), lalu exit program.

Method wajib yang harus ada:
- `load_state()` — baca dari disk, buat default kalau belum ada
- `save_state()` — tulis ke disk SETIAP kali balance berubah
- `open_position(trade_data)` — tambah posisi baru
- `close_position(position_id, outcome, final_price)` — tutup posisi
- `start_new_day()` — reset daily target, log hari sebelumnya
- `check_death()` → bool — cek apakah balance di bawah threshold
- `get_status_summary()` → dict — untuk display di console

---

### FILE: engine/decision_engine.py

Orkestrator utama yang menggabungkan semua engine.
Ini yang dipanggil oleh main loop.

Flow yang harus diimplementasikan:

```
Untuk setiap market aktif (yang sudah difilter):
  
  STEP 0 — Base Rate
    category = base_rate.classify_market(market.question)
    prior = base_rate.get_base_rate(category)
  
  STEP 1 — Cari berita relevan
    relevant_news = cari berita dari last 6 jam yang relevan
    dengan market question (keyword matching sederhana)
    Kalau tidak ada berita relevan → SKIP market ini
  
  STEP 2 — AI Analysis (Bayesian update)
    result = ai_analyzer.analyze(
        question=market.question,
        market_price=market.best_ask_yes,
        base_rate=prior,
        category=category,
        end_date=market.end_date,
        news=relevant_news
    )
    Kalau result None (API error) → SKIP
  
  STEP 3 — EV Calculation
    ev_data = ev_calculator.calculate_ev(
        ai_probability=result.probability,
        market_price=market.best_ask_yes,
        stake=100,  # dummy stake untuk kalkulasi
        side="YES" kalau result.probability > 0.5 else "NO"
    )
  
  STEP 4 — Kelly Sizing
    sizing = kelly_sizer.calculate_bet_size(
        ai_probability=result.probability,
        market_price=(best_ask_yes kalau YES, best_ask_no kalau NO),
        bankroll=survival_engine.balance,
        confidence=result.confidence
    )
  
  STEP 5 — Pre-execution Checklist
    check = checklist.pre_execution_checklist(
        trade_data={...gabungan semua data...},
        bankroll=survival_engine.balance,
        active_positions=len(survival_engine.active_positions)
    )
    Kalau check.passed == False → log alasan, SKIP
  
  STEP 6 — Output keputusan
    Kalau semua lolos → return BUY signal dengan semua detail
    Format output keputusan:
    {
      "action": "BUY" atau "SKIP",
      "market_id": str,
      "question": str,
      "side": "YES" atau "NO",
      "entry_price": float,
      "bet_size": float,
      "ai_probability": float,
      "market_probability": float,
      "edge_pct": float,
      "ev_net": float,
      "confidence": str,
      "reasoning": str,
      "skip_reason": str atau None,
      "timestamp": str ISO8601
    }
```

---

### FILE: execution/paper_trader.py

Simulasikan eksekusi tanpa uang nyata.

Saat "BUY" signal masuk:
1. Catat posisi via survival_engine.open_position()
2. Simpan ke state.json
3. Log ke log.json

Saat resolusi market (simulasi):
- Gunakan `random.random() < ai_probability` untuk simulasikan outcome
  TAPI tambahkan noise Gaussian (mean=0, std=0.1) ke ai_probability dulu
  untuk mensimulasikan bahwa AI tidak selalu benar
- Kalau WIN: balance += profit
- Kalau LOSS: balance -= stake
- Update survival_engine state
- Log hasilnya

Implement `simulate_market_resolution(position, actual_prob=None)`:
- Kalau actual_prob tidak diberikan → simulasikan dengan AI probability + noise
- Kalau actual_prob diberikan → gunakan itu (untuk testing)

---

### FILE: execution/live_trader.py

Wrapper untuk Polymarket CLOB API.
PENTING: Fungsi ini HANYA dijalankan kalau env var PAPER_TRADING=false.
Tambahkan guard di awal setiap fungsi:

```python
def place_order(self, ...):
    if os.getenv("PAPER_TRADING", "true").lower() == "true":
        raise RuntimeError(
            "PAPER_TRADING=true. Set PAPER_TRADING=false untuk live trading."
        )
```

Implementasikan:
- `get_client()` → ClobClient dengan credentials dari .env
- `place_order(market_id, side, price, size)` → kirim order
- `cancel_order(order_id)` → cancel order
- `get_balance()` → cek saldo USDC di proxy wallet

---

### FILE: monitoring/telegram_alert.py

Kirim notifikasi ke Telegram. Ini OPSIONAL — kalau TELEGRAM_BOT_TOKEN
tidak ada di .env, skip silently tanpa error.

Alert yang dikirim:
1. Saat bot start: "🚀 Bot started. Balance: $X.XX | Day: N"
2. Saat BUY signal: "📈 BUY [SIDE] | Market: [question truncated 50 char]
   | Edge: X.X% | Bet: $XX | Confidence: HIGH/MEDIUM"
3. Saat posisi closed (WIN): "✅ WIN +$XX.XX | New balance: $XXX.XX"
4. Saat posisi closed (LOSS): "❌ LOSS -$XX.XX | New balance: $XXX.XX"
5. Saat death: "💀 SYSTEM DEAD | Survived: N days | Final: $X.XX"
6. Setiap 6 jam: "📊 Status | Balance: $XXX | Day N | Target: $XXX | 
   Positions: N active"

Jangan kirim lebih dari 1 alert per menit (rate limit sendiri).
Gunakan requests library saja, tidak perlu python-telegram-bot.

---

### FILE: main.py

Entry point utama. Harus support argparse dengan mode berikut:

```
python main.py --mode paper     ← jalankan paper trading (default)
python main.py --mode live      ← live trading (butuh PAPER_TRADING=false di .env)
python main.py --mode once      ← satu siklus analisis lalu exit
python main.py --mode status    ← tampilkan status tanpa trading
python main.py --mode backtest  ← analisis log.json dan tampilkan statistik
```

Main loop untuk mode `paper` dan `live`:

```
1. Load state dari disk
2. Cegah laptop sleep
3. Kirim Telegram alert "bot started"
4. Check: apakah hari baru? → panggil survival_engine.start_new_day()
5. Check: apakah sudah DEAD? → exit kalau iya

Loop setiap 15 menit:
  a. Collect RSS feeds (setiap iterasi)
  b. Collect NewsAPI (setiap 60 menit saja — hemat quota)
  c. Update daftar market aktif (setiap 30 menit)
  d. Untuk setiap market aktif:
       → Jalankan decision_engine
       → Kalau BUY: jalankan paper_trader atau live_trader
  e. Cek posisi aktif yang mendekati resolusi (< 2 jam)
       → Simulasikan resolusi untuk paper trading
  f. Tampilkan status di console (balance, posisi aktif, today P&L)
  g. Tunggu 15 menit

Graceful shutdown saat Ctrl+C:
  → Simpan state
  → Log session summary
  → Allow laptop sleep kembali
  → Exit
```

---

### FILE: README.md

Tulis README yang menjelaskan:
1. Setup (pip install, buat .env dari .env.example)
2. Cara jalankan tiap mode
3. Penjelasan singkat arsitektur
4. Cara interpret log.json
5. Cara upgrade dari paper ke live trading
6. Troubleshooting umum (koneksi error, API key error, dll)

---

## VALIDASI AKHIR YANG HARUS KAMU LAKUKAN

Setelah semua file dibuat, jalankan validasi ini satu per satu:

1. `python -c "import requests, feedparser, dotenv, schedule, anthropic"` 
   → Harus tidak ada error

2. `python main.py --mode status`
   → Harus print status awal tanpa error, balance $1000

3. `python main.py --mode once`
   → Harus: collect berita, print daftar market, jalankan decision engine
     (dengan MOCK_AI=true), print keputusan BUY/SKIP, exit bersih

4. Cek semua file di data/ sudah terbuat dengan format JSON yang valid

5. Cek bahwa tidak ada hardcoded API key di kode manapun
   → Semua credentials HARUS dari os.getenv()

---

## CONSTRAINT ABSOLUT (TIDAK BOLEH DILANGGAR)

1. Total RAM usage saat idle harus di bawah 400MB
2. Tidak ada LLM lokal, tidak ada model ML yang diload ke memory
3. MOCK_AI=true berarti $0 cost — tidak boleh ada API call ke Anthropic
4. Semua state HARUS persist ke disk — restart laptop tidak boleh kehilangan data
5. Bot harus graceful terhadap network error — satu error tidak boleh kill bot
6. PAPER_TRADING=true harus benar-benar tidak menyentuh wallet atau order nyata
7. Maksimal 3 posisi aktif bersamaan
8. Tidak ada trade dengan edge < 12% atau confidence LOW
9. Tidak ada bet > 15% bankroll dalam satu trade
10. Semua keputusan AI harus bisa di-trace ke log — no black box

---

## URUTAN PENGERJAAN

Kerjakan file dalam urutan ini untuk menghindari import error:

1. utils/logger.py
2. utils/sleep_prevention.py
3. requirements.txt + .env.example + .gitignore
4. engine/base_rate.py
5. collector/rss_collector.py
6. collector/newsapi_collector.py
7. collector/market_collector.py
8. engine/ai_analyzer.py
9. engine/ev_calculator.py
10. engine/kelly_sizer.py
11. risk/checklist.py
12. risk/survival_engine.py
13. engine/decision_engine.py
14. execution/paper_trader.py
15. execution/live_trader.py
16. monitoring/telegram_alert.py
17. main.py
18. README.md
19. Jalankan validasi akhir

Setelah semua selesai, tunjukkan output dari `python main.py --mode once`
dan konfirmasi semua 5 validasi di atas passed.

---

MULAI SEKARANG. Kerjakan urutan di atas dari nomor 1.
Konfirmasi setiap file selesai dibuat sebelum lanjut ke file berikutnya.
Kalau ada keputusan desain yang ambigu, tanya dulu.
