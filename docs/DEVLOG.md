# HermesDesk 开发日志

给以后写博客用的本地记录。按时间倒序。写的时候尽量记下「当时看到了什么、为什么这么改」，而不是只列文件名。

---

## 2026-08-28　立项：从 fork 变成自己的项目

### 从哪来

仓库是 [chentanwan/telegram-interactive-bot](https://github.com/chentanwan/telegram-interactive-bot)，fork 自 [MiHaKun/Telegram-interactive-bot](https://github.com/MiHaKun/Telegram-interactive-bot)。原作者米哈（[@MrMiHa](https://t.me/MrMiHa)）在 2024 年 7 月用大约两小时写出初版，之后几个月补上了：

- 话题（Forum Topic）一人一帖
- 消息 copy 而不是 forward，客户看不到客服账号
- 引用回复的 message_id 映射
- 媒体组延迟聚合
- 图片验证码
- `/clear`、`/broadcast`
- 刷屏间隔，减轻 FloodWait
- 一份「能跑但不完整」的 Dockerfile

README 里的 ToDo 已经全部打勾。代码大约 650 行，核心挤在 `interactive-bot/__main__.py`。这是一个很适合自托管的小工具，也是一个还停在「能跑」阶段的代码库。

### 为什么叫 HermesDesk

不想继续用 `interactive-bot` 这种功能描述当项目名。Hermes 是信使，Desk 是客服台：消息从客户手里接过来，放到后台一张桌子上，再送回去。文件夹本来就叫「Hermes 工作文件夹」，名字和本地工作流也顺。

对外 enterypoint：`python -m hermesdesk`。

### 第一轮不做什么

明确不做（留给 0.3）：

- `/ban` `/unban` `/info` `/note` 客服命令
- 消息编辑 / 撤回同步
- Webhook、Postgres、Web 管理台
- 更强的验证码或 AI 自动回复

第一轮只做「骨架」：行为对外尽量不变，里面换成能接着改的结构。

### 拆开之后的形状

```
hermesdesk/
  __main__.py          # python -m hermesdesk
  bot.py               # 装配 Application、注册 handler
  config.py            # .env
  logging_setup.py     # stdout + data/hermesdesk.log 滚动
  db/
    session.py         # 短 Session、SQLite WAL、缺列补齐
    models.py          # User / MessageMap / FormnStatus / MediaGroupMessage
  handlers/
    user.py            # /start、u2a 转发、名片
    admin.py           # a2u、话题开关、/clear /broadcast /status
    captcha.py         # 图片验证码
  services/
    users.py           # upsert
    topics.py          # open/closed
    messages.py        # 两边 message_id 映射
    media_group.py     # 相册延迟发送
    jobs.py            # 延时删消息
```

数据默认进 `data/`，验证码图仍在 `assets/imgs/`（文件名即答案，这是上游的实现，0.2 原样保留）。

### 动手时踩到的坑（写博客可以展开）

1. **全局 Session**  
   上游 `db = SessionMaker()` 在 import 时建一个用到进程结束。SQLite 还配了 `pool_size=100`，对 SQLite 没有意义。网络请求（`create_forum_topic`、`send_copy`）夹在同一次 Session 里，请求慢或失败时连接一直占着。0.2 改成 `with get_session()`，并且尽量让 Session 不跨网络调用。

2. **User 只插入**  
   `update_user_db` 发现有记录就 return。客户改名、改 username、开通 Premium，名片永远是第一次的快照。模型里有 `is_premium`，写入路径却从未赋值。upsert 之后名片上的「高级会员」才可能是真的。

3. **`/clear` 不收数据库**  
   话题删了，`MessageMap` 和 `message_thread_id` 还在。客户再来一条，引用会串到已经不存在的消息。0.2 在 `/clear` 里删映射、把 thread id 归零。

4. **媒体组 job 用 name 传参**  
   `sendmediagroup_{chat}_{target}_{dir}`，同一用户连发两组相册时 name 碰撞。0.2 把 `media_group_id` 放进 job.data，name 也带上 group id。

5. **README 写了 API_ID/HASH，env 里没有**  
   这是 Bot API 项目，python-telegram-bot 只用 Bot Token。文档抄到「准备工作」时把 MTProto 的概念带进来了。0.2 文档删掉这一条，避免后来的自己被坑。

6. **Dockerfile 不 COPY 代码**  
   上游镜像只装依赖，靠 `docker run -v "$PWD":/app`。本机没代码就空跑。0.2 把 `hermesdesk/` 和 `assets/` 打进镜像，compose 只挂 `data/`。

7. **广播是定时器里裸循环**  
   没有间隔、没有回执、`Forbidden` 和 429 一视同仁当失败。用户一多必撞限流。0.2 加了 `BROADCAST_INTERVAL`，并回「成功 / 失败 / 拉黑或停用」。

### 原作者该被怎么写进博客

建议的致谢口径：

> 这个项目不是从零发明「Telegram 客服 Bot」。米哈的 Telegram-interactive-bot 已经证明：用超级群的 Forum Topic 当工单，copy 消息而不是 forward，是自托管场景里最省事的模型。HermesDesk 是在这条路上做工程化和后续产品，而不是换一套协议重新发明轮子。

原协议是 Apache-2.0，致谢段和 LICENSE 都要留。

### 下一轮预告（当时写的 0.3，现已做完）

客服每天会碰到的命令，优先于花活：

- `/ban` `/unban`：替代「删话题 = 封禁」
- `/info`：刷新名片、显示 last_seen、Premium、是否封禁
- `/note`：话题内备注，只给客服看
- 广播结束后把 `Forbidden` 用户标成停用，避免下次再打

然后再考虑编辑/撤回同步和快捷回复。

---

## 2026-08-28　0.3 客服命令

0.2 把骨架立住以后，客服侧仍然只有 `/clear` 和 `/broadcast`。真实值班时最别扭的是：要拉黑一个人得删掉整个话题，记录没了；广播打到已经 `/stop` 的用户，下次还打。

### 两个开关，不要混

| 字段 | 谁设置 | 含义 |
|---|---|---|
| `is_banned` | 客服 `/ban` | 我们不接待这个人 |
| `is_blocked` | Telegram `Forbidden` | 对方停用了机器人，再发也没用 |

`/unban` 两个都清。广播名单是「未封禁且未停用」。客户再主动发消息进来时会清掉 `is_blocked`（能发过来就说明机器人没被停）。`is_banned` 仍拦截客户→客服。

### 命令都绑在话题上

`/ban` `/unban` `/info` `/note` 必须在客户 Topic 里用。解析路径是 `message_thread_id → User`，不接受随手在总群里敲。`/note` 也可以回复一条消息把正文当备注；空参数或 `clear` / `-` / `删除` 清空。

`/info` 会再调一次名片发送。名片还是 0.2 那套 `send_contact_card`，数据改成库里的 upsert 结果，Premium 标记这回是真的。

### 没做的（当时）

编辑/撤回同步、快捷回复、认领话题，留给后面。0.3 只解决「值班时手边缺的四条命令」。

---

## 2026-08-28　0.4 编辑同步与 /del

客服改了一句错别字，客户那边还是旧的，这在值班里很常见。MessageMap 已经有两边的 message_id，缺的只是监听 `edited_message`。

### 为什么没有「自动撤回」

Telegram Bot API 不会把「用户删除了一条私聊消息」推给你。群里客服自己删，机器人也未必看得到（取决于删除方式）。所以 0.4 不做假的撤回同步，改成明确的客服命令：回复那条消息发 `/del`，两边一起删，映射从表里拿掉。

### 编辑能同步什么

- 纯文本：`editMessageText`，带上 `text_html`
- 带说明的媒体：`editMessageCaption`
- 换成另一种媒体、或编辑相册：Bot API 限制多，0.4 不管，失败只打日志

关闭的话题和被封禁的客户，编辑会被忽略。客服侧编辑撞到 `Forbidden`，同样打 `is_blocked`。

### 下一步

快捷回复（预设话术按钮）和 `/claim` 认领，仍然比 Webhook / 管理台更贴近值班。

---

## 博客提纲（可直接扩写成文章）

标题备选：

- 《把别人的 Telegram 客服 Bot 养成自己的项目》
- 《HermesDesk：在 Forum Topic 上长出来的自托管工单》

结构：

1. **为什么 fork，而不是重写**  
   米哈已经验证了 copy + 话题模型。重写协议没有意义，缺的是工程骨架。
2. **Demo 怎么走一遍**  
   客户私聊 → 后台出现 `姓名|uid` 话题 → 客服回复 → 客户收到。强调 copy 不是 forward。
3. **650 行单文件的代价**  
   全局 Session、User 不更新、`/clear` 不收映射、Dockerfile 不 COPY 代码。各用一个小故事。
4. **换名 HermesDesk**  
   信使 + 客服台。entrypoint 变成 `python -m hermesdesk`。
5. **0.2 做了什么、刻意没做什么**  
   做了拆包 / Session / upsert / compose / 文档。没做 ban 命令和 AI，避免第一轮变成大爆炸。
6. **致谢**  
   Apache-2.0，原作者米哈，仓库链接。不要写成「我从零做了一个客服机器人」。
