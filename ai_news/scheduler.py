"""定时循环调度（本地无人值守模式）"""
from __future__ import annotations

import logging
import signal
import time

log = logging.getLogger("ai_news.scheduler")


class LoopRunner:
    def __init__(self, pipeline, interval: int = 3600, limit: int = 5, dry_run: bool = False, skip_llm: bool = False):
        self.pipeline = pipeline
        self.interval = max(60, int(interval))
        self.limit = limit
        self.dry_run = dry_run
        self.skip_llm = skip_llm
        self._stop = False
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)

    def _on_signal(self, *args) -> None:
        log.info("收到停止信号，当前轮结束后退出")
        self._stop = True

    def run_forever(self) -> None:
        log.info("定时任务启动：每 %d 秒运行一轮", self.interval)
        while not self._stop:
            started = time.time()
            try:
                stats = self.pipeline.run(limit=self.limit, dry_run=self.dry_run, skip_llm=self.skip_llm)
                log.info("本轮完成: %s", stats)
            except Exception as e:
                log.error("本轮失败: %s", e)
            elapsed = time.time() - started
            if self._stop:
                break
            time.sleep(max(1, self.interval - elapsed))
        log.info("定时任务退出")
