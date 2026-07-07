# run.py
# 主入口：只负责加载配置 + 注册回调 + 启动子模块

import signal, sys, threading
from lib.logger import log
from lib.mailer import send_mail_with_retry
from lib.email_config import get_config
from feature.ticket_timeout_pm import TicketTimeoutPM
from feature.person_location_monitor import PersonLocationMonitor


# ===== 信号处理（优雅退出） =====
def handle_exit(signum, frame):
    log.info('收到退出信号，程序关闭中...')
    sys.exit(0)


signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)


# ===== 主逻辑 =====
def main():
    config = get_config()

    def on_send(title, body, timeout_list):
        send_mail_with_retry(config, title, body, timeout_list, retry_window=25)

    def on_location_alert(title, body):
        # 定位告警：简单发送，不重试、无超时列表
        send_mail_with_retry(config, title, body, retry_window=0)

    # 工单超时监控（守护线程）
    tkpm = TicketTimeoutPM(send_callback=on_send)
    t = threading.Thread(target=tkpm.run, daemon=True)
    t.start()

    # 人员定位监控（主线程）
    monitor = PersonLocationMonitor(send_callback=on_location_alert)
    monitor.run()  # 阻塞


if __name__ == '__main__':
    log.info('=' * 50)
    log.info('工单超时邮件提醒 启动')
    log.info('=' * 50)
    log.info('检测窗口: 超时前 40 分钟 | 发送时机: 超时前 30 分钟 | SMTP 重试窗口: 25 分钟')
    main()
