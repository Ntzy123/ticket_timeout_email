# run.py
# 工单超时邮件提醒 - 纯后台版，7x24h 运行
#
# 核心逻辑：
#   1. 每 5 分钟轮询一次工单
#   2. 发现 40 分钟内即将超时的工单 → 启动倒计时线程，确保在超时前 30 分钟准时发邮件
#   3. 调度成功后冷却 30 分钟，避免重复调度
#   4. SMTP 发送失败则在 25 分钟内自动重试

import os, smtplib, time, signal, sys, threading
from datetime import datetime, timedelta
import pytz
from feature.ticket_timeout_pm import TicketTimeoutPM
from email.mime.text import MIMEText
from email.header import Header


# ===== 日志模块（控制台 + 每日文件） =====
class Logger:
    def __init__(self):
        self.china_tz = pytz.timezone('Asia/Shanghai')
        self.log_dir = 'log'
        os.makedirs(self.log_dir, exist_ok=True)

    def _log_path(self):
        now = datetime.now(self.china_tz)
        return os.path.join(self.log_dir, f"tte_{now.strftime('%Y_%m_%d')}.log")

    def _write(self, level, msg):
        ts = datetime.now(self.china_tz).strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{level}] [{ts}] {msg}"
        print(line)
        try:
            with open(self._log_path(), 'a', encoding='utf-8') as f:
                f.write(line + '\n')
        except Exception as e:
            print(f"[ERROR] [{ts}] 日志文件写入失败: {e}")

    def info(self, msg):    self._write('INFO ', msg)
    def error(self, msg):   self._write('ERROR', msg)
    def debug(self, msg):   self._write('DEBUG', msg)

log = Logger()


# ===== 信号处理（优雅退出） =====
def handle_exit(signum, frame):
    log.info('收到退出信号，程序关闭中...')
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)


# ===== 邮件发送（基础函数 + 重试包装） =====
def send_mail(title, body):
    """基础邮件发送，返回 True/False"""
    log.debug('开始发送邮件')

    mail_host = os.environ.get("MAIL_HOST", "smtp.qq.com")
    mail_port = int(os.environ.get("MAIL_PORT", "465"))
    mail_user = os.environ.get("MAIL_USER", "657192583@qq.com")
    mail_pass = os.environ.get("MAIL_PASS", "bemuiuigmrewbbbc")
    receivers = os.environ.get("MAIL_RECEIVERS", "cs16fox@vip.qq.com").split(",")

    message = MIMEText(body, "plain", "utf-8")
    message["From"] = f"Ntzy <{mail_user}>"
    message["To"] = "Ntzy"
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


def send_mail_with_retry(title, body, ticket_timeout_str, retry_window=25):
    """发送邮件，失败后在 retry_window 分钟内自动重试

    参数:
        title, body: 邮件标题和正文
        ticket_timeout_str: 工单超时时间，用于超时后停止重试
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

        if send_mail(title, body):
            return True

        # 检查工单是否已超时，超时则不再重试
        if ticket_timeout_str:
            try:
                target = datetime.strptime(ticket_timeout_str, "%Y-%m-%d %H:%M:%S")
                now = datetime.now(china_tz).replace(tzinfo=None)
                if now >= target:
                    log.info('工单已超时，停止重试')
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


# ===== 已调度的工单集合（防止重复调度） =====
_scheduled_lock = threading.Lock()
_scheduled_tickets = {}  # {workorderNo: feedBackTime} 记录已调度工单及超时时间


def _cleanup_expired_scheduled():
    """清理已超时的工单记录，防止集合无限增长"""
    china_tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(china_tz).replace(tzinfo=None)
    with _scheduled_lock:
        expired = []
        for no, fb_time in _scheduled_tickets.items():
            try:
                if datetime.strptime(fb_time, "%Y-%m-%d %H:%M:%S") <= now:
                    expired.append(no)
            except (ValueError, TypeError):
                expired.append(no)
        for no in expired:
            del _scheduled_tickets[no]
        if expired:
            log.debug(f'清理 {len(expired)} 条已超时的工单调度记录')


def _countdown_and_send(ticket_info):
    """倒计时线程：等待至超时前 30 分钟，然后发送邮件（含重试）

    此函数由 threading.Thread 调用，独立运行。
    ticket_info 包含工单详细信息和计算好的等待秒数。
    """
    workorder_no = ticket_info['workorderNo']
    wait_seconds = ticket_info['_wait_seconds']
    feed_back_time = ticket_info['feedBackTime']
    description = ticket_info.get('workorderDescription', '')
    accept_name = ticket_info.get('acceptName', '')

    log.info(f'工单 [{workorder_no}] 倒计时 {wait_seconds:.0f} 秒后发送提醒')

    if wait_seconds > 0:
        time.sleep(wait_seconds)

    # 醒来后确认工单状态
    china_tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(china_tz).replace(tzinfo=None)
    try:
        target_time = datetime.strptime(feed_back_time, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        log.error(f'工单 [{workorder_no}] 超时时间解析失败，跳过发送')
        return

    if now >= target_time:
        log.info(f'工单 [{workorder_no}] 已超时，跳过发送')
        return

    # 构造邮件正文
    current_time_str = now.strftime('%Y-%m-%d %H:%M:%S')
    body = f"{current_time_str}\n你有1条周期性工单即将超时，请及时处理！\n\n"
    body += f"编号：{workorder_no}\n"
    body += f"{description}\n"
    body += f"接单人：{accept_name}\n"
    body += f"超时时间：{feed_back_time}\n\n"
    body += "（此邮件由系统自动发送）"

    # 发送邮件（25 分钟重试窗口）
    success = send_mail_with_retry("周期性工单即将超时", body, feed_back_time, retry_window=25)
    if success:
        log.info(f'工单 [{workorder_no}] 提醒邮件发送成功')
    else:
        log.error(f'工单 [{workorder_no}] 提醒邮件发送失败（已达重试上限或工单已超时）')


def _dispatch_countdown(ticket_info):
    """为单个工单启动倒计时线程"""
    thread = threading.Thread(target=_countdown_and_send, args=(ticket_info,), daemon=True)
    thread.start()
    return thread


# ===== 工单查询循环 =====
def tkpm_query(tkpm):
    ALERT_WINDOW = 40       # 检测窗口：超时前 40 分钟内触发调度
    COOLDOWN_HAS = 1800     # 有工单时冷却 30 分钟
    COOLDOWN_NONE = 300     # 无工单时冷却 5 分钟

    while True:
        try:
            log.debug('开始工单查询')
            tkpm.query()

            # 等待查询完成（带 60 秒超时保护）
            wait_start = time.time()
            while tkpm.content is None:
                if time.time() - wait_start > 60:
                    raise TimeoutError('查询完成但 content 仍为 None')
                time.sleep(0.5)

            # 清理已过期的调度记录
            _cleanup_expired_scheduled()

            # 查询 40 分钟内即将超时的工单
            upcoming = tkpm.query_upcoming(within_minutes=ALERT_WINDOW)

            if not upcoming:
                log.debug(f'无 {ALERT_WINDOW} 分钟内即将超时的工单，等待 5 分钟')
                time.sleep(COOLDOWN_NONE)
                continue

            # 过滤出尚未调度的工单
            new_tickets = []
            with _scheduled_lock:
                for t in upcoming:
                    if t['workorderNo'] not in _scheduled_tickets:
                        new_tickets.append(t)
                        _scheduled_tickets[t['workorderNo']] = t['feedBackTime']

            if not new_tickets:
                log.debug('所有即将超时的工单均已调度过，等待 5 分钟')
                time.sleep(COOLDOWN_NONE)
                continue

            log.info(f'发现 {len(new_tickets)} 条新工单即将超时，启动倒计时线程')

            # 对每条新工单计算等待时间并启动线程
            china_tz = pytz.timezone('Asia/Shanghai')
            for t in new_tickets:
                try:
                    target_time = datetime.strptime(t['feedBackTime'], "%Y-%m-%d %H:%M:%S")
                    alert_time = target_time - timedelta(minutes=30)
                    now = datetime.now(china_tz).replace(tzinfo=None)
                    wait_seconds = max(0, (alert_time - now).total_seconds())
                    t['_wait_seconds'] = wait_seconds
                except (ValueError, TypeError):
                    t['_wait_seconds'] = 0

                _dispatch_countdown(t)

            log.info(f'已调度 {len(new_tickets)} 条工单的倒计时，冷却 30 分钟')
            time.sleep(COOLDOWN_HAS)

        except TimeoutError as e:
            log.error(f'等待超时: {e}')
            time.sleep(60)
        except Exception as e:
            log.error(f'发生异常 [{type(e).__name__}]: {e}')
            time.sleep(60)


if __name__ == '__main__':
    log.info('=' * 50)
    log.info('工单超时邮件提醒 启动')
    log.info('=' * 50)
    log.info('检测窗口: 超时前 40 分钟 | 发送时机: 超时前 30 分钟 | SMTP 重试窗口: 25 分钟')
    tkpm = TicketTimeoutPM()
    tkpm_query(tkpm)
