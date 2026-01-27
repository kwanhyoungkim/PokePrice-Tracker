import requests
import json
import os

# 설정
TCGDEX_EN_SETS_URL = "https://api.tcgdex.net/v2/en/sets"
OUTPUT_JSON = 'backend/data/pokemon_series_us_info.json'

def update_sets_json_only():
    print("="*70)
    print("🌐 TCGdex API를 사용하여 영문 세트(Sets) 정보를 업데이트합니다.")
    print("="*70)

    try:
        # 1. TCGdex API에서 영문 세트 목록 호출
        response = requests.get(TCGDEX_EN_SETS_URL)
        response.raise_for_status()
        api_data = response.json()
        
        updated_sets_list = []
        
        print(f"🔍 총 {len(api_data)}개의 세트를 분석 중...")

        for s in api_data:
            # TCGdex 세트 데이터 구조에서 정보 추출
            set_id = s.get('id')          # 세트 고유 ID (예: sv03.5)
            set_name = s.get('name')      # 세트 이름 (예: 151)
            series_name = s.get('series', {}).get('name') # 소속 시리즈 (예: Scarlet & Violet)
            
            # 로고 및 심볼 URL 생성
            # 로고는 세트의 큰 로고, 심볼은 카드에 박히는 작은 아이콘입니다.
            logo_url = f"{s.get('logo')}.png" if s.get('logo') else None
            symbol_url = f"{s.get('symbol')}.png" if s.get('symbol') else None
            
            # 카드 개수 정보
            card_count = s.get('cardCount', {}).get('total', 0)

            # 저장할 데이터 구조
            entry = {
                "set_id": set_id,                 # 세트 코드
                "set_name_us": set_name,          # 세트 영문명
                "series_name_us": series_name,    # 소속 시리즈명
                "logo_url": logo_url,             # 세트 로고
                "symbol_url": symbol_url,         # 세트 심볼 아이콘
                "card_count": card_count,         # 총 카드 수
                "type": "official-set-api"        # 데이터 출처
            }
            
            updated_sets_list.append(entry)

        # 2. 결과 저장 (JSON 파일로 출력)
        os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
        
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(updated_sets_list, f, indent=2, ensure_ascii=False)
        
        print("\n" + "="*70)
        print(f"🎉 업데이트 완료! 총 {len(updated_sets_list)}개의 세트 정보가 저장되었습니다.")
        print(f"파일 위치: {os.path.abspath(OUTPUT_JSON)}")
        print("="*70)

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    update_sets_json_only()