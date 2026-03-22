"""
給料日サイクル管理ルート - Firestore 連携版
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import TRANSACTION_TYPE_LABELS, TRANSACTION_TYPE_COLORS
from datetime import date, datetime, timedelta

# firebase_config から Firestore インスタンスをインポート
from firebase_config import fs_db

cycle_bp = Blueprint('cycle', __name__, url_prefix='/cycle')

PAYDAY = 25


def get_cycle_start(target_date: date) -> date:
    if target_date.day >= PAYDAY:
        return target_date.replace(day=PAYDAY)
    else:
        if target_date.month == 1:
            return date(target_date.year - 1, 12, PAYDAY)
        else:
            return date(target_date.year, target_date.month - 1, PAYDAY)


def get_cycle_end(cycle_start: date) -> date:
    if cycle_start.month == 12:
        return date(cycle_start.year + 1, 1, 24)
    else:
        return date(cycle_start.year, cycle_start.month + 1, 24)


def _attach_tx_meta(t: dict) -> dict:
    """取引辞書に type_label / type_color / is_income プロパティを付与する"""
    tx_type = t.get('transaction_type', 'other')
    t['type_label'] = TRANSACTION_TYPE_LABELS.get(tx_type, tx_type)
    t['type_color']  = TRANSACTION_TYPE_COLORS.get(tx_type, '#94a3b8')
    # is_income が未設定のフォールバック
    if 'is_income' not in t:
        t['is_income'] = tx_type == 'income'
    return t


def get_cycle_summary(family_id, cycle_start: date) -> dict:
    cycle_end  = get_cycle_end(cycle_start)
    today      = date.today()
    start_iso  = cycle_start.isoformat()
    end_iso    = cycle_end.isoformat()

    # 型変換（SQLite移行データへの配慮）
    try:
        f_id = int(family_id)
    except Exception:
        f_id = family_id

    # ---- ユーザーマップ（display_name 表示用） ----
    user_docs = fs_db.collection('users').where('family_id', '==', f_id).stream()
    user_map  = {doc.id: doc.to_dict() for doc in user_docs}

    class _UserProxy:
        """辞書を .display_name でアクセスできるようにするラッパー"""
        def __init__(self, d):
            self.display_name = d.get('display_name', '不明')

    # ---- 1. 実績（Transactions）の取得と集計 ----
    actual_docs = fs_db.collection('transactions') \
                       .where('family_id', '==', f_id) \
                       .where('transaction_date', '>=', start_iso) \
                       .where('transaction_date', '<=', end_iso) \
                       .stream()

    actual_txs      = []
    actual_income   = 0
    actual_expense  = 0
    category_actual = {}

    for doc in actual_docs:
        t       = doc.to_dict()
        t['id'] = doc.id
        _attach_tx_meta(t)

        # transaction_date を date オブジェクトに変換（テンプレートの .strftime 対応）
        td = t.get('transaction_date', '')
        if isinstance(td, str) and td:
            try:
                t['transaction_date'] = date.fromisoformat(td)
            except ValueError:
                t['transaction_date'] = today
        elif not isinstance(td, date):
            t['transaction_date'] = today

        # ユーザー情報を付与
        u_id      = str(t.get('user_id', ''))
        t['user'] = _UserProxy(user_map.get(u_id, {}))

        actual_txs.append(t)

        amount = t.get('amount', 0)
        if t.get('is_income'):
            actual_income += amount
        else:
            actual_expense += amount
            tx_type = t.get('transaction_type', 'other')
            category_actual[tx_type] = category_actual.get(tx_type, 0) + amount

    # ---- 2. 予定支出（PlannedExpenses）の取得と集計 ----
    planned_docs = fs_db.collection('planned_expenses') \
                        .where('family_id', '==', f_id) \
                        .where('cycle_start', '==', start_iso) \
                        .stream()

    planned          = []
    category_planned = {}
    planned_total    = 0
    planned_done_amt = 0
    planned_all_amt  = 0

    for doc in planned_docs:
        p       = doc.to_dict()
        p['id'] = doc.id

        # type_label / type_color を付与
        tx_type = p.get('transaction_type', 'fixed')
        p['type_label'] = TRANSACTION_TYPE_LABELS.get(tx_type, tx_type)
        p['type_color']  = TRANSACTION_TYPE_COLORS.get(tx_type, '#94a3b8')

        # planned_date を date オブジェクトに変換
        pd = p.get('planned_date', '')
        if isinstance(pd, str) and pd:
            try:
                p['planned_date'] = date.fromisoformat(pd)
            except ValueError:
                p['planned_date'] = None
        elif not isinstance(pd, date):
            p['planned_date'] = None

        # ユーザー情報を付与
        u_id      = str(p.get('user_id', ''))
        p['user'] = _UserProxy(user_map.get(u_id, {}))

        planned.append(p)

        amt = p.get('amount', 0)
        planned_all_amt += amt
        if p.get('is_done'):
            planned_done_amt += amt
        else:
            planned_total += amt
            category_planned[tx_type] = category_planned.get(tx_type, 0) + amt

    # ---- 3. 予算（Budgets）の取得 ----
    budget_docs = fs_db.collection('budgets') \
                       .where('family_id', '==', f_id) \
                       .where('cycle_start', '==', start_iso) \
                       .stream()

    budget_map = {}
    for doc in budget_docs:
        d = doc.to_dict()
        budget_map[d.get('transaction_type')] = d.get('amount', 0)

    # ---- 4. 計算ロジック ----
    actual_balance   = actual_income - actual_expense
    forecast_balance = actual_balance - planned_total
    next_payday      = cycle_end + timedelta(days=1)
    days_remaining   = max(0, (next_payday - today).days)
    days_elapsed     = max(0, (today - cycle_start).days)
    days_total       = (next_payday - cycle_start).days
    progress_pct     = min(100, int(days_elapsed / days_total * 100)) if days_total else 0
    daily_budget     = forecast_balance // days_remaining if days_remaining > 0 else 0

    # ---- 5. 支出内訳（Breakdown）の作成 ----
    all_types = set(
        list(category_actual.keys()) +
        list(category_planned.keys()) +
        list(budget_map.keys())
    )
    breakdown = []
    for t in ['fixed', 'food', 'daily', 'entertainment', 'medical', 'education', 'other']:
        if t not in all_types:
            continue
        actual      = category_actual.get(t, 0)
        planned_amt = category_planned.get(t, 0)
        budget      = budget_map.get(t, 0)
        total       = actual + planned_amt
        pct         = min(100, int(total / budget * 100)) if budget > 0 else None
        breakdown.append({
            'type':    t,
            'label':   TRANSACTION_TYPE_LABELS.get(t, t),
            'color':   TRANSACTION_TYPE_COLORS.get(t, '#94a3b8'),
            'actual':  actual,
            'planned': planned_amt,
            'total':   total,
            'budget':  budget,
            'pct':     pct,
        })

    # planned_list を planned_date 順にソート
    planned_sorted = sorted(
        planned,
        key=lambda x: (x.get('planned_date') or date.max)
    )

    return {
        'cycle_start':     cycle_start,
        'cycle_end':       cycle_end,
        'next_payday':     next_payday,
        'days_remaining':  days_remaining,
        'days_elapsed':    days_elapsed,       # ★ 追加
        'days_total':      days_total,         # ★ 追加
        'progress_pct':    progress_pct,       # ★ 追加
        'actual_income':   actual_income,
        'actual_expense':  actual_expense,
        'actual_balance':  actual_balance,
        'planned_list':    planned_sorted,
        'planned_total':   planned_total,
        'planned_done':    planned_done_amt,   # ★ キー名を planned_done に統一
        'planned_all':     planned_all_amt,    # ★ キー名を planned_all に統一
        'forecast_balance': forecast_balance,
        'daily_budget':    daily_budget,
        'actual_txs':      actual_txs,         # ★ 追加
        'budget_map':      budget_map,         # ★ 追加
        'category_actual': category_actual,
        'category_planned': category_planned,
        'breakdown':       breakdown,
    }


@cycle_bp.route('/')
@login_required
def index():
    today = date.today()
    cycle_start_str = request.args.get('cycle_start')
    if cycle_start_str:
        cycle_start = datetime.strptime(cycle_start_str, '%Y-%m-%d').date()
    else:
        cycle_start = get_cycle_start(today)

    summary = get_cycle_summary(current_user.family_id, cycle_start)

    prev_cycle_start = get_cycle_start(cycle_start - timedelta(days=1))
    next_cycle_start = get_cycle_end(cycle_start) + timedelta(days=1)
    current_cycle    = get_cycle_start(today)
    can_go_next      = cycle_start < current_cycle + timedelta(days=31)  # ★ 追加

    return render_template(
        'cycle.html',
        s=summary,
        today=today,
        prev_cycle_start=prev_cycle_start,
        next_cycle_start=next_cycle_start,
        can_go_next=can_go_next,                # ★ 追加
        type_labels=TRANSACTION_TYPE_LABELS,
        type_colors=TRANSACTION_TYPE_COLORS,
        payday=PAYDAY,
    )


@cycle_bp.route('/planned/add', methods=['POST'])
@login_required
def add_planned():
    cycle_start_str = request.form.get('cycle_start')
    try:
        cycle_start  = datetime.strptime(cycle_start_str, '%Y-%m-%d').date()
        description  = request.form.get('description', '').strip()
        amount       = int(request.form.get('amount', '0').replace(',', ''))
        tx_type      = request.form.get('transaction_type', 'fixed')
        planned_date = request.form.get('planned_date', '')
        is_recurring = request.form.get('is_recurring') == '1'

        if amount <= 0 or not description:
            flash('金額と名前を入力してください。', 'warning')
            return redirect(url_for('cycle.index', cycle_start=cycle_start_str))

        f_id = current_user.family_id
        try:
            f_id = int(f_id)
        except Exception:
            pass

        data = {
            'family_id':        f_id,
            'user_id':          current_user.id,
            'description':      description,
            'amount':           amount,
            'transaction_type': tx_type,
            'cycle_start':      cycle_start_str,
            'planned_date':     planned_date or None,
            'is_recurring':     is_recurring,
            'is_done':          False,
            'created_at':       datetime.now(),
        }
        fs_db.collection('planned_expenses').add(data)

        # 毎月繰り返し → 次サイクルにも追加
        if is_recurring:
            next_start = get_cycle_end(cycle_start) + timedelta(days=1)
            next_data  = dict(data)
            next_data['cycle_start'] = next_start.isoformat()
            if planned_date:
                try:
                    diff = (date.fromisoformat(planned_date) - cycle_start).days
                    next_data['planned_date'] = (next_start + timedelta(days=diff)).isoformat()
                except Exception:
                    next_data['planned_date'] = None
            # 次サイクルに同名が既存でなければ追加
            existing = fs_db.collection('planned_expenses') \
                            .where('family_id', '==', f_id) \
                            .where('description', '==', description) \
                            .where('cycle_start', '==', next_data['cycle_start']) \
                            .limit(1).get()
            if not existing:
                fs_db.collection('planned_expenses').add(next_data)

        flash(f'✓「{description}」¥{amount:,} を追加しました。', 'success')

    except Exception as e:
        flash(f'エラー: {e}', 'danger')

    return redirect(url_for('cycle.index', cycle_start=cycle_start_str))


@cycle_bp.route('/planned/toggle/<pe_id>', methods=['POST'])
@login_required
def toggle_planned(pe_id):
    ref = fs_db.collection('planned_expenses').document(str(pe_id))
    doc = ref.get()
    if doc.exists:
        new_status = not doc.to_dict().get('is_done', False)
        ref.update({'is_done': new_status})
        return jsonify({'success': True, 'is_done': new_status})
    return jsonify({'success': False}), 404


@cycle_bp.route('/planned/edit/<pe_id>', methods=['POST'])
@login_required
def edit_planned(pe_id):
    """予定支出を編集（JSON API）"""
    ref = fs_db.collection('planned_expenses').document(str(pe_id))
    doc = ref.get()
    if not doc.exists:
        return jsonify({'success': False, 'message': 'Not found'}), 404

    data = request.get_json()
    try:
        update = {
            'description':      data.get('description', '').strip(),
            'amount':           int(str(data.get('amount', 0)).replace(',', '')),
            'transaction_type': data.get('transaction_type', 'fixed'),
            'planned_date':     data.get('planned_date') or None,
            'is_recurring':     data.get('is_recurring', False),
        }
        ref.update(update)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@cycle_bp.route('/planned/delete/<pe_id>', methods=['POST'])
@login_required
def delete_planned(pe_id):
    ref = fs_db.collection('planned_expenses').document(str(pe_id))
    ref.delete()
    return jsonify({'success': True})


@cycle_bp.route('/budget/save', methods=['POST'])
@login_required
def save_budget():
    cycle_start_str = request.form.get('cycle_start')
    f_id = current_user.family_id
    try:
        f_id = int(f_id)
    except Exception:
        pass

    for tx_type in ['fixed', 'food', 'daily', 'entertainment', 'medical', 'education', 'other']:
        amt_str = request.form.get(f'budget_{tx_type}', '').replace(',', '')
        if amt_str and amt_str.isdigit() and int(amt_str) > 0:
            query = fs_db.collection('budgets') \
                         .where('family_id', '==', f_id) \
                         .where('transaction_type', '==', tx_type) \
                         .where('cycle_start', '==', cycle_start_str) \
                         .limit(1).get()
            amt = int(amt_str)
            if query:
                query[0].reference.update({'amount': amt})
            else:
                fs_db.collection('budgets').add({
                    'family_id':        f_id,
                    'transaction_type': tx_type,
                    'cycle_start':      cycle_start_str,
                    'amount':           amt,
                    'created_at':       datetime.now(),
                })

    flash('予算を保存しました。', 'success')
    return redirect(url_for('cycle.index', cycle_start=cycle_start_str))


@cycle_bp.route('/carryover', methods=['POST'])
@login_required
def carryover():
    """
    現在のサイクルの残高を次のサイクルに「繰り越し収入」として登録する。
    - 繰り越し額 = 確定収入 - 確定支出 - 支払済み予定支出
    - 次サイクルの transaction_date = 次の給料日（cycle_start）
    - 二重登録を防ぐため、同一サイクルへの繰り越しが既存でないか確認する
    """
    cycle_start_str = request.form.get('cycle_start')
    try:
        cycle_start = datetime.strptime(cycle_start_str, '%Y-%m-%d').date()
    except Exception:
        flash('サイクル日付が不正です。', 'danger')
        return redirect(url_for('cycle.index'))

    summary = get_cycle_summary(current_user.family_id, cycle_start)

    # 繰り越し額 = 収入 - 支出（確定のみ、予定未払い分は含まない）
    carryover_amount = summary['actual_income'] - summary['actual_expense']

    if carryover_amount <= 0:
        flash(f'繰り越せる残高がありません（確定残高: ¥{carryover_amount:,}）。', 'warning')
        return redirect(url_for('cycle.index', cycle_start=cycle_start_str))

    # 次サイクルの開始日
    next_cycle_start = get_cycle_end(cycle_start) + timedelta(days=1)
    next_cycle_start_iso = next_cycle_start.isoformat()

    f_id = current_user.family_id
    try:
        f_id = int(f_id)
    except Exception:
        pass

    # 二重登録チェック
    existing = fs_db.collection('transactions') \
                    .where('family_id', '==', f_id) \
                    .where('transaction_type', '==', 'carryover') \
                    .where('transaction_date', '==', next_cycle_start_iso) \
                    .limit(1).get()

    if existing:
        flash('このサイクルの繰り越しはすでに登録されています。', 'warning')
        return redirect(url_for('cycle.index', cycle_start=cycle_start_str))

    # 次サイクルに繰り越し収入として登録
    fs_db.collection('transactions').add({
        'family_id':        f_id,
        'user_id':          current_user.id,
        'amount':           carryover_amount,
        'transaction_type': 'carryover',
        'is_income':        True,
        'description':      f'前サイクル繰り越し（{cycle_start.strftime("%Y/%m/%d")}〜）',
        'transaction_date': next_cycle_start_iso,
        'created_at':       datetime.now(),
    })

    flash(
        f'✅ ¥{carryover_amount:,} を次のサイクル（{next_cycle_start.strftime("%Y/%m/%d")}〜）に繰り越しました。',
        'success'
    )
    return redirect(url_for('cycle.index', cycle_start=next_cycle_start_iso))