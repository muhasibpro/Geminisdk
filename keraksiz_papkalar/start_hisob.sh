#!/usr/bin/env bash
# MUHASIB HISOB (8778-port) dasturini ishga tushirish skripti
cd "$(dirname "$0")" || exit 1

PID=$(lsof -ti :8778)

if [ -n "$PID" ]; then
  if [ "$1" == "--restart" ] || [ "$1" == "-r" ]; then
    echo "🔄 Port 8778 da ishlayotgan jarayon (PID $PID) to'xtatilmoqda..."
    kill -9 $PID 2>/dev/null
    sleep 1
  else
    echo "✅ MUHASIB HISOB allaqachon 8778-portda ishlab turibdi! (PID: $PID)"
    echo "🌐 Brauzerda oching: http://localhost:8778"
    echo "💡 Qayta ishga tushirish uchun: ./start_hisob.sh --restart"
    exit 0
  fi
fi

echo "🚀 MUHASIB HISOB 8778-portda ishga tushmoqda..."
exec .venv/bin/python hisob_app.py
