#!/usr/bin/env zsh
cd "$(dirname "$0")"
echo "🇲🇽 正在启动 FastMoss 墨西哥私有化选品智能体中枢..."
PYTHONNOUSERSITE=1 python3 server.py 8688
