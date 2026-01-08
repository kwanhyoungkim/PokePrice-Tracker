import sqlite3
import os
from dotenv import load_dotenv
from backend.scraper.ebay_scraper import EbayScraper

load_dotenv()

class PokemonPriceApp:
    def __init__(self, db_path="backend/data/pokemon_cards.db"):
        self.db_path = db_path
        self.scraper = EbayScraper()
        
    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def translate_ko_to_en(self, ko_name):
        """한글 포켓몬 이름을 입력받아 영어 이름을 반환"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # pokemon_names 테이블에서 한글 이름으로 영어 이름 조회
        query = "SELECT english_name FROM pokemon_names WHERE korean_name = ?"
        cursor.execute(query, (ko_name,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None

    def find_cards_from_db(self, en_name):
        """영어 이름으로 카드 리스트(시리즈, 번호) 검색"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # pokemon_cards 테이블에서 영어 이름이 포함된 카드들 검색
        query = "SELECT card_name_en, series_name_en, card_number FROM pokemon_cards WHERE card_name_en LIKE ?"
        cursor.execute(query, (f'%{en_name}%',))
        results = cursor.fetchall()
        conn.close()
        
        return [{"name": r[0], "series": r[1], "number": r[2]} for r in results]

    def run(self):
        print("="*60)
        print("🔍 한글/영문 지원 포켓몬 카드 시세 조회 시스템")
        print("="*60)

        while True:
            user_input = input("\n검색할 포켓몬 이름(한글 또는 영문)을 입력하세요 (종료: q): ").strip()
            
            if user_input.lower() == 'q': break

            # 1. 번역 시도 (한글 입력 대응)
            english_name = self.translate_ko_to_en(user_input)
            
            if english_name:
                print(f"✅ 번역 완료: {user_input} -> {english_name}")
                search_target = english_name
            else:
                # 번역 결과가 없으면 사용자가 직접 영어로 입력했을 가능성 고려
                search_target = user_input

            # 2. 카드 DB 검색
            matches = self.find_cards_from_db(search_target)
            
            if not matches:
                print(f"❌ '{search_target}'에 해당하는 카드를 찾을 수 없습니다.")
                continue

            print(f"\n검색 결과 {len(matches)}개가 발견되었습니다.")
            for i, card in enumerate(matches[:15], 1):
                print(f"{i}. {card['name']} | {card['series']} | {card['number']}")

            # 3. 카드 선택 및 이베이 조회
            try:
                choice = int(input("\n시세를 확인할 번호를 선택하세요: ")) - 1
                selected = matches[choice]
                
                # 최종 이베이 쿼리 생성
                ebay_query = f"{selected['name']} {selected['series']} {selected['number']} Pokemon card"
                print(f"\n🌐 이베이 검색 중... ({ebay_query})")
                
                results = self.scraper.fetch_recent_sales(ebay_query)
                self.display_results(selected, results)
                
            except (ValueError, IndexError):
                print("올바른 번호를 선택해 주세요.")

    def display_results(self, card, results):
        print("\n" + "-"*60)
        print(f"📊 [시세 결과] {card['name']} ({card['series']})")
        print("-"*60)
        if not results or "error" in results:
            print("데이터를 가져오지 못했습니다.")
            return
        for item in results[:5]:
            print(f"💰 {item['price']} {item['currency']} | {item['title']}")

if __name__ == "__main__":
    app = PokemonPriceApp()
    app.run()