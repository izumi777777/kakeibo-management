"""
家計簿2024.xlsx の「食費リスト」シートから抽出した食品・日用品マスターデータ。

Flaskアプリへの組み込み例:
  from food_data import FOOD_ITEMS, CATEGORIES

使用例（買い物メモ機能）:
  from food_data import get_items_by_category, search_items
"""

CATEGORIES = [
    "肉", "野菜", "パン", "たまご", "乳製品", "豆腐・納豆",
    "麺類", "スープ", "調味料", "冷凍食品", "カレーなど",
    "ジュース類", "コーヒー", "米", "日用品", "魚介類" # 魚介類を新規追加しました
]

# 各アイテムのフィールド:
#   id            : 一意のID
#   category      : カテゴリ名
#   name          : 商品名
#   amount        : 内容量・サイズ
#   price_basia   : ベイシア価格（円）
#   price_kanesue : カネスエ価格（円、未登録はNone）
#   price_ec      : その他EC価格（円、未登録はNone）
#   quantity      : 購入個数（デフォルト1）
#   total         : 合計金額（円）
#   note          : 備考（月初め購入など）
FOOD_ITEMS = [
    {"id": 1,  "category": "肉",      "name": "豚肉コマ切れ",                      "amount": "1kg",   "price_basia": 960,  "price_kanesue": None, "price_ec": None, "quantity": 2, "total": 1920, "note": None},
    {"id": 2,  "category": "肉",      "name": "若鳥ささみ",                        "amount": "300g",  "price_basia": 353,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 353,  "note": None},
    {"id": 3,  "category": "肉",      "name": "若鳥もも",                          "amount": "750g",  "price_basia": 801,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 801,  "note": None},
    {"id": 4,  "category": "肉",      "name": "若鳥からあげ用モモ肉大",            "amount": "300g",  "price_basia": 515,  "price_kanesue": None, "price_ec": None, "quantity": 2, "total": 1030, "note": None},
    {"id": 5,  "category": "肉",      "name": "牛豚挽肉",                          "amount": "300g",  "price_basia": 482,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 482,  "note": None},
    {"id": 6,  "category": "野菜",    "name": "人参",                              "amount": "1袋",   "price_basia": 214,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 214,  "note": None},
    {"id": 7,  "category": "野菜",    "name": "玉ねぎ",                            "amount": "1袋",   "price_basia": 322,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 322,  "note": None},
    {"id": 8,  "category": "野菜",    "name": "長ネギ",                            "amount": "1袋",   "price_basia": 214,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 214,  "note": None},
    {"id": 9,  "category": "野菜",    "name": "ピーマン",                          "amount": "1袋",   "price_basia": 171,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 171,  "note": None},
    {"id": 10, "category": "野菜",    "name": "えのき",                            "amount": "1袋",   "price_basia": 106,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 106,  "note": None},
    {"id": 11, "category": "野菜",    "name": "ぶなしめじ",                        "amount": "2袋",   "price_basia": 171,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 171,  "note": None},
    {"id": 12, "category": "野菜",    "name": "レタス",                            "amount": "1",     "price_basia": 150,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 150,  "note": None},
    {"id": 13, "category": "野菜",    "name": "新ジャガイモ",                      "amount": "1袋",   "price_basia": 372,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 372,  "note": None},
    {"id": 14, "category": "野菜",    "name": "きゃべつ",                          "amount": "1",     "price_basia": 171,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 171,  "note": None},
    {"id": 15, "category": "野菜",    "name": "小松菜",                            "amount": "1",     "price_basia": 106,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 106,  "note": None},
    {"id": 16, "category": "野菜",    "name": "白菜",                              "amount": "1/4",   "price_basia": 106,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 106,  "note": None},
    {"id": 17, "category": "野菜",    "name": "まいたけ",                          "amount": "1",     "price_basia": 171,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 171,  "note": None},
    {"id": 18, "category": "野菜",    "name": "ほうれんそう",                      "amount": "1",     "price_basia": 150,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 150,  "note": None},
    {"id": 19, "category": "野菜",    "name": "トマト",                            "amount": "2個",   "price_basia": 322,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 322,  "note": None},
    {"id": 20, "category": "野菜",    "name": "サニーレタス",                      "amount": "1",     "price_basia": 150,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 150,  "note": None},
    {"id": 21, "category": "野菜",    "name": "長いも",                            "amount": "400g",  "price_basia": 367,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 367,  "note": None},
    {"id": 22, "category": "野菜",    "name": "大葉",                              "amount": "1",     "price_basia": 96,   "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 96,   "note": None},
    {"id": 23, "category": "野菜",    "name": "バナナ",                            "amount": "1",     "price_basia": 150,  "price_kanesue": None, "price_ec": None, "quantity": 2, "total": 300,  "note": None},
    {"id": 24, "category": "野菜",    "name": "アボガド",                          "amount": "1",     "price_basia": 182,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 182,  "note": None},
    {"id": 25, "category": "パン",    "name": "超熟食パン",                        "amount": "1",     "price_basia": 236,  "price_kanesue": None, "price_ec": None, "quantity": 2, "total": 472,  "note": None},
    {"id": 26, "category": "パン",    "name": "バゲット",                          "amount": "1",     "price_basia": 128,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 128,  "note": None},
    {"id": 27, "category": "パン",    "name": "ミニロールパン",                    "amount": "1",     "price_basia": 214,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 214,  "note": None},
    {"id": 28, "category": "たまご",  "name": "たまご大玉",                        "amount": "1",     "price_basia": 355,  "price_kanesue": None, "price_ec": None, "quantity": 2, "total": 710,  "note": None},
    {"id": 29, "category": "乳製品",  "name": "明治美味しい牛乳900ml",              "amount": "1",     "price_basia": 321,  "price_kanesue": None, "price_ec": None, "quantity": 2, "total": 642,  "note": None},
    {"id": 30, "category": "乳製品",  "name": "ミックスチーズ",                    "amount": "1",     "price_basia": 387,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 387,  "note": None},
    {"id": 31, "category": "乳製品",  "name": "さけるチーズ",                      "amount": "1",     "price_basia": 204,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 204,  "note": None},
    {"id": 32, "category": "豆腐・納豆", "name": "金の粒納豆",                     "amount": "1",     "price_basia": 106,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 106,  "note": None},
    {"id": 33, "category": "豆腐・納豆", "name": "金の粒納豆梅風味黒酢たれ",       "amount": "1",     "price_basia": 106,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 106,  "note": None},
    {"id": 34, "category": "豆腐・納豆", "name": "絹厚揚げ4本入り",               "amount": "1",     "price_basia": 106,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 106,  "note": None},
    {"id": 35, "category": "豆腐・納豆", "name": "豆腐",                           "amount": "1",     "price_basia": 128,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 128,  "note": None},
    {"id": 36, "category": "麺類",    "name": "もちもち食感スパゲッティ",          "amount": "1",     "price_basia": 268,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 268,  "note": None},
    {"id": 37, "category": "麺類",    "name": "アラビアータ完熟トマト",            "amount": "1",     "price_basia": 268,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 268,  "note": None},
    {"id": 38, "category": "麺類",    "name": "しょうゆらーめん5食入り",          "amount": "1",     "price_basia": 214,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 214,  "note": None},
    {"id": 39, "category": "スープ",  "name": "クノールコーンクリーム8食",         "amount": "1",     "price_basia": 355,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 355,  "note": None},
    {"id": 40, "category": "スープ",  "name": "クノールカップスープポタージュ8食", "amount": "1",     "price_basia": 355,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 355,  "note": None},
    {"id": 41, "category": "スープ",  "name": "インスタント味噌汁25食",            "amount": "1",     "price_basia": 430,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 430,  "note": None},
    {"id": 42, "category": "調味料",  "name": "キャノーラ油 1000g",               "amount": "1",     "price_basia": 430,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 430,  "note": None},
    {"id": 43, "category": "調味料",  "name": "トマトケチャップ",                  "amount": "1",     "price_basia": 268,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 268,  "note": None},
    {"id": 44, "category": "調味料",  "name": "完熟トマト紙パック",                "amount": "1",     "price_basia": 279,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 279,  "note": None},
    {"id": 45, "category": "調味料",  "name": "濃いだだし本つゆ 1L",               "amount": "1",     "price_basia": 344,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 344,  "note": None},
    {"id": 46, "category": "調味料",  "name": "味の素ほんだし120g",               "amount": "1",     "price_basia": 376,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 376,  "note": None},
    {"id": 47, "category": "冷凍食品", "name": "讃岐うどん5食",                     "amount": "1",     "price_basia": 214,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 214,  "note": None},
    {"id": 48, "category": "冷凍食品", "name": "自然解凍できるブロッコリー",        "amount": "500g",  "price_basia": 409,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 409,  "note": None},
    {"id": 49, "category": "冷凍食品", "name": "オクラ",                            "amount": "300g",  "price_basia": 225,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 225,  "note": None},
    {"id": 50, "category": "冷凍食品", "name": "ほうれんそう（冷凍）",              "amount": "200g",  "price_basia": 268,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 268,  "note": None},
    {"id": 51, "category": "冷凍食品", "name": "日清冷凍パスタ 明太子クリーム",    "amount": "1",     "price_basia": 193,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 193,  "note": None},
    {"id": 52, "category": "冷凍食品", "name": "日清冷凍パスタ トマトクリーム",    "amount": "1",     "price_basia": 193,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 193,  "note": None},
    {"id": 53, "category": "冷凍食品", "name": "日清冷凍パスタ エビのトマトクリーム","amount": "1",   "price_basia": 193,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 193,  "note": None},
    {"id": 54, "category": "冷凍食品", "name": "日清冷凍パスタ ジェノベーゼ",      "amount": "1",     "price_basia": 214,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 214,  "note": None},
    {"id": 55, "category": "冷凍食品", "name": "日清冷凍パスタ さーもんほうれん草","amount": "1",     "price_basia": 193,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 193,  "note": None},
    {"id": 56, "category": "冷凍食品", "name": "日清冷凍パスタ 濃厚カルボナーラ",  "amount": "2",     "price_basia": 193,  "price_kanesue": None, "price_ec": None, "quantity": 2, "total": 386,  "note": None},
    {"id": 57, "category": "冷凍食品", "name": "日清冷凍パスタ 牛ひき肉ボロネーゼ","amount": "2",     "price_basia": 214,  "price_kanesue": None, "price_ec": None, "quantity": 2, "total": 428,  "note": None},
    {"id": 58, "category": "冷凍食品", "name": "日清冷凍パスタ 海の幸のペスカトーレ","amount": "1",   "price_basia": 214,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 214,  "note": None},
    {"id": 59, "category": "カレーなど","name": "ジャワカレー甘口",                 "amount": "1",     "price_basia": 430,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 430,  "note": None},
    {"id": 60, "category": "カレーなど","name": "こくまろはやし",                   "amount": "1",     "price_basia": 236,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 236,  "note": None},
    {"id": 61, "category": "カレーなど","name": "五目釜飯の素",                     "amount": "1",     "price_basia": 247,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 247,  "note": None},
    {"id": 62, "category": "カレーなど","name": "味の素CookDo 麻婆豆腐",            "amount": "1",     "price_basia": 193,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 193,  "note": None},
    {"id": 63, "category": "ジュース類","name": "三ツ矢サイダー",                   "amount": "500ml", "price_basia": 96,   "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 96,   "note": None},
    {"id": 64, "category": "ジュース類","name": "コカ・コーラ",                     "amount": "500ml", "price_basia": 106,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 106,  "note": None},
    {"id": 65, "category": "ジュース類","name": "CCレモン",                         "amount": "500ml", "price_basia": 106,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 106,  "note": None},
    {"id": 66, "category": "ジュース類","name": "ジンジャエール",                   "amount": "500ml", "price_basia": 106,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 106,  "note": None},
    {"id": 67, "category": "ジュース類","name": "レモンスカッシュ",                 "amount": "500ml", "price_basia": 106,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 106,  "note": None},
    {"id": 68, "category": "コーヒー", "name": "スタバカフェモーメントスムース",    "amount": "65g",   "price_basia": 1132, "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 1132, "note": None},
    {"id": 69, "category": "米",       "name": "米",                               "amount": "15kg",  "price_basia": 11500,"price_kanesue": None, "price_ec": None, "quantity": 1, "total": 11500,"note": "月初めに購入"},
    {"id": 70, "category": "日用品",   "name": "花柄トイレットペーパー",           "amount": "18ロール","price_basia": 1540,"price_kanesue": None, "price_ec": None, "quantity": 1, "total": 1540, "note": "月初めに購入"},
    {"id": 71, "category": "日用品",   "name": "アタック洗剤",                     "amount": "2500g", "price_basia": 1404, "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 1404, "note": "月初めに購入"},
    {"id": 72, "category": "日用品",   "name": "さらさ食器用洗剤（詰替）",         "amount": "280ml", "price_basia": 279,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 279,  "note": None},
    {"id": 73, "category": "日用品",   "name": "さらさ食器用洗剤（大容量）",       "amount": "1060ml","price_basia": 848,  "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 848,  "note": "月初めに購入"},
    {"id": 74, "category": "日用品",   "name": "シーチキン",                       "amount": "70g×12","price_basia": 2016, "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 2016, "note": None},
    {"id": 75, "category": "日用品",   "name": "味付け海苔",                       "amount": "8切160枚","price_basia": 1299,"price_kanesue": None, "price_ec": None, "quantity": 1, "total": 1299, "note": None},
    {"id": 76, "category": "日用品",   "name": "エリエール ウォータティッシュ",    "amount": "5箱",   "price_basia": 646,  "price_kanesue": None, "price_ec": None, "quantity": 2, "total": 1292, "note": None},
    {"id": 77, "category": "日用品",   "name": "キッチンペーパー",                 "amount": "400枚", "price_basia": 1454, "price_kanesue": None, "price_ec": None, "quantity": 1, "total": 1454, "note": "月初めに購入"},
    {"id": 78, "category": "日用品",   "name": "ポリラップ",                       "amount": "30cm×40m","price_basia": 1221,"price_kanesue": None, "price_ec": None, "quantity": 1, "total": 1221, "note": None},
    {"id": 79, "category": "日用品",   "name": "アルミホイル",                     "amount": "25cm×25m","price_basia": 1257,"price_kanesue": None, "price_ec": None, "quantity": 1, "total": 1257, "note": None},

    # --- 以下、追加分 ---
    {"id": 80,  "category": "野菜", "name": "オレンジ", "amount": "1", "price_basia": None, "price_kanesue": 597, "price_ec": None, "quantity": 1, "total": 597, "note": "5個入り"},
    {"id": 81,  "category": "野菜", "name": "小松菜", "amount": "1", "price_basia": None, "price_kanesue": 85, "price_ec": None, "quantity": 1, "total": 85, "note": None},
    {"id": 82,  "category": "野菜", "name": "ほうれん草", "amount": "1", "price_basia": None, "price_kanesue": 127, "price_ec": None, "quantity": 1, "total": 127, "note": None},
    {"id": 83,  "category": "野菜", "name": "白菜", "amount": "1", "price_basia": None, "price_kanesue": 104, "price_ec": None, "quantity": 1, "total": 104, "note": None},
    {"id": 84,  "category": "野菜", "name": "白ネギ", "amount": "1", "price_basia": None, "price_kanesue": 169, "price_ec": None, "quantity": 1, "total": 169, "note": None},
    {"id": 85,  "category": "野菜", "name": "バナナ", "amount": "1", "price_basia": None, "price_kanesue": 212, "price_ec": None, "quantity": 1, "total": 212, "note": "4本"},
    {"id": 86,  "category": "野菜", "name": "アボガド", "amount": "1", "price_basia": None, "price_kanesue": 106, "price_ec": None, "quantity": 1, "total": 106, "note": None},
    {"id": 87,  "category": "野菜", "name": "大葉", "amount": "1", "price_basia": None, "price_kanesue": 137, "price_ec": None, "quantity": 1, "total": 137, "note": None},
    {"id": 88,  "category": "野菜", "name": "にんじん", "amount": "1", "price_basia": None, "price_kanesue": 169, "price_ec": None, "quantity": 1, "total": 169, "note": "3本"},
    {"id": 89,  "category": "野菜", "name": "かぼちゃ", "amount": "1", "price_basia": None, "price_kanesue": 201, "price_ec": None, "quantity": 1, "total": 201, "note": None},
    {"id": 90,  "category": "野菜", "name": "カットじゃがいも", "amount": "1", "price_basia": None, "price_kanesue": 212, "price_ec": None, "quantity": 1, "total": 212, "note": "3個入り"},
    {"id": 91,  "category": "野菜", "name": "玉ねぎ", "amount": "1", "price_basia": None, "price_kanesue": 212, "price_ec": None, "quantity": 1, "total": 212, "note": "4玉"},
    {"id": 92,  "category": "野菜", "name": "ミニトマト", "amount": "1", "price_basia": None, "price_kanesue": 242, "price_ec": None, "quantity": 1, "total": 242, "note": None},
    {"id": 93,  "category": "野菜", "name": "トマト", "amount": "1", "price_basia": None, "price_kanesue": 300, "price_ec": None, "quantity": 1, "total": 300, "note": "3個入り"},
    {"id": 94,  "category": "野菜", "name": "レタス", "amount": "1", "price_basia": None, "price_kanesue": 99, "price_ec": None, "quantity": 1, "total": 99, "note": None},
    {"id": 95,  "category": "野菜", "name": "ぶなしめじ", "amount": "1", "price_basia": None, "price_kanesue": 96, "price_ec": None, "quantity": 1, "total": 96, "note": None},
    {"id": 96,  "category": "野菜", "name": "ピーマン", "amount": "1", "price_basia": None, "price_kanesue": 169, "price_ec": None, "quantity": 1, "total": 169, "note": None},
    {"id": 97,  "category": "野菜", "name": "もやし", "amount": "1", "price_basia": None, "price_kanesue": 20, "price_ec": None, "quantity": 1, "total": 20, "note": None},
    {"id": 98,  "category": "肉", "name": "シャウエッセン", "amount": "468g", "price_basia": None, "price_kanesue": 646, "price_ec": None, "quantity": 1, "total": 646, "note": None},
    {"id": 99,  "category": "肉", "name": "チーズインソーセージ", "amount": "71g×2", "price_basia": None, "price_kanesue": 320, "price_ec": None, "quantity": 1, "total": 320, "note": None},
    {"id": 100, "category": "日用品", "name": "2倍長持ちトイレットペーパー", "amount": "50m×12ロール", "price_basia": None, "price_kanesue": 546, "price_ec": None, "quantity": 1, "total": 546, "note": None},
    {"id": 101, "category": "日用品", "name": "ダブルBOXティッシュボレロ", "amount": "5箱", "price_basia": None, "price_kanesue": 304, "price_ec": None, "quantity": 1, "total": 304, "note": None},
    {"id": 102, "category": "日用品", "name": "キッチンタオル4R2倍巻き", "amount": "1", "price_basia": None, "price_kanesue": 326, "price_ec": None, "quantity": 1, "total": 326, "note": None},
    {"id": 103, "category": "肉", "name": "ベーコン", "amount": "31g×3", "price_basia": None, "price_kanesue": 169, "price_ec": None, "quantity": 1, "total": 169, "note": None},
    {"id": 104, "category": "肉", "name": "ロースハム", "amount": "40g×3", "price_basia": None, "price_kanesue": 169, "price_ec": None, "quantity": 1, "total": 169, "note": None},
    {"id": 105, "category": "肉", "name": "ミートボール", "amount": "120g×2", "price_basia": None, "price_kanesue": 214, "price_ec": None, "quantity": 1, "total": 214, "note": None},
    {"id": 106, "category": "肉", "name": "チキンハンバーグ", "amount": "69g×3", "price_basia": None, "price_kanesue": 212, "price_ec": None, "quantity": 1, "total": 212, "note": None},
    {"id": 107, "category": "肉", "name": "チキンナゲット", "amount": "234g", "price_basia": None, "price_kanesue": 199, "price_ec": None, "quantity": 1, "total": 199, "note": None},
    {"id": 108, "category": "肉", "name": "魚肉ソーセージ", "amount": "70g×4", "price_basia": None, "price_kanesue": 182, "price_ec": None, "quantity": 1, "total": 182, "note": None},
    {"id": 109, "category": "野菜", "name": "キャベツ", "amount": "1", "price_basia": None, "price_kanesue": 137, "price_ec": None, "quantity": 1, "total": 137, "note": None},
    {"id": 110, "category": "魚介類", "name": "スモークサーモン", "amount": "106g", "price_basia": None, "price_kanesue": 424, "price_ec": None, "quantity": 1, "total": 424, "note": None},
    {"id": 111, "category": "魚介類", "name": "きはだまぐろ", "amount": "170g", "price_basia": None, "price_kanesue": 606, "price_ec": None, "quantity": 1, "total": 606, "note": None},
    {"id": 112, "category": "魚介類", "name": "たこ", "amount": "170g", "price_basia": None, "price_kanesue": 572, "price_ec": None, "quantity": 1, "total": 572, "note": None},
    {"id": 113, "category": "魚介類", "name": "白身魚", "amount": "309g", "price_basia": None, "price_kanesue": 305, "price_ec": None, "quantity": 1, "total": 305, "note": None},
    {"id": 114, "category": "魚介類", "name": "バナメイえび", "amount": "276g", "price_basia": None, "price_kanesue": 405, "price_ec": None, "quantity": 1, "total": 405, "note": None},
    {"id": 115, "category": "魚介類", "name": "ほっけ", "amount": "2枚", "price_basia": None, "price_kanesue": 349, "price_ec": None, "quantity": 1, "total": 349, "note": None},
    {"id": 116, "category": "魚介類", "name": "鮭西京漬け", "amount": "4切", "price_basia": None, "price_kanesue": 430, "price_ec": None, "quantity": 1, "total": 430, "note": None},
    {"id": 117, "category": "魚介類", "name": "鮭小口切身", "amount": "195g", "price_basia": None, "price_kanesue": 318, "price_ec": None, "quantity": 1, "total": 318, "note": None},
    {"id": 118, "category": "肉", "name": "牛バラ", "amount": "345g", "price_basia": None, "price_kanesue": 733, "price_ec": None, "quantity": 1, "total": 733, "note": None},
    {"id": 119, "category": "肉", "name": "豚薄切り", "amount": "517g", "price_basia": None, "price_kanesue": 501, "price_ec": None, "quantity": 1, "total": 501, "note": None},
    {"id": 120, "category": "肉", "name": "牛肩ロースブロック", "amount": "369g", "price_basia": None, "price_kanesue": 726, "price_ec": None, "quantity": 1, "total": 726, "note": None},
    {"id": 121, "category": "肉", "name": "豚肉こま切れ", "amount": "686g", "price_basia": None, "price_kanesue": 583, "price_ec": None, "quantity": 1, "total": 583, "note": None},
    {"id": 122, "category": "肉", "name": "若鶏手羽元", "amount": "867g", "price_basia": None, "price_kanesue": 494, "price_ec": None, "quantity": 1, "total": 494, "note": None},
    {"id": 123, "category": "肉", "name": "若鶏手羽先", "amount": "631g", "price_basia": None, "price_kanesue": 536, "price_ec": None, "quantity": 1, "total": 536, "note": None},
    {"id": 124, "category": "肉", "name": "タイ産若鶏モモ角切り", "amount": "487g", "price_basia": None, "price_kanesue": 423, "price_ec": None, "quantity": 1, "total": 423, "note": None},
    {"id": 125, "category": "肉", "name": "若鶏モモ", "amount": "649g", "price_basia": None, "price_kanesue": 642, "price_ec": None, "quantity": 1, "total": 642, "note": None},
    {"id": 126, "category": "肉", "name": "若鶏ムネ肉", "amount": "1056g", "price_basia": None, "price_kanesue": 792, "price_ec": None, "quantity": 1, "total": 792, "note": None},
    {"id": 127, "category": "肉", "name": "牛豚合挽きミンチ", "amount": "411g", "price_basia": None, "price_kanesue": 411, "price_ec": None, "quantity": 1, "total": 411, "note": None},
    {"id": 128, "category": "調味料", "name": "ソース", "amount": "500ml", "price_basia": None, "price_kanesue": 212, "price_ec": None, "quantity": 1, "total": 212, "note": None},
    {"id": 129, "category": "調味料", "name": "カットトマト", "amount": "400g", "price_basia": None, "price_kanesue": 89, "price_ec": None, "quantity": 1, "total": 89, "note": None},
    {"id": 130, "category": "調味料", "name": "キャノーラ油", "amount": "900g", "price_basia": None, "price_kanesue": 299, "price_ec": None, "quantity": 1, "total": 299, "note": None},
    {"id": 131, "category": "調味料", "name": "料理酒", "amount": "1000ml", "price_basia": None, "price_kanesue": 149, "price_ec": None, "quantity": 1, "total": 149, "note": None},
    {"id": 132, "category": "調味料", "name": "みりん", "amount": "1000ml", "price_basia": None, "price_kanesue": 147, "price_ec": None, "quantity": 1, "total": 147, "note": None},
    {"id": 133, "category": "調味料", "name": "つゆのもと", "amount": "1000ml", "price_basia": None, "price_kanesue": 191, "price_ec": None, "quantity": 1, "total": 191, "note": None},
    {"id": 134, "category": "調味料", "name": "みそ", "amount": "750g", "price_basia": None, "price_kanesue": 245, "price_ec": None, "quantity": 1, "total": 245, "note": None},
    {"id": 135, "category": "調味料", "name": "かつおだしのもと", "amount": "300g", "price_basia": None, "price_kanesue": 299, "price_ec": None, "quantity": 1, "total": 299, "note": None},
    {"id": 136, "category": "米", "name": "米", "amount": "5kg", "price_basia": None, "price_kanesue": 3670, "price_ec": None, "quantity": 1, "total": 3670, "note": "あきたこまち"},
    {"id": 137, "category": "米", "name": "もち麦", "amount": "800g", "price_basia": None, "price_kanesue": 536, "price_ec": None, "quantity": 1, "total": 536, "note": None},
    {"id": 138, "category": "カレーなど", "name": "ゴールデンカレー甘口", "amount": "1", "price_basia": None, "price_kanesue": 223, "price_ec": None, "quantity": 1, "total": 223, "note": None},
    {"id": 139, "category": "麺類", "name": "醤油ラーメン", "amount": "5袋", "price_basia": None, "price_kanesue": 204, "price_ec": None, "quantity": 1, "total": 204, "note": None},
    {"id": 140, "category": "麺類", "name": "パスタ", "amount": "1kg", "price_basia": None, "price_kanesue": 197, "price_ec": None, "quantity": 1, "total": 197, "note": "1.7mm"},
    {"id": 141, "category": "たまご", "name": "卵", "amount": "1", "price_basia": None, "price_kanesue": 257, "price_ec": None, "quantity": 1, "total": 257, "note": None},
    {"id": 142, "category": "豆腐・納豆", "name": "豆腐", "amount": "1", "price_basia": None, "price_kanesue": 83, "price_ec": None, "quantity": 1, "total": 83, "note": None},
    {"id": 143, "category": "乳製品", "name": "牛乳", "amount": "1", "price_basia": None, "price_kanesue": 214, "price_ec": None, "quantity": 1, "total": 214, "note": None},
    {"id": 144, "category": "乳製品", "name": "ヨーグルト", "amount": "400g", "price_basia": None, "price_kanesue": 171, "price_ec": None, "quantity": 1, "total": 171, "note": None},
    {"id": 145, "category": "冷凍食品", "name": "冷凍パスタ", "amount": "283g", "price_basia": None, "price_kanesue": 212, "price_ec": None, "quantity": 1, "total": 212, "note": "日清"},
    {"id": 146, "category": "冷凍食品", "name": "冷凍パスタボロネーゼ", "amount": "285g", "price_basia": None, "price_kanesue": 182, "price_ec": None, "quantity": 1, "total": 182, "note": None},
    {"id": 147, "category": "パン", "name": "超熟食パン", "amount": "1", "price_basia": None, "price_kanesue": 212, "price_ec": None, "quantity": 1, "total": 212, "note": None},
    {"id": 148, "category": "パン", "name": "フランスパン", "amount": "1", "price_basia": None, "price_kanesue": 147, "price_ec": None, "quantity": 1, "total": 147, "note": None},
]

def get_items_by_category(category: str) -> list:
    """指定カテゴリのアイテム一覧を返す"""
    return [item for item in FOOD_ITEMS if item["category"] == category]

def search_items(keyword: str) -> list:
    """商品名でキーワード検索"""
    keyword = keyword.lower()
    return [item for item in FOOD_ITEMS if keyword in item["name"].lower()]

def get_item_by_id(item_id: int) -> dict | None:
    """IDでアイテムを取得"""
    for item in FOOD_ITEMS:
        if item["id"] == item_id:
            return item
    return None

def get_standard_shopping_list() -> list:
    """標準的な買い物リスト（全アイテム）を返す"""
    return [{"id": item["id"], "name": item["name"], "category": item["category"],
             "amount": item["amount"], "price": item["price_basia"] or item["price_kanesue"], # price_basiaがない場合はprice_kanesueを使用
             "quantity": item["quantity"], "checked": False}
            for item in FOOD_ITEMS]