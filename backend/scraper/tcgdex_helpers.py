"""
TCGdex API에서 "빠짐없이" 전체 카드 ID 목록을 모으기 위한 공용 유틸리티.

[배경]
처음에는 `GET /v2/{lang}/cards` (전체 카드 요약 목록) 한 번만 호출해서 카드 ID를 모았는데,
이 전체 목록 API가 새로 추가된 시리즈를 늦게 반영한다는 게 실사용 중 확인됐다.
예) 2025-08 출시된 일본어판 "MEGA(M)" 시리즈는 `/v2/ja/series` 와 `/v2/ja/sets/{id}` 에는
    정상적으로 카드가 들어있는데, `/v2/ja/cards` 전체 목록에는 누락되어 있었음.

그래서 이제는 series -> series 상세(sets 목록) -> set 상세(cards 목록) 순서로 순회해서
카드 ID를 모은다. 이 방식이 더 느리긴 하지만(시리즈/세트 수만큼 API 호출이 추가됨),
최신 세트 누락 없이 전체 카드 ID를 확보할 수 있다.
"""

import requests


def collect_all_card_ids(lang_url: str, request_timeout: int = 20, verbose: bool = True):
    """series -> sets -> cards 순서로 전체 카드 ID를 모아 정렬된 리스트로 반환한다.

    Args:
        lang_url: 예) "https://api.tcgdex.net/v2/en" 또는 ".../v2/ja"
        request_timeout: 개별 API 호출 타임아웃(초)
        verbose: 진행 상황을 print 할지 여부
    """
    card_ids = set()

    series_res = requests.get(f"{lang_url}/series", timeout=request_timeout)
    series_res.raise_for_status()
    series_list = series_res.json()

    if verbose:
        print(f"📚 시리즈 {len(series_list):,}개 확인. 시리즈별 세트 목록을 조회합니다...")

    all_set_ids = []
    for series in series_list:
        series_id = series.get("id")
        if not series_id:
            continue
        try:
            series_detail = requests.get(f"{lang_url}/series/{series_id}", timeout=request_timeout).json()
        except Exception as e:
            if verbose:
                print(f"⚠️  시리즈 '{series_id}' 상세 조회 실패: {e}")
            continue

        for s in series_detail.get("sets", []) or []:
            set_id = s.get("id")
            if set_id:
                all_set_ids.append(set_id)

    # 중복 제거(여러 시리즈에 같은 세트가 걸쳐 있는 경우 대비)
    all_set_ids = sorted(set(all_set_ids))

    if verbose:
        print(f"📦 세트 {len(all_set_ids):,}개 확인. 세트별 카드 ID를 조회합니다...")

    for idx, set_id in enumerate(all_set_ids, start=1):
        try:
            set_detail = requests.get(f"{lang_url}/sets/{set_id}", timeout=request_timeout).json()
        except Exception as e:
            if verbose:
                print(f"⚠️  세트 '{set_id}' 상세 조회 실패: {e}")
            continue

        for c in set_detail.get("cards", []) or []:
            cid = c.get("id")
            if cid:
                card_ids.add(cid)

        if verbose and (idx % 20 == 0 or idx == len(all_set_ids)):
            print(f"   세트 조회 진행: {idx}/{len(all_set_ids)} | 누적 카드 ID: {len(card_ids):,}")

    return sorted(card_ids)
