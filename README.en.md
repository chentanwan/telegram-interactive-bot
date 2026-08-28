# HermesDesk

A self-hosted bidirectional Telegram helpdesk bot. Customers talk to the bot in private chat; each conversation becomes a **forum topic** in your staff group so several agents can reply as the same bot.

> HermesDesk is [chentanwan](https://github.com/chentanwan)'s fork of [MiHaKun/Telegram-interactive-bot](https://github.com/MiHaKun/Telegram-interactive-bot). Credit to [MiHa (@MrMiHa)](https://t.me/MrMiHa) for the original “one topic per customer” design. This tree keeps the Apache-2.0 license and the thanks.

[中文文档](README.md) · [Dev log](docs/DEVLOG.md) · [Changelog](CHANGELOG.md)

## What it does

- Copies (not forwards) customer messages into a dedicated topic named `Full Name|user_id`
- Copies staff replies back to the customer; quote-replies map in both directions
- Closing / reopening a topic pauses / resumes the conversation
- Albums, image captcha, flood interval, optional forever-ban when a topic is deleted
- `/clear`, `/broadcast` (success / fail / bot-blocked summary), `/status`
- Staff topic commands: `/ban`, `/unban`, `/info`, `/note`, `/del` (paired delete)
- Text / caption edits sync both ways. Bots do not receive user-side deletes, so staff use `/del`.

## Run locally

```bash
cp .env_example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m hermesdesk
```

You need a BotFather token, a supergroup with Topics enabled, and the bot as admin with message + topic management. Telegram API_ID / API_HASH are **not** required.

```bash
docker compose up -d --build
```

See the Chinese README for the full env table. Runtime data lives in `data/`.
