# person_location_monitor.py
# 夜班人员靠近项目监控子模块
# 0:00-6:00 检查定位，满足条件时每小时最多发一封告警邮件

import time
from datetime import datetime
import pytz
from lib.person_locator import get_latest, find_alert_records, format_distance
from lib.logger import log


class PersonLocationMonitor:
    def __init__(self, send_callback=None, base_url='https://kyrian.asia'):
        self.send_callback = send_callback
        self.base_url = base_url
        self._last_hour_bucket = None  # e.g. '2026-07-07-01'

    @staticmethod
    def _hour_bucket(dt):
        return dt.strftime('%Y-%m-%d-%H')

    def _build_body(self, record, now_str):
        name = record.get('name', '未知')
        dist = float(record.get('distance_m', 0))
        dist_str = format_distance(dist)
        lines = [
            '=== 夜班人员靠近项目告警 ===',
            '',
            f'告警时间：{now_str}',
            '',
            f'人员：{name}',
            f'状态：在线',
            f'距离：{dist_str}',
            '',
            '当前设备在线且在距离项目 3 km 内，请注意关注！',
            '',
            '（此邮件由系统在 0:00-6:00 时段自动发送，每小时最多一封）',
        ]
        return '\n'.join(lines)

    def run(self):
        log.info('人员定位监控启动（0:00-6:00 生效，每小时最多一封）')
        china_tz = pytz.timezone('Asia/Shanghai')

        while True:
            try:
                now = datetime.now(china_tz)
                hour = now.hour

                # 只在 0:00-6:00 工作
                if hour >= 6:
                    time.sleep(300)
                    continue

                records = get_latest(self.base_url)
                alerts = find_alert_records(records)

                if alerts:
                    bucket = self._hour_bucket(now)
                    a = alerts[0]
                    dist_str = format_distance(float(a.get('distance_m', 0)))
                    if bucket != self._last_hour_bucket:
                        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
                        body = self._build_body(a, now_str)
                        log.info(f'定位告警触发：{a["name"]} 距项目 {dist_str}')
                        if self.send_callback:
                            self.send_callback('夜班人员靠近项目告警', body)
                        self._last_hour_bucket = bucket
                    else:
                        log.debug(f'本小时({bucket})已发过告警，跳过')
                else:
                    log.debug(f'定位检查完毕，无满足告警条件的人员')

                time.sleep(60)

            except Exception as e:
                log.error(f'定位监控异常 [{type(e).__name__}]: {e}')
                time.sleep(60)
