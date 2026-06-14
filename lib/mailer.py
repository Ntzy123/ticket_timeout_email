# mailer.py
# 邮件发送核心（SMTP 发送 + 重试逻辑）

import smtplib, time, pytz
from datetime import datetime
from email.mime.text import MIMEText
from email.header import Header
from lib.logger import log


def send_mail(config, title, body):
    """基础邮件发送，返回 True/False

    参数:
        config: 邮件配置字典，包含 smtp_host/smtp_port/mail_user/mail_pass/receivers
        title, body: 邮件标题和正文
    """
    log.debug('开始发送邮件')

    mail_host = config['smtp_host']
    mail_port = config['smtp_port']
    mail_user = config['mail_user']
    mail_pass = config['mail_pass']
    receivers = config['receivers']

    message = MIMEText(body, "plain", "utf-8")
    message["From"] = f"Ntzy <{mail_user}>"
    message["To"] = ", ".join(receivers)
    message["Subject"] = Header(title, "utf-8")

    try:
        smtp_obj = smtplib.SMTP_SSL(mail_host, mail_port, timeout=30)
        smtp_obj.login(mail_user, mail_pass)
        failed = smtp_obj.sendmail(mail_user, receivers, message.as_string())
        if not failed:
            log.info('邮件发送成功（所有收件人已接受）')
            return True
        else:
            for addr, reason in failed.items():
                log.error(f'邮件发送失败 - 收件人 [{addr}]: {reason}')
            return False
    except smtplib.SMTPRecipientsRefused as e:
        log.error(f'所有收件人均被拒绝: {e.recipients}')
    except smtplib.SMTPSenderRefused as e:
        log.error(f'发件人被拒绝: {e}')
    except smtplib.SMTPAuthenticationError as e:
        log.error(f'邮箱登录认证失败: {e}')
    except smtplib.SMTPException as e:
        log.error(f'邮件发送失败: {e}')
    except Exception as e:
        log.error(f'发送邮件时发生未知异常 [{type(e).__name__}]: {e}')
    finally:
        if 'smtp_obj' in locals():
            smtp_obj.quit()
    return False


def send_mail_with_retry(config, title, body, ticket_timeout_list=None, retry_window=25):
    """发送邮件，失败后在 retry_window 分钟内自动重试

    参数:
        config: 邮件配置字典
        title, body: 邮件标题和正文
        ticket_timeout_list: 所有工单的超时时间列表，用于工单全超时后停止重试
        retry_window: 重试时间窗口（分钟），默认 25
    返回:
        True 表示最终发送成功，False 表示失败
    """
    deadline = time.time() + retry_window * 60
    china_tz = pytz.timezone('Asia/Shanghai')
    retry_count = 0

    while time.time() < deadline:
        retry_count += 1
        if retry_count > 1:
            log.info(f'第 {retry_count - 1} 次重试发送邮件')

        if send_mail(config, title, body):
            return True

        # 检查所有工单是否都已超时，如果全部超时则停止重试
        if ticket_timeout_list:
            try:
                now = datetime.now(china_tz).replace(tzinfo=None)
                all_expired = True
                for fb_time in ticket_timeout_list:
                    target = datetime.strptime(fb_time, "%Y-%m-%d %H:%M:%S")
                    if now < target:
                        all_expired = False
                        break
                if all_expired:
                    log.info('所有工单均已超时，停止重试')
                    return False
            except (ValueError, TypeError):
                pass

        # 指数退避：1, 2, 4, 8... 最大 60 秒
        sleep_time = min(60, 2 ** (retry_count - 1))
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(sleep_time, remaining))

    log.error(f'重试 {retry_count - 1} 次后邮件发送仍失败，放弃')
    return False
