import json
import time
import re
import os
import urllib.parse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import traceback

# =========================================================================
# 1. 환경 설정 및 URL 생성
# =========================================================================

EBAY_BASE_URL = "https://www.ebay.com/sch/i.html"
# 판매 완료(Sold Listings) 및 완료된 항목만 필터링하는 eBay 고정 쿼리 파라미터
EBAY_SOLD_FILTERS = "LH_Complete=1&LH_Sold=1"
# 검색 결과가 포함된 핵심 요소 (로드 확인용)
RESULTS_SELECTOR = '#srp-river-results' 
# 타임아웃 설정
LONG_TIMEOUT = 60000 

def build_ebay_url(card_name: str, series_name: str) -> str:
    """eBay Sold Listings 검색 URL을 생성합니다."""
    # 검색어 조합 (lot, set, bulk는 제외하여 단일 카드 거래만 필터링)
    search_query = f"{card_name} {series_name} pokemon tcg -lot -set -bulk"
    
    # URL 인코딩
    encoded_query = urllib.parse.urlencode({'_nkw': search_query})
    
    # 최종 URL 생성 (최근 완료된 항목 우선순위)
    url = f"{EBAY_BASE_URL}?{encoded_query}&{EBAY_SOLD_FILTERS}&_sop=13" 
    
    print(f"\n[INFO] 검색어: '{search_query}'")
    print(f"[INFO] 타겟 URL: {url}")
    return url

# =========================================================================
# 2. eBay 스크래핑 로직 (Playwright 사용)
# =========================================================================

def scrape_ebay_sold_listings(url: str, limit: int = 10) -> list:
    """
    Playwright를 사용하여 eBay의 판매 완료 목록을 스크래핑합니다.
    """
    listings = []

    # TargetClosedError 방지 및 Anti-Bot 설정 적용
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                # ⭐ 디버그를 위해 잠시 headless=False로 변경하여 눈으로 확인합니다. ⭐
                # 성공하면 다시 headless=True로 변경하세요.
                headless=False, 
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ]
            )
            # 봇 감지 회피를 위한 Context 설정
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 800}
            )
            page = context.new_page()
            page.set_default_timeout(LONG_TIMEOUT)

            # 봇 감지 변수 숨기기
            page.evaluate("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("[INFO] 브라우저 시작 및 페이지 로딩 중...")
            page.goto(url, wait_until='domcontentloaded')
            
            # 핵심 검색 결과 요소가 로드될 때까지 대기
            page.wait_for_selector(RESULTS_SELECTOR, timeout=30000)
            print("✅ 검색 결과 로드 완료.")
            
            # 5초간 추가 대기 (JavaScript 렌더링 완료 시간 확보)
            time.sleep(5)
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # ⭐ 강화된 셀렉터: 가장 포괄적인 아이템 컨테이너를 타겟합니다. ⭐
            item_containers = soup.select('li.s-item')
            
            if not item_containers:
                 print("❌ 오류: 검색 결과 아이템을 찾을 수 없습니다. (HTML 구조 변경 또는 봇 감지)")
                 return []
            
            print(f"총 {len(item_containers)}개의 아이템 컨테이너 발견. 상위 {limit}개 추출.")

            for i, item in enumerate(item_containers):
                if len(listings) >= limit:
                    break
                    
                # 1. 제목 추출 (가장 일반적인 제목 셀렉터)
                title_elem = item.select_one('div.s-item__title')
                title = title_elem.get_text(strip=True).replace('New Listing', '').strip() if title_elem else None
                
                # 2. 가격 추출 (가장 일반적인 가격 셀렉터)
                price_elem = item.select_one('span.s-item__price')
                price_text = price_elem.get_text(strip=True) if price_elem else None
                
                # 3. 판매일/상태 추출 (Sold date, Completed status)
                # sold-info 태그를 사용하여 추출을 시도합니다.
                status_elem = item.select_one('.s-item__detail--value')
                status_text = status_elem.get_text(strip=True) if status_elem else "정보 없음"

                # 가격 텍스트 정리 및 유효성 검사
                final_price = "N/A"
                if price_text:
                    # US$ 기호를 기준으로 가격 문자열 추출
                    price_match = re.search(r'US\s*\$([\d,\.]+)', price_text)
                    final_price = price_match.group(1) if price_match else "N/A"
                
                # 유효성 검사 및 디버그 출력
                if not title or final_price == "N/A" or "Shop by Category" in title:
                    # 광고나 불필요한 빈 요소를 걸러냅니다.
                    if title:
                        print(f"    [DEBUG] Item {i+1} 스킵됨 (제목:{title[:30]}..., 가격:{final_price})")
                    continue

                # Data appending
                listings.append({
                    "title": title,
                    "sold_price": final_price,
                    "sold_currency": "USD", # eBay US 사이트 기준
                    "sold_date_status": status_text
                })
                print(f"    [DEBUG] Item {i+1}: 성공 추출. 제목: {title[:30]}..., 가격: {final_price}")

        except PlaywrightTimeoutError:
            print("\n❌ 오류: 페이지 로딩 시간 초과 (네트워크 문제 또는 강력한 봇 감지 차단)")
        except Exception as e:
            print(f"\n❌ 예상치 못한 오류 발생: {e}")
            traceback.print_exc()
        finally:
            if 'browser' in locals():
                browser.close()
            
    return listings

# =========================================================================
# 3. 메인 실행 함수 (동일)
# =========================================================================

def main():
    """사용자 입력을 받고 스크래핑을 실행합니다."""
    print("="*50)
    print("포켓몬 카드 eBay 최근 거래가 확인 프로그램")
    print("="*50)
    print("⚠️ 주의: eBay는 봇 감지 시스템이 매우 강력합니다. 반복 실행 시 IP가 차단될 수 있습니다.")
    print("--------------------------------------------------")

    card_name = input("🔍 검색할 포켓몬 카드 이름 (예: Charizard): ").strip()
    series_name = input("🔍 검색할 카드 시리즈 이름 (예: Base Set, Evolving Skies): ").strip()
    
    if not card_name or not series_name:
        print("\n[ERROR] 카드 이름과 시리즈 이름은 필수 입력 항목입니다.")
        return

    search_url = build_ebay_url(card_name, series_name)
    recent_listings = scrape_ebay_sold_listings(search_url)

    print("\n" + "="*50)
    print(f"📉 '{card_name} ({series_name})'의 최근 eBay 거래가 (USD) 결과")
    print("="*50)

    if not recent_listings:
        print("결과를 찾을 수 없거나 봇 감지로 인해 차단되었습니다.")
        print("입력한 카드 이름과 시리즈 이름이 정확한지 확인 후 다시 시도해 주세요.")
        return

    for i, listing in enumerate(recent_listings, 1):
        print(f"[{i:02d}] 💵 {listing['sold_price']} {listing['sold_currency']}")
        print(f"      - 제목: {listing['title'][:70]}...")
        print(f"      - 상태: {listing['sold_date_status']}")
        print("-" * 20)
        
    print(f"\n총 {len(recent_listings)}개의 최근 거래가 확인 완료.")


if __name__ == "__main__":
    main()