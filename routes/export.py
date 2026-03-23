"""データエクスポートルート - CSV出力"""

import csv
import io
from datetime import datetime, date
from flask import Blueprint, render_template, request, Response, flash, redirect, url_for
from flask_login import login_required, current_user
from firebase_config import fs_db

export_bp = Blueprint('export', __name__, url_prefix='/export')


def _family_id(raw):
    try:
        return int(raw)
    except Exception:
        return raw


def _to_date_str(value) -> str:
    """日付系の値を YYYY-MM-DD 文字列に統一"""
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d')
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value[:10]
    return ''


def _to_datetime_str(value) -> str:
    """datetime 系の値を YYYY-MM-DD HH:MM:SS 文字列に統一"""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(value, str):
        return value
    return ''


# ------------------------------------------------------------------ #
# ヘルパー：各コレクションからデータ取得
# ------------------------------------------------------------------ #

def _get_transactions(f_id, date_from: str, date_to: str) -> list:
    docs = fs_db.collection('transactions') \
                .where('family_id', '==', f_id) \
                .where('transaction_date', '>=', date_from) \
                .where('transaction_date', '<=', date_to) \
                .stream()
    rows = []
    for doc in docs:
        d = doc.to_dict()
        rows.append({
            'id':               doc.id,
            'transaction_date': _to_date_str(d.get('transaction_date')),
            'transaction_type': d.get('transaction_type', ''),
            'is_income':        'TRUE' if d.get('is_income') else 'FALSE',
            'amount':           d.get('amount', 0),
            'description':      d.get('description', ''),
            'user_id':          str(d.get('user_id', '')),
            'created_at':       _to_datetime_str(d.get('created_at')),
        })
    rows.sort(key=lambda x: x['transaction_date'])
    return rows


def _get_planned_expenses(f_id, cycle_from: str, cycle_to: str) -> list:
    docs = fs_db.collection('planned_expenses') \
                .where('family_id', '==', f_id) \
                .stream()
    rows = []
    for doc in docs:
        d = doc.to_dict()
        cs = d.get('cycle_start', '')
        if isinstance(cs, datetime):
            cs = cs.strftime('%Y-%m-%d')
        if cs < cycle_from or cs > cycle_to:
            continue
        rows.append({
            'id':               doc.id,
            'cycle_start':      cs[:10] if cs else '',
            'transaction_type': d.get('transaction_type', ''),
            'description':      d.get('description', ''),
            'amount':           d.get('amount', 0),
            'planned_date':     _to_date_str(d.get('planned_date')),
            'is_done':          'TRUE' if d.get('is_done') else 'FALSE',
            'is_recurring':     'TRUE' if d.get('is_recurring') else 'FALSE',
            'user_id':          str(d.get('user_id', '')),
        })
    rows.sort(key=lambda x: (x['cycle_start'], x['planned_date']))
    return rows


def _get_memos(f_id) -> list:
    docs = fs_db.collection('memos') \
                .where('family_id', '==', f_id) \
                .stream()
    rows = []
    for doc in docs:
        d = doc.to_dict()
        rows.append({
            'id':            doc.id,
            'memo_type':     d.get('memo_type', ''),
            'item_category': d.get('item_category', ''),
            'content':       d.get('content', ''),
            'price':         d.get('price', 0),
            'is_done':       'TRUE' if d.get('is_done') else 'FALSE',
            'week':          d.get('week', ''),
            'user_id':       str(d.get('user_id', '')),
            'created_at':    _to_datetime_str(d.get('created_at')),
        })
    return rows


def _get_ai_advices(f_id) -> list:
    docs = fs_db.collection('ai_advices') \
                .where('family_id', '==', f_id) \
                .stream()
    rows = []
    for doc in docs:
        d = doc.to_dict()
        rows.append({
            'id':          doc.id,
            'advice_type': d.get('advice_type', ''),
            'advice_text': d.get('advice_text', '').replace('\n', ' '),
            'created_at':  _to_datetime_str(d.get('created_at')),
        })
    rows.sort(key=lambda x: x['created_at'], reverse=True)
    return rows


def _make_csv(rows: list, fieldnames: list) -> str:
    """リストデータを CSV 文字列に変換（BOM付き UTF-8）"""
    buf = io.StringIO()
    # BOM付き UTF-8 で Excel でも文字化けしない
    buf.write('\ufeff')
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction='ignore', lineterminator='\r\n')
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _csv_response(csv_str: str, filename: str) -> Response:
    return Response(
        csv_str.encode('utf-8-sig'),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Type': 'text/csv; charset=utf-8-sig',
        }
    )


# ------------------------------------------------------------------ #
# ルート
# ------------------------------------------------------------------ #

@export_bp.route('/')
@login_required
def index():
    today     = date.today()
    date_from = request.args.get('date_from', date(today.year, today.month, 1).isoformat())
    date_to   = request.args.get('date_to',   today.isoformat())
    return render_template(
        'export.html',
        date_from=date_from,
        date_to=date_to,
        today=today.isoformat(),
    )


@export_bp.route('/transactions.csv')
@login_required
def transactions_csv():
    f_id      = _family_id(current_user.family_id)
    date_from = request.args.get('date_from', '2000-01-01')
    date_to   = request.args.get('date_to',   date.today().isoformat())

    rows = _get_transactions(f_id, date_from, date_to)
    if not rows:
        flash('指定期間の取引データがありません。', 'warning')
        return redirect(url_for('export.index', date_from=date_from, date_to=date_to))

    fieldnames = ['id', 'transaction_date', 'transaction_type', 'is_income',
                  'amount', 'description', 'user_id', 'created_at']
    csv_str  = _make_csv(rows, fieldnames)
    filename = f'transactions_{date_from}_{date_to}.csv'
    return _csv_response(csv_str, filename)


@export_bp.route('/planned_expenses.csv')
@login_required
def planned_expenses_csv():
    f_id       = _family_id(current_user.family_id)
    cycle_from = request.args.get('date_from', '2000-01-01')
    cycle_to   = request.args.get('date_to',   date.today().isoformat())

    rows = _get_planned_expenses(f_id, cycle_from, cycle_to)
    if not rows:
        flash('指定期間の予定支出データがありません。', 'warning')
        return redirect(url_for('export.index', date_from=cycle_from, date_to=cycle_to))

    fieldnames = ['id', 'cycle_start', 'transaction_type', 'description',
                  'amount', 'planned_date', 'is_done', 'is_recurring', 'user_id']
    csv_str  = _make_csv(rows, fieldnames)
    filename = f'planned_expenses_{cycle_from}_{cycle_to}.csv'
    return _csv_response(csv_str, filename)


@export_bp.route('/memos.csv')
@login_required
def memos_csv():
    f_id = _family_id(current_user.family_id)
    rows = _get_memos(f_id)
    if not rows:
        flash('メモデータがありません。', 'warning')
        return redirect(url_for('export.index'))

    fieldnames = ['id', 'memo_type', 'item_category', 'content',
                  'price', 'is_done', 'week', 'user_id', 'created_at']
    csv_str  = _make_csv(rows, fieldnames)
    filename = f'memos_{date.today().isoformat()}.csv'
    return _csv_response(csv_str, filename)


@export_bp.route('/ai_advices.csv')
@login_required
def ai_advices_csv():
    f_id = _family_id(current_user.family_id)
    rows = _get_ai_advices(f_id)
    if not rows:
        flash('AIアドバイスデータがありません。', 'warning')
        return redirect(url_for('export.index'))

    fieldnames = ['id', 'advice_type', 'advice_text', 'created_at']
    csv_str  = _make_csv(rows, fieldnames)
    filename = f'ai_advices_{date.today().isoformat()}.csv'
    return _csv_response(csv_str, filename)


@export_bp.route('/all.zip')
@login_required
def all_zip():
    """全データを ZIP にまとめてダウンロード"""
    import zipfile
    f_id       = _family_id(current_user.family_id)
    today_str  = date.today().isoformat()
    date_from  = request.args.get('date_from', '2000-01-01')
    date_to    = request.args.get('date_to',   today_str)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:

        # 取引
        rows = _get_transactions(f_id, date_from, date_to)
        if rows:
            fieldnames = ['id', 'transaction_date', 'transaction_type', 'is_income',
                          'amount', 'description', 'user_id', 'created_at']
            zf.writestr(f'transactions_{date_from}_{date_to}.csv',
                        _make_csv(rows, fieldnames).encode('utf-8-sig'))

        # 予定支出
        rows = _get_planned_expenses(f_id, date_from, date_to)
        if rows:
            fieldnames = ['id', 'cycle_start', 'transaction_type', 'description',
                          'amount', 'planned_date', 'is_done', 'is_recurring', 'user_id']
            zf.writestr(f'planned_expenses_{date_from}_{date_to}.csv',
                        _make_csv(rows, fieldnames).encode('utf-8-sig'))

        # メモ
        rows = _get_memos(f_id)
        if rows:
            fieldnames = ['id', 'memo_type', 'item_category', 'content',
                          'price', 'is_done', 'week', 'user_id', 'created_at']
            zf.writestr(f'memos_{today_str}.csv',
                        _make_csv(rows, fieldnames).encode('utf-8-sig'))

        # AIアドバイス
        rows = _get_ai_advices(f_id)
        if rows:
            fieldnames = ['id', 'advice_type', 'advice_text', 'created_at']
            zf.writestr(f'ai_advices_{today_str}.csv',
                        _make_csv(rows, fieldnames).encode('utf-8-sig'))

    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype='application/zip',
        headers={
            'Content-Disposition': f'attachment; filename="kakeibo_export_{today_str}.zip"',
        }
    )