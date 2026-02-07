#!/bin/bash

echo "=========================================="
echo "🎬 抖音弹幕实时监控 Web 服务器"
echo "=========================================="
echo ""

# 安装依赖
echo "📦 安装依赖..."
python3 -m pip install flask flask-socketio flask-cors simple-websocket websocket-client pyexecjs protobuf --break-system-packages --quiet

if [ $? -eq 0 ]; then
    echo "✅ 依赖安装完成"
else
    echo "❌ 依赖安装失败"
    exit 1
fi

echo ""
echo "🚀 启动服务器..."
echo "📡 服务器地址: http://localhost:8080"
echo "💡 按 Ctrl+C 停止服务器"
echo ""
echo "=========================================="
echo ""

# 启动服务器
python3 web_server.py
