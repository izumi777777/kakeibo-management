"""運用手順メモルート"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

ops_bp = Blueprint('ops', __name__, url_prefix='/ops')


# OperationsMemo モデルはここで直接定義（models.pyに追記でもOK）
class OperationsMemo(db.Model):
    __tablename__ = 'operations_memos'
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])


INITIAL_MEMOS = [
    {
        "title": "📅 給料日サイクル管理 — 使い方",
        "content": """毎月25日にやること（5分で完了）

【ステップ1】サイドバーの「給料日サイクル管理」を開く

【ステップ2】「予定支出を追加」で固定費を先入力
  家賃       ¥80,000  → 毎月繰り返す ✅
  電気代     ¥ 8,000
  ガス代     ¥ 5,000
  スマホ代   ¥10,000  → 毎月繰り返す ✅
  保険       ¥15,000  → 毎月繰り返す ✅

【ステップ3】予算を設定（任意）
  食費     ¥50,000
  日用品   ¥20,000
  娯楽     ¥15,000

→ 入力した瞬間に残高・1日あたりの使える金額が自動計算されます。""",
    },
    {
        "title": "🖥️ ダッシュボードの見方",
        "content": """予測残高   … 給料 − 確定支出 − 未払い予定支出
1日あたり … 予測残高 ÷ 給料日までの残り日数
カテゴリ別 … 食費80%使用、残り¥10,000など
赤字警告   … 予定支出を含めると赤字になる場合に自動アラート
支払済み   … チェックを入れると残高が即座に更新""",
    },
    {
        "title": "🔄 アップデート手順",
        "content": """新しい kakeibo_app.zip をダウンロードしたら：

1. PowerShell を開く
2. kakeimanagement フォルダに移動
   cd C:\\Users\\izumi\\work\\IT\\趣味\\app\\kakeimanagement

3. 上書き展開
   Expand-Archive -Path kakeibo_app.zip -DestinationPath . -Force

4. アプリを起動
   cd kakeibo
   venv\\Scripts\\Activate.ps1
   python app.py

※ DBファイル(kakeibo.db)は削除しないこと！データが消えます。""",
    },
]


def seed_initial_memos(family_id, user_id):
    """初回のみデフォルトメモを挿入"""
    existing = OperationsMemo.query.filter_by(family_id=family_id).first()
    if not existing:
        for i, m in enumerate(INITIAL_MEMOS):
            db.session.add(OperationsMemo(
                family_id=family_id,
                user_id=user_id,
                title=m['title'],
                content=m['content'],
                sort_order=i,
            ))
        db.session.commit()


@ops_bp.route('/')
@login_required
def index():
    seed_initial_memos(current_user.family_id, current_user.id)
    memos = OperationsMemo.query.filter_by(
        family_id=current_user.family_id
    ).order_by(OperationsMemo.sort_order, OperationsMemo.created_at).all()
    return render_template('ops.html', memos=memos)


@ops_bp.route('/add', methods=['POST'])
@login_required
def add():
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    if not title or not content:
        flash('タイトルと内容を入力してください。', 'warning')
        return redirect(url_for('ops.index'))

    max_order = db.session.query(db.func.max(OperationsMemo.sort_order)).filter_by(
        family_id=current_user.family_id
    ).scalar() or 0

    db.session.add(OperationsMemo(
        family_id=current_user.family_id,
        user_id=current_user.id,
        title=title,
        content=content,
        sort_order=max_order + 1,
    ))
    db.session.commit()
    flash(f'✅「{title}」を追加しました。', 'success')
    return redirect(url_for('ops.index'))


@ops_bp.route('/edit/<int:memo_id>', methods=['POST'])
@login_required
def edit(memo_id):
    memo = OperationsMemo.query.filter_by(
        id=memo_id, family_id=current_user.family_id
    ).first_or_404()
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    if not title or not content:
        return jsonify({'success': False, 'message': '内容が空です'}), 400
    memo.title = title
    memo.content = content
    memo.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})


@ops_bp.route('/delete/<int:memo_id>', methods=['POST'])
@login_required
def delete(memo_id):
    memo = OperationsMemo.query.filter_by(
        id=memo_id, family_id=current_user.family_id
    ).first_or_404()
    db.session.delete(memo)
    db.session.commit()
    return jsonify({'success': True})
