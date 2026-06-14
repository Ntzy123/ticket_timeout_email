# ticket.py

import json, requests
from datetime import date, datetime, timedelta
import pytz


class Ticket:

    # 加载配置文件
    def load(self, filename):
        with open(filename, 'r', encoding='utf-8') as file:
            config = json.load(file)
            self.url = config['url']
            self.headers = config['headers']
            self.json = config['json']

    # 查询工单
    def query(self, serach=None, status=None, fm_type=None, ticket_type=None, time_range=None):
        input_param = [serach, status, fm_type, ticket_type, time_range]
        target_param = ["workorderTitle", "workorderStatus", "fmWoType", "workOrderTypeNoList", ["date1", "startTime", "endTime"]]
        workorderTitle = ""
        for i, key in enumerate(target_param):
            if i == 0 and input_param[i] is not None:
                workorderTitle = input_param[i]
            elif i == 1 and input_param[i] is not None:
                self.json[key] = input_param[i]
            elif i == 3 and input_param[i] is not None:
                self.json[key] = input_param[i]
            elif i == 4 and input_param[i] is not None:
                if time_range == "today":
                    time_range = [str(date.today() - timedelta(days=1)), str(date.today())]
                self.json[key[0]] = time_range
                start = f"{time_range[0]} 00:00:00"
                end = f"{time_range[1]} 23:59:59"
                self.json[key[1]] = start
                self.json[key[2]] = end
            elif input_param[i] is not None:
                self.json[key] = input_param[i]

        # 发起 POST 请求（带 30 秒超时）
        try:
            res = requests.post(self.url, json=self.json, headers=self.headers, timeout=30)
            res.raise_for_status()
            self.data = res.json()
        except requests.exceptions.Timeout:
            print(f"[ERROR] HTTP 请求超时: {self.url}")
            raise
        except requests.exceptions.ConnectionError:
            print(f"[ERROR] 网络连接失败: {self.url}")
            raise
        except requests.exceptions.HTTPError as e:
            print(f"[ERROR] HTTP 错误 [{res.status_code}]: {e}")
            raise
        except json.JSONDecodeError:
            print(f"[ERROR] 响应不是合法 JSON: {res.status_code} {res.text[:200]}")
            raise

        # 处理返回数据
        config = {
            'msg': self.data.get('msg', ''),
            'data': []
        }
        if config['msg'] != "success":
            return config

        for record in self.data.get('data', {}).get('records', []):
            data = {
                "workorderNo": record.get('workorderNo'),
                "workorderTitle": record.get('workorderTitle'),
                "workorderStatusName": record.get('workorderStatusName'),
                "acceptName": record.get('acceptName'),
                "feedBackTime": record.get('feedBackTime')
            }
            config['data'].append(data)
        return config

    # 查询超时工单（超时前 30 分钟窗口）
    def query_timeout(self):
        timeout_ticket = {
            'num': '',
            'data': []
        }
        records = self.data.get('data', {}).get('records', [])
        for record in records:
            self._timeout_pm(record, timeout_ticket)
        timeout_ticket['num'] = len(timeout_ticket['data'])
        return timeout_ticket

    # PM 工单超时提醒（超时前 30 分钟）
    def _timeout_pm(self, record, timeout_ticket):
        china_tz = pytz.timezone('Asia/Shanghai')
        current_time = datetime.now(china_tz).replace(tzinfo=None)

        feed_back_time = record.get('feedBackTime')
        if not feed_back_time:
            return
        try:
            target_time = datetime.strptime(feed_back_time, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return

        alert_time = target_time - timedelta(minutes=30)
        if target_time > current_time >= alert_time:
            data = {
                'workorderNo': record.get('workorderNo'),
                'workorderDescription': record.get('workorderDescription'),
                'acceptName': record.get('acceptName'),
                'feedBackTime': record.get('feedBackTime')
            }
            timeout_ticket['data'].append(data)

    # 查询 within_minutes 分钟内即将超时的工单（用于提前调度倒计时线程）
    def query_upcoming(self, within_minutes=40):
        """查找在 within_minutes 分钟内即将超时的工单（含详细信息）"""
        china_tz = pytz.timezone('Asia/Shanghai')
        current_time = datetime.now(china_tz).replace(tzinfo=None)

        upcoming = []
        records = self.data.get('data', {}).get('records', [])
        for record in records:
            feed_back_time = record.get('feedBackTime')
            if not feed_back_time:
                continue
            try:
                target_time = datetime.strptime(feed_back_time, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                continue

            # 只关心尚未超时的工单
            diff_minutes = (target_time - current_time).total_seconds() / 60
            if 0 <= diff_minutes <= within_minutes:
                upcoming.append({
                    'workorderNo': record.get('workorderNo'),
                    'workorderDescription': record.get('workorderDescription'),
                    'acceptName': record.get('acceptName'),
                    'feedBackTime': feed_back_time,
                    'diff_minutes': diff_minutes
                })
        return upcoming
