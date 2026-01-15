import json
import os

# 파일 경로 설정
CARDS_EN_PATH = 'backend/data/all_cards_en.json'
SERIES_INFO_PATH = 'backend/data/pokemon_series_us_info.json'
OUTPUT_PATH = 'backend/data/all_cards_en_fixed.json'

def fix_card_series_info():
    # 1. 데이터 불러오기
    if not os.path.exists(CARDS_EN_PATH) or not os.path.exists(SERIES_INFO_PATH):
        print("❌ 필요한 JSON 파일이 없습니다.")
        return

    with open(CARDS_EN_PATH, 'r', encoding='utf-8') as f:
        cards = json.load(f)
    
    with open(SERIES_INFO_PATH, 'r', encoding='utf-8') as f:
        series_info_list = json.load(f)

    # 2. 빠른 검색을 위해 시리즈 정보를 사전(Dict)으로 변환 (Key: set_id)
    # 
    series_map = {item['set_id']: item for item in series_info_list}

    fixed_count = 0
    print("🔄 시리즈 정보 매칭 및 수정 시작...")

    # 3. 카드 데이터 수정
    for card in cards:
        # id가 "base1-8" 형태라면 "-" 앞의 "base1"만 추출
        if '-' in card['id']:
            set_id_part = card['id'].split('-')[0]
            
            # 시리즈 정보 파일에서 해당 ID 찾기
            if set_id_part in series_map:
                target_info = series_map[set_id_part]
                
                # 데이터 업데이트
                card['series'] = target_info.get('set_name_us') # 세트명 (Base Set 등)
                card['series_id'] = set_id_part                # 세트 ID (base1 등)
                # 필요하다면 상위 시리즈명(series_name_us)을 추가 필드로 넣을 수도 있습니다.
                
                fixed_count += 1

    # 4. 결과 저장
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)

    print(f"✅ 수정 완료! 총 {fixed_count:,}장의 카드 정보가 업데이트되었습니다.")
    print(f"💾 저장된 파일: {OUTPUT_PATH}")

if __name__ == "__main__":
    fix_card_series_info()