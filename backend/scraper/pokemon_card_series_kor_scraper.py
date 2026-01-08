import json
import time
import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup, NavigableString
import random

# 상수 정의
SERIES_URL = "https://pokemoncard.co.kr/card/category/info1"
# 타임아웃 설정을 유지 (90초)
LONG_TIMEOUT = 90000 

def handle_route(route):
    """이미지, 폰트 파일 로딩을 차단하는 함수."""
    if route.request.resource_type in ["image", "font"]:
        route.abort()
    else:
        route.continue_()

def run_playwright_scraping(url, selector_to_wait, callback_func):
    """Playwright 실행을 캡슐화한 범용 함수 (최종 방어 설정 유지)"""
    try:
        with sync_playwright() as p:
            # 봇 감지 회피 및 성능 설정 유지
            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled"
                ]
            ) 
            page = browser.new_page(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
            
            # 봇 감지 변수 숨기기
            page.evaluate_handle("Object.defineProperty(navigator, 'webdriver', {get: () => false})")
            
            page.route("**/*", handle_route)

            print(f"접속 시도: {url}")
            
            # wait_until='load'로 완화된 접속 대기
            page.goto(url, wait_until="load", timeout=LONG_TIMEOUT) 
            
            # 핵심 요소 로드가 완료될 때까지 90초 대기
            print("콘텐츠 로딩 대기 중...")
            page.wait_for_selector(selector_to_wait, timeout=LONG_TIMEOUT) 
            
            content = page.content()
            browser.close()
            
            return callback_func(content)

    except PlaywrightTimeoutError:
        print(f"\n[오류] 페이지 로딩 또는 요소 대기 중 최종 타임아웃 발생 ({LONG_TIMEOUT // 1000}초 초과).")
        return None 
    except Exception as e:
        print(f"\n[오류] Playwright 실행 중 예상치 못한 오류 발생: {e}")
        return None

# =========================================================================
# 데이터 추출 로직 (발매일 항목 제외)
# =========================================================================

def extract_series_info(content):
    """series/info1 페이지에서 시리즈 이름과 썸네일만 추출합니다."""
    soup = BeautifulSoup(content, 'html.parser')
    series_data = []

    # 성공적으로 작동했던 목록 아이템 셀렉터
    series_items = soup.select('#pinBoot1 > article') 
    
    for item in series_items: 
        
        # 1. 제목 태그 추출 (완벽하게 작동하는 부분)
        title_tag = item.select_one('div > h4')
        title = title_tag.text.strip() if title_tag else "제목 없음"
        
        # 2. 썸네일 URL 추출
        img_tag = item.select_one('img') 
        img_url = img_tag.get('src') if img_tag else "URL 없음"
        
        # ⭐ 데이터에 발매일 항목을 추가하지 않습니다. ⭐
        series_data.append({
            "series_name": title,
            "thumbnail_url": img_url,
        })
        
    return series_data


# =========================================================================
# 메인 실행 및 저장
# =========================================================================

if __name__ == "__main__":
    
    # 시리즈 정보 추출 실행
    final_data = run_playwright_scraping(
        url=SERIES_URL,
        selector_to_wait='#pinBoot1 > article',
        callback_func=extract_series_info
    )
    
    if final_data:
        json_output = json.dumps(final_data, indent=4, ensure_ascii=False)
        print("\n" + "="*50)
        print("스크래핑 최종 결과 (JSON):")
        print("="*50)
        print(json_output)
        
        # JSON 파일 저장
        output_dir = "backend/data"
        file_name = "pokemon_series_info.json"
        
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, file_name) 

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(json_output)
        print(f"\n✅ 최종 결과가 '{output_path}' 파일에 저장되었습니다.")
        
    else:
        print("\n데이터를 가져오는 데 실패했습니다.")