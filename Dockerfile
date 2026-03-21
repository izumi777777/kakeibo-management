# =============================================
# Dockerfile - AWS App Runner 対応
# =============================================
FROM python:3.12-slim

WORKDIR /app

# 依存関係インストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリコードをコピー
COPY . .

# 環境変数（App Runner / Secrets Manager で上書き）
ENV FLASK_ENV=production
ENV PORT=8080

EXPOSE 8080

# Gunicorn で起動（App Runner 推奨）
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "2", "--timeout", "120", "app:app"]