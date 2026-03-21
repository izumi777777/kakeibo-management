"""ダッシュボードルート - Firestore 対応版"""

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from models import TRANSACTION_TYPE_LABELS, TRANSACTION_TYPE_COLORS
from datetime import date, datetime, timedelta

from firebase_config import fs_db

dashboard_bp = Blueprint('dashboard', __name__)


# ------------------------------------------------------------------ #
# ヘルパー
# ------------------------------------------------------------------ #

def _family_id(raw):
    try:
        return int(raw)
    except Exception:
        return raw


def _to_date(value) -> date:
    """文字列 / date / datetime を date に統一"""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            pass
    return date.today()


class _TxProxy:
    """取引辞書を属性アクセスできるようにするラッパー"""
    def __init__(self, d: dict, user_map: dict):
        self._d = d
        tx_type          = d.get('transaction_type', 'other')
        self.id          = d.get('id')
        self.amount      = d.get('amount', 0)
        self.is_income   = d.get('is_income', tx_type == 'income')
        self.description = d.get('description', '')
        self.transaction_type = tx_type
        self.transaction_date = _to_date(d.get('transaction_date'))
        self.type_label  = TRANSACTION_TYPE_LABELS.get(tx_type, tx_type)
        self.type_color  = TRANSACTION_TYPE_COLORS.get(tx_type, '#94a3b8')

        u_id       = str(d.get('user_id', ''))
        u_dict     = user_map.get(u_id, {})
        self.user  = type('U', (), {'display_name': u_dict.get('display_name', '不明')})()


# ------------------------------------------------------------------ #
# データ取得
# ------------------------------------------------------------------ #

def _get_transactions_for_month(family_id, year: int, month: int) -> list[_TxProxy]:
    """指定年月の取引を Firestore から取得して _TxProxy のリストで返す"""
    f_id      = _family_id(family_id)
    start_iso = date(year, month, 1).isoformat()
    # 月末日
    if month == 12:
        end_iso = date(year + 1, 1, 1).isoformat()
    else:
        end_iso = date(year, month + 1, 1).isoformat()

    # ユーザーマップ
    user_docs = fs_db.collection('users').where('family_id', '==', f_id).stream()
    user_map  = {doc.id: doc.to_dict() for doc in user_docs}

    tx_docs = fs_db.collection('transactions') \
                   .where('family_id', '==', f_id) \
                   .where('transaction_date', '>=', start_iso) \
                   .where('transaction_date', '<',  end_iso) \
                   .stream()

    result = []
    for doc in tx_docs:
        d       = doc.to_dict()
        d['id'] = doc.id
        result.append(_TxProxy(d, user_map))

    # 日付降順にソート
    result.sort(key=lambda t: t.transaction_date, reverse=True)
    return result


def get_monthly_summary(family_id, year: int, month: int) -> dict:
    """月次収支サマリーを取得"""
    txs = _get_transactions_for_month(family_id, year, month)

    income  = sum(t.amount for t in txs if t.is_income)
    expense = sum(t.amount for t in txs if not t.is_income)
    balance = income - expense

    category_totals = {}
    for t in txs:
        if not t.is_income:
            category_totals[t.transaction_type] = \
                category_totals.get(t.transaction_type, 0) + t.amount

    return {
        'income':          income,
        'expense':         expense,
        'balance':         balance,
        'category_totals': category_totals,
        'transactions':    txs,
    }


def get_monthly_trend(family_id, months: int = 6) -> list:
    """過去 N ヶ月のトレンドデータ"""
    today  = date.today()
    result = []
    for i in range(months - 1, -1, -1):
        d       = (date(today.year, today.month, 1) - timedelta(days=i * 28)).replace(day=1)
        summary = get_monthly_summary(family_id, d.year, d.month)
        result.append({
            'label':   f'{d.year}/{d.month:02d}',
            'income':  summary['income'],
            'expense': summary['expense'],
            'balance': summary['balance'],
        })
    return result


def detect_financial_signals(trend_data: list) -> list:
    """赤字・黒字回復の兆候を検出"""
    signals = []
    if len(trend_data) < 2:
        return signals

    last = trend_data[-1]
    prev = trend_data[-2]

    if last['balance'] < 0 and prev['balance'] < 0:
        signals.append({
            'type':    'danger',
            'icon':    '⚠️',
            'message': f'2ヶ月連続で赤字です。今月の残高: {last["balance"]:,}円',
        })
    elif last['balance'] > prev['balance'] and prev['balance'] < 0:
        diff = last['balance'] - prev['balance']
        signals.append({
            'type':    'warning',
            'icon':    '📈',
            'message': f'先月より{diff:,}円改善しています。このままがんばりましょう！',
        })
    elif last['balance'] > 0 and prev['balance'] > 0:
        signals.append({
            'type':    'success',
            'icon':    '✅',
            'message': f'2ヶ月連続黒字！今月の黒字: {last["balance"]:,}円',
        })

    if prev['expense'] > 0 and last['expense'] > prev['expense'] * 1.3:
        signals.append({
            'type':    'warning',
            'icon':    '💸',
            'message': f'先月より支出が30%以上増加しています（{last["expense"]:,}円）',
        })

    return signals


def _get_recent_transactions(family_id, limit: int = 10) -> list[_TxProxy]:
    """最新取引を件数指定で取得"""
    f_id = _family_id(family_id)

    user_docs = fs_db.collection('users').where('family_id', '==', f_id).stream()
    user_map  = {doc.id: doc.to_dict() for doc in user_docs}

    tx_docs = fs_db.collection('transactions') \
                   .where('family_id', '==', f_id) \
                   .stream()

    all_txs = []
    for doc in tx_docs:
        d       = doc.to_dict()
        d['id'] = doc.id
        all_txs.append(_TxProxy(d, user_map))

    all_txs.sort(key=lambda t: t.transaction_date, reverse=True)
    return all_txs[:limit]


# ------------------------------------------------------------------ #
# ルート
# ------------------------------------------------------------------ #

@dashboard_bp.route('/')
@login_required
def index():
    today = date.today()
    year  = int(request.args.get('year',  today.year))
    month = int(request.args.get('month', today.month))

    family_id = current_user.family_id
    summary   = get_monthly_summary(family_id, year, month)
    trend     = get_monthly_trend(family_id, 6)
    signals   = detect_financial_signals(trend)

    recent_transactions = _get_recent_transactions(family_id, limit=10)

    # 次の給料日まで（25日を給料日と想定）
    payday = date(today.year, today.month, 25)
    if today.day > 25:
        next_month = today.month + 1 if today.month < 12 else 1
        next_year  = today.year if today.month < 12 else today.year + 1
        payday = date(next_year, next_month, 25)
    days_to_payday = (payday - today).days

    # 前月・次月ナビ
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year_nav, next_month_nav = year + 1, 1
    else:
        next_year_nav, next_month_nav = year, month + 1

    return render_template(
        'dashboard.html',
        summary=summary,
        trend=trend,
        signals=signals,
        recent_transactions=recent_transactions,
        days_to_payday=days_to_payday,
        payday=payday,
        current_year=year,
        current_month=month,
        prev_year=prev_year,     prev_month=prev_month,
        next_year=next_year_nav, next_month=next_month_nav,
        type_labels=TRANSACTION_TYPE_LABELS,
        type_colors=TRANSACTION_TYPE_COLORS,
        today=today,
    )


@dashboard_bp.route('/api/chart-data')
@login_required
def chart_data():
    """グラフ用データ API"""
    family_id = current_user.family_id
    today = date.today()
    year  = int(request.args.get('year',  today.year))
    month = int(request.args.get('month', today.month))

    summary = get_monthly_summary(family_id, year, month)
    trend   = get_monthly_trend(family_id, 6)

    pie_data = {
        'labels': [TRANSACTION_TYPE_LABELS.get(k, k) for k in summary['category_totals']],
        'values': list(summary['category_totals'].values()),
        'colors': [TRANSACTION_TYPE_COLORS.get(k, '#94a3b8') for k in summary['category_totals']],
    }

    bar_data = {
        'labels':  [t['label']   for t in trend],
        'income':  [t['income']  for t in trend],
        'expense': [t['expense'] for t in trend],
        'balance': [t['balance'] for t in trend],
    }

    return jsonify({'pie': pie_data, 'bar': bar_data})