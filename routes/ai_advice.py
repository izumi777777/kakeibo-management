"""AIアドバイスルート（給料日サイクル対応版）"""

import os, json
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, AiAdvice, Transaction, PlannedExpense, TRANSACTION_TYPE_LABELS
from sqlalchemy import extract
from datetime import date, datetime, timedelta

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')

PAYDAY = 25

def get_cycle_start(target_date: date) -> date:
    if target_date.day >= PAYDAY:
        return target_date.replace(day=PAYDAY)
    if target_date.month == 1:
        return date(target_date.year - 1, 12, PAYDAY)
    return date(target_date.year, target_date.month - 1, PAYDAY)

def get_cycle_end(cycle_start: date) -> date:
    if cycle_start.month == 12:
        return date(cycle_start.year + 1, 1, 24)
    return date(cycle_start.year, cycle_start.month + 1, 24)


def build_cycle_context(family_id: int, cycle_start: date) -> dict:
    """給料日サイクルベースのAI用データ構築"""
    cycle_end   = get_cycle_end(cycle_start)
    today       = date.today()

    # 実績
    txs = Transaction.query.filter(
        Transaction.family_id == family_id,
        Transaction.transaction_date >= cycle_start,
        Transaction.transaction_date <= cycle_end,
    ).all()
    income  = sum(t.amount for t in txs if t.is_income)
    expense = sum(t.amount for t in txs if not t.is_income)

    # カテゴリ別実績
    cat_actual = {}
    for t in txs:
        if not t.is_income:
            label = TRANSACTION_TYPE_LABELS.get(t.transaction_type, t.transaction_type)
            cat_actual[label] = cat_actual.get(label, 0) + t.amount

    # 予定支出
    planned = PlannedExpense.query.filter_by(
        family_id=family_id, cycle_start=cycle_start
    ).all()
    planned_undone = [(p.description, p.amount, TRANSACTION_TYPE_LABELS.get(p.transaction_type,'')) 
                      for p in planned if not p.is_done]
    planned_done   = [(p.description, p.amount) for p in planned if p.is_done]
    planned_total  = sum(p.amount for p in planned if not p.is_done)

    forecast_balance = income - expense - planned_total
    next_payday      = cycle_end + timedelta(days=1)
    days_remaining   = max(0, (next_payday - today).days)
    daily_budget     = forecast_balance // days_remaining if days_remaining > 0 else 0

    # 過去2サイクルの実績
    history = []
    cs = cycle_start
    for i in range(1, 3):
        prev_end   = cs - timedelta(days=1)
        prev_start = get_cycle_start(prev_end)
        past_txs   = Transaction.query.filter(
            Transaction.family_id == family_id,
            Transaction.transaction_date >= prev_start,
            Transaction.transaction_date <= prev_end,
        ).all()
        history.append({
            'period': f'{prev_start.strftime("%Y/%m/%d")}〜{prev_end.strftime("%Y/%m/%d")}',
            'income':  sum(t.amount for t in past_txs if t.is_income),
            'expense': sum(t.amount for t in past_txs if not t.is_income),
        })
        cs = prev_start

    return {
        'サイクル期間': f'{cycle_start.strftime("%Y/%m/%d")}〜{cycle_end.strftime("%Y/%m/%d")}',
        '今日': today.strftime('%Y/%m/%d'),
        '給料日まで残り': f'{days_remaining}日',
        '実績収入': income,
        '実績支出': expense,
        'カテゴリ別実績支出': cat_actual,
        '未払い予定支出': [f'{d}（{c}）¥{a:,}' for d,a,c in planned_undone],
        '未払い予定支出合計': planned_total,
        '支払済み予定支出': [f'{d} ¥{a:,}' for d,a in planned_done],
        '予測残高': forecast_balance,
        '1日あたり使える金額': daily_budget,
        '過去2サイクルの履歴': history,
    }


def get_ai_advice(context: dict, advice_type: str, family_id: int = None) -> str:
    """Azure OpenAI を使ってアドバイスを生成する"""
    from family_utils import family_profile_prompt
    family_section = family_profile_prompt(family_id) if family_id else ''

    api_key  = os.environ.get('AZURE_OPENAI_API_KEY', '')
    endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT', '')

    if not api_key or not endpoint:
        return _mock_advice(context, advice_type)

    from openai import AzureOpenAI
    client = AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=os.environ.get('AZURE_OPENAI_API_VERSION', '2024-12-01-preview'),
    )
    deployment = os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')

    # システムプロンプトに家族構成を固定注入
    system_prompt = f"""あなたは家計管理の専門アドバイザーです。データに基づいた具体的なアドバイスをしてください。

{family_section}"""

    days = context.get('給料日まで残り', '?')
    prompts = {
        'cycle_review': f"""以下の給料日サイクルの家計データを分析してください。

## データ
{json.dumps(context, ensure_ascii=False, indent=2)}

以下の観点で日本語でアドバイスしてください（マークダウン・絵文字使用可）：

## 1. 📊 今サイクルの総評
収支の状況、予測残高についての評価

## 2. ⚠️ 注意点・リスク
未払い予定支出・支出ペースの問題点

## 3. 💡 残り{days}でできる節約アクション
家族構成を踏まえ、具体的な金額を交えた3つの提案

## 4. 📈 来月サイクルへの改善提案
次の給料日までにやっておくこと""",

        'saving_tip': f"""以下の家計データから、家族構成を踏まえた節約テクニックを3つ提案してください。
{json.dumps(context, ensure_ascii=False, indent=2)}
1つ当たり節約できる金額の目安も含めて、具体的に日本語で。""",

        'forecast': f"""以下の家計データから、来月の給料日サイクルの収支を予測してください。
{json.dumps(context, ensure_ascii=False, indent=2)}
楽観・標準・悲観の3シナリオと、それぞれの達成条件を日本語で。""",
    }

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',   'content': prompts.get(advice_type, prompts['cycle_review'])},
        ],
        max_tokens=1500,
        temperature=0.7,
    )
    return response.choices[0].message.content


def _mock_advice(ctx: dict, advice_type: str) -> str:
    fb = ctx.get('予測残高', 0)
    daily = ctx.get('1日あたり使える金額', 0)
    days  = ctx.get('給料日まで残り', '?')
    undone = ctx.get('未払い予定支出合計', 0)

    status = f'✅ 黒字（¥{fb:,}）' if fb >= 0 else f'⚠️ 赤字見込み（¥{fb:,}）'

    return f"""## 📊 給料日サイクル 家計レポート

**{ctx.get('サイクル期間','')}**

### 今サイクルの総評
現在の予測残高は **{status}** です。
給料日まで残り **{days}日**、1日あたり **¥{daily:,}** の範囲で使えます。

- 実績収入：¥{ctx.get('実績収入',0):,}
- 実績支出：¥{ctx.get('実績支出',0):,}
- 未払い予定支出：¥{undone:,}
- **予測残高：¥{fb:,}**

### ⚠️ 注意点
{'予定支出を含めると赤字になる見込みです。支出を抑えましょう。' if fb < 0 else '現時点では問題ありません。予定支出の支払い管理を忘れずに。'}

### 💡 節約アクション（残り{days}日）
1. 食費は週単位で予算を決めてまとめ買いを活用する
2. サブスクリプションの不要なものを見直す
3. 外食を週1回減らすと約3,000〜5,000円の節約になります

### 📈 来月サイクルへ
毎月繰り返す固定費は「毎月繰り返す」にチェックを入れておくと自動で次サイクルに追加されます。

> ⚙️ .env に AZURE_OPENAI_API_KEY / AZURE_OPENAI_ENDPOINT を設定するとAzure OpenAIによる本格アドバイスが利用できます。"""


@ai_bp.route('/')
@login_required
def index():
    today = date.today()
    cycle_start_str = request.args.get('cycle_start')
    if cycle_start_str:
        cycle_start = datetime.strptime(cycle_start_str, '%Y-%m-%d').date()
    else:
        cycle_start = get_cycle_start(today)

    advices = AiAdvice.query.filter_by(
        family_id=current_user.family_id
    ).order_by(AiAdvice.created_at.desc()).limit(10).all()

    return render_template(
        'ai_advice.html',
        advices=advices,
        current_year=today.year,
        current_month=today.month,
        default_cycle_start=cycle_start.strftime('%Y-%m-%d'),
        cycle_label=f'{cycle_start.strftime("%Y/%m/%d")} 〜 {get_cycle_end(cycle_start).strftime("%Y/%m/%d")}',
    )


@ai_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    """家計データを文脈にしてユーザーの質問に回答する"""
    data        = request.get_json()
    messages_in = data.get('messages', [])   # [{role, content}, ...]
    cycle_start_str = data.get('cycle_start')

    today = date.today()
    if cycle_start_str:
        cycle_start = datetime.strptime(cycle_start_str, '%Y-%m-%d').date()
    else:
        cycle_start = get_cycle_start(today)

    # 家計コンテキストをシステムプロンプトに埋め込む
    context = build_cycle_context(current_user.family_id, cycle_start)
    from family_utils import family_profile_prompt
    system_prompt = f"""あなたは家計管理の専門アドバイザーです。
{family_profile_prompt(current_user.family_id)}

以下のユーザーの今サイクルの家計データを踏まえて、質問に日本語で答えてください。
回答は具体的・簡潔に。マークダウンと絵文字を使ってOKです。

## 家計データ
{json.dumps(context, ensure_ascii=False, indent=2)}"""

    api_key  = os.environ.get('AZURE_OPENAI_API_KEY', '')
    endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT', '')

    if not api_key or not endpoint:
        return jsonify({'success': True, 'answer': '⚙️ AZURE_OPENAI_API_KEY を設定するとチャット機能が使えます。'})

    try:
        from openai import AzureOpenAI
        client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=os.environ.get('AZURE_OPENAI_API_VERSION', '2024-12-01-preview'),
        )
        deployment = os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')

        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {'role': 'system', 'content': system_prompt},
                *messages_in,   # アドバイス本文 + チャット履歴をそのまま渡す
            ],
            max_tokens=800,
            temperature=0.7,
        )
        answer = response.choices[0].message.content
        return jsonify({'success': True, 'answer': answer})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@ai_bp.route('/generate', methods=['POST'])
@login_required
def generate():
    today = date.today()
    cycle_start_str = request.form.get('cycle_start')
    if cycle_start_str:
        cycle_start = datetime.strptime(cycle_start_str, '%Y-%m-%d').date()
    else:
        cycle_start = get_cycle_start(today)

    advice_type = request.form.get('advice_type', 'cycle_review')
    context = build_cycle_context(current_user.family_id, cycle_start)

    try:
        text = get_ai_advice(context, advice_type, family_id=current_user.family_id)
        advice = AiAdvice(
            family_id=current_user.family_id,
            advice_text=text,
            advice_type=advice_type,
        )
        db.session.add(advice)
        db.session.commit()
        return jsonify({'success': True, 'advice': text, 'id': advice.id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500