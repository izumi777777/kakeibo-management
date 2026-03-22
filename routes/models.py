"""
データモデル定義
SQLite/SQLAlchemy (将来的にFirestoreへ移行可能な構造)
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date

db = SQLAlchemy()


class Family(db.Model):
    __tablename__ = 'families'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    profile    = db.Column(db.Text, nullable=True)  # ★ 家族構成プロフィール（AIプロンプト用）
    users             = db.relationship('User',            backref='family', lazy=True)
    transactions      = db.relationship('Transaction',     backref='family', lazy=True)
    memos             = db.relationship('Memo',            backref='family', lazy=True)
    planned_expenses  = db.relationship('PlannedExpense',  backref='family', lazy=True)
    budgets           = db.relationship('Budget',          backref='family', lazy=True)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    display_name  = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    family_id     = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    firebase_uid  = db.Column(db.String(128), nullable=True)
    transactions  = db.relationship('Transaction', backref='user', lazy=True)
    memos         = db.relationship('Memo',        backref='user', lazy=True)


TRANSACTION_TYPE_LABELS = {
    'income':        '収入',
    'carryover':     '繰り越し', 
    'fixed':         '固定費',
    'food':          '食費',
    'daily':         '日用品',
    'entertainment': '娯楽・交際費',
    'medical':       '医療・健康',
    'education':     '教育費',
    'other':         'その他',
}

TRANSACTION_TYPE_COLORS = {
    'income':        '#10b981',
    'carryover':     '#06b6d4',
    'fixed':         '#6366f1',
    'food':          '#f59e0b',
    'daily':         '#3b82f6',
    'entertainment': '#ec4899',
    'medical':       '#14b8a6',
    'education':     '#8b5cf6',
    'other':         '#94a3b8',
}


class Transaction(db.Model):
    __tablename__ = 'transactions'
    id               = db.Column(db.Integer, primary_key=True)
    family_id        = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False)
    user_id          = db.Column(db.Integer, db.ForeignKey('users.id'),    nullable=False)
    amount           = db.Column(db.Integer, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)
    category         = db.Column(db.String(50))
    description      = db.Column(db.String(200))
    transaction_date = db.Column(db.Date, nullable=False, default=date.today)
    is_income        = db.Column(db.Boolean, nullable=False, default=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def type_label(self):
        return TRANSACTION_TYPE_LABELS.get(self.transaction_type, self.transaction_type)

    @property
    def type_color(self):
        return TRANSACTION_TYPE_COLORS.get(self.transaction_type, '#94a3b8')


class PlannedExpense(db.Model):
    """予定支出（給料日サイクル管理用）"""
    __tablename__ = 'planned_expenses'
    id               = db.Column(db.Integer, primary_key=True)
    family_id        = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False)
    user_id          = db.Column(db.Integer, db.ForeignKey('users.id'),    nullable=False)
    description      = db.Column(db.String(200), nullable=False)
    amount           = db.Column(db.Integer, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False, default='fixed')
    cycle_start      = db.Column(db.Date, nullable=False)    # 属するサイクルの給料日
    planned_date     = db.Column(db.Date, nullable=True)     # 支払い予定日
    is_done          = db.Column(db.Boolean, default=False)  # 支払い済み
    is_recurring     = db.Column(db.Boolean, default=False)  # 毎月繰り返し
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def type_label(self):
        return TRANSACTION_TYPE_LABELS.get(self.transaction_type, self.transaction_type)

    @property
    def type_color(self):
        return TRANSACTION_TYPE_COLORS.get(self.transaction_type, '#94a3b8')

    user = db.relationship('User', foreign_keys=[user_id])


class Budget(db.Model):
    """カテゴリ別予算（給料日サイクル単位）"""
    __tablename__ = 'budgets'
    id               = db.Column(db.Integer, primary_key=True)
    family_id        = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)
    amount           = db.Column(db.Integer, nullable=False)
    cycle_start      = db.Column(db.Date, nullable=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('family_id', 'transaction_type', 'cycle_start',
                            name='uq_budget_family_type_cycle'),
    )


class Memo(db.Model):
    __tablename__ = 'memos'
    id         = db.Column(db.Integer, primary_key=True)
    family_id  = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'),    nullable=False)
    content    = db.Column(db.Text, nullable=False)
    memo_type  = db.Column(db.String(20), default='shopping')
    is_done    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AiAdvice(db.Model):
    __tablename__ = 'ai_advices'
    id          = db.Column(db.Integer, primary_key=True)
    family_id   = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False)
    advice_text = db.Column(db.Text, nullable=False)
    advice_type = db.Column(db.String(50), default='monthly')
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
