# logger.py
# 日志模块（控制台 + 每日文件）

import os, pytz
from datetime import datetime


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
