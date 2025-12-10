from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
import time
import re

app = Flask(__name__)

def scrape_ebay_price(product_name, max_results=5):
    """
    Playwright를 사용한 eBay 가격 스크래퍼 (고급 봇 우회)
    """
    with sync_playwright() as p:
        print("브라우저 시작 중...")
        
        # Chromium 사용 (설치 확인됨)
        browser = p.chromium.launch(
            headless=False,
            channel='chrome',  # 일단 창을 보면서 테스트
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
        
        # 브라우저 컨텍스트 생성
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/Los_Angeles',
            permissions=['geolocation'],
            geolocation={'latitude': 37.7749, 'longitude': -122.4194},
            color_scheme='light',
            has_touch=False,
            is_mobile=False,
            java_script_enabled=True,
        )
        
        # JavaScript로 webdriver 감지 우회
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
        page.set_default_timeout(120000)  # 120초
        
        try:
            # 먼저 eBay 홈페이지 방문 (쿠키 얻기)
            print("eBay 홈페이지 방문 중...")
            page.goto('https://www.ebay.com', wait_until='domcontentloaded', timeout=60000)
            time.sleep(3)  # 쿠키 설정 대기
            
            # 검색 URL
            search_url = f'https://www.ebay.com/sch/i.html?_nkw={product_name}'
            
            print(f"검색 중: {product_name}")
            print(f"URL: {search_url}")
            
            # 페이지 로드
            print("페이지 로딩 시작...")
            page.goto(search_url, wait_until='domcontentloaded', timeout=90000)
            
            # 사람처럼 행동
            page.mouse.move(100, 200)
            time.sleep(1)
            page.mouse.move(400, 500)
            time.sleep(2)
            
            print("페이지 로딩 완료!")
            
            # 검색 결과 대기
            print("검색 결과 대기 중...")
            try:
                page.wait_for_selector('.s-item', timeout=30000)
            except:
                try:
                    page.wait_for_selector('.srp-results', timeout=20000)
                except:
                    print("검색 결과 셀렉터를 찾을 수 없음 - CAPTCHA 가능성")
            
            print("검색 결과 찾음!")
            
            # 스크롤 (사람처럼)
            page.evaluate('window.scrollTo(0, 300)')
            time.sleep(1)
            page.evaluate('window.scrollTo(0, 600)')
            time.sleep(1)
            
            # HTML 가져오기
            html = page.content()
            print(f"HTML 크기: {len(html)} bytes")
            
            # BeautifulSoup으로 파싱
            soup = BeautifulSoup(html, 'html.parser')
            
            # 여러 방법으로 검색 결과 찾기
            results = []
            
            # 방법 1: ul.srp-results 안의 li 태그
            items = soup.select('ul.srp-results li.s-item')
            print(f"방법1 (ul.srp-results li.s-item): {len(items)}개 발견")
            
            if not items:
                # 방법 2: 클래스만으로 검색
                items = soup.select('li.s-item')
                print(f"방법2 (li.s-item): {len(items)}개 발견")
            
            if not items:
                # 방법 3: s-item__wrapper로 검색
                items = soup.select('.s-item__wrapper')
                print(f"방법3 (.s-item__wrapper): {len(items)}개 발견")
            
            if not items:
                # 방법 4: 아무 클래스에 s-item이 포함된 것
                items = soup.find_all(class_=lambda x: x and 's-item' in x)
                print(f"방법4 (s-item 포함): {len(items)}개 발견")
            
            print(f"총 {len(items)}개 아이템 발견")
            
            for idx, item in enumerate(items):
                if len(results) >= max_results:
                    break
                    
                try:
                    # 제목 찾기 (여러 방법 시도)
                    title_elem = (
                        item.select_one('.s-item__title span') or 
                        item.select_one('.s-item__title') or
                        item.select_one('[role="heading"]')
                    )
                    
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    # 광고 건너뛰기
                    if not title or 'Shop on eBay' in title or len(title) < 3:
                        print(f"아이템 {idx}: 건너뛰기 - {title}")
                        continue
                    
                    # 가격 찾기
                    price_elem = (
                        item.select_one('.s-item__price') or
                        item.select_one('[class*="price"]')
                    )
                    price = price_elem.get_text(strip=True) if price_elem else 'N/A'
                    
                    # 링크 찾기
                    link_elem = item.select_one('a.s-item__link')
                    link = link_elem.get('href', 'N/A') if link_elem else 'N/A'
                    
                    # 배송 정보
                    shipping_elem = item.select_one('.s-item__shipping')
                    shipping = shipping_elem.get_text(strip=True) if shipping_elem else 'N/A'
                    
                    print(f"✓ 아이템 {idx}: {title[:60]}... | {price}")
                    
                    if price != 'N/A' and title:
                        results.append({
                            'title': title,
                            'price': price,
                            'link': link,
                            'shipping': shipping
                        })
                        
                except Exception as e:
                    print(f"✗ 아이템 {idx} 파싱 오류: {e}")
                    continue
            
            return results
            
        except PlaywrightTimeout as e:
            print(f"타임아웃 상세: {str(e)}")
            raise Exception(f"eBay 페이지 로딩 타임아웃 - {str(e)}")
            
        except Exception as e:
            print(f"상세 오류: {str(e)}")
            raise Exception(f"스크래핑 오류: {str(e)}")
            
        finally:
            browser.close()


@app.route('/api/price', methods=['GET'])
def get_price():
    """
    API 엔드포인트
    예시: /api/price?name=Charizard
    """
    product_name = request.args.get('name')
    
    if not product_name:
        return jsonify({
            'error': '상품명을 입력해주세요',
            'example': '/api/price?name=Charizard'
        }), 400
    
    try:
        print(f"\n=== API 요청 시작 ===")
        print(f"검색어: {product_name}")
        
        start_time = time.time()
        
        # eBay 스크래핑
        results = scrape_ebay_price(product_name)
        
        elapsed_time = time.time() - start_time
        
        print(f"검색 완료: {len(results)}개 결과 ({elapsed_time:.2f}초)")
        print(f"=== API 요청 완료 ===\n")
        
        if not results:
            return jsonify({
                'success': False,
                'message': '검색 결과가 없습니다',
                'query': product_name
            }), 404
        
        return jsonify({
            'success': True,
            'query': product_name,
            'count': len(results),
            'elapsed_time': f"{elapsed_time:.2f}s",
            'results': results
        }), 200
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        return jsonify({
            'error': str(e),
            'query': product_name
        }), 503


@app.route('/health', methods=['GET'])
def health_check():
    """서버 상태 확인"""
    return jsonify({'status': 'healthy'}), 200


if __name__ == '__main__':
    print("eBay 스크래퍼 서버 시작...")
    print("테스트: http://127.0.0.1:5000/api/price?name=Charizard")
    app.run(debug=True, port=5000)