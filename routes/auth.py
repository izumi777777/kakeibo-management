"""認証ルート - Firestore 対応版"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

from firebase_config import fs_db, FirestoreUser

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def _find_user_by_username(username: str):
    """
    Firestore の users コレクションから username フィールドで検索する。
    ドキュメントID = username の旧形式と、.add() で追加した新形式の両方に対応。
    """
    # ① フィールド検索（admin.py の add() で追加したユーザー向け）
    docs = fs_db.collection('users') \
                .where('username', '==', username) \
                .limit(1).get()
    if docs:
        d       = docs[0].to_dict()
        d['id'] = docs[0].id   # Firestore ドキュメント ID を id として付与
        return d

    # ② ドキュメントID検索（seed で username = doc_id にした旧形式向け）
    doc = fs_db.collection('users').document(username).get()
    if doc.exists:
        d       = doc.to_dict()
        d['id'] = doc.id
        # username フィールドが未設定のデータに補完
        if 'username' not in d:
            d['username'] = username
        return d

    return None


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not fs_db:
            flash('システムエラー: データベースに接続できません。', 'danger')
            return render_template('login.html')

        try:
            user_data = _find_user_by_username(username)

            if user_data and check_password_hash(
                user_data.get('password_hash', ''), password
            ):
                user_obj = FirestoreUser(user_data)
                login_user(user_obj, remember=True)
                flash(f'おかえりなさい、{user_obj.display_name}さん！', 'success')
                next_page = request.args.get('next')
                return redirect(next_page or url_for('dashboard.index'))

            flash('ユーザー名またはパスワードが正しくありません。', 'danger')

        except Exception as e:
            print(f"Login error: {e}")
            import traceback; traceback.print_exc()
            flash('ログイン処理中にエラーが発生しました。', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('ログアウトしました。', 'info')
    return redirect(url_for('auth.login'))