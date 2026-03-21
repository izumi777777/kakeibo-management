"""収支記録ルート"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Transaction, TRANSACTION_TYPE_LABELS, TRANSACTION_TYPE_COLORS
from datetime import date, datetime
from sqlalchemy import extract

transactions_bp = Blueprint('transactions', __name__, url_prefix='/transactions')

EXPENSE_TYPES = ['fixed', 'food', 'daily', 'entertainment', 'medical', 'education', 'other']
INCOME_TYPES  = ['income']


@transactions_bp.route('/')
@login_required
def index():
    today = date.today()
    year      = int(request.args.get('year',   today.year))
    month     = int(request.args.get('month',  today.month))
    tx_filter = request.args.get('filter', 'all')

    q = Transaction.query.filter(
        Transaction.family_id == current_user.family_id,
        extract('year',  Transaction.transaction_date) == year,
        extract('month', Transaction.transaction_date) == month,
    )
    if tx_filter == 'income':
        q = q.filter(Transaction.is_income == True)
    elif tx_filter == 'expense':
        q = q.filter(Transaction.is_income == False)

    transactions = q.order_by(Transaction.transaction_date.desc()).all()

    # 月ナビ
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    return render_template(
        'transactions.html',
        transactions=transactions,
        type_labels=TRANSACTION_TYPE_LABELS,
        type_colors=TRANSACTION_TYPE_COLORS,
        expense_types=EXPENSE_TYPES,
        income_types=INCOME_TYPES,
        current_year=year,   current_month=month,
        prev_year=prev_year, prev_month=prev_month,
        next_year=next_year, next_month=next_month,
        tx_filter=tx_filter,
        today=today,
    )


@transactions_bp.route('/add', methods=['POST'])
@login_required
def add():
    try:
        tx_type     = request.form.get('transaction_type')
        amount_str  = request.form.get('amount', '0').replace(',', '')
        amount      = int(amount_str)
        description = request.form.get('description', '').strip()
        tx_date_str = request.form.get('transaction_date', str(date.today()))
        tx_date     = datetime.strptime(tx_date_str, '%Y-%m-%d').date()

        if amount <= 0:
            flash('金額は1円以上で入力してください。', 'warning')
            return redirect(request.referrer or url_for('transactions.index'))

        is_income = tx_type in INCOME_TYPES

        tx = Transaction(
            family_id=current_user.family_id,
            user_id=current_user.id,
            amount=amount,
            transaction_type=tx_type,
            description=description,
            transaction_date=tx_date,
            is_income=is_income,
        )
        db.session.add(tx)
        db.session.commit()

        label = TRANSACTION_TYPE_LABELS.get(tx_type, tx_type)
        flash(f'✅ {label}「{description or label}」{amount:,}円を記録しました。', 'success')

    except (ValueError, TypeError) as e:
        flash(f'入力値が正しくありません: {e}', 'danger')

    return redirect(request.referrer or url_for('transactions.index'))


@transactions_bp.route('/delete/<int:tx_id>', methods=['POST'])
@login_required
def delete(tx_id):
    tx = Transaction.query.filter_by(
        id=tx_id, family_id=current_user.family_id
    ).first_or_404()
    db.session.delete(tx)
    db.session.commit()
    flash('記録を削除しました。', 'info')
    return redirect(request.referrer or url_for('transactions.index'))


@transactions_bp.route('/quick-add', methods=['POST'])
@login_required
def quick_add():
    """ダッシュボードからのクイック入力（JSON対応）"""
    try:
        data        = request.get_json()
        tx_type     = data.get('transaction_type')
        amount      = int(data.get('amount', 0))
        description = data.get('description', '').strip()
        tx_date_str = data.get('transaction_date', str(date.today()))
        tx_date     = datetime.strptime(tx_date_str, '%Y-%m-%d').date()

        if amount <= 0:
            return jsonify({'success': False, 'message': '金額は1円以上で入力してください。'}), 400

        is_income = tx_type in INCOME_TYPES

        tx = Transaction(
            family_id=current_user.family_id,
            user_id=current_user.id,
            amount=amount,
            transaction_type=tx_type,
            description=description,
            transaction_date=tx_date,
            is_income=is_income,
        )
        db.session.add(tx)
        db.session.commit()

        label = TRANSACTION_TYPE_LABELS.get(tx_type, tx_type)
        return jsonify({
            'success': True,
            'message': f'{label}「{description or label}」{amount:,}円を記録しました。',
        })

    except (ValueError, TypeError) as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@transactions_bp.route('/edit/<int:tx_id>', methods=['POST'])
@login_required
def edit(tx_id):
    tx = Transaction.query.filter_by(
        id=tx_id, family_id=current_user.family_id
    ).first_or_404()

    try:
        tx.transaction_type = request.form.get('transaction_type', tx.transaction_type)
        amount_str          = request.form.get('amount', str(tx.amount)).replace(',', '')
        tx.amount           = int(amount_str)
        tx.description      = request.form.get('description', '').strip()
        tx_date_str         = request.form.get('transaction_date', str(tx.transaction_date))
        tx.transaction_date = datetime.strptime(tx_date_str, '%Y-%m-%d').date()
        tx.is_income        = tx.transaction_type in INCOME_TYPES
        db.session.commit()
        flash('✅ 記録を更新しました。', 'success')
    except (ValueError, TypeError) as e:
        flash(f'入力値が正しくありません: {e}', 'danger')

    return redirect(request.referrer or url_for('transactions.index'))