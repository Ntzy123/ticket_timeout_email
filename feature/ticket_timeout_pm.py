# ticket_timeout_pm.py
# 周期性工单（PM）超时检测子模块
# 负责：查询循环 + 调度防重 + 倒计时线程 + 汇总构建
# 到发送时机时，通过 send_callback 通知主程序发送邮件

import threading, time
from datetime import datetime, timedelta
import pytz
from lib.ticket import Ticket
from lib.logger import log


class TicketTimeoutPM:
    def __init__(self, send_callback=None):
        """初始化

        参数:
            send_callback: callable(title, body, timeout_list)
                当工单到达发送时机时回调，由主程序注册
        """
        self.tk = Ticket()
        self.content = None
        self.lock = threading.Lock()
        self.send_callback = send_callback

        # 已调度的工单集合（防止重复调度）
        self._scheduled_lock = threading.Lock()
        self._scheduled_tickets = {}  # {workorderNo: feedBackTime}

    # ========== 查询接口 ==========

    def query(self):
        with self.lock:
            self.tk.load(".config.json")
            self.content = self.tk.query(time_range="today")

    def query_timeout(self):
        ticket_timeout = {
            'num': '0',
            'data': []
        }
        with self.lock:
            if self.content and self.content.get('msg') == "success":
                ticket_timeout = self.tk.query_timeout()
            return ticket_timeout

    def query_upcoming(self, within_minutes=40):
        """查找 within_minutes 分钟内即将超时的工单"""
        with self.lock:
            if self.content and self.content.get('msg') == "success":
                return self.tk.query_upcoming(within_minutes)
            return []

    # ========== 调度管理 ==========

    def _cleanup_expired_scheduled(self):
        """清理已超时的工单记录，防止集合无限增长"""
        china_tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(china_tz).replace(tzinfo=None)
        with self._scheduled_lock:
            expired = []
            for no, fb_time in self._scheduled_tickets.items():
                try:
                    if datetime.strptime(fb_time, "%Y-%m-%d %H:%M:%S") <= now:
                        expired.append(no)
                except (ValueError, TypeError):
                    expired.append(no)
            for no in expired:
                del self._scheduled_tickets[no]
            if expired:
                log.debug(f'清理 {len(expired)} 条已超时的工单调度记录')

    # ========== 邮件内容构建 ==========

    @staticmethod
    def _build_summary_body(tickets, now_str):
        """将多条工单汇总成邮件正文"""
        lines = [f"{now_str}\n你有 {len(tickets)} 条周期性工单即将超时，请及时处理！\n"]
        lines.append("=" * 50)
        for item in tickets:
            lines.append("")
            lines.append(f"编号：{item['workorderNo']}")
            lines.append(f"{item.get('workorderDescription', '')}")
            lines.append(f"接单人：{item.get('acceptName', '')}")
            lines.append(f"超时时间：{item['feedBackTime']}")
        lines.append("")
        lines.append("=" * 50)
        lines.append("（此邮件由系统自动发送）")
        return "\n".join(lines)

    # ========== 倒计时 + 发送 ==========

    def _batch_countdown_and_send(self, new_tickets, wait_seconds):
        """批量倒计时线程：等待到最早工单的 30 分钟节点，然后重新查询并回调发送

        参数:
            new_tickets: 本次调度的新工单列表（含完整信息）
            wait_seconds: 需要等待的秒数（到最早工单的 30 分钟节点）
        """
        log.info(f'批量倒计时，等待 {wait_seconds:.0f} 秒后汇总发送（共 {len(new_tickets)} 条工单）')

        if wait_seconds > 0:
            slept = 0
            chunk = 10
            while slept < wait_seconds:
                time.sleep(min(chunk, wait_seconds - slept))
                slept += min(chunk, wait_seconds - slept)

        # 倒计时结束，重新查询 API，获取当前处于 30 分钟窗口内的所有工单
        log.info('倒计时结束，重新查询工单数据')
        try:
            self.query()
            wait_start = time.time()
            while self.content is None:
                if time.time() - wait_start > 60:
                    raise TimeoutError('查询完成但 content 仍为 None')
                time.sleep(0.5)

            alerting = self.query_timeout()
            alert_items = alerting.get('data', [])
        except Exception as e:
            log.error(f'倒计时后重新查询工单失败: {e}')
            alert_items = new_tickets

        if not alert_items:
            log.info('倒计时后查询无处于 30 分钟窗口的工单，可能已处理完毕')
            return

        # 汇总成一条邮件发送
        china_tz = pytz.timezone('Asia/Shanghai')
        now_str = datetime.now(china_tz).strftime('%Y-%m-%d %H:%M:%S')
        body = self._build_summary_body(alert_items, now_str)
        timeout_list = [item['feedBackTime'] for item in alert_items]

        log.info(f'汇总发送 {len(alert_items)} 条工单提醒邮件')
        if self.send_callback:
            self.send_callback(
                f"周期性工单即将超时（共 {len(alert_items)} 条）",
                body,
                timeout_list
            )
        else:
            log.error('未设置 send_callback，无法发送邮件')

    # ========== 主循环 ==========

    def run(self):
        """主查询循环（阻塞运行）"""
        ALERT_WINDOW = 40       # 检测窗口：超时前 40 分钟内触发调度
        COOLDOWN_HAS = 1800     # 有工单时冷却 30 分钟
        COOLDOWN_NONE = 300     # 无工单时冷却 5 分钟

        while True:
            try:
                log.debug('开始工单查询')
                self.query()

                # 等待查询完成（带 60 秒超时保护）
                wait_start = time.time()
                while self.content is None:
                    if time.time() - wait_start > 60:
                        raise TimeoutError('查询完成但 content 仍为 None')
                    time.sleep(0.5)

                # 清理已过期的调度记录
                self._cleanup_expired_scheduled()

                # 查询 40 分钟内即将超时的工单
                upcoming = self.query_upcoming(within_minutes=ALERT_WINDOW)

                if not upcoming:
                    log.debug(f'无 {ALERT_WINDOW} 分钟内即将超时的工单，等待 5 分钟')
                    time.sleep(COOLDOWN_NONE)
                    continue

                # 过滤出尚未调度的工单
                new_tickets = []
                with self._scheduled_lock:
                    for t in upcoming:
                        if t['workorderNo'] not in self._scheduled_tickets:
                            new_tickets.append(t)
                            self._scheduled_tickets[t['workorderNo']] = t['feedBackTime']

                if not new_tickets:
                    log.debug('所有即将超时的工单均已调度过，等待 5 分钟')
                    time.sleep(COOLDOWN_NONE)
                    continue

                log.info(f'发现 {len(new_tickets)} 条新工单即将超时')

                # 计算到最早工单 30 分钟节点的等待时间
                china_tz = pytz.timezone('Asia/Shanghai')
                now = datetime.now(china_tz).replace(tzinfo=None)
                earliest_wait = None
                for t in new_tickets:
                    try:
                        target_time = datetime.strptime(t['feedBackTime'], "%Y-%m-%d %H:%M:%S")
                        alert_time = target_time - timedelta(minutes=30)
                        wait = max(0, (alert_time - now).total_seconds())
                        if earliest_wait is None or wait < earliest_wait:
                            earliest_wait = wait
                    except (ValueError, TypeError):
                        pass

                if earliest_wait is None:
                    earliest_wait = 0

                # 启动一个批量倒计时线程
                thread = threading.Thread(
                    target=self._batch_countdown_and_send,
                    args=(new_tickets, earliest_wait),
                    daemon=True
                )
                thread.start()

                log.info(f'已调度 {len(new_tickets)} 条工单的批量倒计时（等待 {earliest_wait:.0f} 秒），冷却 30 分钟')
                time.sleep(COOLDOWN_HAS)

            except TimeoutError as e:
                log.error(f'等待超时: {e}')
                time.sleep(60)
            except Exception as e:
                log.error(f'发生异常 [{type(e).__name__}]: {e}')
                time.sleep(60)
