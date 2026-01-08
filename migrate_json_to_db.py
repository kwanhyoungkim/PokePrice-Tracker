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
        """각 JSON 파일의 구조에 맞는 테이블 정의"""
        # 1. 영문 카드 리스트 테이블
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS pokemon_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name_en TEXT,
                series_name_en TEXT,
                card_number TEXT,
                UNIQUE(card_name_en, series_name_en, card_number)
            )
        ''')

        # 2. 포켓몬 이름 번역 테이블 (한/영)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS pokemon_names (
                number TEXT PRIMARY KEY,
                korean_name TEXT,
                english_name TEXT
            )
        ''')

        # 3. 한국 시리즈 정보 테이블
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS series_kr_info (
                series_name TEXT PRIMARY KEY,
                thumbnail_url TEXT
            )
        ''')

        # 4. 글로벌(일/미) 시리즈 통합 정보 테이블
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
        """pokemon_card_list_en.json 데이터를 DB로 이전"""
        data = self._load_json(file_path)
        count = 0
        for item in data:
            self.cursor.execute('''
                INSERT OR IGNORE INTO pokemon_cards (card_name_en, series_name_en, card_number)
                VALUES (?, ?, ?)
            ''', (item.get('card_name_en'), item.get('series_name_en'), item.get('card_number')))
            if self.cursor.rowcount > 0: count += 1
        print(f"✅ 카드 리스트 이전 완료: {count}개 추가")

    def migrate_names(self, file_path):
        """pokemon_names.json 데이터를 DB로 이전"""
        data = self._load_json(file_path)
        count = 0
        for item in data:
            self.cursor.execute('''
                INSERT OR IGNORE INTO pokemon_names (number, korean_name, english_name)
                VALUES (?, ?, ?)
            ''', (item.get('number'), item.get('korean_name'), item.get('english_name')))
            if self.cursor.rowcount > 0: count += 1
        print(f"✅ 포켓몬 이름 이전 완료: {count}개 추가")

    def migrate_series_kr(self, file_path):
        """pokemon_series_info.json 데이터를 DB로 이전"""
        data = self._load_json(file_path)
        count = 0
        for item in data:
            self.cursor.execute('''
                INSERT OR IGNORE INTO series_kr_info (series_name, thumbnail_url)
                VALUES (?, ?)
            ''', (item.get('series_name'), item.get('thumbnail_url')))
            if self.cursor.rowcount > 0: count += 1
        print(f"✅ 한국 시리즈 정보 이전 완료: {count}개 추가")

    def migrate_global_series(self, jp_path, us_path):
        """일본/미국 시리즈 정보를 영어 이름 기준으로 통합하여 이전"""
        jp_data = self._load_json(jp_path)
        us_data = self._load_json(us_path)
        
        combined = {}
        # 일본 데이터 기준 생성
        for item in jp_data:
            en_name = item.get('series_name_en')
            combined[en_name] = {
                'en': en_name,
                'jp': item.get('series_name_jp'),
                'date': item.get('release_date'),
                'era': item.get('era'),
                'us': None
            }
        
        # 미국 데이터 매핑
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

    def backup_to_sql(self, sql_path="backend/database/pokemon_cards_backup.sql"):
        """DB 내용을 사람이 읽을 수 있는 SQL 텍스트 파일로 저장 (덤프)"""
        os.makedirs(os.path.dirname(sql_path), exist_ok=True)
        try:
            with open(sql_path, 'w', encoding='utf-8') as f:
                for line in self.conn.iterdump():
                    f.write(f'{line}\n')
            print(f"📄 SQL 텍스트 백업 완료: {sql_path}")
        except Exception as e:
            print(f"❌ SQL 백업 중 오류 발생: {e}")

    def _load_json(self, path):
        if not os.path.exists(path):
            print(f"⚠️ 파일을 찾을 수 없습니다: {path}")
            return []
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def close(self):
        self.conn.commit()
        # 닫기 직전에 자동으로 SQL 백업 실행
        self.backup_to_sql()
        self.conn.close()

if __name__ == "__main__":
    migrator = DataMigrator()
    
    # JSON 파일들이 위치한 경로 (수정 필요 시 변경)
    data_dir = "backend/data"
    
    print("🚀 데이터베이스 마이그레이션을 시작합니다...")
    
    # 1. 카드 리스트 이전
    migrator.migrate_cards(os.path.join(data_dir, "pokemon_card_list_en.json"))
    
    # 2. 이름 번역 이전
    migrator.migrate_names(os.path.join(data_dir, "pokemon_names.json"))
    
    # 3. 한국 시리즈 이전
    migrator.migrate_series_kr(os.path.join(data_dir, "pokemon_series_info.json"))
    
    # 4. 글로벌 시리즈 통합 이전
    migrator.migrate_global_series(
        os.path.join(data_dir, "pokemon_series_jp_info.json"),
        os.path.join(data_dir, "pokemon_series_us_info.json")
    )
    
    # 저장 및 자동 백업 후 종료
    migrator.close()
    print("\n✨ 모든 작업이 성공적으로 마무리되었습니다!")