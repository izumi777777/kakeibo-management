"""
家計管理アプリ - メインアプリケーション
Flask + Firestore
"""

import os
import boto3
from flask import Flask, redirect, url_for
from flask_login import LoginManager
from models import db  # SQLAlchemy は models.py の定義用に残す
from dotenv import load_dotenv


load_dotenv()

# Firestore クライアントと FirestoreUser を firebase_config から取得
from firebase_config import fs_db, FirestoreUser


def create_app():
    app = Flask(__name__)

    # --- 設定 ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 'sqlite:///kakeibo.db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # --- SQLAlchemy 初期化（models.py のテーブル定義用） ---
    db.init_app(app)

    # --- Flask-Login 設定 ---
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'ログインが必要です。'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id: str):
        """
        セッションに保存された user_id（= Firestore ドキュメントID）で
        ユーザーを復元する。

        ① ドキュメントIDで直接 get()
        ② 見つからなければ username フィールドで検索（旧データ互換）
        """
        if not fs_db:
            return None
        try:
            # ① ドキュメントIDで直接取得（admin.py で追加した新ユーザー向け）
            doc = fs_db.collection('users').document(user_id).get()
            if doc.exists:
                d       = doc.to_dict()
                d['id'] = doc.id
                return FirestoreUser(d)

            # ② username フィールドで検索（seed でドキュメントIDがusernameでない場合）
            docs = fs_db.collection('users') \
                        .where('username', '==', user_id) \
                        .limit(1).get()
            if docs:
                d       = docs[0].to_dict()
                d['id'] = docs[0].id
                return FirestoreUser(d)

        except Exception as e:
            print(f"user_loader error: {e}")
        return None

    # --- Blueprint 登録 ---
    from routes.auth         import auth_bp
    from routes.dashboard    import dashboard_bp
    from routes.transactions import transactions_bp
    from routes.memo         import memo_bp
    from routes.ai_advice    import ai_bp
    from routes.cycle        import cycle_bp
    from routes.admin        import admin_bp
    from routes.ops          import ops_bp
    from routes.receipts     import receipts_bp
    from routes.export       import export_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(memo_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(cycle_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(ops_bp)
    app.register_blueprint(receipts_bp)
    app.register_blueprint(export_bp)

    # --- DB 初期化 ---
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"[db] create_all skipped (already exists): {e}")
        _seed_demo_users()

    return app


def _seed_demo_users():
    """Firestore にデモユーザーを作成（初回のみ）"""
    if not fs_db:
        print("Firestore not initialized, skipping seed.")
        return

    from werkzeug.security import generate_password_hash
    from google.cloud import firestore as _fs

    try:
        # 家族グループ
        family_ref = fs_db.collection('families').document('tanaka_family')
        if not family_ref.get().exists:
            family_ref.set({'name': '田中家', 'created_at': _fs.SERVER_TIMESTAMP})

        # デモユーザー（ドキュメントID = username にして旧 user_loader と互換性を保つ）
        demo_users = [
            {'username': 'taro',   'display_name': '太郎（夫）', 'email': 'taro@example.com',   'password': 'demo1234'},
            {'username': 'hanako', 'display_name': '花子（妻）', 'email': 'hanako@example.com', 'password': 'demo1234'},
        ]
        for u in demo_users:
            # ドキュメントID = username で保存
            ref = fs_db.collection('users').document(u['username'])
            if not ref.get().exists:
                ref.set({
                    'username':      u['username'],
                    'display_name':  u['display_name'],
                    'email':         u['email'],
                    'password_hash': generate_password_hash(u['password']),
                    'family_id':     'tanaka_family',
                    # ★ id フィールドも明示的に保存しておく
                    'id':            u['username'],
                })
        print("Firestore demo seeding completed.")
    except Exception as e:
        print(f"Firestore seeding error: {e}")


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)