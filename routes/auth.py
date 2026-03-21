"""認証ルート - Firestore 連携版"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

# 【修正ポイント】app からではなく、firebase_config から読み込む！
from firebase_config import fs_db, FirestoreUser

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # すでにログイン済みならダッシュボードへ
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not fs_db:
            flash('システムエラー: データベースに接続できません。', 'danger')
            return render_template('login.html')

        try:
            # 1. Firestore からドキュメントを取得 (ドキュメントID = username)
            user_doc = fs_db.collection('users').document(username).get()

            if user_doc.exists:
                user_data = user_doc.to_dict()
                
                # 2. パスワードの照合 (werkzeug のハッシュチェック)
                if check_password_hash(user_data.get('password_hash'), password):
                    # 3. FirestoreUser オブジェクトを作成してログイン
                    user_obj = FirestoreUser(user_data)
                    login_user(user_obj, remember=True)
                    
                    flash(f'おかえりなさい、{user_obj.display_name}さん！', 'success')
                    next_page = request.args.get('next')
                    return redirect(next_page or url_for('dashboard.index'))
            
            # ユーザーが存在しない、またはパスワード不一致
            flash('ユーザー名またはパスワードが正しくありません。', 'danger')

        except Exception as e:
            print(f"Login error: {e}")
            flash('ログイン処理中にエラーが発生しました。', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('ログアウトしました。', 'info')
    return redirect(url_for('auth.login'))