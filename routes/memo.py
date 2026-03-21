"""メモ・買い物リストルート（食品リスト・AIアドバイス対応版）"""

import os, json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Memo, Transaction, PlannedExpense, Budget
from datetime import date, timedelta
from food_data2 import FOOD_ITEMS, CATEGORIES

memo_bp = Blueprint('memo', __name__, url_prefix='/memo')

PAYDAY = 25

# 給料日サイクルの週定義（25日起算）
WEEK_LABELS = {
    1: '第1週（25〜31日）',
    2: '第2週（1〜7日）',
    3: '第3週（8〜14日）',
    4: '第4週（15〜24日）',
}

def _current_week() -> int:
    """今日が給料日サイクルの何週目かを返す"""
    day = date.today().day
    if day >= 25: return 1
    if day <= 7:  return 2
    if day <= 14: return 3
    return 4

def _get_week_budgets(food_budget: int) -> dict:
    """食費予算を4週に均等割り"""
    base = food_budget // 4
    return {
        1: base,
        2: base,
        3: base,
        4: food_budget - base * 3,  # 端数は第4週
    }

# ------------------------------------------------------------------ #
# ヘルパー：今サイクルの食費予算残高を計算
# ------------------------------------------------------------------ #
def _get_cycle_range(target: date = None):
    """今サイクルの開始日・終了日を返す"""
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


def _get_food_budget_status(family_id: int) -> dict:
    """今サイクルの食費実績・予算残高を返す（Budget テーブルから取得）"""
    from models import Budget
    cycle_start, cycle_end = _get_cycle_range()

    txs = Transaction.query.filter(
        Transaction.family_id == family_id,
        Transaction.transaction_date >= cycle_start,
        Transaction.transaction_date <= cycle_end,
    ).all()
    food_spent = sum(
        t.amount for t in txs
        if not t.is_income and t.transaction_type == 'food'
    )

    # Budget テーブルから食費予算を取得（なければデフォルト50,000円）
    budget_rec = Budget.query.filter_by(
        family_id=family_id,
        transaction_type='food',
        cycle_start=cycle_start,
    ).first()
    food_budget = budget_rec.amount if budget_rec else 50000

    return {
        'cycle_start':    cycle_start.strftime('%Y/%m/%d'),
        'cycle_end':      cycle_end.strftime('%Y/%m/%d'),
        'cycle_start_iso': cycle_start.isoformat(),
        'food_budget':    food_budget,
        'food_spent':     food_spent,
        'food_remaining': food_budget - food_spent,
    }


# ------------------------------------------------------------------ #
# AI：食品リストから今月の買い物プランを提案
# ------------------------------------------------------------------ #
def _ai_shopping_plan(budget_status: dict, selected_items: list[dict]) -> str:
    """予算状況と食品候補リストからAIが買い物プランを提案"""
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

## 買い物候補リスト（food_data.pyより）
{items_text}

以下の観点で日本語でアドバイスしてください（マークダウン・絵文字使用可）：

## 1. 🛒 今月の推奨買い物リスト
残り予算 ¥{budget_status['food_remaining']:,} の範囲で、優先度の高い商品を具体的に。
各商品の個数・金額も含めて合計予算内に収まるよう提案。

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


def _mock_shopping_plan(budget_status: dict, selected_items: list[dict]) -> str:
    remaining = budget_status['food_remaining']
    total_if_all = sum(
        item['price_basia'] * item['quantity']
        for item in selected_items
        if item.get('price_basia')
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


# ------------------------------------------------------------------ #
# 既存ルート（変更なし）
# ------------------------------------------------------------------ #
@memo_bp.route('/')
@login_required
def index():
    selected_week = int(request.args.get('week', _current_week()))

    # 選択週の買い物リスト（食品・日用品・その他）
    shopping_all = Memo.query.filter_by(
        family_id=current_user.family_id,
        memo_type='shopping',
        week=selected_week,
    ).order_by(Memo.is_done, Memo.created_at.desc()).all()

    food_list  = [m for m in shopping_all if m.item_category == 'food']
    daily_list = [m for m in shopping_all if m.item_category == 'daily']
    other_list = [m for m in shopping_all if m.item_category == 'other']

    # 合計金額（未完了・完了別）
    total_price    = sum(m.price for m in shopping_all if m.price)
    done_price     = sum(m.price for m in shopping_all if m.price and m.is_done)
    undone_price   = total_price - done_price

    # 週別予算
    budget_status  = _get_food_budget_status(current_user.family_id)
    week_budgets   = _get_week_budgets(budget_status['food_budget'])

    notes = Memo.query.filter_by(
        family_id=current_user.family_id, memo_type='note'
    ).order_by(Memo.created_at.desc()).all()

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

    memo = Memo(
        family_id=current_user.family_id,
        user_id=current_user.id,
        content=content,
        memo_type=memo_type,
        week=week,
        item_category=item_category,
        price=price,
    )
    db.session.add(memo)
    db.session.commit()
    flash('追加しました。', 'success')
    return redirect(url_for('memo.index', week=week))


@memo_bp.route('/update-price/<int:memo_id>', methods=['POST'])
@login_required
def update_price(memo_id):
    """買い物メモの金額を更新する"""
    memo = Memo.query.filter_by(
        id=memo_id, family_id=current_user.family_id
    ).first_or_404()
    data  = request.get_json()
    price = int(data.get('price', 0) or 0)
    memo.price = price
    db.session.commit()
    return jsonify({'success': True, 'price': price})



@login_required
def toggle(memo_id):
    memo = Memo.query.filter_by(
        id=memo_id, family_id=current_user.family_id
    ).first_or_404()
    memo.is_done = not memo.is_done
    db.session.commit()
    return jsonify({'success': True, 'is_done': memo.is_done})


@memo_bp.route('/delete/<int:memo_id>', methods=['POST'])
@login_required
def delete(memo_id):
    memo = Memo.query.filter_by(
        id=memo_id, family_id=current_user.family_id
    ).first_or_404()
    db.session.delete(memo)
    db.session.commit()
    return jsonify({'success': True})


@memo_bp.route('/shopping-plan/chat', methods=['POST'])
@login_required
def shopping_plan_chat():
    """買い物プラン画面のチャット：選択商品・予算状況を文脈にして回答"""
    data           = request.get_json()
    messages_in    = data.get('messages', [])
    selected_items_req = data.get('selected_items', [])
    override_map   = {item['id']: item for item in selected_items_req}

    # 選択商品リストを構築（単価・個数はユーザー調整後）
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

## 現在選択中の商品（合計 ¥{total:,}）
{json.dumps(
    [{'name': i['name'], 'amount': i['amount'],
      'price': i['price_basia'], 'qty': i['quantity'],
      'subtotal': i['price_basia'] * i['quantity']}
     for i in selected_items],
    ensure_ascii=False, indent=2
)}"""

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


@memo_bp.route('/food-budget', methods=['POST'])
@login_required
def update_food_budget():
    """今サイクルの食費予算を更新する"""
    data   = request.get_json()
    amount = int(data.get('amount', 0))
    if amount <= 0:
        return jsonify({'success': False, 'message': '予算は1円以上で入力してください'}), 400

    cycle_start, _ = _get_cycle_range()

    budget_rec = Budget.query.filter_by(
        family_id=current_user.family_id,
        transaction_type='food',
        cycle_start=cycle_start,
    ).first()

    if budget_rec:
        budget_rec.amount = amount
    else:
        db.session.add(Budget(
            family_id=current_user.family_id,
            transaction_type='food',
            amount=amount,
            cycle_start=cycle_start,
        ))
    db.session.commit()
    return jsonify({'success': True, 'amount': amount})


# ------------------------------------------------------------------ #
# 新規ルート：食品リスト関連
# ------------------------------------------------------------------ #
@memo_bp.route('/food-items')
@login_required
def food_items():
    """食品マスターをカテゴリ別に返す API"""
    category = request.args.get('category')
    if category:
        items = [i for i in FOOD_ITEMS if i['category'] == category]
    else:
        items = FOOD_ITEMS
    return jsonify({'items': items, 'categories': CATEGORIES})


@memo_bp.route('/shopping-plan', methods=['GET'])
@login_required
def shopping_plan():
    """食品リスト選択 + AIアドバイス画面"""
    budget_status = _get_food_budget_status(current_user.family_id)

    # カテゴリ別に食品リストを整理
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
    """選択した食品リストをもとにAIアドバイスを生成（単価・個数ともにユーザー調整後の値を使用）"""
    data = request.get_json()
    # selected_items: [{id, price, quantity}, ...]
    selected_items_req = data.get('selected_items', [])
    override_map = {item['id']: item for item in selected_items_req}

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


@memo_bp.route('/shopping-plan/add-to-memo', methods=['POST'])
@login_required
def add_food_to_memo():
    """選択した食品を買い物メモに一括追加（単価・個数ともにユーザー調整後の値で登録）"""
    data = request.get_json()
    selected_items_req = data.get('selected_items', [])
    override_map = {item['id']: item for item in selected_items_req}
    week = int(data.get('week', _current_week()))

    added = 0
    for item in FOOD_ITEMS:
        if item['id'] not in override_map:
            continue
        qty   = override_map[item['id']].get('quantity', item['quantity'])
        price = override_map[item['id']].get('price', item['price_basia'] or 0)
        content = f"{item['name']}（{item['amount']}）× {qty}"

        # カテゴリ判定
        item_category = 'daily' if item['category'] == '日用品' else 'food'

        exists = Memo.query.filter_by(
            family_id=current_user.family_id,
            memo_type='shopping',
            content=content,
            week=week,
            is_done=False,
        ).first()
        if not exists:
            db.session.add(Memo(
                family_id=current_user.family_id,
                user_id=current_user.id,
                content=content,
                memo_type='shopping',
                item_category=item_category,
                week=week,
                price=price * qty,
            ))
            added += 1

    db.session.commit()
    return jsonify({'success': True, 'added': added})