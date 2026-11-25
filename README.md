# PlatePal

Text-only local stage. A Telegram bot sends a typed meal to a FastAPI engine. The engine matches the food sheet, compares the day with ICMR-NIN 2020 adult targets, and asks Groq to choose up to three fillers from that sheet.

Photos are not part of this stage.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Fill `GROQ_API_KEY` and `TG_TOKEN` in `.env`. Leave `ENGINE_KEY` as `dev-key` or change it in both places. Create the bot with [@BotFather](https://t.me/BotFather) using `/newbot`.

## Run

Terminal 1:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn engine.app:app --reload --port 8000
```

Terminal 2:

```powershell
.\.venv\Scripts\Activate.ps1
python -m bot.bot
```

On your phone, open the bot, send `/start`, set sex, diet, and weight, then send `2 idli and sambar`. Confirm with Yes. The reply is an estimate, not a diagnosis.

`pytest` checks matching, serving math, and the gap threshold without calling Groq or Telegram.
