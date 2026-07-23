"""
영문판 포켓몬 카드 전체 데이터 수집 스크래퍼.

[변경 이력]
기존에는 이 파일이 실제로는 TCGdex를 호출하지 않고, 로컬 series 정보로
all_cards_en.json 의 series/series_id 필드만 보정하는 유틸리티였다.
그 결과 all_cards_en.json 은 sv10(2025/05) 이후 새로 나온 세트
(Black Bolt/White Flare, Mega Evolution 등)의 카드가 전혀 채워지지 않는
문제가 있었다 (개선사항 우선순위 1).

이 파일은 이제 backend/scraper/all_card_jp_scraper.py 와 동일한 방식으로
TCGdex API(https://api.tcgdex.net/v2/en)에서 전체 영문 카드 목록을 실제로
가져와 backend/data/all_cards_en.json 을 새로 생성한다. 실행할 때마다
현재 TCGdex에 등록된 모든 세트(최신 세트 포함)를 다시 받아오므로, 새 세트가
나올 때마다 이 스크립트만 재실행하면 우선순위 1이 해결된다.

또한 Pokemon TCG Pocket(모바일 게임 "포켓") 세트는 실물 카드가 아니므로
tcg_pocket_filter.is_tcg_pocket_set() 으로 걸러낸다 (개선사항 우선순위 2).

기존의 "로컬 series 정보로 series/series_id 보정" 기능은
enrich_with_local_series_info() 함수로 남겨두었다. TCGdex가 특정 카드에
대해 series 정보를 "Unknown"으로 내려줄 때 backend/data/pokemon_series_us_info.json
으로 보정하고 싶다면 스크립트 실행 후 별도로 호출하면 된다.
"""

import json
import os
import time

import requests

from tcg_pocket_filter import is_tcg_pocket_set

# 설정
TCGDEX_EN_URL = "https://api.tcgdex.net/v2/en"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "all_cards_en.json")
CHECKPOINT_FILE = os.path.join(DATA_DIR, "all_cards_en.partial.json")

CARDS_EN_PATH = os.path.join(DATA_DIR, "all_cards_en.json")
SERIES_INFO_PATH = os.path.join(DATA_DIR, "pokemon_series_us_info.json")


def fetch_all_english_cards():
    """TCGdex API를 사용하여 모든 영문 카드 정보 수집 (TCG Pocket 세트는 제외)"""
    print("=" * 70)
    print("🇺🇸 영문 포켓몬 카드 전체 데이터 수집 시작")
    print("=" * 70)

    print("\n🔍 전체 카드 리스트를 불러오는 중...")
    try:
        response = requests.get(f"{TCGDEX_EN_URL}/cards", timeout=30)
        response.raise_for_status()
        summary_list = response.json()
    except Exception as e:
        print(f"❌ 목록 호출 실패: {e}")
        return []

    total_count = len(summary_list)
    print(f"✅ 총 {total_count:,}개의 카드 ID를 확인했습니다.")
    print("-" * 70)

    all_details = []
    skipped_pocket = 0

    for idx, card in enumerate(summary_list, start=1):
        card_id = card["id"]

        try:
            detail_res = requests.get(f"{TCGDEX_EN_URL}/cards/{card_id}", timeout=10)
            if detail_res.status_code == 200:
                data = detail_res.json()
                set_info = data.get("set", {}) or {}

                # Pokemon TCG Pocket(모바일 게임) 세트는 실물 카드가 아니므로 제외
                if is_tcg_pocket_set(set_id=set_info.get("id"), set_obj=set_info):
                    skipped_pocket += 1
                else:
                    card_entry = {
                        "id": data.get("id"),
                        "name": data.get("name"),
                        "series": set_info.get("name", "Unknown"),
                        "series_id": set_info.get("id"),
                        "number": data.get("localId"),
                        "rarity": data.get("rarity"),
                        "image": f"{data.get('image')}/low.jpg" if data.get("image") else "",
                    }
                    all_details.append(card_entry)

            if idx % 100 == 0 or idx == total_count:
                print(
                    f"🚀 진행 중: {idx}/{total_count} ({idx / total_count * 100:.1f}%) "
                    f"| 수집: {len(all_details):,} | TCG Pocket 제외: {skipped_pocket:,}"
                )

            # 대용량(20,000+ 건) 수집이라 중간에 끊길 경우를 대비해 주기적으로 체크포인트 저장
            if idx % 1000 == 0:
                _save_checkpoint(all_details)

            # 서버 매너를 위한 딜레이
            time.sleep(0.05)

        except Exception as e:
            print(f"\n⚠️  ID {card_id} 수집 중 오류: {e}")
            continue
        except KeyboardInterrupt:
            print("\n\n🛑 중단됨! 현재까지 수집된 데이터를 저장합니다...")
            break

    print(f"\n🚫 Pokemon TCG Pocket(모바일 게임) 세트로 판단되어 제외된 카드: {skipped_pocket:,}장")
    return all_details


def _save_checkpoint(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def save_to_json(data):
    """수집된 데이터를 중복 제거 후 JSON 파일로 저장"""
    if not data:
        print("❌ 저장할 데이터가 없습니다.")
        return False

    os.makedirs(DATA_DIR, exist_ok=True)

    # ID 기준으로 중복 제거
    unique_data = {item["id"]: item for item in data}
    final_list = list(unique_data.values())

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_list, f, indent=2, ensure_ascii=False)

    # 정상 완료되었으면 임시 체크포인트 파일은 정리
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

    print("\n" + "=" * 70)
    print(f"✅ 저장 완료: {OUTPUT_FILE}")
    print(f"   총 수집 카드: {len(final_list):,}개")
    print("=" * 70)
    return True


def enrich_with_local_series_info():
    """(선택) 로컬 pokemon_series_us_info.json 으로 series/series_id 값을 보정.

    TCGdex가 일부 카드에 대해 set 정보를 비워서 내려줄 때만 보조적으로 사용한다.
    """
    if not os.path.exists(CARDS_EN_PATH) or not os.path.exists(SERIES_INFO_PATH):
        print("❌ 필요한 JSON 파일이 없습니다.")
        return

    with open(CARDS_EN_PATH, "r", encoding="utf-8") as f:
        cards = json.load(f)

    with open(SERIES_INFO_PATH, "r", encoding="utf-8") as f:
        series_info_list = json.load(f)

    series_map = {item["set_id"]: item for item in series_info_list}

    fixed_count = 0
    for card in cards:
        if card.get("series") in (None, "", "Unknown") and card.get("id") and "-" in card["id"]:
            set_id_part = card["id"].split("-")[0]
            if set_id_part in series_map:
                target_info = series_map[set_id_part]
                card["series"] = target_info.get("set_name_us")
                card["series_id"] = set_id_part
                fixed_count += 1

    with open(CARDS_EN_PATH, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)

    print(f"✅ 보정 완료: {fixed_count:,}장의 series 정보를 로컬 데이터로 채웠습니다.")


if __name__ == "__main__":
    start_time = time.time()

    collected_cards = fetch_all_english_cards()
    save_to_json(collected_cards)

    elapsed_time = time.time() - start_time
    print(f"\n⏱️  총 소요 시간: {elapsed_time / 60:.2f}분")
