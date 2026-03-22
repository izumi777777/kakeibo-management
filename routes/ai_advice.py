"""AIアドバイスルート - Firestore 対応版"""

import os, json
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta

from firebase_config import fs_db

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')

PAYDAY = 25


# ------------------------------------------------------------------ #
# ヘルパー
# ------------------------------------------------------------------ #

def _family_id(raw):
    try:
        return int(raw)
    except Exception:
        return raw


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


# ------------------------------------------------------------------ #
# Firestore からアドバイス履歴を取得
# ------------------------------------------------------------------ #

def _get_advices(family_id, limit: int = 10) -> list:
    f_id = _family_id(family_id)
    docs = fs_db.collection('ai_advices') \
                .where('family_id', '==', f_id) \
                .stream()

    advices = []
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        # created_at を datetime に統一
        ca = d.get('created_at')
        if isinstance(ca, str):
            try:
                d['created_at'] = datetime.fromisoformat(ca).replace(tzinfo=None)
            except Exception:
                d['created_at'] = datetime.now()
        elif isinstance(ca, datetime):
            d['created_at'] = ca.replace(tzinfo=None)
        else:
            d['created_at'] = datetime.now()
        advices.append(d)

    # 降順ソート・件数制限
    advices.sort(
        key=lambda x: x['created_at'].replace(tzinfo=None),
        reverse=True
    )
    return advices[:limit]


def _save_advice(family_id, advice_text: str, advice_type: str) -> str:
    """Firestore に保存して doc_id を返す"""
    f_id = _family_id(family_id)
    _, ref = fs_db.collection('ai_advices').add({
        'family_id':   f_id,
        'advice_text': advice_text,
        'advice_type': advice_type,
        'created_at':  datetime.now(),
    })
    return ref.id


# ------------------------------------------------------------------ #
# Firestore から家計コンテキストを構築
# ------------------------------------------------------------------ #

def build_cycle_context(family_id, cycle_start: date) -> dict:
    """給料日サイクルベースの AI 用データを Firestore から構築"""
    f_id       = _family_id(family_id)
    cycle_end  = get_cycle_end(cycle_start)
    today      = date.today()
    start_iso  = cycle_start.isoformat()
    end_iso    = cycle_end.isoformat()

    # 実績取引
    tx_docs = fs_db.collection('transactions') \
                   .where('family_id', '==', f_id) \
                   .where('transaction_date', '>=', start_iso) \
                   .where('transaction_date', '<=', end_iso) \
                   .stream()

    txs = [doc.to_dict() for doc in tx_docs]
    income  = sum(t.get('amount', 0) for t in txs if t.get('is_income'))
    expense = sum(t.get('amount', 0) for t in txs if not t.get('is_income'))

    # カテゴリ別実績
    cat_actual = {}
    for t in txs:
        if not t.get('is_income'):
            label = t.get('transaction_type', 'other')
            cat_actual[label] = cat_actual.get(label, 0) + t.get('amount', 0)

    # 予定支出
    planned_docs = fs_db.collection('planned_expenses') \
                        .where('family_id', '==', f_id) \
                        .where('cycle_start', '==', start_iso) \
                        .stream()

    planned = [doc.to_dict() for doc in planned_docs]
    planned_undone = [
        (p.get('description', ''), p.get('amount', 0), p.get('transaction_type', ''))
        for p in planned if not p.get('is_done')
    ]
    planned_done   = [
        (p.get('description', ''), p.get('amount', 0))
        for p in planned if p.get('is_done')
    ]
    planned_total = sum(p.get('amount', 0) for p in planned if not p.get('is_done'))

    # 残高・日数計算
    forecast_balance = income - expense - planned_total
    next_payday      = cycle_end + timedelta(days=1)
    days_remaining   = max(0, (next_payday - today).days)
    daily_budget     = forecast_balance // days_remaining if days_remaining > 0 else 0

    # 過去2サイクルの履歴
    history = []
    cs = cycle_start
    for _ in range(2):
        prev_end   = cs - timedelta(days=1)
        prev_start = get_cycle_start(prev_end)
        past_docs  = fs_db.collection('transactions') \
                          .where('family_id', '==', f_id) \
                          .where('transaction_date', '>=', prev_start.isoformat()) \
                          .where('transaction_date', '<=', prev_end.isoformat()) \
                          .stream()
        past_txs = [doc.to_dict() for doc in past_docs]
        history.append({
            'period':  f'{prev_start.strftime("%Y/%m/%d")}〜{prev_end.strftime("%Y/%m/%d")}',
            'income':  sum(t.get('amount', 0) for t in past_txs if t.get('is_income')),
            'expense': sum(t.get('amount', 0) for t in past_txs if not t.get('is_income')),
        })
        cs = prev_start

    return {
        'サイクル期間':       f'{start_iso.replace("-","/")} 〜 {end_iso.replace("-","/")}',
        '今日':               today.strftime('%Y/%m/%d'),
        '給料日まで残り':     f'{days_remaining}日',
        '実績収入':           income,
        '実績支出':           expense,
        'カテゴリ別実績支出': cat_actual,
        '未払い予定支出':     [f'{d}（{c}）¥{a:,}' for d, a, c in planned_undone],
        '未払い予定支出合計': planned_total,
        '支払済み予定支出':   [f'{d} ¥{a:,}' for d, a in planned_done],
        '予測残高':           forecast_balance,
        '1日あたり使える金額': daily_budget,
        '過去2サイクルの履歴': history,
    }


# ------------------------------------------------------------------ #
# AI 呼び出し
# ------------------------------------------------------------------ #

def get_ai_advice(context: dict, advice_type: str, family_id=None) -> str:
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
    fb    = ctx.get('予測残高', 0)
    daily = ctx.get('1日あたり使える金額', 0)
    days  = ctx.get('給料日まで残り', '?')
    undone = ctx.get('未払い予定支出合計', 0)
    status = f'✅ 黒字（¥{fb:,}）' if fb >= 0 else f'⚠️ 赤字見込み（¥{fb:,}）'

    return f"""## 📊 給料日サイクル 家計レポート

**{ctx.get('サイクル期間', '')}**

### 今サイクルの総評
現在の予測残高は **{status}** です。
給料日まで残り **{days}**、1日あたり **¥{daily:,}** の範囲で使えます。

- 実績収入：¥{ctx.get('実績収入', 0):,}
- 実績支出：¥{ctx.get('実績支出', 0):,}
- 未払い予定支出：¥{undone:,}
- **予測残高：¥{fb:,}**

### ⚠️ 注意点
{'予定支出を含めると赤字になる見込みです。支出を抑えましょう。' if fb < 0 else '現時点では問題ありません。予定支出の支払い管理を忘れずに。'}

### 💡 節約アクション（残り{days}）
1. 食費は週単位で予算を決めてまとめ買いを活用する
2. サブスクリプションの不要なものを見直す
3. 外食を週1回減らすと約3,000〜5,000円の節約になります

### 📈 来月サイクルへ
毎月繰り返す固定費は「毎月繰り返す」にチェックを入れておくと自動で次サイクルに追加されます。

> ⚙️ .env に AZURE_OPENAI_API_KEY / AZURE_OPENAI_ENDPOINT を設定するとAzure OpenAIによる本格アドバイスが利用できます。"""


# ------------------------------------------------------------------ #
# ルート
# ------------------------------------------------------------------ #

@ai_bp.route('/')
@login_required
def index():
    today = date.today()
    cycle_start_str = request.args.get('cycle_start')
    if cycle_start_str:
        cycle_start = datetime.strptime(cycle_start_str, '%Y-%m-%d').date()
    else:
        cycle_start = get_cycle_start(today)

    advices = _get_advices(current_user.family_id, limit=10)

    return render_template(
        'ai_advice.html',
        advices=advices,
        current_year=today.year,
        current_month=today.month,
        default_cycle_start=cycle_start.strftime('%Y-%m-%d'),
        cycle_label=(
            f'{cycle_start.strftime("%Y/%m/%d")} 〜 '
            f'{get_cycle_end(cycle_start).strftime("%Y/%m/%d")}'
        ),
    )


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
    context     = build_cycle_context(current_user.family_id, cycle_start)

    try:
        text   = get_ai_advice(context, advice_type, family_id=current_user.family_id)
        doc_id = _save_advice(current_user.family_id, text, advice_type)
        return jsonify({'success': True, 'advice': text, 'id': doc_id})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@ai_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    """家計データを文脈にしてユーザーの質問に回答する"""
    data            = request.get_json()
    messages_in     = data.get('messages', [])
    cycle_start_str = data.get('cycle_start')

    today = date.today()
    if cycle_start_str:
        cycle_start = datetime.strptime(cycle_start_str, '%Y-%m-%d').date()
    else:
        cycle_start = get_cycle_start(today)

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
        return jsonify({'success': True,
                        'answer': '⚙️ AZURE_OPENAI_API_KEY を設定するとチャット機能が使えます。'})

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
                *messages_in,
            ],
            max_tokens=800,
            temperature=0.7,
        )
        return jsonify({'success': True, 'answer': response.choices[0].message.content})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500