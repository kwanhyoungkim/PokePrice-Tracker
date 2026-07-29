"""
Postgres(cards_en 테이블)에 이미 들어가 있는 Pokemon TCG Pocket(모바일 게임) 카드를
찾아서 삭제하는 스크립트.

[배경]
tcg_pocket_filter.KNOWN_TCG_POCKET_SET_IDS 는 작성 시점까지 확인된 세트 ID를
하드코딩해둔 목록이다. TCG Pocket은 계속 새 시즌(세트)이 나오기 때문에, 이 목록이
갱신되기 전에 스크래핑한 데이터에는 새로 나온 Pocket 세트가 필터링되지 않고 섞여
들어갈 수 있다.

이 스크립트는 매번 실행 시점에 TCGdex API(series -> series 상세의 sets 목록)를
직접 순회해서 "지금 시점" 기준 정확한 Pocket 세트 목록을 다시 구한 다음
(logo 경로에 "/tcgp/" 가 포함되는지로 판별 + 기존 하드코딩 목록도 함께 참고),
그 세트에 속한 카드를 DB에서 전부 삭제한다.

사용법:
    python3 backend/database/purge_pocket_cards.py --dry-run   # 삭제 대상만 미리 확인
    python3 backend/database/purge_pocket_cards.py             # 실제로 삭제
"""

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRAPER_DIR = os.path.join(_THIS_DIR, "..", "scraper")
sys.path.insert(0, _THIS_DIR)
sys.path.insert(0, _SCRAPER_DIR)

import requests

from db import get_connection  # noqa: E402
from tcg_pocket_filter import is_tcg_pocket_set, KNOWN_TCG_POCKET_SET_IDS  # noqa: E402

TCGDEX_EN_URL = "https://api.tcgdex.net/v2/en"


def find_current_pocket_set_ids(lang_url: str = TCGDEX_EN_URL, request_timeout: int = 20):
    """TCGdex를 순회해서 '지금 시점' 기준 Pocket 세트 ID 전체를 구한다.

    카드 단위까지 들어갈 필요는 없고, series -> 세트 목록까지만 확인하면 된다.
    """
    series_res = requests.get(f"{lang_url}/series", timeout=request_timeout)
    series_res.raise_for_status()
    series_list = series_res.json()

    pocket_set_ids = set(KNOWN_TCG_POCKET_SET_IDS)  # 기존 하드코딩 목록도 기본으로 포함
    checked = 0

    for series in series_list:
        series_id = series.get("id")
        if not series_id:
            continue
        try:
            series_detail = requests.get(f"{lang_url}/series/{series_id}", timeout=request_timeout).json()
        except Exception as e:
            print(f"⚠️  시리즈 '{series_id}' 조회 실패: {e}")
            continue

        for s in series_detail.get("sets", []) or []:
            set_id = s.get("id")
            if not set_id:
                continue
            checked += 1

            set_obj = s
            # series 상세의 sets 목록에 logo가 안 실려있을 수 있어서, 애매하면 세트 상세를 한 번 더 확인
            if "logo" not in set_obj and "logo_url" not in set_obj:
                try:
                    set_obj = requests.get(f"{lang_url}/sets/{set_id}", timeout=request_timeout).json()
                except Exception:
                    pass

            if is_tcg_pocket_set(set_id=set_id, set_obj=set_obj):
                pocket_set_ids.add(str(set_id).upper())

    print(f"🔍 세트 {checked:,}개 확인, Pocket 세트로 판별된 세트: {len(pocket_set_ids):,}개")

    new_ids = pocket_set_ids - set(KNOWN_TCG_POCKET_SET_IDS)
    if new_ids:
        print(
            "🆕 backend/scraper/tcg_pocket_filter.py 의 KNOWN_TCG_POCKET_SET_IDS 에 "
            f"없던 새 Pocket 세트 ID를 발견했습니다: {sorted(new_ids)}"
        )
        print("   (이 목록을 KNOWN_TCG_POCKET_SET_IDS 에 추가해두면 다음 스크래핑부터 처음부터 걸러집니다)")

    return pocket_set_ids


def purge(dry_run: bool = False):
    pocket_set_ids = find_current_pocket_set_ids()
    if not pocket_set_ids:
        print("✅ Pocket 세트로 판별된 항목이 없습니다.")
        return

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM cards_en")
            all_ids = [row[0] for row in cur.fetchall()]

            target_ids = [cid for cid in all_ids if cid.split("-")[0].upper() in pocket_set_ids]

            print(f"🗑️  삭제 대상 카드: {len(target_ids):,}장 (전체 {len(all_ids):,}장 중)")

            if not target_ids:
                print("✅ 삭제할 카드가 없습니다. (이미 깨끗하거나, 필터가 못 잡은 다른 패턴일 수 있습니다)")
                return

            if dry_run:
                print("(--dry-run 이라 실제로 삭제하지는 않았습니다)")
                return

            cur.execute("DELETE FROM cards_en WHERE id = ANY(%s)", (target_ids,))
            conn.commit()
            print(f"✅ {cur.rowcount:,}장 삭제 완료.")
    finally:
        conn.close()


if __name__ == "__main__":
    purge(dry_run="--dry-run" in sys.argv)
