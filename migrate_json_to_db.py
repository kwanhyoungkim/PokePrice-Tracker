import json
import sqlite3
import os

class DataMigrator:
    def __init__(self, db_path="backend/data/pokemon_cards.db"):
        self.db_path = db_path
        # 데이터 디렉토리 생성
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        """각 JSON 파일에 대응하는 테이블 생성"""
        # 1. 영문 카드 리스트 (이름 + 시리즈 + 번호 중복 방지)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS pokemon_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name_en TEXT,
                series_name_en TEXT,
                card_number TEXT,
                UNIQUE(card_name_en, series_name_en, card_number)
            )
        ''')

        # 2. 포켓몬 이름 번역 (도감번호 + 한국어명 + 영어명)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS pokemon_names (
                number TEXT PRIMARY KEY,
                korean_name TEXT,
                english_name TEXT
            )
        ''')

        # 3. 한국 시리즈 정보
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS series_kr_info (
                series_name TEXT PRIMARY KEY,
                thumbnail_url TEXT
            )
        ''')

        # 4. 일본/미국 시리즈 매핑 및 상세 정보
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS series_global_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_name_en TEXT,
                series_name_jp TEXT,
                series_name_us TEXT,
                release_date TEXT,
                era TEXT,
                UNIQUE(series_name_en)
            )
        ''')
        self.conn.commit()

    def migrate_cards(self, file_path):
        """pokemon_card_list_en.json 마이그레이션"""
        data = self._load_json(file_path)
        count = 0
        for item in data:
            self.cursor.execute('''
                INSERT OR IGNORE INTO pokemon_cards (card_name_en, series_name_en, card_number)
                VALUES (?, ?, ?)
            ''', (item['card_name_en'], item['series_name_en'], item['card_number']))
            if self.cursor.rowcount > 0: count += 1
        print(f"✅ 카드 리스트 이전 완료: {count}개 추가")

    def migrate_names(self, file_path):
        """pokemon_names.json 마이그레이션"""
        data = self._load_json(file_path)
        count = 0
        for item in data:
            self.cursor.execute('''
                INSERT OR IGNORE INTO pokemon_names (number, korean_name, english_name)
                VALUES (?, ?, ?)
            ''', (item['number'], item['korean_name'], item['english_name']))
            if self.cursor.rowcount > 0: count += 1
        print(f"✅ 포켓몬 이름 이전 완료: {count}개 추가")

    def migrate_series_kr(self, file_path):
        """pokemon_series_info.json (한국) 마이그레이션"""
        data = self._load_json(file_path)
        count = 0
        for item in data:
            self.cursor.execute('''
                INSERT OR IGNORE INTO series_kr_info (series_name, thumbnail_url)
                VALUES (?, ?)
            ''', (item['series_name'], item['thumbnail_url']))
            if self.cursor.rowcount > 0: count += 1
        print(f"✅ 한국 시리즈 정보 이전 완료: {count}개 추가")

    def migrate_global_series(self, jp_path, us_path):
        """일본 및 미국 시리즈 정보를 통합하여 저장"""
        jp_data = self._load_json(jp_path)
        us_data = self._load_json(us_path)
        
        # 영어 이름을 키로 사용하여 데이터 통합
        combined = {}
        for item in jp_data:
            en_name = item.get('series_name_en')
            combined[en_name] = {
                'en': en_name,
                'jp': item.get('series_name_jp'),
                'date': item.get('release_date'),
                'era': item.get('era'),
                'us': None
            }
        
        for item in us_data:
            en_name = item.get('series_name_us')
            if en_name in combined:
                combined[en_name]['us'] = en_name
            else:
                combined[en_name] = {
                    'en': en_name, 'jp': None, 'us': en_name,
                    'date': item.get('release_date_us'), 'era': item.get('era')
                }

        count = 0
        for info in combined.values():
            self.cursor.execute('''
                INSERT OR IGNORE INTO series_global_info (series_name_en, series_name_jp, series_name_us, release_date, era)
                VALUES (?, ?, ?, ?, ?)
            ''', (info['en'], info['jp'], info['us'], info['date'], info['era']))
            if self.cursor.rowcount > 0: count += 1
        print(f"✅ 글로벌 시리즈 통합 정보 이전 완료: {count}개 추가")

    def _load_json(self, path):
        if not os.path.exists(path):
            print(f"⚠️ 파일을 찾을 수 없음: {path}")
            return []
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def close(self):
        self.conn.commit()
        self.conn.close()

if __name__ == "__main__":
    migrator = DataMigrator()
    
    # 각 파일 경로 설정 (본인의 환경에 맞게 조정)
    data_dir = "backend/data"
    
    migrator.migrate_cards(os.path.join(data_dir, "pokemon_card_list_en.json"))
    migrator.migrate_names(os.path.join(data_dir, "pokemon_names.json"))
    migrator.migrate_series_kr(os.path.join(data_dir, "pokemon_series_info.json"))
    migrator.migrate_global_series(
        os.path.join(data_dir, "pokemon_series_jp_info.json"),
        os.path.join(data_dir, "pokemon_series_us_info.json")
    )
    
    migrator.close()
    print("\n🎉 모든 데이터 마이그레이션이 완료되었습니다!")