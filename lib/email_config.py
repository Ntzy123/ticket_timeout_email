# email_config.py
# 邮件配置管理 - 检测 / 释放 email_config.toml

import os, sys, tomllib

_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'email_config.toml')

_TEMPLATE = """\
[smtp]
host = "smtp.qq.com"
port = 465
user = "your_email@qq.com"
password = "your_smtp_auth_code"

[receivers]
addresses = ["receiver1@qq.com", "receiver2@qq.com"]
"""

if not os.path.exists(_CONFIG_FILE):
    with open(_CONFIG_FILE, 'w', encoding='utf-8') as f:
        f.write(_TEMPLATE)
    print(f"[email_config] 配置文件不存在，已创建模板: {_CONFIG_FILE}")
    print("[email_config] 请编辑该文件填入您的邮箱配置后重新运行")
    sys.exit(1)

with open(_CONFIG_FILE, 'rb') as f:
    _cfg = tomllib.load(f)


def get_config():
    """返回邮件配置字典"""
    return {
        "smtp_host": _cfg["smtp"]["host"],
        "smtp_port": _cfg["smtp"]["port"],
        "mail_user": _cfg["smtp"]["user"],
        "mail_pass": _cfg["smtp"]["password"],
        "receivers": list(_cfg["receivers"]["addresses"]),
    }
