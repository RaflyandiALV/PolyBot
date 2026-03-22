# Polymarket Trading Bot 🤖

News-based edge trading bot for [Polymarket](https://polymarket.com) prediction markets.

## Strategi

Bot menggunakan **News-Based Edge Trading**:
1. Kumpulkan berita breaking dari RSS feeds + NewsAPI (gratis)
2. Kirim ke Claude API untuk analisis probabilitas (atau mock mode untuk $0)
3. Bandingkan estimasi AI vs harga pasar Polymarket
4. Kalau ada edge > 12%, hitung bet size pakai Half-Kelly Criterion
5. Jalankan validasi pre-execution (6 checkpoint)
6. Eksekusi trade (paper/live)

## Setup

### 1. Install Dependencies

```bash
cd polymarket-bot
pip install -r requirements.txt
```

### 2. Konfigurasi Environment

```bash
# Copy template
cp .env.example .env

# Edit .env dan isi API keys yang diperlukan
# Untuk paper trading, cukup biarkan default (MOCK_AI=true, PAPER_TRADING=true)
```

### 3. Jalankan Bot

```bash
# Paper trading (default, gratis $0)
python main.py --mode paper

# Single cycle analysis (lalu exit)
python main.py --mode once

# Lihat status saat ini
python main.py --mode status

# Analisis statistik trading
python main.py --mode backtest

# Live trading (HANYA kalau sudah siap)
python main.py --mode live
```

## Arsitektur

```
polymarket-bot/
├── collector/          ← Kumpulkan data (berita + harga market)
│   ├── rss_collector.py       9 RSS feeds (Reuters, BBC, CNBC, dll)
│   ├── newsapi_collector.py   NewsAPI free tier (100 req/hari)
│   └── market_collector.py    Polymarket CLOB API
│
├── engine/             ← Analisis dan keputusan trading
│   ├── base_rate.py           Prior probabilitas historis
│   ├── ai_analyzer.py         Claude API integration (atau mock)
│   ├── ev_calculator.py       Expected Value + fee
│   ├── kelly_sizer.py         Half-Kelly bet sizing
│   └── decision_engine.py     Orkestrator: 6 steps → BUY/SKIP
│
├── risk/               ← Risk management
│   ├── checklist.py           6-point pre-execution validation
│   └── survival_engine.py     "Survive or Die" — track bankroll
│
├── execution/          ← Eksekusi trade
│   ├── paper_trader.py        Simulasi (paper trading)
│   └── live_trader.py         Polymarket CLOB API (live)
│
├── monitoring/         ← Alert dan monitoring
│   └── telegram_alert.py      Telegram notifications (opsional)
│
├── utils/              ← Utility
│   ├── logger.py              Centralized logging
│   └── sleep_prevention.py    Cegah laptop sleep
│
├── data/               ← Data persisten (auto-generated)
│   ├── news/                  Berita yang dikumpulkan
│   ├── markets/               Data market Polymarket
│   └── survival/              State bot + trade log
│
└── main.py             ← Entry point
```

## Cara Baca log.json

File `data/survival/log.json` berisi history harian:

```json
{
  "date": "2026-03-22",
  "day_number": 1,
  "starting_balance": 1000.0,
  "ending_balance": 1050.0,
  "target_balance": 1250.0,
  "target_achieved": false,
  "trades_today": [],
  "death": false
}
```

- `target_achieved`: Apakah target harian tercapai
- `death`: Apakah sistem mati (balance < $10)

## Upgrade: Paper → Live Trading

1. Dapatkan API credentials dari [polymarket.com](https://polymarket.com) → Settings → API Keys
2. Isi semua `POLY_*` variables di `.env`
3. Isi `ANTHROPIC_API_KEY` di `.env` (dari [console.anthropic.com](https://console.anthropic.com))
4. Set `MOCK_AI=false` dan `PAPER_TRADING=false` di `.env`
5. Jalankan: `python main.py --mode live`

> ⚠️ **PENTING**: Pastikan paper trading statistics sudah memuaskan sebelum go live!

## Troubleshooting

| Problem | Solusi |
|---------|--------|
| `ModuleNotFoundError` | Jalankan `pip install -r requirements.txt` |
| RSS feeds error | Normal — bot akan skip feed yang error dan lanjut |
| NewsAPI quota habis | Otomatis fallback ke RSS saja |
| Balance $0 / DEAD | Hapus `data/survival/state.json` untuk reset |
| Bot crash saat sleep | `sleep_prevention.py` seharusnya mencegah ini |
| Telegram tidak kirim | Opsional — cek `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID` di `.env` |

## Constraints

- RAM usage < 400MB
- Tidak ada LLM lokal
- Max 3 posisi aktif bersamaan
- Min 12% edge untuk entry
- Max 15% bankroll per trade
- State persist ke disk (survive restart)

## Credits

Developed by Rafly — BINUS University  
Framework: Gojo.ether quant playbook (Base Rate → Bayes → EV → Kelly → KL-Diverge)
