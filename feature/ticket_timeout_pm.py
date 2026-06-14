# ticket_timeout_pm.py

import threading
from lib.ticket import Ticket


class TicketTimeoutPM:
    def __init__(self):
        self.tk = Ticket()
        self.content = None
        self.lock = threading.Lock()

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
