# Changelog

## 0.2.0 — 2026-08-28

HermesDesk 第一轮：换名、拆包、修会话层，产品行为与上游双向客服保持一致。

### 工程

- 包名从 `interactive-bot` 换成 `hermesdesk`
- 配置、数据库、handlers、services 拆开
- 每次请求使用短 SQLAlchemy Session；SQLite 打开 WAL
- User upsert（姓名 / username / Premium / last_seen）
- `/clear` 级联清理 `MessageMap` 与话题状态
- 广播限速，结束后回执成功 / 失败 / 拉黑数
- 未捕获异常摘要发到后台群
- 新增 `/status`
- 滚动日志与 SQLite 放到 `data/`
- 可用的 Dockerfile + docker-compose
- 修正 README 里「需要 API_ID/HASH」的过时说明

### 致谢

基于 [MiHaKun/Telegram-interactive-bot](https://github.com/MiHaKun/Telegram-interactive-bot)。
