import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """애플리케이션 전역 설정 관리"""

    def __init__(self):
        # 환경 변수 로드
        self.EBAY_APP_ID = os.getenv('EBAY_APP_ID', '')
        self.DB_URL = os.getenv('DB_URL', 'sqlite:///pokemon_mapping.db')
        
        # 'API' 또는 'WEB' 스크래퍼 타입을 결정합니다.
        # EBAY_APP_ID가 설정되어 있으면 'API'를 기본으로 합니다.
        if self.EBAY_APP_ID:
            self.SCRAPER_TYPE = os.getenv('SCRAPER_TYPE', 'API')
        else:
            # API 키가 없으면 웹 스크래퍼를 사용합니다. (Mocking 기간 동안)
            self.SCRAPER_TYPE = os.getenv('SCRAPER_TYPE', 'WEB')

    def get_scraper_type(self) -> str:
        """현재 사용 중인 스크래퍼 타입 (API 또는 WEB)을 반환"""
        return self.SCRAPER_TYPE

# 싱글톤 패턴으로 설정 객체 생성
def get_config() -> Config:
    return Config()

# 테스트 코드
if __name__ == "__main__":
    config = get_config()
    print("=" * 50)
    print("✅ Configuration Test")
    print("=" * 50)
    print(f"Scraper Type (Default: WEB if no key): {config.get_scraper_type()}")
    print(f"DB URL: {config.DB_URL}")
    if not config.EBAY_APP_ID:
         print("⚠️  EBAY_APP_ID가 .env에 설정되지 않아 'WEB' 스크래퍼가 사용됩니다.")