"""レシート管理ルート - S3 + Firestore"""

import os
import boto3
import uuid
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from firebase_config import fs_db
from werkzeug.utils import secure_filename

receipts_bp = Blueprint('receipts', __name__, url_prefix='/receipts')

# ------------------------------------------------------------------ #
# 設定
# ------------------------------------------------------------------ #
S3_BUCKET   = os.environ.get('S3_RECEIPT_BUCKET', '')
S3_REGION   = os.environ.get('AWS_REGION', 'ap-northeast-1')
ALLOWED_EXT = {'jpg', 'jpeg', 'png', 'gif', 'pdf'}
MAX_SIZE_MB = 10

CATEGORY_LABELS = {
    'food':          '🍱 食費',
    'daily':         '🛍 日用品',
    'fixed':         '🏠 固定費',
    'entertainment': '🎉 娯楽',
    'medical':       '💊 医療',
    'education':     '📚 教育',
    'other':         '📦 その他',
}


def _s3_client():
    return boto3.client('s3', region_name=S3_REGION)


def _family_id(raw):
    try:
        return int(raw)
    except Exception:
        return raw


def _allowed(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def _s3_key(family_id, doc_id: str, filename: str) -> str:
    ext = filename.rsplit('.', 1)[-1].lower()
    return f"receipts/{family_id}/{doc_id}.{ext}"


def _presigned_url(s3_key: str, expires: int = 3600) -> str:
    """S3 の署名付き URL を生成（1時間有効）"""
    try:
        s3 = _s3_client()
        return s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET, 'Key': s3_key},
            ExpiresIn=expires,
        )
    except Exception as e:
        print(f"[receipts] presigned_url error: {e}")
        return ''


def _to_datetime(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value).replace(tzinfo=None)
        except Exception:
            pass
    return datetime.now()


# ------------------------------------------------------------------ #
# ルート
# ------------------------------------------------------------------ #

@receipts_bp.route('/')
@login_required
def index():
    f_id = _family_id(current_user.family_id)

    # Firestore からメタデータ取得
    docs = fs_db.collection('receipts') \
                .where('family_id', '==', f_id) \
                .stream()

    receipts = []
    for doc in docs:
        d = doc.to_dict()
        d['id']         = doc.id
        d['created_at'] = _to_datetime(d.get('created_at'))
        # S3 署名付き URL を生成
        d['url'] = _presigned_url(d.get('s3_key', '')) if d.get('s3_key') else ''
        receipts.append(d)

    # 日付降順ソート
    receipts.sort(key=lambda x: x['created_at'], reverse=True)

    # カテゴリ別フィルター
    selected_cat = request.args.get('category', 'all')
    if selected_cat != 'all':
        receipts = [r for r in receipts if r.get('category') == selected_cat]

    return render_template(
        'receipts.html',
        receipts=receipts,
        categories=CATEGORY_LABELS,
        selected_cat=selected_cat,
        s3_configured=bool(S3_BUCKET),
    )


@receipts_bp.route('/upload', methods=['POST'])
@login_required
def upload():
    if not S3_BUCKET:
        flash('S3バケットが設定されていません。環境変数 S3_RECEIPT_BUCKET を設定してください。', 'danger')
        return redirect(url_for('receipts.index'))

    file = request.files.get('receipt_file')
    if not file or file.filename == '':
        flash('ファイルを選択してください。', 'warning')
        return redirect(url_for('receipts.index'))

    if not _allowed(file.filename):
        flash('JPG / PNG / GIF / PDF のみアップロードできます。', 'warning')
        return redirect(url_for('receipts.index'))

    # サイズチェック
    file.seek(0, 2)
    size_mb = file.tell() / (1024 * 1024)
    file.seek(0)
    if size_mb > MAX_SIZE_MB:
        flash(f'ファイルサイズは {MAX_SIZE_MB}MB 以下にしてください。', 'warning')
        return redirect(url_for('receipts.index'))

    doc_id   = str(uuid.uuid4())
    f_id     = _family_id(current_user.family_id)
    filename = secure_filename(file.filename)
    s3_key   = _s3_key(f_id, doc_id, filename)
    ext      = filename.rsplit('.', 1)[-1].lower()

    # フォームデータ
    receipt_date = request.form.get('receipt_date', date.today().isoformat())
    amount       = int(request.form.get('amount', 0) or 0)
    category     = request.form.get('category', 'other')
    memo         = request.form.get('memo', '').strip()

    try:
        # S3 アップロード
        s3 = _s3_client()
        content_type = 'application/pdf' if ext == 'pdf' else f'image/{ext}'
        s3.upload_fileobj(
            file,
            S3_BUCKET,
            s3_key,
            ExtraArgs={'ContentType': content_type},
        )

        # Firestore にメタデータ保存
        fs_db.collection('receipts').document(doc_id).set({
            'family_id':    f_id,
            'user_id':      current_user.id,
            's3_key':       s3_key,
            'filename':     filename,
            'ext':          ext,
            'receipt_date': receipt_date,
            'amount':       amount,
            'category':     category,
            'memo':         memo,
            'created_at':   datetime.utcnow(),
        })

        flash(f'✅ レシートをアップロードしました。', 'success')

    except Exception as e:
        print(f"[receipts] upload error: {e}")
        flash(f'アップロードに失敗しました: {e}', 'danger')

    return redirect(url_for('receipts.index'))


@receipts_bp.route('/delete/<doc_id>', methods=['POST'])
@login_required
def delete(doc_id):
    f_id = _family_id(current_user.family_id)
    ref  = fs_db.collection('receipts').document(doc_id)
    doc  = ref.get()

    if not doc.exists:
        return jsonify({'success': False, 'message': 'Not found'}), 404

    d = doc.to_dict()
    if d.get('family_id') != f_id:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    try:
        # S3 から削除
        if d.get('s3_key') and S3_BUCKET:
            _s3_client().delete_object(Bucket=S3_BUCKET, Key=d['s3_key'])

        # Firestore から削除
        ref.delete()
        return jsonify({'success': True})

    except Exception as e:
        print(f"[receipts] delete error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@receipts_bp.route('/presign/<doc_id>')
@login_required
def presign(doc_id):
    """署名付き URL を再生成して返す（URL 期限切れ対応）"""
    f_id = _family_id(current_user.family_id)
    doc  = fs_db.collection('receipts').document(doc_id).get()

    if not doc.exists or doc.to_dict().get('family_id') != f_id:
        return jsonify({'success': False}), 404

    url = _presigned_url(doc.to_dict().get('s3_key', ''))
    return jsonify({'success': True, 'url': url})