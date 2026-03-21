"""ダッシュボードルート"""

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from models import db, Transaction, TRANSACTION_TYPE_LABELS, TRANSACTION_TYPE_COLORS
from sqlalchemy import func, extract
from datetime import date, datetime, timedelta
import calendar

dashboard_bp = Blueprint('dashboard', __name__)


def get_monthly_summary(family_id, year, month):
    """月次収支サマリーを取得"""
    txs = Transaction.query.filter(
        Transaction.family_id == family_id,
        extract('year',  Transaction.transaction_date) == year,
        extract('month', Transaction.transaction_date) == month
    ).all()

    income  = sum(t.amount for t in txs if t.is_income)
    expense = sum(t.amount for t in txs if not t.is_income)
    balance = income - expense

    # カテゴリ別集計
    category_totals = {}
    for t in txs:
        if not t.is_income:
            key = t.transaction_type
            category_totals[key] = category_totals.get(key, 0) + t.amount

    return {
        'income':           income,
        'expense':          expense,
        'balance':          balance,
        'category_totals':  category_totals,
        'transactions':     txs,
    }


def get_monthly_trend(family_id, months=6):
    """過去N ヶ月のトレンドデータ"""
    today  = date.today()
    result = []
    for i in range(months - 1, -1, -1):
        d = date(today.year, today.month, 1) - timedelta(days=i * 28)
        d = d.replace(day=1)
        summary = get_monthly_summary(family_id, d.year, d.month)
        result.append({
            'label':   f'{d.year}/{d.month:02d}',
            'income':  summary['income'],
            'expense': summary['expense'],
            'balance': summary['balance'],
        })
    return result


def detect_financial_signals(trend_data):
    """赤字・黒字回復の兆候を検出"""
    signals = []
    if len(trend_data) < 2:
        return signals

    last = trend_data[-1]
    prev = trend_data[-2]

    # 赤字が続いている
    if last['balance'] < 0 and prev['balance'] < 0:
        signals.append({
            'type':    'danger',
            'icon':    '⚠️',
            'message': f'2ヶ月連続で赤字です。今月の残高: {last["balance"]:,}円',
        })
    # 赤字から改善中
    elif last['balance'] > prev['balance'] and prev['balance'] < 0:
        diff = last['balance'] - prev['balance']
        signals.append({
            'type':    'warning',
            'icon':    '📈',
            'message': f'先月より{diff:,}円改善しています。このままがんばりましょう！',
        })
    # 黒字継続
    elif last['balance'] > 0 and prev['balance'] > 0:
        signals.append({
            'type':    'success',
            'icon':    '✅',
            'message': f'2ヶ月連続黒字！今月の黒字: {last["balance"]:,}円',
        })
    # 急激な支出増加
    if prev['expense'] > 0 and last['expense'] > prev['expense'] * 1.3:
        signals.append({
            'type':    'warning',
            'icon':    '💸',
            'message': f'先月より支出が30%以上増加しています（{last["expense"]:,}円）',
        })

    return signals


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

    # 最近の取引（10件）
    recent_transactions = Transaction.query.filter_by(
        family_id=family_id
    ).order_by(Transaction.transaction_date.desc()).limit(10).all()

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
        prev_year=prev_year,   prev_month=prev_month,
        next_year=next_year_nav, next_month=next_month_nav,
        type_labels=TRANSACTION_TYPE_LABELS,
        type_colors=TRANSACTION_TYPE_COLORS,
        today=today,
    )


@dashboard_bp.route('/api/chart-data')
@login_required
def chart_data():
    """グラフ用データAPI"""
    family_id = current_user.family_id
    today = date.today()
    year  = int(request.args.get('year',  today.year))
    month = int(request.args.get('month', today.month))

    summary = get_monthly_summary(family_id, year, month)
    trend   = get_monthly_trend(family_id, 6)

    # カテゴリ別円グラフ
    pie_data = {
        'labels': [TRANSACTION_TYPE_LABELS.get(k, k) for k in summary['category_totals']],
        'values': list(summary['category_totals'].values()),
        'colors': [TRANSACTION_TYPE_COLORS.get(k, '#94a3b8') for k in summary['category_totals']],
    }

    # 月次トレンド棒グラフ
    bar_data = {
        'labels':  [t['label']   for t in trend],
        'income':  [t['income']  for t in trend],
        'expense': [t['expense'] for t in trend],
        'balance': [t['balance'] for t in trend],
    }

    return jsonify({'pie': pie_data, 'bar': bar_data})