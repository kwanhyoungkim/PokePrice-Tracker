import json
import os
from dotenv import load_dotenv
from backend.scraper.ebay_scraper import EbayScraper

# .env 파일 로드
load_dotenv()

class PokemonPriceApp:
    def __init__(self, db_path="backend/data/pokemon_card_list_en.json"):
        self.db_path = db_path
        self.card_db = self._load_database()
        self.scraper = EbayScraper()

    def _load_database(self):
        """스크래핑된 카드 JSON 데이터를 로드"""
        if not os.path.exists(self.db_path):
            print(f"⚠️ 데이터베이스 파일이 없습니다: {self.db_path}")
            return []
        with open(self.db_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def find_cards_by_name(self, search_name):
        """로컬 DB에서 이름이 유사한 카드들을 검색"""
        return [card for card in self.card_db if search_name.lower() in card['card_name_en'].lower()]

    def run(self):
        print("="*60)
        print("🔍 포켓몬 카드 이베이 시세 조회 시스템")
        print("="*60)

        while True:
            search_input = input("\n검색할 포켓몬 이름을 입력하세요 (종료: q): ").strip()
            
            if search_input.lower() == 'q':
                print("프로그램을 종료합니다.")
                break

            # 1. 로컬 DB에서 후보 카드 검색
            matches = self.find_cards_by_name(search_input)
            
            if not matches:
                print(f"❌ '{search_input}'에 해당하는 카드를 DB에서 찾을 수 없습니다.")
                continue

            print(f"\n검색 결과 {len(matches)}개가 발견되었습니다.")
            for i, card in enumerate(matches[:10], 1): # 최대 10개만 출력
                print(f"{i}. {card['card_name_en']} | {card['series_name_en']} | {card['card_number']}")

            # 2. 카드 선택
            try:
                choice = int(input("\n시세를 확인할 번호를 선택하세요: ")) - 1
                selected_card = matches[choice]
            except (ValueError, IndexError):
                print("올바른 번호를 선택해 주세요.")
                continue

            # 3. 이베이 쿼리 생성 및 검색
            # 예: "Charizard Base Set 4/102 Pokemon card"
            query = f"{selected_card['card_name_en']} {selected_card['series_name_en']} {selected_card['card_number']} Pokemon card"
            print(f"\n🌐 이베이에서 최신 시세를 가져오는 중... ({query})")
            
            ebay_results = self.scraper.fetch_recent_sales(query)

            # 4. 결과 출력
            self.display_results(selected_card, ebay_results)

    def display_results(self, card, results):
        """가져온 이베이 데이터를 보기 좋게 출력"""
        print("\n" + "-"*60)
        print(f"📊 [시세 결과] {card['card_name_en']} ({card['series_name_en']})")
        print("-"*60)

        if isinstance(results, dict) and "error" in results:
            print(f"에러 발생: {results['error']}")
            return

        if not results:
            print("최근 판매 기록이 없습니다.")
            return

        for item in results:
            print(f"💰 가격: {item['price']} {item['currency']}")
            print(f"📝 제목: {item['title']}")
            print(f"🔗 링크: {item['item_url']}")
            print("-" * 30)

if __name__ == "__main__":
    app = PokemonPriceApp()
    app.run()