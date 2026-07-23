"""
Pokemon TCG Pocket(모바일 게임 "포켓") 세트를 실물 카드 데이터에서 걸러내기 위한 공용 유틸리티.

TCGdex API는 실물 카드 세트와 모바일 게임 "Pokemon TCG Pocket" 세트를 같은 엔드포인트에서
함께 내려주는 경우가 있어, 스크래퍼 단계에서 명시적으로 제외해야 한다.
TCG Pocket 세트는 로고 경로에 "/tcgp/" 가 포함되고, set id가 A1, A2, B1 같은 짧은 코드로
실물 카드 세트 코드(base1, sv10 등)와 다른 패턴을 가진다.

backend/data/pokemon_series_us_info.json 을 조사해서 확인된 TCG Pocket 세트 목록:
A1, P-A, A1a, A2, A2a, A2b, A3, A4, A4a, B1
(신규 시즌이 계속 추가되므로 아래 목록은 최소 기준이고, logo 경로 검사로도 함께 필터링한다.)
"""

# 확인된 TCG Pocket(모바일 게임) 세트 ID 목록 (대문자 기준)
KNOWN_TCG_POCKET_SET_IDS = {
    "A1", "P-A", "A1A", "A2", "A2A", "A2B",
    "A3", "A3A", "A3B", "A4", "A4A", "A4B", "B1", "B1A", "B2",
}


def is_tcg_pocket_set(set_id: str = None, set_obj: dict = None) -> bool:
    """주어진 세트가 Pokemon TCG Pocket(모바일 게임) 세트인지 판별한다.

    Args:
        set_id: 세트 코드 (예: "A1", "base1", "sv10")
        set_obj: TCGdex API가 반환하는 set 객체 전체 (logo, id 등 포함 가능)
    """
    candidate_id = set_id
    if not candidate_id and set_obj:
        candidate_id = set_obj.get("id")

    if candidate_id and str(candidate_id).upper() in KNOWN_TCG_POCKET_SET_IDS:
        return True

    if set_obj:
        logo = (set_obj.get("logo") or set_obj.get("logo_url") or "") or ""
        if "/tcgp/" in logo:
            return True

    return False


def filter_out_pocket_sets(series_info_list, id_key="set_id", logo_key="logo_url"):
    """시리즈 정보 리스트에서 TCG Pocket 세트를 제거한 새 리스트를 반환한다."""
    cleaned = []
    removed = []
    for item in series_info_list:
        set_obj = {"id": item.get(id_key), "logo": item.get(logo_key)}
        if is_tcg_pocket_set(set_obj=set_obj):
            removed.append(item.get(id_key))
        else:
            cleaned.append(item)
    return cleaned, removed
