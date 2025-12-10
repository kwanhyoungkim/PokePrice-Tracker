from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import json
import os
import time
import re

# 포켓몬 공식 북미 사이트
URL = "https://www.pokemon.com/us/pokemon-tcg/trading-card-expansions"
TIMEOUT = 120000  # 120초

def scrape_pokemon_official_us(url):
    """포켓몬 공식 사이트에서 북미판 확장팩 정보 스크래핑"""
    series_data = []
    
    with sync_playwright() as p:
        print("="*50)
        print("브라우저 시작 및 봇 방어 설정 중...")
        
        browser = p.chromium.launch(
            headless=False,  # 디버깅을 위해 브라우저 창 표시 (성공 후 True로 변경 가능)
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security"
            ]
        )
        
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US'
        )
        
        # 봇 감지 회피 스크립트
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.navigator.chrome = {
                runtime: {}
            };
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)
        
        page = context.new_page()
        page.set_default_timeout(TIMEOUT)
        
        try:
            print(f"페이지 로딩 중: {url}")
            page.goto(url, wait_until='load', timeout=TIMEOUT)
            
            print("JavaScript 렌더링을 위해 10초 강제 대기 중...")
            time.sleep(10)
            
            # ⭐ 핵심 요소 (제목) 대기: <li> 안의 h2.us-title이 로드될 때까지 기다립니다.
            CORE_ELEMENT_SELECTOR = 'li h2.us-title'
            try:
                page.wait_for_selector(CORE_ELEMENT_SELECTOR, timeout=30000) # 30초 대기
                print(f"✅ 핵심 요소 '{CORE_ELEMENT_SELECTOR}' 발견!")
            except PlaywrightTimeoutError:
                print(f"✗ 핵심 요소 '{CORE_ELEMENT_SELECTOR}' 30초 내에 찾지 못함. 하지만 스크래핑 계속 시도.")
            
            # 스크롤하여 모든 콘텐츠 로드
            print("페이지 스크롤 및 로딩 대기 중...")
            for i in range(3):
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(2)
            
            print("✅ 최종 페이지 로딩 완료\n")
            
            # HTML 가져오기
            html = page.content()
            
            # HTML 저장 (디버깅용)
            with open('pokemon_official_debug.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"디버그 HTML 저장: pokemon_official_debug.html ({len(html)} bytes)\n")
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # ⭐ 최종 추출 로직: h2.us-title을 포함하는 모든 <li> 태그를 찾음 ⭐
            # 이 <li>가 고객님이 확인해주신 실제 확장팩 카드의 컨테이너입니다.
            items = soup.select('li:has(h2.us-title)')
            
            if not items:
                 # 안전장치: animating 클래스를 가진 <li>를 찾습니다.
                 items = soup.select('li.animating')

            print(f"BS4를 사용하여 총 {len(items)}개 아이템 발견 및 처리 중...\n")

            if len(items) == 0:
                print("\n⚠️ BeautifulSoup이 확장팩 아이템을 찾을 수 없습니다. (li/h2.us-title 불일치)")
                return []
            
            # 각 아이템에서 데이터 추출
            for idx, item in enumerate(items, 1):
                try:
                    # 1. 제목/이름 추출 (h2.us-title)
                    title_elem = item.select_one('h2.us-title') 
                    title = title_elem.get_text(strip=True) if title_elem else "N/A"
                    
                    if title == "N/A" or len(title) < 3:
                        continue
                    
                    # 2. 로고 이미지 URL 추출 (<li> 내부의 img)
                    img = item.select_one('img') 
                    logo_url = img.get('src', 'N/A') if img else "N/A"
                    if logo_url.startswith('//'):
                        logo_url = 'https:' + logo_url
                    
                    # 3. 발매일 추출 (span.release-date)
                    date_tag = item.select_one('span.release-date') 
                    release_date = date_tag.get_text(strip=True) if date_tag else "N/A"

                    series_data.append({
                        "series_name_us": title,
                        "release_date_us": release_date,
                        "logo_url": logo_url
                    })
                    
                    if idx <= 5:
                        print(f"✓ {title}")
                
                except Exception:
                    continue
            
            print(f"\n✅ 총 {len(series_data)}개의 시리즈 정보 수집 완료\n")
            
            return series_data
            
        except PlaywrightTimeoutError:
            print(f"\n❌ 페이지 로딩 타임아웃 ({TIMEOUT // 1000}초 초과)")
            return []
            
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return []
            
        finally:
            browser.close()


def clean_and_deduplicate(data):
    """중복 제거 및 데이터 정리"""
    seen = set()
    cleaned = []
    
    for item in data:
        key = item['series_name_us']
        
        if key not in seen:
            seen.add(key)
            cleaned.append(item)
    
    removed = len(data) - len(cleaned)
    if removed > 0:
        print(f"중복 제거: {removed}개\n")
    
    return cleaned


def save_to_json(data, output_dir="backend/data", file_name="pokemon_series_us_info.json"):
    """JSON 파일로 저장"""
    if not data:
        print("저장할 데이터가 없습니다.")
        return False
    
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, file_name)
    
    json_output = json.dumps(data, indent=2, ensure_ascii=False)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(json_output)
    
    file_size = os.path.getsize(output_path) / 1024
    print(f"✅ '{output_path}' 파일에 저장 완료!")
    print(f"   - 데이터 개수: {len(data)}개")
    print(f"   - 파일 크기: {file_size:.2f} KB\n")
    
    return True


def main():
    """메인 함수"""
    print("="*70)
    print("포켓몬 카드 게임 북미판 시리즈 스크래퍼 (공식 사이트)")
    print("="*70)
    print("⚠️ 브라우저 창이 열립니다 - 페이지 로딩을 확인하세요")
    print("⏳ 로딩 시간: 30초 ~ 2분 소요\n")
    
    # 스크래핑 실행
    raw_data = scrape_pokemon_official_us(URL)
    
    if not raw_data:
        print("\n❌ 데이터 수집 실패")
        print("\n💡 해결 방법:")
        print("  1. pokemon_official_debug.html 파일을 브라우저로 열어 HTML 구조 확인")
        print("  2. 인터넷 연결 확인 및 VPN 상태 점검")
        return
    
    # 데이터 정리
    cleaned_data = clean_and_deduplicate(raw_data)
    
    # 미리보기
    print("="*70)
    print("수집된 데이터 미리보기 (최신 5개)")
    print("="*70)
    for idx, item in enumerate(cleaned_data[:5], 1):
        print(f"{idx}. {item['series_name_us']}")
        print(f"   발매: {item['release_date_us']}")
        print(f"   로고: {item['logo_url'][:50]}...\n")
    
    # JSON 저장
    print("="*70)
    save_to_json(cleaned_data)
    
    print("="*70)
    print("✅ 완료!")
    print("="*70)


if __name__ == "__main__":
    main()