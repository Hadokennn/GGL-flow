#!/bin/bash
# debug.sh - 启动辅助服务，LangGraph 用 VSCode 调试

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

mkdir -p logs

# echo "Starting Gateway API..."
# (cd backend && uv run uvicorn src.gateway.app:app --host 0.0.0.0 --port 8001 --reload > ../logs/gateway.log 2>&1) &
# GATEWAY_PID=$!

echo "Starting Frontend..."
(cd frontend && pnpm run dev > ../logs/frontend.log 2>&1) &
FRONTEND_PID=$!

echo "Starting Nginx..."
NGINX_PID=""
if ! command -v nginx &>/dev/null; then
    echo "✗ nginx not found. Install with: brew install nginx"
else
    nginx -g 'daemon off;' -c "$REPO_ROOT/docker/nginx/nginx.local.conf" -p "$REPO_ROOT" > logs/nginx.log 2>&1 &
    NGINX_PID=$!
fi

echo ""
echo "=========================================="
echo "  辅助服务已启动"
echo "=========================================="
echo ""
echo "  Gateway API: http://localhost:8001"
echo "  Frontend:    http://localhost:3000"
echo "  Nginx:       http://localhost:2026"
echo ""
echo "  ⚠️  请在 VSCode 中启动 'Python: LangGraph Dev Server'"
echo ""
echo "  日志文件:"
echo "    - logs/gateway.log"
echo "    - logs/frontend.log"
echo "    - logs/nginx.log"
echo ""
echo "  按 Ctrl+C 停止辅助服务"

# 清理函数
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $GATEWAY_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    [ -n "$NGINX_PID" ] && kill $NGINX_PID 2>/dev/null || true
    exit 0
}

trap cleanup INT TERM
wait