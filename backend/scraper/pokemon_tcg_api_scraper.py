import requests
import json
import os
import time
from typing import Dict, List, Any

# =========================================================================
# 1. 설정 및 경로
# =========================================================================
BASE_URL = "https://api.pokemontcg.io/v2"

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "data")

TRANSLATION_FILE_PATHS = {
    "pokemon": os.path.join(DATA_DIR, "pokemon_names.json"),
    "series_kr": os.path.join(DATA_DIR, "pokemon_series_info.json"),
    "series_jp": os.path.join(DATA_DIR, "pokemon_series_jp_info.json"),
    "series_en": os.path.join(DATA_DIR, "pokemon_series_us_info.json")
}

OUTPUT_FILE = os.path.join(DATA_DIR, "all_korean_pokemon_cards.json")

TRANSLATION_MAPS = {
    "pokemon": {}, "series_kr": {}, "series_jp": {}, "series_en": {}
}

# =========================================================================
# 2. 유틸리티 함수
# =========================================================================

def load_all_translations():
    print("="*70)
    print(f"📂 로컬 데이터 로드 중...")
    for key, path in TRANSLATION_FILE_PATHS.items():
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                TRANSLATION_MAPS[key] = json.load(f)
                print(f"✅ {key} 로드 성공! (항목 수: {len(TRANSLATION_MAPS[key])})")
    print("="*70)

def translate_pokemon_name(eng_name: str) -> str:
    name = eng_name
    suffix = ''
    for s in [' ex', ' V', ' VMAX', ' VSTAR', ' GX', ' EX', ' BREAK', ' TAG TEAM']:
        if name.endswith(s):
            suffix = s
            name = name[:-len(s)].strip()
            break
    
    p_data = TRANSLATION_MAPS['pokemon']
    kor_name = name
    if isinstance(p_data, list):
        for item in p_data:
            if isinstance(item, dict):
                # 키 이름에 상관없이 en이 포함된 키나 첫 번째 키를 영어로 간주
                vals = list(item.values())
                keys = list(item.keys())
                if name in vals:
                    # 'kr' 키가 있으면 사용, 없으면 리스트의 마지막 값 사용
                    kor_name = item.get('kr') or vals[-1]
                    break
    elif isinstance(p_data, dict):
        kor_name = p_data.get(name, name)
    return kor_name + suffix

def get_series_translated(eng_series: str, lang_key: str) -> str:
    s_data = TRANSLATION_MAPS.get(lang_key, {})
    if isinstance(s_data, list):
        for item in s_data:
            if isinstance(item, dict):
                vals = list(item.values())
                if eng_series in vals:
                    return item.get('kr') or item.get('jp') or vals[-1]
    elif isinstance(s_data, dict):
        return s_data.get(eng_series, eng_series)
    return eng_series

# =========================================================================
# 3. 메인 스크래핑 로직
# =========================================================================

def fetch_all_cards():
    load_all_translations()
    
    series_data = TRANSLATION_MAPS['series_kr']
    search_targets = []

    # ⭐ [수정 포인트] JSON 구조가 어떤 형태든 영어 이름을 찾아냅니다.
    if isinstance(series_data, list):
        for item in series_data:
            if isinstance(item, dict):
                # 'en' 키가 있으면 사용, 없으면 딕셔너리의 첫 번째 값을 영어 이름으로 간주
                eng_name = item.get('en') or list(item.values())[0]
                # 'kr' 키가 있으면 사용, 없으면 딕셔너리의 마지막 값을 한글 이름으로 간주
                kor_name = item.get('kr') or list(item.values())[-1]
                
                if eng_name:
                    search_targets.append({'en': eng_name, 'kr': kor_name})
            elif isinstance(item, str):
                search_targets.append({'en': item, 'kr': item})
    
    if not search_targets:
        print("❌ 수집할 영문 세트 목록을 추출하지 못했습니다.")
        print("💡 JSON 파일 내용을 확인해 주세요: ", str(series_data)[:100], "...")
        return

    all_cards = []
    print(f"\n🚀 총 {len(search_targets)}개 세트 수집 시작...\n")

    for target in search_targets:
        set_en = target['en']
        set_kr = target['kr']
        
        # 만약 첫 번째 값이 한글이라면 수집이 안 되므로 로그에 출력
        print(f"🔍 세트 수집 중: {set_en} (표기명: {set_kr})")
        
        page = 1
        set_card_count = 0
        
        while True:
            try:
                params = {'q': f'set.name:"{set_en}"', 'page': page, 'pageSize': 250}
                response = requests.get(f"{BASE_URL}/cards", params=params, timeout=60)
                
                if response.status_code != 200:
                    break
                    
                data = response.json()
                cards = data.get('data', [])
                if not cards: break
                
                for card in cards:
                    eng_name = card.get('name', 'N/A')
                    eng_series = card.get('set', {}).get('name', 'N/A')
                    
                    all_cards.append({
                        'card_name_en': eng_name,
                        'card_name_kr': translate_pokemon_name(eng_name),
                        'series_name_en': eng_series,
                        'series_name_kr': get_series_translated(eng_series, 'series_kr'),
                        'series_name_jp': get_series_translated(eng_series, 'series_jp'),
                        'card_number': card.get('number', 'N/A'),
                        'rarity': card.get('rarity', 'N/A'),
                        'image_url': card.get('images', {}).get('small', 'N/A')
                    })
                    set_card_count += 1
                
                if len(cards) < 250: break
                page += 1
                time.sleep(0.3)
                
            except Exception as e:
                print(f"  ⚠️ 오류: {e}")
                break
        
        print(f"  ✅ {set_card_count}개 완료 (누적: {len(all_cards):,})")

    save_data(all_cards)

def save_data(data: List[Dict[str, Any]]):
    if not data: return
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    unique_data = {(item['card_name_en'], item['card_number']): item for item in data}
    final_list = list(unique_data.values())
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_list, f, ensure_ascii=False, indent=2)
    print(f"\n🎉 저장 완료! (총 {len(final_list):,}개)")

if __name__ == "__main__":
    fetch_all_cards()