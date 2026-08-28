# Changelog

## 0.5.0 — 2026-08-28

值班时两个人抢同一单、反复复制欢迎语，这两件事先收掉。

- `/claim` `/unclaim`：话题软认领，不锁死其他客服回复；`/info` 和 `/status` 能看到
- `/setreply` `/replies` `/reply` `/delreply`：快捷回复库，话题内可点按钮发出
- 快捷回复会在后台话题留底，并写入 MessageMap，之后能编辑同步 / `/del`
- `/clear` 清话题时同时丢掉认领标记

## 0.4.0 — 2026-08-28

消息改过之后，另一侧跟着改；撤回只能客服来做。

- 客户或客服编辑文本 / 说明，映射对端同步 `editMessageText` / `editMessageCaption`
- `/del`：回复一条已映射消息，成对删除客户侧和后台副本
- Bot API 没有「对方撤回了」的更新，所以不做自动撤回同步

## 0.3.0 — 2026-08-28

客服每天会用到的命令，替代「删话题 = 封禁」。

- `/ban` `/unban`：在客户话题里封禁 / 解封，话题可保留作记录
- `/info`：档案（Premium、封禁、停用、last_seen、备注）并刷新名片
- `/note`：仅客服可见的备注；`/note clear` 清空
- 广播跳过已封禁和已停用用户；`Forbidden` 自动打 `is_blocked`
- 客服回复遇到客户停用机器人时，同样标记，避免下次再打
- `/status` 增加「停用机器人」计数

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
