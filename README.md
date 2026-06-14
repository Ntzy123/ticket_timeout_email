# Ticket Timeout Email

工单超时邮件提醒系统，部署于云服务器，定时查询工单并发送邮件提醒。

## 项目结构

```
ticket_timeout_email/
├── run.py                     # 主入口：加载配置 + 启动子模块
├── email_config.toml          # 邮件配置（SMTP + 收件人，git 不追踪）
├── requirements.txt           # Python 依赖
├── .config.json               # API 配置文件
├── ignore.txt                 # 忽略工单列表
├── lib/
│   ├── email_config.py        # 邮件配置管理（自动检测/释放 email_config.toml）
│   ├── logger.py              # 日志模块（控制台 + 每日文件）
│   ├── mailer.py              # 邮件发送核心（SMTP + 重试）
│   └── ticket.py              # 核心库：工单查询、超时判断
└── feature/
    ├── ticket_timeout_pm.py   # 周期性工单（PM）超时检测（查询+调度+汇总）
    └── ticket_timeout_od.py   # 临时性工单（OD）超时检测
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行（首次会自动生成 email_config.toml 模板）
python run.py
```

## 配置

首次运行会自动生成 `email_config.toml` 模板文件，编辑后重新运行即可：

```toml
[smtp]
host = "smtp.qq.com"
port = 465
user = "your_email@qq.com"
password = "your_smtp_auth_code"

[receivers]
addresses = ["receiver1@qq.com", "receiver2@qq.com"]
```

**注意：** `email_config.toml` 已被 `.gitignore` 忽略，不会提交到 Git。

## 说明

- 每 5 分钟查询一次周期性工单
- 发现超时前 40 分钟内的工单后，倒计时到超时前 30 分钟准时发送
- 多条工单汇总为一条邮件发送
- SMTP 发送失败在 25 分钟内自动重试（指数退避）
- 异常时等待 60 秒自动重试
