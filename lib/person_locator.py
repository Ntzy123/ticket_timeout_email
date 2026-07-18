# person_locator.py
# 人员定位 API 封装

import requests
from lib.logger import log


def get_latest(base_url):
    """请求定位 API，返回 records 列表，失败时返回空列表"""
    url = f"{base_url.rstrip('/')}/api/person-device-status/location-latest"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get('records', [])
    except Exception as e:
        log.error(f'定位 API 请求失败: {e}')
        return []


def find_alert_records(records):
    """返回满足 distance_m <= 3000 且 status == '1' 的记录"""
    return [
        r for r in records
        if r.get('status') == '1' and float(r.get('distance_m', 99999)) <= 3000
    ]


def format_distance(distance_m):
    """距离格式化：<1000m 显示整数米，>=1000m 显示 xx.xx km"""
    if distance_m < 1000:
        return f"{int(distance_m)} m"
    return f"{distance_m / 1000:.2f} km"


def sort_records(records):
    """
    对所有记录排序，优先级：
    1. 在线且有定位（distance_m > 0），按距离升序
    2. 在线但无定位（distance_m == 0）
    3. 离线
    """
    def _key(r):
        is_online = r.get('status') == '1'
        dist = float(r.get('distance_m', 0))
        if not is_online:
            return (1, 0, 0)       # 离线 → 最后
        if dist == 0:
            return (0, 2, 0)       # 在线无定位 → 中间
        return (0, 1, dist)        # 在线有定位 → 最前，按距离升序
    return sorted(records, key=_key)
