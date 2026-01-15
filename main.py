import sqlite3
import os
import json
import requests
from dotenv import load_dotenv
from backend.scraper.ebay_scraper import EbayScraper

load_dotenv()

class PokemonPriceApp:
    def __init__(self, db_path="backend/data/pokemon_cards.db"):
        self.db_path = db_path
        self.scraper = EbayScraper()
        self.tcgdex_url = "https://api.tcgdex.net/v2"
        # 세트 정보 보정을 위한 로드
        self.set_data = self.load_sets_data()
        
    def load_sets_data(self):
        sets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sets', 'en.json')
        if not os.path.exists(sets_path):
            return {}
        try:
            with open(sets_path, 'r', encoding='utf-8') as f:
                sets_list = json.load(f)
                return {
                    "name": {s['name'].lower(): s for s in sets_list},
                    "id": {s['id'].lower(): s for s in sets_list}
                }
        except:
            return {}

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def translate_ko_to_en(self, ko_name):
        """DB를 통해 한글 이름을 영어로 변환"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            query = "SELECT english_name FROM pokemon_names WHERE korean_name = ?"
            cursor.execute(query, (ko_name,))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except:
            return None

    def find_cards_via_api(self, en_name, lang_code):
        """TCGdex API를 사용하여 실시간 카드 검색 (이미지 및 정확한 번호 확보)"""
        print(f"📡 TCGdex API 연결 중... ({lang_code})")
        try:
            url = f"{self.tcgdex_url}/{lang_code}/cards"
            params = {'name': en_name}
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                cards = response.json()
                results = []
                for card in cards[:30]: # 상위 30개만 표시
                    results.append({
                        'name': card.get('name'),
                        'series': card.get('set', {}).get('name', 'Unknown'),
                        'series_id': card.get('set', {}).get('id', '').upper(),
                        'number': card.get('localId', '?'),
                        'image_url': f"{card.get('image')}/low.jpg" if card.get('image') else ""
                    })
                return results
        except Exception as e:
            print(f"⚠️ API 검색 실패: {e}")
        return []

    def run(self):
        print("="*60)
        print("🔍 [Ver 3.0] TCGdex API 통합 포켓몬 시세 시스템 (터미널용)")
        print("="*60)

        while True:
            print("\n[ 버전 선택 ]")
            print("1. 영문판 (English)")
            print("2. 일본판 (Japanese)")
            choice = input("원하는 버전을 선택하세요 (1 또는 2, 종료: q): ").strip()

            if choice.lower() == 'q': break
            
            # TCGdex 규격에 맞는 언어 코드 설정
            lang_code = 'ja' if choice == '2' else 'en'
            lang_label = 'JP' if choice == '2' else 'EN'

            user_input = input(f"\n[{lang_label} 검색] 포켓몬 이름 입력: ").strip()
            
            # 1. 이름 변환 (한글 -> 영어)
            english_name = self.translate_ko_to_en(user_input)
            search_target = english_name if english_name else user_input

            # 2. API를 통한 실시간 검색 (중요: 여기서 해당 언어의 정확한 데이터를 가져옴)
            matches = self.find_cards_via_api(search_target, lang_code)
            
            if not matches:
                print(f"❌ '{search_target}'에 해당하는 '{lang_label}' 카드를 찾을 수 없습니다.")
                continue

            print(f"\n✨ '{lang_label}' 버전 검색 결과 ({len(matches)}개 발견):")
            for i, card in enumerate(matches, 1):
                print(f"{i:2d}. {card['name']} | {card['series']} ({card['series_id']}) | #{card['number']}")

            # 3. 카드 선택 및 이베이 조회
            try:
                sel_num = input("\n시세를 확인할 번호를 선택하세요 (취소: c): ").strip()
                if sel_num.lower() == 'c': continue
                
                selected = matches[int(sel_num) - 1]
                
                # 쿼리 생성 로직: 일본판일 경우 'Japanese' 키워드와 세트 ID 강조
                if lang_code == 'ja':
                    ebay_query = f"{selected['series_id']} {selected['name']} {selected['number']} Japanese Pokemon card"
                else:
                    ebay_query = f"{selected['name']} {selected['number']} {selected['series_id']} Pokemon card"
                
                print(f"\n🌐 이베이(eBay) 실거래가 조회 중...")
                print(f"🔎 검색어: {ebay_query}")
                
                results = self.scraper.fetch_recent_sales(ebay_query)
                self.display_results(selected, results, lang_label)
                
            except (ValueError, IndexError):
                print("올바른 번호를 선택해 주세요.")

    def display_results(self, card, results, lang):
        print("\n" + "━"*60)
        print(f"📊 [시세 결과] {card['name']} ({lang} Ver.)")
        print(f"📍 정보: {card['series']} ({card['series_id']}) | 카드번호: #{card['number']}")
        print("━"*60)
        
        if not results:
            print("최근 판매 데이터를 찾을 수 없습니다.")
            return

        for i, item in enumerate(results[:10], 1):
            print(f"{i}. 💰 {item['price']} {item['currency']} | {item['title']}")
            # 스크래퍼에 link 정보가 있다면 아래 주석 해제하여 출력 가능
            # print(f"   🔗 {item.get('link', 'No Link')}")

if __name__ == "__main__":
    app = PokemonPriceApp()
    app.run()