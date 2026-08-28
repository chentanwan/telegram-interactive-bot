# HermesDesk

自托管的 Telegram 双向客服机器人。客户私聊 Bot，后台用**论坛话题（Forum Topic）**一人一帖，多位客服可以共用同一个机器人身份持续接待。

> 本项目由 [chentanwan](https://github.com/chentanwan) 基于 [MiHaKun/Telegram-interactive-bot](https://github.com/MiHaKun/Telegram-interactive-bot) fork 后独立演进。原作者 [米哈 @MrMiHa](https://t.me/MrMiHa) 用很短的时间把「话题当工单」这条路走通了，HermesDesk 在此之上做工程化与后续迭代。感谢米哈同学的开源。

[English](README.en.md) · [开发日志](docs/DEVLOG.md) · [变更记录](CHANGELOG.md)

## 它做什么

```
客户私聊 Bot
    ↓  copy（不是 forward，客户看不到客服账号）
管理群 Topic（姓名|uid）
    ↓  copy
客户私聊
```

- 客户发来的每条消息进入独立话题，完整保留沟通记录
- 客服在话题里回复，会原样发回客户；引用回复两边都能对上
- 关闭 / 重开话题 = 暂停 / 恢复对话
- 支持相册（媒体组）、图片验证码、刷屏间隔、永久封禁开关
- `/clear` 删除话题（可选同时清客户侧消息）
- `/broadcast` 向全部用户广播，完成后回执成功 / 失败 / 拉黑数
- `/status` 查看用户数、开放话题、后台任务

## 和上游的关系

上游仓库已经把核心能力做完：双向转发、话题、引用、媒体组、验证码、Docker 草稿。HermesDesk 第一轮没有改产品语义，而是把「能跑」做成「能维护」：

| 上游 | HermesDesk 0.2 |
|---|---|
| `interactive-bot/__main__.py` 单文件 | `hermesdesk/` 分包：config / db / handlers / services |
| 全局一个 SQLAlchemy Session | 每次请求短 Session |
| User 只插入不更新 | upsert（名字、username、Premium、last_seen） |
| `/clear` 不收映射 | 级联清理 MessageMap / 话题状态 |
| 广播无回执、无限速 | 限速 + 成功/失败/拉黑统计 |
| Dockerfile 不 COPY 代码 | 镜像内含代码 + `docker-compose` |
| 日志写仓库根目录 `log.txt` | 滚动日志在 `data/hermesdesk.log` |

下一步会做客服命令（`/ban` `/unban` `/info` `/note`）、编辑撤回同步、快捷回复。路线写在 [docs/DEVLOG.md](docs/DEVLOG.md)。

## 准备工作

1. 找 [@BotFather](https://t.me/BotFather) 申请机器人，拿到 Token。**不需要** Telegram API_ID / API_HASH（那是 MTProto 用户协议的东西）。
2. 建一个超级群，打开「话题 / Topics」。
3. 把机器人拉进群，设为管理员，权限至少包含 **消息管理** 和 **话题管理**。
4. 用 [@userinfobot](https://t.me/userinfobot) 之类的工具拿到群 ID（通常是 `-100...`）和客服账号的 user id。

## 本地运行

```bash
cp .env_example .env
# 填 BOT_TOKEN、ADMIN_GROUP_ID、ADMIN_USER_IDS

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m hermesdesk
```

数据文件默认写到 `data/`（SQLite、pickle 会话、滚动日志），不要提交进 git。

正式运营请用 systemd、supervisor 或 Docker 做守护，避免进程挂了没人知道。

## Docker

```bash
cp .env_example .env
docker compose up -d --build
```

容器只持久化 `./data`。验证码图片来自镜像内的 `assets/imgs`。

## 配置

| 变量 | 含义 | 默认 |
|---|---|---|
| `BOT_TOKEN` | BotFather 发的 token | 必填 |
| `APP_NAME` | 显示名、pickle 文件名前缀 | `HermesDesk` |
| `WELCOME_MESSAGE` | 客户 `/start` 欢迎语 | 内置中文 |
| `ADMIN_GROUP_ID` | 后台话题群 | 必填 |
| `ADMIN_USER_IDS` | 逗号分隔的管理员 user id | 必填 |
| `DELETE_TOPIC_AS_FOREVER_BAN` | 删话题视为永久封禁 | `FALSE` |
| `DELETE_USER_MESSAGE_ON_CLEAR_CMD` | `/clear` 同时删客户侧消息 | `FALSE` |
| `DISABLE_CAPTCHA` | 关闭人机验证 | `FALSE` |
| `MESSAGE_INTERVAL` | 客户消息最短间隔（秒），`0` 不限制 | `5` |
| `BROADCAST_INTERVAL` | 广播间隔（秒） | `0.05` |
| `MEDIA_GROUP_DELAY` | 相册聚合等待（秒） | `5` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `DATA_DIR` | 数据目录 | `./data` |
| `DATABASE_URL` | SQLAlchemy URL | `sqlite:///./data/hermesdesk.sqlite3` |

## 后台命令

在管理群使用：

- `/clear`：在某个客户话题里删除该话题，并清理本地映射
- `/broadcast`：回复一条消息后广播给全部未封禁用户
- `/status`：用户数、封禁数、开放话题、队列任务

客户侧只有 `/start`。

## 致谢

- 原项目：[MiHaKun/Telegram-interactive-bot](https://github.com/MiHaKun/Telegram-interactive-bot)，作者 米哈（[@MrMiHa](https://t.me/MrMiHa)），Apache-2.0
- 原讨论群：https://t.me/DeveloperTeamGroup
- HermesDesk 维护：[chentanwan](https://github.com/chentanwan)

本仓库继续使用 Apache-2.0。Fork 时请保留本段致谢与 LICENSE。
