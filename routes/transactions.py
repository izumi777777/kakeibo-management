"""収支記録ルート - Firestore 連携版"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import TRANSACTION_TYPE_LABELS, TRANSACTION_TYPE_COLORS
from datetime import date, datetime, timedelta
import calendar

# firebase_config から Firestore クライアントをインポート
from firebase_config import fs_db

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

    last_day = calendar.monthrange(year, month)[1]
    start_date_str = f"{year}-{month:02d}-01"
    end_date_str   = f"{year}-{month:02d}-{last_day:02d}"

    f_id = current_user.family_id
    # 検索用IDの型を調整（移行データが数値の場合を考慮）
    try: search_f_id = int(f_id)
    except: search_f_id = f_id

    query = fs_db.collection('transactions') \
                 .where('family_id', '==', search_f_id) \
                 .where('transaction_date', '>=', start_date_str) \
                 .where('transaction_date', '<=', end_date_str)

    if tx_filter == 'income':
        query = query.where('is_income', '==', True)
    elif tx_filter == 'expense':
        query = query.where('is_income', '==', False)

    docs = query.stream()
    
    # --- データの整形プロセス ---
    # ユーザー名のマッピングを作成（N+1問題を避けるため一括取得）
    user_docs = fs_db.collection('users').where('family_id', '==', search_f_id).stream()
    user_map = {doc.id: doc.to_dict() for doc in user_docs}

    transactions = []
    for doc in docs:
        tx = doc.to_dict()
        tx['id'] = doc.id
        
        # 1. 文字列の日付を date オブジェクトに変換 (strftime を使えるようにする)
        if isinstance(tx['transaction_date'], str):
            tx['transaction_date'] = datetime.strptime(tx['transaction_date'], '%Y-%m-%d').date()
        
        # 2. テンプレートで使うラベルと色を注入
        tx['type_label'] = TRANSACTION_TYPE_LABELS.get(tx['transaction_type'], tx['transaction_type'])
        tx['type_color'] = TRANSACTION_TYPE_COLORS.get(tx['transaction_type'], '#ccc')
        
        # 3. ユーザー情報をオブジェクト形式でシミュレート
        u_data = user_map.get(str(tx['user_id']), {'display_name': '不明'})
        tx['user'] = type('User', (object,), u_data)
        
        transactions.append(tx)

    # 日付順にソート
    transactions.sort(key=lambda x: x['transaction_date'], reverse=True)

    # 月ナビ計算
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

        if amount <= 0:
            flash('金額は1円以上で入力してください。', 'warning')
            return redirect(request.referrer or url_for('transactions.index'))

        is_income = tx_type in INCOME_TYPES

        # Firestore への書き込みデータ作成
        f_id = current_user.family_id
        try: f_id = int(f_id)
        except: pass

        data = {
            'family_id': f_id,
            'user_id': current_user.id,
            'amount': amount,
            'transaction_type': tx_type,
            'description': description,
            'transaction_date': tx_date_str, # 文字列として保存
            'is_income': is_income,
            'created_at': datetime.now().isoformat()
        }
        
        fs_db.collection('transactions').add(data)

        label = TRANSACTION_TYPE_LABELS.get(tx_type, tx_type)
        flash(f'✅ {label}「{description or label}」{amount:,}円を記録しました。', 'success')

    except (ValueError, TypeError) as e:
        flash(f'入力値が正しくありません: {e}', 'danger')

    return redirect(request.referrer or url_for('transactions.index'))


@transactions_bp.route('/delete/<tx_id>', methods=['POST']) # intから汎用的なIDへ
@login_required
def delete(tx_id):
    # ドキュメントを直接削除
    fs_db.collection('transactions').document(str(tx_id)).delete()
    flash('記録を削除しました。', 'info')
    return redirect(request.referrer or url_for('transactions.index'))


@transactions_bp.route('/quick-add', methods=['POST'])
@login_required
def quick_add():
    try:
        data        = request.get_json()
        tx_type     = data.get('transaction_type')
        amount      = int(data.get('amount', 0))
        description = data.get('description', '').strip()
        tx_date_str = data.get('transaction_date', str(date.today()))

        if amount <= 0:
            return jsonify({'success': False, 'message': '金額は1円以上で入力してください。'}), 400

        is_income = tx_type in INCOME_TYPES
        
        f_id = current_user.family_id
        try: f_id = int(f_id)
        except: pass

        new_tx = {
            'family_id': f_id,
            'user_id': current_user.id,
            'amount': amount,
            'transaction_type': tx_type,
            'description': description,
            'transaction_date': tx_date_str,
            'is_income': is_income,
            'created_at': datetime.now().isoformat()
        }
        
        fs_db.collection('transactions').add(new_tx)

        label = TRANSACTION_TYPE_LABELS.get(tx_type, tx_type)
        return jsonify({
            'success': True,
            'message': f'{label}「{description or label}」{amount:,}円を記録しました。',
        })

    except (ValueError, TypeError) as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@transactions_bp.route('/edit/<tx_id>', methods=['POST'])
@login_required
def edit(tx_id):
    try:
        tx_type     = request.form.get('transaction_type')
        amount_str  = request.form.get('amount').replace(',', '')
        amount      = int(amount_str)
        description = request.form.get('description', '').strip()
        tx_date_str = request.form.get('transaction_date')

        update_data = {
            'transaction_type': tx_type,
            'amount': amount,
            'description': description,
            'transaction_date': tx_date_str,
            'is_income': tx_type in INCOME_TYPES,
            'updated_at': datetime.now().isoformat()
        }
        
        fs_db.collection('transactions').document(str(tx_id)).update(update_data)
        flash('✅ 記録を更新しました。', 'success')
    except (ValueError, TypeError) as e:
        flash(f'入力値が正しくありません: {e}', 'danger')

    return redirect(request.referrer or url_for('transactions.index'))