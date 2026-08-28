"""Load runtime configuration from the environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        raise SystemExit(f"{name} 未填写，请检查 .env")
    return str(value).strip()


def _as_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().upper() in {"TRUE", "1", "YES", "ON"}


def _as_int(name: str, default: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        if default is None:
            raise SystemExit(f"{name} 未填写，请检查 .env")
        return default
    try:
        return int(str(raw).strip())
    except ValueError as exc:
        raise SystemExit(f"{name} 应该是数字") from exc


DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).expanduser()
DATA_DIR.mkdir(parents=True, exist_ok=True)

ASSETS_DIR = Path(os.getenv("ASSETS_DIR", "./assets")).expanduser()
CAPTCHA_DIR = ASSETS_DIR / "imgs"

BOT_TOKEN = _require("BOT_TOKEN")
APP_NAME = os.getenv("APP_NAME", "HermesDesk").strip() or "HermesDesk"
WELCOME_MESSAGE = (
    os.getenv("WELCOME_MESSAGE")
    or "你好，我是 HermesDesk 客服助手。\n请直接发送消息，我会转给人工客服。"
)

try:
    ADMIN_GROUP_ID = int(_require("ADMIN_GROUP_ID"))
except ValueError as exc:
    raise SystemExit("ADMIN_GROUP_ID 应该是数字") from exc

try:
    ADMIN_USER_IDS = [
        int(item.strip())
        for item in _require("ADMIN_USER_IDS").split(",")
        if item.strip()
    ]
except ValueError as exc:
    raise SystemExit("ADMIN_USER_IDS 应该是以逗号分隔的数字") from exc

if not ADMIN_USER_IDS:
    raise SystemExit("ADMIN_USER_IDS 未填写，请检查 .env")

DELETE_TOPIC_AS_FOREVER_BAN = _as_bool("DELETE_TOPIC_AS_FOREVER_BAN", False)
DELETE_USER_MESSAGE_ON_CLEAR_CMD = _as_bool("DELETE_USER_MESSAGE_ON_CLEAR_CMD", False)
DISABLE_CAPTCHA = _as_bool("DISABLE_CAPTCHA", False)
MESSAGE_INTERVAL = _as_int("MESSAGE_INTERVAL", 5)
BROADCAST_INTERVAL = float(os.getenv("BROADCAST_INTERVAL", "0.05"))
MEDIA_GROUP_DELAY = float(os.getenv("MEDIA_GROUP_DELAY", "5"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{(DATA_DIR / 'hermesdesk.sqlite3').as_posix()}",
)
PERSISTENCE_PATH = DATA_DIR / f"{APP_NAME}.pickle"
LOG_PATH = DATA_DIR / "hermesdesk.log"
