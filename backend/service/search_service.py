import sqlite3
import os
from backend.scraper.ebay_scraper import EbayScraper

class SearchService:
    def __init__(self, db_path=None):
        # 프로젝트 루트 기준 경로 설정
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.db_path = os.path.join(base_dir, "backend/data/pokemon_cards.db")
        else:
            self.db_path = db_path
        
        self.scraper = EbayScraper()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def search_card_list(self, keyword):
        """한글 번역 후 DB에서 카드 리스트 조회"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 1. 한글명 -> 영어명 번역 조회
        cursor.execute("SELECT english_name FROM pokemon_names WHERE korean_name = ?", (keyword,))
        row = cursor.fetchone()
        search_target = row[0] if row else keyword
        
        # 2. 관련 카드 리스트 조회 (이름에 영문명이 포함된 것들)
        cursor.execute("""
            SELECT card_name_en, series_name_en, card_number 
            FROM pokemon_cards 
            WHERE card_name_en LIKE ?
        """, (f'%{search_target}%',))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{"name": r[0], "series": r[1], "number": r[2]} for r in rows]

    def get_ebay_prices(self, name, series, number):
        """특정 카드의 이베이 실시간 시세 조회"""
        query = f"{name} {series} {number} Pokemon card"
        return self.scraper.fetch_recent_sales(query)