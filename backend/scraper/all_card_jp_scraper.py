import requests
import json
import os
import time

# 설정
TCGDEX_JP_URL = "https://api.tcgdex.net/v2/ja"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../backend/data")
FILE_NAME = "all_cards_jp.json"

def fetch_all_japanese_cards():
    """TCGdex API를 사용하여 모든 일본어 카드 정보 수집"""
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
    
    # 2. 개별 카드 상세 정보 수집
    # API 부하를 줄이기 위해 0.05초의 대기 시간을 둡니다.
    for idx, card in enumerate(summary_list, start=1):
        card_id = card['id']
        
        try:
            detail_res = requests.get(f"{TCGDEX_JP_URL}/cards/{card_id}", timeout=10)
            if detail_res.status_code == 200:
                data = detail_res.json()
                
                # 필요한 정보만 정제해서 저장 (메모리 절약)
                card_entry = {
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "series": data.get("set", {}).get("name", "Unknown"),
                    "series_id": data.get("set", {}).get("id"),
                    "number": data.get("localId"),
                    "rarity": data.get("rarity"),
                    "image": f"{data.get('image')}/low.jpg" if data.get('image') else ""
                }
                all_details.append(card_entry)

            # 진행 상황 표시
            if idx % 100 == 0 or idx == total_count:
                print(f"🚀 진행 중: {idx}/{total_count} ({idx/total_count*100:.1f}%)")

            # 서버 매너를 위한 딜레이
            time.sleep(0.05)

        except Exception as e:
            print(f"\n⚠️  ID {card_id} 수집 중 오류: {e}")
            continue
        except KeyboardInterrupt:
            print("\n\n🛑 중단됨! 현재까지 수집된 데이터를 저장합니다...")
            break

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

    print("\n" + "="*70)
    print(f"✅ 저장 완료: {output_path}")
    print(f"   총 수집 카드: {len(final_list):,}개")
    print("="*70)
    return True

if __name__ == "__main__":
    start_time = time.time()
    
    collected_cards = fetch_all_japanese_cards()
    save_to_json(collected_cards)
    
    elapsed_time = time.time() - start_time
    print(f"\n⏱️  총 소요 시간: {elapsed_time/60:.2f}분")