import requests
import json
import os
import time

POKEAPI_BASE = "https://pokeapi.co/api/v2"
# 파일 경로는 기존과 동일
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "../data/pokemon_names.json")

def fetch_pokemon_names(max_pokemon=1025):
    """PokeAPI에서 포켓몬 이름(한/영/일) 수집"""
    print("=" * 70)
    print(f"PokeAPI에서 포켓몬 데이터 수집 중 (최대 {max_pokemon}개)")
    print("=" * 70)
    print("⏱️  예상 소요 시간: 4-6분 (데이터 항목 추가로 약간 증가)")
    print("=" * 70 + "\n")
    
    pokemon_data = []
    
    for pokemon_id in range(1, max_pokemon + 1):
        try:
            if pokemon_id % 50 == 0:
                print(f"진행: {pokemon_id}/{max_pokemon} ({pokemon_id/max_pokemon*100:.1f}%)")
            
            pokemon_url = f"{POKEAPI_BASE}/pokemon/{pokemon_id}"
            response = requests.get(pokemon_url, timeout=10)
            
            if response.status_code == 404:
                continue
            
            response.raise_for_status()
            pokemon_detail = response.json()
            
            # 영어 이름 (API 기본값)
            english_name = pokemon_detail['name'].replace('-', ' ').title()
            number = str(pokemon_detail['id']).zfill(4)
            
            # 상세 종 정보(Species) 호출
            species_url = pokemon_detail['species']['url']
            species_response = requests.get(species_url, timeout=10)
            species_response.raise_for_status()
            species_data = species_response.json()
            
            # 언어별 이름 초기화
            korean_name = None
            japanese_name = None
            
            # names 배열을 돌며 ko(한국어)와 ja(일본어) 추출
            for name_entry in species_data.get('names', []):
                lang = name_entry.get('language', {}).get('name')
                
                if lang == 'ko':
                    korean_name = name_entry.get('name')
                elif lang == 'ja': # 일본어 이름 (한자 섞임 또는 카타카나)
                    japanese_name = name_entry.get('name')
            
            # 데이터 백업 (이름이 없을 경우 영어로 대체)
            if not korean_name: korean_name = english_name
            if not japanese_name: japanese_name = english_name
            
            pokemon_data.append({
                "number": number,
                "korean_name": korean_name,
                "english_name": english_name,
                "japanese_name": japanese_name 
            })
            
            time.sleep(0.1)
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️  포켓몬 #{pokemon_id} 처리 실패: {e}")
            continue
        except KeyboardInterrupt:
            print("\n\n중단됨! 저장 시도 중...")
            break
    
    return pokemon_data

def save_to_json(data, filename):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n✅ {len(data)}개의 데이터를 저장했습니다.")
        return True
    except IOError as e:
        print(f"❌ 저장 실패: {e}")
        return False

if __name__ == "__main__":
    pokemon_names = fetch_pokemon_names(max_pokemon=1025)
    
    if pokemon_names:
        pokemon_names.sort(key=lambda x: int(x['number']))
        
        print("\n[ 처음 5개 포켓몬 샘플 ]")
        for p in pokemon_names[:5]:
            # 한/영/일 출력 확인
            print(f"  #{p['number']} {p['korean_name']} | {p['english_name']} | {p['japanese_name']}")
        
        save_to_json(pokemon_names, OUTPUT_FILE)