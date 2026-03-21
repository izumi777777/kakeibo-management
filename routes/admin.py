"""
管理画面ルート - Firestore 対応版
・ユーザー管理（追加・削除・パスワード変更）
・家族グループ名の変更
・家族プロフィール編集（AIプロンプト用）
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

from firebase_config import fs_db
from family_utils import DEFAULT_PROFILE

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ------------------------------------------------------------------ #
# ヘルパー：family_id から家族ドキュメントを取得
# ------------------------------------------------------------------ #

def _get_family(family_id):
    """family_id（int or str）で Firestore の families ドキュメントを返す"""
    try:
        f_id = int(family_id)
    except Exception:
        f_id = family_id

    # まず数値IDで検索
    docs = fs_db.collection('families').where('id', '==', f_id).limit(1).get()
    if docs:
        d       = docs[0].to_dict()
        d['_doc_id'] = docs[0].id   # Firestore ドキュメント ID も保持
        return d

    # フォールバック：ドキュメントIDで直接取得
    doc = fs_db.collection('families').document(str(family_id)).get()
    if doc.exists:
        d = doc.to_dict()
        d['_doc_id'] = doc.id
        return d

    return {'id': family_id, 'name': '不明', 'profile': None, '_doc_id': str(family_id)}


def _get_members(family_id):
    """family_id に属するユーザー一覧を返す（辞書のリスト）"""
    try:
        f_id = int(family_id)
    except Exception:
        f_id = family_id

    docs = fs_db.collection('users').where('family_id', '==', f_id).stream()
    members = []
    for doc in docs:
        d       = doc.to_dict()
        d['id'] = doc.id   # Firestore ドキュメント ID を .id として付与
        members.append(d)
    return members


# ------------------------------------------------------------------ #
# テンプレート用の薄いプロキシクラス
# ------------------------------------------------------------------ #

class _FamilyProxy:
    """辞書を属性アクセスできるようにするラッパー"""
    def __init__(self, d: dict):
        self._d = d

    def __getattr__(self, key):
        return self._d.get(key)


class _MemberProxy:
    """メンバー辞書を属性アクセスできるようにするラッパー"""
    def __init__(self, d: dict):
        self._d = d

    def __getattr__(self, key):
        return self._d.get(key)


# ------------------------------------------------------------------ #
# ルート
# ------------------------------------------------------------------ #

@admin_bp.route('/')
@login_required
def index():
    f_id    = current_user.family_id
    family  = _FamilyProxy(_get_family(f_id))
    members = [_MemberProxy(m) for m in _get_members(f_id)]
    return render_template('admin.html', family=family, members=members)


@admin_bp.route('/user/add', methods=['POST'])
@login_required
def add_user():
    username     = request.form.get('username', '').strip()
    display_name = request.form.get('display_name', '').strip()
    email        = request.form.get('email', '').strip()
    password     = request.form.get('password', '')
    password2    = request.form.get('password2', '')

    if not all([username, display_name, email, password]):
        flash('すべての項目を入力してください。', 'warning')
        return redirect(url_for('admin.index'))
    if password != password2:
        flash('パスワードが一致しません。', 'danger')
        return redirect(url_for('admin.index'))
    if len(password) < 6:
        flash('パスワードは6文字以上にしてください。', 'warning')
        return redirect(url_for('admin.index'))

    # ユーザー名の重複チェック
    dup_user = fs_db.collection('users').where('username', '==', username).limit(1).get()
    if dup_user:
        flash(f'ユーザー名「{username}」はすでに使われています。', 'danger')
        return redirect(url_for('admin.index'))

    # メールの重複チェック
    dup_email = fs_db.collection('users').where('email', '==', email).limit(1).get()
    if dup_email:
        flash(f'メールアドレス「{email}」はすでに使われています。', 'danger')
        return redirect(url_for('admin.index'))

    f_id = current_user.family_id
    try:
        f_id = int(f_id)
    except Exception:
        pass

    fs_db.collection('users').add({
        'username':      username,
        'display_name':  display_name,
        'email':         email,
        'password_hash': generate_password_hash(password),
        'family_id':     f_id,
        'created_at':    datetime.now(),
    })
    flash(f'✅ アカウント「{display_name}（{username}）」を作成しました。', 'success')
    return redirect(url_for('admin.index'))


@admin_bp.route('/user/change-password', methods=['POST'])
@login_required
def change_password():
    current_pw = request.form.get('current_password', '')
    new_pw     = request.form.get('new_password', '')
    new_pw2    = request.form.get('new_password2', '')

    if not check_password_hash(current_user.password_hash, current_pw):
        flash('現在のパスワードが正しくありません。', 'danger')
        return redirect(url_for('admin.index'))
    if new_pw != new_pw2:
        flash('新しいパスワードが一致しません。', 'danger')
        return redirect(url_for('admin.index'))
    if len(new_pw) < 6:
        flash('パスワードは6文字以上にしてください。', 'warning')
        return redirect(url_for('admin.index'))

    # current_user の Firestore ドキュメントを更新
    user_ref = fs_db.collection('users').document(str(current_user.id))
    user_ref.update({'password_hash': generate_password_hash(new_pw)})
    flash('✅ パスワードを変更しました。', 'success')
    return redirect(url_for('admin.index'))


@admin_bp.route('/user/delete/<user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if str(user_id) == str(current_user.id):
        flash('自分自身は削除できません。', 'warning')
        return redirect(url_for('admin.index'))

    ref = fs_db.collection('users').document(str(user_id))
    doc = ref.get()
    if not doc.exists:
        flash('ユーザーが見つかりません。', 'danger')
        return redirect(url_for('admin.index'))

    display_name = doc.to_dict().get('display_name', user_id)
    ref.delete()
    flash(f'ユーザー「{display_name}」を削除しました。', 'info')
    return redirect(url_for('admin.index'))


@admin_bp.route('/family/update', methods=['POST'])
@login_required
def update_family():
    name = request.form.get('family_name', '').strip()
    if not name:
        flash('家族名を入力してください。', 'warning')
        return redirect(url_for('admin.index'))

    family_data = _get_family(current_user.family_id)
    doc_id      = family_data.get('_doc_id', str(current_user.family_id))
    fs_db.collection('families').document(doc_id).update({'name': name})
    flash(f'✅ 家族名を「{name}」に変更しました。', 'success')
    return redirect(url_for('admin.index'))


@admin_bp.route('/family-profile', methods=['GET', 'POST'])
@login_required
def family_profile():
    """家族構成プロフィールの確認・編集（AIプロンプトに固定注入される）"""
    family_data = _get_family(current_user.family_id)
    doc_id      = family_data.get('_doc_id', str(current_user.family_id))

    if request.method == 'POST':
        profile = request.form.get('profile', '').strip()
        fs_db.collection('families').document(doc_id).update(
            {'profile': profile if profile else None}
        )
        flash('✅ 家族プロフィールを更新しました。', 'success')
        return redirect(url_for('admin.family_profile'))

    current_profile = family_data.get('profile') or DEFAULT_PROFILE
    family_proxy    = _FamilyProxy(family_data)

    return render_template(
        'family_profile.html',
        family=family_proxy,
        current_profile=current_profile,
        default_profile=DEFAULT_PROFILE,
    )