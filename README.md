# Ticket Timeout Email

工单超时邮件提醒系统，部署于云服务器，定时查询工单并发送邮件提醒。

## 项目结构

```
ticket_timeout_email/
├── index.py                  # 主入口，定时查询 + 邮件发送
├── requirements.txt          # Python 依赖
├── .config.json              # API 配置文件
├── ignore.txt                # 忽略工单列表
├── lib/
│   └── ticket.py             # 核心库：工单查询、超时判断
└── feature/
    ├── ticket_timeout_pm.py  # 周期性工单（PM）超时检测
    └── ticket_timeout_od.py  # 临时性工单（OD）超时检测
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python index.py
```

## 环境变量（可选）

邮件配置支持通过环境变量覆盖：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `MAIL_HOST` | SMTP 服务器 | smtp.qq.com |
| `MAIL_PORT` | SMTP 端口 | 465 |
| `MAIL_USER` | 发件邮箱 | - |
| `MAIL_PASS` | 邮箱授权码 | - |
| `MAIL_RECEIVERS` | 收件人（逗号分隔） | - |

## 说明

- 每 5 分钟查询一次周期性工单
- 发现超时工单后发送邮件，等待 30 分钟后继续查询
- 异常时等待 60 秒自动重试
