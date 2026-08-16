#!/bin/bash
# 安装并启动定时任务（第一次执行后，每 4 小时自动跑流水线）
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_SRC="$DIR/scripts/com.luolingli.ai-news-douyin.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.luolingli.ai-news-douyin.plist"
mkdir -p "$HOME/Library/LaunchAgents" data/logs
cp "$PLIST_SRC" "$PLIST_DST"
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
echo "已安装: $PLIST_DST"
launchctl list | grep ai-news-douyin
