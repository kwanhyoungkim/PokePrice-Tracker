import json
import os
import time
import re
from playwright.sync_api import sync_playwright

# Bulbapedia의 일본판 포켓몬 카드 확장팩 목록
URL = "https://bulbapedia.bulbagarden.net/wiki/List_of_Japanese_Pok%C3%A9mon_Trading_Card_Game_expansions"
# HTML 파싱을 위해 BeautifulSoup을 Playwright와 함께 사용
from bs4 import BeautifulSoup, NavigableString

# 스크래핑 로직: 성공한 로직을 유지하고 출력만 정리
def scrape_bulbapedia_jp_expansions(url):
    """Bulbapedia에서 일본판 확장팩 정보 스크래핑"""
    series_data = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = context.new_page()
        # 타임아웃 90초 설정
        page.set_default_timeout(90000)
        
        try:
            # 페이지 로딩 (최대 90초)
            page.goto(url, wait_until='domcontentloaded', timeout=90000)
            time.sleep(3)
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # 여러 방법으로 표 찾기 (안정성 확보)
            tables = soup.find_all('table', class_='wikitable')
            if not tables:
                tables = soup.find_all('table')

            if len(tables) == 0:
                return []

            for table in tables:
                # 표 제목 확인 (테이블 위의 h3 또는 h4 태그)
                heading = table.find_previous(['h3', 'h4', 'h5'])
                table_title = heading.get_text(strip=True) if heading else "N/A"
                
                # 주요 확장팩 시리즈만 필터링
                is_main_expansion = any(keyword in table_title for keyword in [
                    'Scarlet & Violet', 'Sword & Shield', 'Sun & Moon', 
                    'XY', 'Black & White', 'DP'
                ])
                
                if not is_main_expansion:
                    continue
                
                # 표 행 처리
                rows = table.find_all('tr')[1:]  # 헤더 제외
                
                for row in rows:
                    cols = row.find_all(['td', 'th'])
                    
                    if len(cols) < 2:
                        continue
                        
                    try:
                        # 시리즈 코드 추출
                        code_elem = cols[0] if len(cols) > 0 else None
                        series_code = code_elem.get_text(strip=True) if code_elem else ""
                        
                        series_name_jp = ""
                        series_name_en = ""
                        release_date = ""
                        
                        # 데이터 유형별 추출 (일본어, 영어, 날짜)
                        for col in cols[1:]:
                            text = col.get_text(strip=True)
                            
                            # 일본어 문자 포함 여부 확인
                            if re.search(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]', text):
                                if not series_name_jp:
                                    series_name_jp = text
                            # 날짜 형식 확인
                            elif re.search(r'\d{4}[-./]\d{1,2}[-./]\d{1,2}', text):
                                release_date = text
                            elif re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}', text):
                                release_date = text
                            # 영어 이름
                            elif len(text) > 2 and not series_name_en:
                                series_name_en = text
                                
                        # 유효한 데이터만 추가
                        if series_name_jp or series_name_en:
                            entry = {
                                "series_code": series_code or "N/A",
                                "series_name_jp": series_name_jp or "N/A",
                                "series_name_en": series_name_en or "N/A",
                                "release_date": release_date or "N/A",
                                "era": table_title
                            }
                            series_data.append(entry)
                            
                    except Exception:
                        continue
            
            return series_data
            
        except Exception:
            return []
            
        finally:
            browser.close()

def clean_and_deduplicate(data):
    """중복 제거 및 데이터 정리"""
    seen = set()
    cleaned = []
    
    for item in data:
        key = f"{item['series_code']}_{item['series_name_jp']}"
        if key not in seen and item['series_name_jp'] != 'N/A':
            seen.add(key)
            cleaned.append(item)
    return cleaned

def save_to_json(data, output_dir="backend/data", file_name="pokemon_series_jp_info.json"):
    """JSON 파일로 저장"""
    if not data:
        print("\n❌ 저장할 데이터가 없습니다.")
        return False
    
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, file_name)
    
    json_output = json.dumps(data, indent=2, ensure_ascii=False)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(json_output)
    
    file_size = os.path.getsize(output_path) / 1024
    
    print("\n" + "—"*50)
    print(f"✅ JSON 저장 완료: {output_path}")
    print(f"—"*50)
    print(f"📦 데이터 개수: {len(data)}개")
    print(f"📏 파일 크기: {file_size:.2f} KB")
    
    return True

if __name__ == "__main__":
    print("="*50)
    print("🚀 포켓몬 카드 일본판 시리즈 스크래퍼 시작")
    print("="*50)
    
    # 스크래핑 실행
    raw_data = scrape_bulbapedia_jp_expansions(URL)
    
    if raw_data:
        # 데이터 정리
        cleaned_data = clean_and_deduplicate(raw_data)
        
        # JSON 저장
        save_to_json(cleaned_data)
        
        # 결과 미리보기 (터미널 정리)
        print("\n" + "="*50)
        print("최신 데이터 미리보기 (3개):")
        print("="*50)
        sample_json = json.dumps(cleaned_data[-3:], indent=2, ensure_ascii=False)
        print(sample_json)
        
        print("\n" + "="*50)
        print("✅ 모든 작업 완료!")
        print("="*50)
        
    else:
        print("\n❌ 데이터 수집 실패. (네트워크/사이트 구조 확인 필요)")