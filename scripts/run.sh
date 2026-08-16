#!/bin/bash
# AI 新闻流水线定时入口（launchd 调用）
cd /Users/luolingli/Documents/work/ai-news-douyin || exit 1
exec flock -n /tmp/ai-news-douyin.lock .venv/bin/python main.py run --limit 3 >> data/logs/launchd.log 2>&1
