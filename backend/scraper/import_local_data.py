import json
import sqlite3
import os
import glob

class LocalDataImporter:
    def __init__(self):
        # 1. 경로 설정 (현재 파일 기준)
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(os.path.dirname(self.current_dir))
        
        # 2. DB 및 클론한 데이터 폴더 경로
        self.db_path = os.path.join(self.root_dir, 'backend', 'data', 'pokemon_cards.db')
        self.json_folder_path = os.path.join(self.root_dir, 'pokemon-tcg-data', 'cards', 'en')
        
        # 3. DB 초기화 (기존 테이블 삭제 및 재생성)
        self._init_db()

    def _init_db(self):
        """기존 테이블을 삭제하고 image_url이 포함된 새 테이블을 생성합니다."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. 기존 테이블이 있다면 삭제 (구조 업데이트를 위해)
        cursor.execute('DROP TABLE IF EXISTS pokemon_cards')
        print("🗑️ 기존 테이블을 삭제했습니다.")
        
        # 2. 새 구조로 테이블 생성 (image_url 포함)
        cursor.execute('''
            CREATE TABLE pokemon_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name_en TEXT,
                series_name_en TEXT,
                card_number TEXT,
                image_url TEXT,
                UNIQUE(card_name_en, series_name_en, card_number)
            )
        ''')
        conn.commit()
        conn.close()
        print(f"✅ DB 초기화 및 새 구조 생성 완료: {self.db_path}")

    def import_all(self):
        """클론한 폴더 내의 모든 JSON 파일을 읽어 DB에 저장합니다."""
        # 모든 세트(.json 파일) 리스트업
        json_files = glob.glob(os.path.join(self.json_folder_path, "*.json"))
        
        if not json_files:
            print(f"❌ JSON 데이터를 찾을 수 없습니다. 경로를 확인하세요: {self.json_folder_path}")
            return

        print(f"🚀 총 {len(json_files)}개의 세트 데이터 임포트 시작...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        total_count = 0
        for file_path in json_files:
            file_name = os.path.basename(file_path)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    cards = json.load(f)
                    
                    batch_count = 0
                    for card in cards:
                        name = card.get('name')
                        series = card.get('set', {}).get('name', 'Unknown')
                        number = card.get('number')
                        # GitHub 데이터 구조에 맞춰 이미지 URL 추출
                        image_url = card.get('images', {}).get('small', '')
                        
                        cursor.execute('''
                            INSERT OR IGNORE INTO pokemon_cards 
                            (card_name_en, series_name_en, card_number, image_url)
                            VALUES (?, ?, ?, ?)
                        ''', (name, series, number, image_url))
                        
                        if cursor.rowcount > 0:
                            batch_count += 1
                            total_count += 1
                    
                    print(f"  📦 {file_name}: {batch_count}장 추가")
            except Exception as e:
                print(f"  ❌ {file_name} 처리 중 오류: {e}")
            
        conn.commit()
        conn.close()
        print(f"\n✨ 완료! 총 {total_count}개의 카드가 DB에 성공적으로 저장되었습니다.")

if __name__ == "__main__":
    importer = LocalDataImporter()
    importer.import_all()
    