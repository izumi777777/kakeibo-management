"""
給料日サイクル管理ルート（改訂版）
・全体サマリーの強化
・予定支出の編集・削除
・AI アドバイスのサイクル対応
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Transaction, PlannedExpense, Budget, TRANSACTION_TYPE_LABELS, TRANSACTION_TYPE_COLORS
from datetime import date, datetime, timedelta

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


def get_cycle_summary(family_id: int, cycle_start: date):
    cycle_end = get_cycle_end(cycle_start)
    today = date.today()

    actual_txs = Transaction.query.filter(
        Transaction.family_id == family_id,
        Transaction.transaction_date >= cycle_start,
        Transaction.transaction_date <= cycle_end,
    ).order_by(Transaction.transaction_date.desc()).all()

    actual_income  = sum(t.amount for t in actual_txs if t.is_income)
    actual_expense = sum(t.amount for t in actual_txs if not t.is_income)

    planned = PlannedExpense.query.filter_by(
        family_id=family_id,
        cycle_start=cycle_start,
    ).order_by(PlannedExpense.planned_date, PlannedExpense.id).all()

    planned_total = sum(p.amount for p in planned if not p.is_done)
    planned_done  = sum(p.amount for p in planned if p.is_done)
    planned_all   = sum(p.amount for p in planned)

    budgets   = Budget.query.filter_by(family_id=family_id, cycle_start=cycle_start).all()
    budget_map = {b.transaction_type: b.amount for b in budgets}

    actual_balance   = actual_income - actual_expense
    forecast_balance = actual_balance - planned_total

    next_payday    = get_cycle_end(cycle_start) + timedelta(days=1)
    days_remaining = max(0, (next_payday - today).days)
    days_elapsed   = max(0, (today - cycle_start).days)
    days_total     = (next_payday - cycle_start).days
    progress_pct   = min(100, int(days_elapsed / days_total * 100)) if days_total else 0

    daily_budget = forecast_balance // days_remaining if days_remaining > 0 else 0

    category_actual = {}
    for t in actual_txs:
        if not t.is_income:
            category_actual[t.transaction_type] = \
                category_actual.get(t.transaction_type, 0) + t.amount

    # カテゴリ別予定支出集計
    category_planned = {}
    for p in planned:
        if not p.is_done:
            category_planned[p.transaction_type] = \
                category_planned.get(p.transaction_type, 0) + p.amount

    # 支出内訳：実績＋予定（未払い）をマージ
    all_types = set(list(category_actual.keys()) + list(category_planned.keys()) + list(budget_map.keys()))
    breakdown = []
    for t in ['fixed','food','daily','entertainment','medical','education','other']:
        if t not in all_types:
            continue
        actual  = category_actual.get(t, 0)
        planned_amt = category_planned.get(t, 0)
        budget  = budget_map.get(t, 0)
        total   = actual + planned_amt
        pct     = min(100, int(total / budget * 100)) if budget > 0 else None
        breakdown.append({
            'type': t,
            'label': TRANSACTION_TYPE_LABELS.get(t, t),
            'color': TRANSACTION_TYPE_COLORS.get(t, '#94a3b8'),
            'actual': actual,
            'planned': planned_amt,
            'total': total,
            'budget': budget,
            'pct': pct,
        })

    return {
        'cycle_start': cycle_start,
        'cycle_end': cycle_end,
        'next_payday': next_payday,
        'days_remaining': days_remaining,
        'days_elapsed': days_elapsed,
        'days_total': days_total,
        'progress_pct': progress_pct,
        'actual_income': actual_income,
        'actual_expense': actual_expense,
        'actual_balance': actual_balance,
        'planned_list': planned,
        'planned_total': planned_total,
        'planned_done': planned_done,
        'planned_all': planned_all,
        'forecast_balance': forecast_balance,
        'daily_budget': daily_budget,
        'actual_txs': actual_txs,
        'budget_map': budget_map,
        'category_actual': category_actual,
        'category_planned': category_planned,
        'breakdown': breakdown,
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
    can_go_next      = cycle_start < current_cycle + timedelta(days=31)

    return render_template(
        'cycle.html',
        s=summary,
        today=today,
        prev_cycle_start=prev_cycle_start,
        next_cycle_start=next_cycle_start,
        can_go_next=can_go_next,
        type_labels=TRANSACTION_TYPE_LABELS,
        type_colors=TRANSACTION_TYPE_COLORS,
        payday=PAYDAY,
    )


@cycle_bp.route('/planned/add', methods=['POST'])
@login_required
def add_planned():
    try:
        cycle_start_str = request.form.get('cycle_start')
        cycle_start  = datetime.strptime(cycle_start_str, '%Y-%m-%d').date()
        description  = request.form.get('description', '').strip()
        amount       = int(request.form.get('amount', '0').replace(',', ''))
        tx_type      = request.form.get('transaction_type', 'fixed')
        planned_date_str = request.form.get('planned_date', '')
        is_recurring = request.form.get('is_recurring') == '1'
        planned_date = datetime.strptime(planned_date_str, '%Y-%m-%d').date() \
            if planned_date_str else None

        if amount <= 0 or not description:
            flash('金額と名前を入力してください。', 'warning')
            return redirect(url_for('cycle.index', cycle_start=cycle_start_str))

        pe = PlannedExpense(
            family_id=current_user.family_id,
            user_id=current_user.id,
            description=description,
            amount=amount,
            transaction_type=tx_type,
            cycle_start=cycle_start,
            planned_date=planned_date,
            is_recurring=is_recurring,
        )
        db.session.add(pe)

        if is_recurring:
            next_start = get_cycle_end(cycle_start) + timedelta(days=1)
            next_planned = None
            if planned_date:
                diff = (planned_date - cycle_start).days
                next_planned = next_start + timedelta(days=diff)
            existing = PlannedExpense.query.filter_by(
                family_id=current_user.family_id,
                description=description,
                cycle_start=next_start,
            ).first()
            if not existing:
                db.session.add(PlannedExpense(
                    family_id=current_user.family_id,
                    user_id=current_user.id,
                    description=description,
                    amount=amount,
                    transaction_type=tx_type,
                    cycle_start=next_start,
                    planned_date=next_planned,
                    is_recurring=True,
                ))

        db.session.commit()
        flash(f'✓「{description}」¥{amount:,} を追加しました。', 'success')

    except Exception as e:
        flash(f'エラー: {e}', 'danger')

    return redirect(url_for('cycle.index', cycle_start=request.form.get('cycle_start')))


@cycle_bp.route('/planned/toggle/<int:pe_id>', methods=['POST'])
@login_required
def toggle_planned(pe_id):
    pe = PlannedExpense.query.filter_by(
        id=pe_id, family_id=current_user.family_id
    ).first_or_404()
    pe.is_done = not pe.is_done
    db.session.commit()
    return jsonify({'success': True, 'is_done': pe.is_done})


@cycle_bp.route('/planned/edit/<int:pe_id>', methods=['POST'])
@login_required
def edit_planned(pe_id):
    """予定支出を編集（JSON API）"""
    pe = PlannedExpense.query.filter_by(
        id=pe_id, family_id=current_user.family_id
    ).first_or_404()
    data = request.get_json()
    try:
        pe.description  = data.get('description', pe.description).strip()
        pe.amount       = int(str(data.get('amount', pe.amount)).replace(',', ''))
        pe.transaction_type = data.get('transaction_type', pe.transaction_type)
        pd_str = data.get('planned_date', '')
        pe.planned_date = datetime.strptime(pd_str, '%Y-%m-%d').date() if pd_str else None
        pe.is_recurring = data.get('is_recurring', pe.is_recurring)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@cycle_bp.route('/planned/delete/<int:pe_id>', methods=['POST'])
@login_required
def delete_planned(pe_id):
    pe = PlannedExpense.query.filter_by(
        id=pe_id, family_id=current_user.family_id
    ).first_or_404()
    db.session.delete(pe)
    db.session.commit()
    return jsonify({'success': True})


@cycle_bp.route('/budget/save', methods=['POST'])
@login_required
def save_budget():
    cycle_start_str = request.form.get('cycle_start')
    cycle_start = datetime.strptime(cycle_start_str, '%Y-%m-%d').date()
    for tx_type in ['fixed','food','daily','entertainment','medical','education','other']:
        amt_str = request.form.get(f'budget_{tx_type}', '').replace(',', '')
        if amt_str and amt_str.isdigit() and int(amt_str) > 0:
            existing = Budget.query.filter_by(
                family_id=current_user.family_id,
                transaction_type=tx_type,
                cycle_start=cycle_start,
            ).first()
            if existing:
                existing.amount = int(amt_str)
            else:
                db.session.add(Budget(
                    family_id=current_user.family_id,
                    transaction_type=tx_type,
                    cycle_start=cycle_start,
                    amount=int(amt_str),
                ))
    db.session.commit()
    flash('予算を保存しました。', 'success')
    return redirect(url_for('cycle.index', cycle_start=cycle_start_str))
