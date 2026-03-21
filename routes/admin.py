"""
管理画面ルート
・ユーザー管理（追加・削除・パスワード変更）
・家族グループ名の変更
・家族プロフィール編集（AIプロンプト用）
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Family
from family_utils import DEFAULT_PROFILE

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/')
@login_required
def index():
    family = current_user.family
    members = User.query.filter_by(family_id=family.id).all()
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
    if User.query.filter_by(username=username).first():
        flash(f'ユーザー名「{username}」はすでに使われています。', 'danger')
        return redirect(url_for('admin.index'))
    if User.query.filter_by(email=email).first():
        flash(f'メールアドレス「{email}」はすでに使われています。', 'danger')
        return redirect(url_for('admin.index'))

    user = User(
        username=username,
        display_name=display_name,
        email=email,
        password_hash=generate_password_hash(password),
        family_id=current_user.family_id,
    )
    db.session.add(user)
    db.session.commit()
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

    current_user.password_hash = generate_password_hash(new_pw)
    db.session.commit()
    flash('✅ パスワードを変更しました。', 'success')
    return redirect(url_for('admin.index'))


@admin_bp.route('/user/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('自分自身は削除できません。', 'warning')
        return redirect(url_for('admin.index'))

    user = User.query.filter_by(
        id=user_id, family_id=current_user.family_id
    ).first_or_404()
    db.session.delete(user)
    db.session.commit()
    flash(f'ユーザー「{user.display_name}」を削除しました。', 'info')
    return redirect(url_for('admin.index'))


@admin_bp.route('/family/update', methods=['POST'])
@login_required
def update_family():
    name = request.form.get('family_name', '').strip()
    if not name:
        flash('家族名を入力してください。', 'warning')
        return redirect(url_for('admin.index'))
    current_user.family.name = name
    db.session.commit()
    flash(f'✅ 家族名を「{name}」に変更しました。', 'success')
    return redirect(url_for('admin.index'))


# ★ 追加：家族プロフィール編集
@admin_bp.route('/family-profile', methods=['GET', 'POST'])
@login_required
def family_profile():
    """家族構成プロフィールの確認・編集（AIプロンプトに固定注入される）"""
    family = Family.query.get(current_user.family_id)

    if request.method == 'POST':
        profile = request.form.get('profile', '').strip()
        family.profile = profile if profile else None
        db.session.commit()
        flash('✅ 家族プロフィールを更新しました。', 'success')
        return redirect(url_for('admin.family_profile'))

    current_profile = family.profile if family.profile else DEFAULT_PROFILE
    return render_template(
        'family_profile.html',
        family=family,
        current_profile=current_profile,
        default_profile=DEFAULT_PROFILE,
    )