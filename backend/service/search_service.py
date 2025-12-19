import sqlite3
import os

class SearchService:
    def __init__(self, db_path, scraper):
        self.db_path = db_path
        self.scraper = scraper

    def translate_ko_to_en(self, ko_name):
        """한글 포켓몬 이름을 영어로 번역 (pokemon_names 테이블)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # pokemon_names 테이블 구조에 따라 컬럼명 확인 필요 (보통 korean_name, english_name)
            query = "SELECT english_name FROM pokemon_names WHERE korean_name = ?"
            cursor.execute(query, (ko_name,))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except Exception as e:
            print(f"❌ 번역 중 오류 발생: {e}")
            return None

    def find_cards_from_db(self, keyword):
        """SQL 파일 구조에 맞게 컬럼명 수정: card_name_en, series_name_en, card_number"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # [수정 완료] SQL 파일의 컬럼명인 card_name_en 등을 사용합니다.
            query = """
                SELECT card_name_en, series_name_en, card_number 
                FROM pokemon_cards 
                WHERE card_name_en LIKE ?
            """
            cursor.execute(query, (f"%{keyword}%",))
            rows = cursor.fetchall()
            conn.close()

            # 결과를 프론트엔드가 기대하는 name, series, number 키값으로 변환
            return [
                {
                    "name": r[0], 
                    "series": r[1], 
                    "number": r[2]
                } for r in rows
            ]
        except Exception as e:
            print(f"❌ DB 검색 중 오류 발생: {e}")
            return []

    def search_card_list(self, user_input):
        print(f"\n--- 검색 시작: {user_input} ---")
        
        # 1. 번역 시도
        english_name = self.translate_ko_to_en(user_input)
        
        if english_name:
            print(f"DEBUG: 번역 성공 '{user_input}' -> '{english_name}'")
            search_target = english_name
        else:
            print(f"DEBUG: 번역 데이터 없음. 입력값 '{user_input}'으로 직접 검색")
            search_target = user_input

        # 2. 카드 DB 검색
        matches = self.find_cards_from_db(search_target)
        
        # 3. 결과가 없을 경우 첫 단어로 재검색 (예: "거북왕 VMAX" -> "거북왕")
        if len(matches) == 0 and ' ' in search_target:
            simplified = search_target.split()[0]
            print(f"DEBUG: 결과 없음. '{simplified}'로 재검색")
            matches = self.find_cards_from_db(simplified)

        print(f"DEBUG: 최종 {len(matches)}건 발견")
        return matches

    def get_ebay_prices(self, name, series, number):
        """이베이 검색어 최적화"""
        # 이름에서 특수문자를 제거하여 검색 성공률을 높임
        clean_name = name.split('&')[0].split('-')[0].strip()
        query = f"{clean_name} {number} pokemon card"
        
        print(f"DEBUG: 이베이 크롤링 시작 -> {query}")
        return self.scraper.fetch_recent_sales(query)