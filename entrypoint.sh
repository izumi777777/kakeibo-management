#!/bin/bash
# 1. ワーカーが起動する前に 1 回だけ初期化を実行
python3 init_db.py

# 2. Gunicorn を起動
exec gunicorn --bind 0.0.0.0:8080 --workers 2 --threads 2 --timeout 120 "app:app"