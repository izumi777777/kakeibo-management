"""家族プロフィールの取得ヘルパー"""

DEFAULT_PROFILE = """夫:38歳
妻:37歳
娘:小学4年生、小学2年生
息子:0歳（乳児）"""

def get_family_profile(family_id: int) -> str:
    """DBからプロフィールを取得。未設定ならデフォルトを返す"""
    try:
        from models import Family
        family = Family.query.get(family_id)
        if family and family.profile:
            return family.profile
    except Exception:
        pass
    return DEFAULT_PROFILE


def family_profile_prompt(family_id: int) -> str:
    """システムプロンプトに埋め込む形式で返す"""
    return f"""## 家族構成
{get_family_profile(family_id)}"""
