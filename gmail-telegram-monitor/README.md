# Gmail Telegram Monitor

券商邮件通知服务：GitHub Actions 每五分钟调用 Render 的受保护轮询接口，扫描最近七天 INBOX 内白名单发件人的邮件。自动回复会标记但不推送；正常邮件发送成功后才加 `BROKER_ALERTS_SENT` 标签。收费 AI 默认关闭。

## 配置与启动

Render 保留 `GOOGLE_CLIENT_ID`、`GOOGLE_CLIENT_SECRET`、`GMAIL_REFRESH_TOKEN`、`MONITORED_GMAIL`、`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`，另设随机 `POLL_SECRET` 和固定安装时间戳 `POLL_BASELINE_BEFORE`（Unix 秒）。GitHub 仓库 Actions secret `GMAIL_POLL_SECRET` 仅保存相同的轮询密钥。

部署后使用 `X-Poll-Secret` 请求头调用 `POST /admin/poll`，JSON `{"bootstrap":true}`，先为安装时间前已有匹配邮件建立基线，避免旧邮件集中通知。成功后 Gmail 的隐藏标签 `BROKER_MONITOR_BASELINE_READY` 记录状态。重复建立基线是空操作；失败后可安全重试。普通轮询使用 `{}`，基线未完成返回 409。

`POST /admin/test-notification` 用同一密钥测试 Telegram 连接；这不是实际邮件投递证据。`GET /health` 只公开聚合状态、最后尝试和成功时间，不公开邮件或凭证。所有扫描路径共享进程内互斥锁；仅运行一个 Uvicorn worker。

## 运行检查

- 定时工作流必须存在于默认分支 `main`；服务代码从 `gmail-monitor-deploy` 部署。
- GitHub → Actions → Gmail Telegram polling 查看最近运行，必要时 Run workflow 手动补扫。失败显示失败状态；服务可连接 Telegram 时会发送错误通知，恢复后发送恢复通知。同一进程内相同错误不会每轮重复提醒。
- Google 外部 OAuth 应用处于 Testing 时，Gmail 刷新令牌通常七天失效。应完成品牌配置、核实个人使用发布条件，发布到 Production 后重新授权并更新 Render；未完成前须按测试授权处理。
- 调度可能延迟或遗漏；公开仓库无活动 60 天可能停用调度，届时在 Actions 手动重新启用。服务整体停用时不能依靠服务自身发送故障通知，需检查 Actions 失败邮件和健康页最后成功时间。
- 免费 Render 每个工作区共享 750 小时/月；本方案只使用现有免费服务。不关联 Google 账单、不使用付费 Cron。
- Telegram 发送与 Gmail 标签写入不是原子事务。发送后标签写入失败可能导致重试重复；停机超过七天窗口也可能漏掉更早邮件。

## 测试

安装监测 requirements 与 pytest，在监测目录运行 `py -3.12 -m pytest tests -q`。测试使用虚构邮件，不访问真实邮箱或 Telegram。
