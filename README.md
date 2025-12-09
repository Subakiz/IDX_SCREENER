# IDX_SCREENER

## Semi-automated Discord signal bot (Option A)

This repository includes a minimal Discord bot that sends trade instructions to a private channel so a human can execute orders manually on their broker. It mirrors the semi-automated flow described in the architecture but uses Discord instead of Telegram.

### Prerequisites

- Python 3.10+
- A Discord application with a bot token
- The bot invited to your Discord server with permission to post messages

Install the dependency:

```bash
pip install -r requirements.txt
```

### Environment variables

- `DISCORD_BOT_TOKEN`: Bot token from the Discord Developer Portal.
- `DISCORD_CHANNEL_ID`: Numeric ID of the channel that should receive signals.
- Optional helpers for defaults when running from CI or scripts:
  - `TRADE_SYMBOL`, `TRADE_ACTION`, `TRADE_ENTRY`, `TRADE_STOP`, `TRADE_SIZE_LOTS`, `TRADE_NOTE`
  - `BROKER_URL`: Link button destination (e.g., broker trade ticket).

### Usage

Send a signal with a single command (bot stays online to keep the action button active):

```bash
DISCORD_BOT_TOKEN=xxxxx DISCORD_CHANNEL_ID=123456789 \
python discord_signal_bot.py \
  --symbol BBRI.JK \
  --action BUY \
  --entry 4800 \
  --stop 4700 \
  --size 50 \
  --note "TDA stable regime; buy-the-dip"
```

The bot posts an embed with entry, stop, size, and a **Mark Executed** action button. If `BROKER_URL` is set, an **Open Broker** link button is also shown for quick navigation to your trading app.

### Notes

- The bot is intentionally lightweight so it can run alongside analytics on a small VPS.
- Messages remain actionable (buttons work) while the process is running; keep it online during trading sessions.
