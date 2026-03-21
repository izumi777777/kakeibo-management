"""
家計管理アプリ - メインアプリケーション
Flask + SQLite (Firestore移行対応構造)
"""

from flask import Flask, redirect, url_for, session
from flask_login import LoginManager
from models import db, User
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.transactions import transactions_bp
from routes.memo import memo_bp
from routes.ai_advice import ai_bp
from routes.cycle import cycle_bp
from routes.admin import admin_bp
from routes.ops import ops_bp
import os

def create_app():
    app = Flask(__name__)
    
    # --- 設定 ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 'sqlite:///kakeibo.db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Anthropic API Key
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
        return User.query.get(int(user_id))

    # --- Blueprint 登録 ---
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(memo_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(cycle_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(ops_bp)

    # --- DB初期化 ---
    with app.app_context():
        db.create_all()
        _seed_demo_users()

    return app


def _seed_demo_users():
    """デモユーザーを作成（本番ではFirestore管理に切り替え）"""
    from models import User, Family
    from werkzeug.security import generate_password_hash

    # 家族グループがなければ作成
    family = Family.query.first()
    if not family:
        family = Family(name="田中家")
        db.session.add(family)
        db.session.flush()

    # デモユーザー
    demo_users = [
        {"username": "taro", "display_name": "太郎（夫）", "email": "taro@example.com", "password": "demo1234"},
        {"username": "hanako", "display_name": "花子（妻）", "email": "hanako@example.com", "password": "demo1234"},
    ]
    for u in demo_users:
        if not User.query.filter_by(username=u["username"]).first():
            user = User(
                username=u["username"],
                display_name=u["display_name"],
                email=u["email"],
                password_hash=generate_password_hash(u["password"]),
                family_id=family.id
            )
            db.session.add(user)
    db.session.commit()


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
