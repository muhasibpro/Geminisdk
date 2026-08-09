#!/usr/bin/env bash
# Antigravity (agy) grafik chat interfeysini ishga tushiradi va brauzerni ochadi.
cd "$HOME/Desktop/Geminisdk" || exit 1
exec .venv/bin/python agy_app.py
