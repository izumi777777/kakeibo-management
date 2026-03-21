"""
家計管理アプリ - メインアプリケーション
Flask + Firestore (ユーザー管理) + SQLite (明細管理)
"""

from flask import Flask, redirect, url_for, session
from flask_login import LoginManager, UserMixin
from models import db  # SQLAlchemy は他テーブル用に残す
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.transactions import transactions_bp
from routes.memo import memo_bp
from routes.ai_advice import ai_bp
from routes.cycle import cycle_bp
from routes.admin import admin_bp
from routes.ops import ops_bp
import os

# --- Firestore 初期設定 ---
from firebase_config import fs_db, FirestoreUser
from google.cloud import firestore
from dotenv import load_dotenv

# .env ファイルを読み込む
load_dotenv()

# インフラエンジニア向け注記: 
# ローカルでは .env に GOOGLE_APPLICATION_CREDENTIALS="firebase-key.json" を設定してください。
fs_db = None
try:
    # クライアントをグローバルに初期化（他モジュールから import fs_db で利用可能にする）
    fs_db = firestore.Client()
except Exception as e:
    print(f"Firestore Client Error: {e}")

# --- Flask-Login 用のユーザーモデルクラス ---
# 他のファイル（auth.pyなど）でも使うため、ここに定義しておきます
# class FirestoreUser(UserMixin):
#     def __init__(self, user_data):
#         self.id = user_data.get('username')
#         self.username = user_data.get('username')
#         self.display_name = user_data.get('display_name')
#         self.email = user_data.get('email')
#         self.password_hash = user_data.get('password_hash')
#         self.family_id = user_data.get('family_id')

def create_app():
    app = Flask(__name__)
    
    # --- 設定 ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 'sqlite:///kakeibo.db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['ANTHROPIC_API_KEY'] = os.environ.get('ANTHROPIC_API_KEY', '')

    # --- 拡張機能の初期化 ---
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'ログインが必要です。'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        """Firestore からユーザーを読み込む"""
        if not fs_db:
            return None
        try:
            doc = fs_db.collection('users').document(user_id).get()
            if doc.exists:
                return FirestoreUser(doc.to_dict())
        except Exception as e:
            print(f"Error loading user from Firestore: {e}")
        return None

    # --- Blueprint 登録 ---
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(memo_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(cycle_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(ops_bp)

    # --- DB/Firestore 初期化 ---
    with app.app_context():
        # SQLite のテーブル作成（明細用などは SQLite を維持）
        db.create_all()
        # Firestore へのデモデータ投入
        _seed_demo_users()

    return app

def _seed_demo_users():
    """Firestore にデモユーザーを作成"""
    if not fs_db:
        print("Firestore not initialized, skipping seed.")
        return

    from werkzeug.security import generate_password_hash

    try:
        # 1. 家族グループの作成
        family_ref = fs_db.collection('families').document('tanaka_family')
        if not family_ref.get().exists:
            family_ref.set({
                'name': '田中家',
                'created_at': firestore.SERVER_TIMESTAMP
            })
            print("Firestore: Family created.")

        # 2. デモユーザーの定義
        demo_users = [
            {"username": "taro", "display_name": "太郎（夫）", "email": "taro@example.com", "password": "demo1234"},
            {"username": "hanako", "display_name": "花子（妻）", "email": "hanako@example.com", "password": "demo1234"},
        ]

        for u in demo_users:
            user_ref = fs_db.collection('users').document(u["username"])
            if not user_ref.get().exists:
                user_ref.set({
                    "username": u["username"],
                    "display_name": u["display_name"],
                    "email": u["email"],
                    "password_hash": generate_password_hash(u["password"]),
                    "family_id": 'tanaka_family'
                })
                print(f"Firestore: User {u['username']} seeded.")
        
        print("Firestore demo seeding completed.")

    except Exception as e:
        print(f"Firestore seeding error: {e}")

# グローバルなアプリインスタンスの作成
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)