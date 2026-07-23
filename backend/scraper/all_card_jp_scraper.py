import requests
import json
import os
import time

from tcg_pocket_filter import is_tcg_pocket_set

# 설정
TCGDEX_JP_URL = "https://api.tcgdex.net/v2/ja"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
FILE_NAME = "all_cards_jp.json"
CHECKPOINT_PATH = os.path.join(OUTPUT_DIR, "all_cards_jp.partial.json")
FAILED_IDS_PATH = os.path.join(OUTPUT_DIR, "all_cards_jp.failed_ids.json")

def fetch_all_japanese_cards():
    """TCGdex API를 사용하여 모든 일본어 카드 정보 수집 (TCG Pocket 세트는 제외)"""
    print("="*70)
    print("🇯🇵 일본어 포켓몬 카드 전체 데이터 수집 시작")
    print("="*70)

    # 1. 전체 카드 목록 가져오기
    print("\n🔍 전체 카드 리스트를 불러오는 중...")
    try:
        response = requests.get(f"{TCGDEX_JP_URL}/cards")
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
    failed_ids = []

    # 2. 개별 카드 상세 정보 수집
    for idx, card in enumerate(summary_list, start=1):
        card_id = card['id']

        try:
            detail_res = requests.get(f"{TCGDEX_JP_URL}/cards/{card_id}", timeout=10)
            if detail_res.status_code == 200:
                data = detail_res.json()
                set_info = data.get("set", {}) or {}

                # Pokemon TCG Pocket(모바일 게임) 세트는 실물 카드가 아니므로 제외
                if is_tcg_pocket_set(set_id=set_info.get("id"), set_obj=set_info):
                    skipped_pocket += 1
                else:
                    # 필요한 정보만 정제해서 저장
                    card_entry = {
                        "id": data.get("id"),
                        "name": data.get("name"),
                        "series": set_info.get("name", "Unknown"),
                        "series_id": set_info.get("id"),
                        "number": data.get("localId"),
                        "rarity": data.get("rarity"),
                        "image": f"{data.get('image')}/low.jpg" if data.get('image') else ""
                    }
                    all_details.append(card_entry)
            else:
                # 200이 아닌 응답(타임아웃/일시적 오류 등)도 실패 목록에 기록해서 나중에 재시도
                failed_ids.append(card_id)

            # 진행 상황 표시
            if idx % 100 == 0 or idx == total_count:
                print(f"🚀 진행 중: {idx}/{total_count} ({idx/total_count*100:.1f}%) | TCG Pocket 제외: {skipped_pocket:,} | 실패: {len(failed_ids):,}")

            # 대용량 수집 중 끊길 경우를 대비한 체크포인트 저장
            if idx % 1000 == 0:
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                with open(CHECKPOINT_PATH, 'w', encoding='utf-8') as f:
                    json.dump(all_details, f, ensure_ascii=False)
                _save_failed_ids(failed_ids)

            # 서버 매너를 위한 딜레이
            time.sleep(0.05)

        except Exception as e:
            print(f"\n⚠️  ID {card_id} 수집 중 오류: {e}")
            failed_ids.append(card_id)
            continue
        except KeyboardInterrupt:
            print("\n\n🛑 중단됨! 현재까지 수집된 데이터를 저장합니다...")
            break

    print(f"\n🚫 Pokemon TCG Pocket(모바일 게임) 세트로 판단되어 제외된 카드: {skipped_pocket:,}장")

    _save_failed_ids(failed_ids)
    if failed_ids:
        print(
            f"⚠️  {len(failed_ids):,}개 카드는 수집에 실패해서 {os.path.basename(FAILED_IDS_PATH)} 에 "
            f"기록해 두었습니다. 나중에 아래 명령으로 그 카드들만 다시 시도할 수 있습니다:\n"
            f"    python3 {os.path.basename(__file__)} --retry-failed"
        )

    return all_details

def save_to_json(data):
    """수집된 데이터를 중복 제거 후 JSON 파일로 저장"""
    if not data:
        print("❌ 저장할 데이터가 없습니다.")
        return False

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, FILE_NAME)

    # ID 기준으로 중복 제거
    unique_data = {item['id']: item for item in data}
    final_list = list(unique_data.values())

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_list, f, indent=2, ensure_ascii=False)

    if os.path.exists(CHECKPOINT_PATH):
        os.remove(CHECKPOINT_PATH)

    print("\n" + "="*70)
    print(f"✅ 저장 완료: {output_path}")
    print(f"   총 수집 카드: {len(final_list):,}개")
    print("="*70)
    return True


def _save_failed_ids(failed_ids):
    """수집에 실패한 카드 ID 목록을 저장(재시도용). 실패가 없으면 파일을 정리한다."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if failed_ids:
        with open(FAILED_IDS_PATH, 'w', encoding='utf-8') as f:
            json.dump(sorted(set(failed_ids)), f, ensure_ascii=False)
    elif os.path.exists(FAILED_IDS_PATH):
        os.remove(FAILED_IDS_PATH)


def retry_failed_cards():
    """이전 실행에서 실패했던 카드 ID만 다시 조회해서 all_cards_jp.json에 병합한다."""
    if not os.path.exists(FAILED_IDS_PATH):
        print("✅ 재시도할 실패 카드 목록이 없습니다 (모두 정상 수집됨).")
        return

    with open(FAILED_IDS_PATH, 'r', encoding='utf-8') as f:
        failed_ids = json.load(f)

    if not failed_ids:
        print("✅ 재시도할 실패 카드가 없습니다.")
        return

    print(f"🔁 이전 실행에서 실패한 {len(failed_ids):,}개 카드를 재시도합니다...")

    output_path = os.path.join(OUTPUT_DIR, FILE_NAME)
    existing = []
    if os.path.exists(output_path):
        with open(output_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)

    still_failed = []
    recovered = 0

    for idx, card_id in enumerate(failed_ids, start=1):
        try:
            detail_res = requests.get(f"{TCGDEX_JP_URL}/cards/{card_id}", timeout=15)
            if detail_res.status_code == 200:
                data = detail_res.json()
                set_info = data.get("set", {}) or {}

                if not is_tcg_pocket_set(set_id=set_info.get("id"), set_obj=set_info):
                    existing.append({
                        "id": data.get("id"),
                        "name": data.get("name"),
                        "series": set_info.get("name", "Unknown"),
                        "series_id": set_info.get("id"),
                        "number": data.get("localId"),
                        "rarity": data.get("rarity"),
                        "image": f"{data.get('image')}/low.jpg" if data.get('image') else ""
                    })
                recovered += 1
            else:
                still_failed.append(card_id)
        except Exception as e:
            print(f"⚠️  재시도 실패 ID {card_id}: {e}")
            still_failed.append(card_id)

        if idx % 50 == 0 or idx == len(failed_ids):
            print(f"   재시도 진행: {idx}/{len(failed_ids)} | 복구: {recovered} | 여전히 실패: {len(still_failed)}")

        time.sleep(0.1)

    save_to_json(existing)
    _save_failed_ids(still_failed)

    print(f"\n✅ 재시도 완료: {recovered:,}개 복구, {len(still_failed):,}개는 여전히 실패로 남았습니다.")
    if still_failed:
        print(f"   (다시 '--retry-failed' 를 실행하면 남은 {len(still_failed):,}개만 재도전합니다.)")


if __name__ == "__main__":
    import sys

    start_time = time.time()

    if "--retry-failed" in sys.argv:
        retry_failed_cards()
    else:
        collected_cards = fetch_all_japanese_cards()
        save_to_json(collected_cards)

    elapsed_time = time.time() - start_time
    print(f"\n⏱️  총 소요 시간: {elapsed_time/60:.2f}분")