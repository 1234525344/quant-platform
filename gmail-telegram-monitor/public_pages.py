# -*- coding: utf-8 -*-
"""Static public disclosures. No mailbox data or credentials are rendered."""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


def page(title, content):
    return HTMLResponse("<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>" + title + "</title><style>body{max-width:760px;margin:48px auto;padding:0 24px;"
        "font:17px/1.8 system-ui;color:#202b36}a{color:#175fa2}</style><main><h1>" + title + "</h1>"
        + content + "<p><a href='/'>应用首页</a> · <a href='/privacy'>隐私说明</a> · "
        "<a href='/terms'>使用说明</a></p></main></html>")


@router.get("/", response_class=HTMLResponse)
def home():
    return page("Gmail Telegram 邮件监测", "<p>个人券商邮件提醒工具，仅供配置者本人使用。</p>"
        "<p>经账户本人授权，定期检查 Gmail 收件箱中指定券商的邮件，将发件人、主题和正文节选发送到本人配置的 Telegram 私聊。"
        "自动回复不推送；使用 Gmail 自定义标签记录处理状态。</p>"
        "<p>本工具不提供公共注册，不处理第三方账户，不代为发送邮件或执行交易。提醒可能延迟；请以原始邮箱和券商信息为准。</p>"
        "<p>账户支持联系信息见 Google 授权页面。</p>")


@router.get("/privacy", response_class=HTMLResponse)
def privacy():
    return page("隐私说明", "<p>更新日期：2026-10-11。适用于 Gmail Telegram 邮件监测的当前个人使用配置。</p>"
        "<h2>访问与用途</h2><p>通过 Gmail API 和账户本人授权的 gmail.modify 权限读取匹配邮件的发件人、主题、正文及标签，"
        "并创建或添加处理标签以避免正常重复推送。该权限允许修改邮箱内容，但当前功能仅用其处理自定义标签，不发送、删除或归档邮件。</p>"
        "<h2>数据流转</h2><p>邮件由 Google 提供，在 Render 托管的服务中处理；匹配邮件的发件人、主题及正文节选通过 Telegram Bot API "
        "发送到本人设置的 Telegram 私聊。Google、Render 和 Telegram 按各自平台规则处理平台侧数据。"
        "GitHub Actions 只持有调用接口的专用密钥，得到聚合计数或错误状态，不得到邮件内容或 Gmail、Telegram 凭证。</p>"
        "<h2>存储与限制</h2><p>OAuth 凭证保存在配置者电脑的受限目录和 Render 环境变量中，不进入公开仓库。"
        "服务不建立邮件正文数据库；处理状态保存在 Gmail 标签中，邮件正文在处理时临时使用，Telegram 中的通知由本人管理。"
        "服务日志仅记录运行信息和聚合错误，功能不主动写入邮件正文或凭证。当前配置未启用付费 AI 摘要。"
        "Google 用户数据仅用于本人请求的邮件提醒，不用于广告、销售或模型训练；更改数据用途前应更新说明并重新取得授权。</p>"
        "<h2>停止与删除</h2><p>本人可在 Google 账户的第三方连接中撤销授权，停用 GitHub 工作流和 Render 服务，删除保存的 OAuth 凭证、"
        "相关 Gmail 自定义标签及 Telegram 通知。撤销授权会停止后续邮箱访问；已发送到 Telegram 的消息不会自动删除。</p>"
        "<p>本应用使用 Google API 收到的信息遵循 Google API Services User Data Policy，包括 Limited Use 要求。</p>")


@router.get("/terms", response_class=HTMLResponse)
def terms():
    return page("使用说明", "<p>本工具只用于配置者自己的 Gmail 账户与 Telegram 私聊，作为辅助提醒。</p>"
        "<p>每五分钟为计划调度间隔，平台排队、免费服务额度、网络及授权到期均可能造成延迟或中断。补扫窗口为最近七天。"
        "Telegram 发送与 Gmail 标签写入无法原子提交，极端故障后重试可能重复。</p>"
        "<p>不依赖本工具作为唯一邮件记录；重要事项应直接核对 Gmail 和原发件人。本工具不执行交易，也不提供交易建议。</p>"
        "<p>可随时停止调度、停用服务或撤销 Google 授权。当前配置不绑定 Google Cloud 账单，不启用付费 AI。</p>")
