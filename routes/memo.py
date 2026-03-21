"""メモ・買い物リストルート - Firestore 完全対応版"""

import os, json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta
from food_data2 import FOOD_ITEMS, CATEGORIES

# firebase_config から Firestore インスタンスをインポート
from firebase_config import fs_db

memo_bp = Blueprint('memo', __name__, url_prefix='/memo')

PAYDAY = 25

# 給料日サイクルの週定義
WEEK_LABELS = {
    1: '第1週（25〜31日）',
    2: '第2週（1〜7日）',
    3: '第3週（8〜14日）',
    4: '第4週（15〜24日）',
}

def _current_week() -> int:
    day = date.today().day
    if day >= 25: return 1
    if day <= 7:  return 2
    if day <= 14: return 3
    return 4

def _get_week_budgets(food_budget: int) -> dict:
    base = food_budget // 4
    return {
        1: base, 2: base, 3: base,
        4: food_budget - base * 3,
    }

def _get_cycle_range(target: date = None):
    today = target or date.today()
    if today.day >= PAYDAY:
        cycle_start = today.replace(day=PAYDAY)
    elif today.month == 1:
        cycle_start = date(today.year - 1, 12, PAYDAY)
    else:
        cycle_start = date(today.year, today.month - 1, PAYDAY)

    if cycle_start.month == 12:
        cycle_end = date(cycle_start.year + 1, 1, 24)
    else:
        cycle_end = date(cycle_start.year, cycle_start.month + 1, 24)
    return cycle_start, cycle_end


def _to_datetime(value) -> datetime:
    """
    Firestore から返ってくる値を datetime に統一する。
    - すでに datetime オブジェクト → そのまま返す
    - ISO形式の文字列             → パースして返す
    - None / 不明な型             → 現在時刻を返す
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now()


def _get_food_budget_status(family_id) -> dict:
    cycle_start, cycle_end = _get_cycle_range()
    start_iso = cycle_start.isoformat()
    end_iso   = cycle_end.isoformat()

    try:
        f_id = int(family_id)
    except Exception:
        f_id = family_id

    # Transactions から食費実績を集計
    tx_docs = fs_db.collection('transactions') \
                   .where('family_id', '==', f_id) \
                   .stream()

    food_spent = 0
    for doc in tx_docs:
        d = doc.to_dict()
        if (d.get('transaction_type') == 'food'
                and not d.get('is_income')
                and start_iso <= d.get('transaction_date', '') <= end_iso):
            food_spent += d.get('amount', 0)

    # Budgets から食費予算を取得（なければデフォルト 50,000 円）
    budget_docs = fs_db.collection('budgets') \
                       .where('family_id', '==', f_id) \
                       .where('transaction_type', '==', 'food') \
                       .where('cycle_start', '==', start_iso) \
                       .limit(1).get()

    food_budget = (budget_docs[0].to_dict().get('amount', 50000)
                   if budget_docs else 50000)

    return {
        'cycle_start':    cycle_start.strftime('%Y/%m/%d'),
        'cycle_end':      cycle_end.strftime('%Y/%m/%d'),
        'food_budget':    food_budget,
        'food_spent':     food_spent,
        'food_remaining': food_budget - food_spent,
    }


# ------------------------------------------------------------------ #
# メインルート
# ------------------------------------------------------------------ #

@memo_bp.route('/')
@login_required
def index():
    selected_week = int(request.args.get('week', _current_week()))
    f_id = current_user.family_id
    try:
        search_f_id = int(f_id)
    except Exception:
        search_f_id = f_id

    # 1. その家族に属する全ユーザーを取得（表示名マッピング用）
    user_docs = fs_db.collection('users').where('family_id', '==', search_f_id).stream()
    user_map  = {doc.id: doc.to_dict() for doc in user_docs}

    # 2. メモを取得
    memo_docs = fs_db.collection('memos') \
                     .where('family_id', '==', search_f_id) \
                     .where('week', '==', selected_week) \
                     .stream()

    shopping_all = []
    notes        = []

    for doc in memo_docs:
        m       = doc.to_dict()
        m['id'] = doc.id

        # ユーザー情報を紐付け（テンプレートは item.user.display_name を参照）
        u_id      = str(m.get('user_id', ''))
        m['user'] = user_map.get(u_id, {'display_name': '不明'})

        # ★ created_at を必ず datetime オブジェクトに変換（strftime 対応）
        m['created_at'] = _to_datetime(m.get('created_at'))

        if m.get('memo_type') == 'shopping':
            shopping_all.append(m)
        elif m.get('memo_type') == 'note':
            notes.append(m)

    # カテゴリ別振り分け
    food_list  = [m for m in shopping_all if m.get('item_category') == 'food']
    daily_list = [m for m in shopping_all if m.get('item_category') == 'daily']
    other_list = [m for m in shopping_all if m.get('item_category') == 'other']

    # 金額集計
    total_price  = sum(m.get('price', 0) for m in shopping_all)
    done_price   = sum(m.get('price', 0) for m in shopping_all if m.get('is_done'))
    undone_price = total_price - done_price

    budget_status = _get_food_budget_status(f_id)
    week_budgets  = _get_week_budgets(budget_status['food_budget'])

    return render_template(
        'memo.html',
        food_list=food_list,
        daily_list=daily_list,
        other_list=other_list,
        shopping_all=shopping_all,
        notes=notes,
        selected_week=selected_week,
        week_labels=WEEK_LABELS,
        week_budgets=week_budgets,
        total_price=total_price,
        done_price=done_price,
        undone_price=undone_price,
        current_week=_current_week(),
    )


@memo_bp.route('/add', methods=['POST'])
@login_required
def add():
    content       = request.form.get('content', '').strip()
    memo_type     = request.form.get('memo_type', 'shopping')
    week          = int(request.form.get('week', _current_week()))
    item_category = request.form.get('item_category', 'other')
    price         = int(request.form.get('price', 0) or 0)

    if not content:
        flash('内容を入力してください。', 'warning')
        return redirect(url_for('memo.index', week=week))

    f_id = current_user.family_id
    try:
        f_id = int(f_id)
    except Exception:
        pass

    # ★ datetime オブジェクトで保存（読み出し時に変換不要になる）
    fs_db.collection('memos').add({
        'family_id':     f_id,
        'user_id':       current_user.id,
        'content':       content,
        'memo_type':     memo_type,
        'week':          week,
        'item_category': item_category,
        'price':         price,
        'is_done':       False,
        'created_at':    datetime.now(),  # ← isoformat() ではなく datetime オブジェクト
    })
    flash('追加しました。', 'success')
    return redirect(url_for('memo.index', week=week))


@memo_bp.route('/toggle/<memo_id>', methods=['POST'])
@login_required
def toggle(memo_id):
    ref = fs_db.collection('memos').document(str(memo_id))
    doc = ref.get()
    if doc.exists:
        new_status = not doc.to_dict().get('is_done', False)
        ref.update({'is_done': new_status})
        return jsonify({'success': True, 'is_done': new_status})
    return jsonify({'success': False}), 404


@memo_bp.route('/update-price/<memo_id>', methods=['POST'])
@login_required
def update_price(memo_id):
    data  = request.get_json()
    price = int(data.get('price', 0) or 0)
    fs_db.collection('memos').document(str(memo_id)).update({'price': price})
    return jsonify({'success': True, 'price': price})


@memo_bp.route('/delete/<memo_id>', methods=['POST'])
@login_required
def delete(memo_id):
    fs_db.collection('memos').document(str(memo_id)).delete()
    return jsonify({'success': True})


@memo_bp.route('/food-budget', methods=['POST'])
@login_required
def update_food_budget():
    data   = request.get_json()
    amount = int(data.get('amount', 0))
    if amount <= 0:
        return jsonify({'success': False, 'message': '予算は1円以上で入力してください'}), 400

    cycle_start, _ = _get_cycle_range()
    start_iso = cycle_start.isoformat()

    f_id = current_user.family_id
    try:
        f_id = int(f_id)
    except Exception:
        pass

    query = fs_db.collection('budgets') \
                 .where('family_id', '==', f_id) \
                 .where('transaction_type', '==', 'food') \
                 .where('cycle_start', '==', start_iso) \
                 .limit(1).get()

    if query:
        query[0].reference.update({'amount': amount})
    else:
        fs_db.collection('budgets').add({
            'family_id':        f_id,
            'transaction_type': 'food',
            'amount':           amount,
            'cycle_start':      start_iso,
            'created_at':       datetime.now(),
        })
    return jsonify({'success': True, 'amount': amount})


# ------------------------------------------------------------------ #
# 食品リスト・買い物プラン関連ルート
# ------------------------------------------------------------------ #

@memo_bp.route('/food-items')
@login_required
def food_items():
    """食品マスターをカテゴリ別に返す API"""
    category = request.args.get('category')
    items = [i for i in FOOD_ITEMS if i['category'] == category] if category else FOOD_ITEMS
    return jsonify({'items': items, 'categories': CATEGORIES})


@memo_bp.route('/shopping-plan', methods=['GET'])
@login_required
def shopping_plan():
    """食品リスト選択 + AIアドバイス画面"""
    budget_status = _get_food_budget_status(current_user.family_id)

    items_by_category = {}
    for cat in CATEGORIES:
        items_by_category[cat] = [i for i in FOOD_ITEMS if i['category'] == cat]

    return render_template(
        'shopping_plan.html',
        items_by_category=items_by_category,
        categories=CATEGORIES,
        budget_status=budget_status,
    )


@memo_bp.route('/shopping-plan/advice', methods=['POST'])
@login_required
def shopping_plan_advice():
    """選択した食品リストをもとに AI アドバイスを生成"""
    data               = request.get_json()
    selected_items_req = data.get('selected_items', [])
    override_map       = {item['id']: item for item in selected_items_req}

    selected_items = []
    for item in FOOD_ITEMS:
        if item['id'] in override_map:
            merged = dict(item)
            merged['price_basia'] = override_map[item['id']].get('price', item['price_basia'])
            merged['quantity']    = override_map[item['id']].get('quantity', item['quantity'])
            selected_items.append(merged)

    budget_status = _get_food_budget_status(current_user.family_id)
    advice = _ai_shopping_plan(budget_status, selected_items)
    total  = sum(
        i['price_basia'] * i['quantity']
        for i in selected_items if i.get('price_basia')
    )
    return jsonify({
        'success':       True,
        'advice':        advice,
        'total':         total,
        'budget_status': budget_status,
    })


@memo_bp.route('/shopping-plan/chat', methods=['POST'])
@login_required
def shopping_plan_chat():
    """買い物プラン画面のチャット"""
    data               = request.get_json()
    messages_in        = data.get('messages', [])
    selected_items_req = data.get('selected_items', [])
    override_map       = {item['id']: item for item in selected_items_req}

    selected_items = []
    for item in FOOD_ITEMS:
        if item['id'] in override_map:
            merged = dict(item)
            merged['price_basia'] = override_map[item['id']].get('price', item['price_basia'])
            merged['quantity']    = override_map[item['id']].get('quantity', item['quantity'])
            selected_items.append(merged)

    budget_status = _get_food_budget_status(current_user.family_id)
    total = sum(
        i['price_basia'] * i['quantity']
        for i in selected_items if i.get('price_basia')
    )

    from family_utils import family_profile_prompt
    system_prompt = f"""あなたは家計管理と食材選びの専門アドバイザーです。
{family_profile_prompt(current_user.family_id)}

以下のユーザーの買い物状況を踏まえて、質問に日本語で答えてください。
回答は具体的・簡潔に。マークダウンと絵文字を使ってOKです。

## 今サイクルの食費状況
- 食費予算: ¥{budget_status['food_budget']:,}
- 使用済み: ¥{budget_status['food_spent']:,}
- 残り予算: ¥{budget_status['food_remaining']:,}
"""

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
        response = client.chat.completions.create(
            model=os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o'),
            messages=[
                {'role': 'system', 'content': system_prompt},
                *messages_in,
            ],
            max_tokens=600,
            temperature=0.7,
        )
        return jsonify({'success': True, 'answer': response.choices[0].message.content})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@memo_bp.route('/shopping-plan/add-to-memo', methods=['POST'])
@login_required
def add_food_to_memo():
    """選択した食品を買い物メモに一括追加"""
    data               = request.get_json()
    selected_items_req = data.get('selected_items', [])
    week               = int(data.get('week', _current_week()))

    f_id = current_user.family_id
    try:
        f_id = int(f_id)
    except Exception:
        pass

    added = 0
    for item_req in selected_items_req:
        base_item = next((i for i in FOOD_ITEMS if i['id'] == item_req['id']), None)
        if not base_item:
            continue

        qty           = item_req.get('quantity', base_item['quantity'])
        price         = item_req.get('price', base_item['price_basia'] or 0)
        content       = f"{base_item['name']}（{base_item['amount']}）× {qty}"
        item_category = 'daily' if base_item['category'] == '日用品' else 'food'

        fs_db.collection('memos').add({
            'family_id':     f_id,
            'user_id':       current_user.id,
            'content':       content,
            'memo_type':     'shopping',
            'item_category': item_category,
            'week':          week,
            'price':         price * qty,
            'is_done':       False,
            'created_at':    datetime.now(),  # ★ datetime オブジェクト
        })
        added += 1

    return jsonify({'success': True, 'added': added})


# ------------------------------------------------------------------ #
# AI ヘルパー（内部関数）
# ------------------------------------------------------------------ #

def _ai_shopping_plan(budget_status: dict, selected_items: list) -> str:
    """予算状況と食品候補リストから AI が買い物プランを提案"""
    api_key  = os.environ.get('AZURE_OPENAI_API_KEY', '')
    endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT', '')

    if not api_key or not endpoint:
        return _mock_shopping_plan(budget_status, selected_items)

    from openai import AzureOpenAI
    client = AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=os.environ.get('AZURE_OPENAI_API_VERSION', '2024-12-01-preview'),
    )
    deployment = os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
    items_text = json.dumps(selected_items, ensure_ascii=False, indent=2)

    prompt = f"""あなたは家計管理と食材選びの専門家です。
以下の情報をもとに、今月25日の買い物プランをアドバイスしてください。

## 今サイクルの食費状況
- 食費予算: ¥{budget_status['food_budget']:,}
- すでに使った食費: ¥{budget_status['food_spent']:,}
- 残り予算: ¥{budget_status['food_remaining']:,}

## 買い物候補リスト
{items_text}

以下の観点で日本語でアドバイスしてください（マークダウン・絵文字使用可）：

## 1. 🛒 今月の推奨買い物リスト
残り予算 ¥{budget_status['food_remaining']:,} の範囲で、優先度の高い商品を具体的に。

## 2. ✂️ 今月は控えめにしたい商品
予算が少ない場合、後回しにできるものの提案。

## 3. 💡 節約ポイント
まとめ買いや代替品など、具体的な節約テクニック。"""

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": "あなたは家計管理と買い物の専門アドバイザーです。"},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=1200,
        temperature=0.7,
    )
    return response.choices[0].message.content


def _mock_shopping_plan(budget_status: dict, selected_items: list) -> str:
    remaining    = budget_status['food_remaining']
    total_if_all = sum(
        item['price_basia'] * item['quantity']
        for item in selected_items if item.get('price_basia')
    )
    status = '✅ 予算内' if total_if_all <= remaining else '⚠️ 予算オーバー'

    return f"""## 🛒 今月の買い物プラン

**食費残り予算: ¥{remaining:,}**
全候補を購入した場合の合計: ¥{total_if_all:,} → {status}

### 推奨アクション
{'候補リストの全購入が可能です。まとめ買いで効率よく！' if total_if_all <= remaining else f'¥{total_if_all - remaining:,} オーバーのため、優先度の低い商品を減らしてください。'}

### 💡 節約ポイント
1. 肉類はまとめ買いして冷凍保存
2. 野菜は季節のものを選ぶと安く栄養豊富
3. 冷凍食品は特売日にまとめて購入

> ⚙️ AZURE_OPENAI_API_KEY を設定するとAIによる詳細プランが利用できます。"""