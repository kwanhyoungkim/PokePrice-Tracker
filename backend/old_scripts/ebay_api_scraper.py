import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import time

class EbayScraper:
    """eBay 판매 완료 데이터 웹 스크래핑"""
    
    BASE_URL = "https://www.ebay.com/sch/i.html"
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        self.session = requests.Session()
        print("✅ eBay 웹 스크래퍼 초기화 완료 (설정 불필요)")
    
    def search_sold_cards(self, card_name, max_results=50):
        """판매 완료된 카드 검색
        
        Args:
            card_name: 검색할 카드 이름 (영어)
            max_results: 최대 결과 수
            
        Returns:
            list: 카드 정보 딕셔너리 리스트
        """
        search_query = f"{card_name} pokemon card"
        
        params = {
            '_nkw': search_query,
            'LH_Sold': '1',        # 판매 완료
            'LH_Complete': '1',    # 거래 완료
            '_sop': '13',          # 최신순
            '_ipg': '60',          # 페이지당 60개
        }
        
        try:
            print(f"🔍 eBay 검색: {search_query}")
            response = self.session.get(
                self.BASE_URL,
                params=params,
                headers=self.headers,
                timeout=15
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = self._parse_results(soup, max_results)
            
            print(f"✅ 검색 완료: {len(results)}개 결과")
            return results
            
        except requests.RequestException as e:
            print(f"❌ eBay 검색 실패: {e}")
            return []
    
    def _parse_results(self, soup, max_results):
        """검색 결과 파싱"""
        results = []
        
        # eBay 검색 결과 아이템 찾기
        items = soup.find_all('div', class_='s-item__wrapper', limit=max_results)
        
        if not items:
            # 대체 셀렉터 시도
            items = soup.find_all('li', class_='s-item', limit=max_results)
        
        print(f"📦 발견된 아이템: {len(items)}개")
        
        for item in items:
            card_data = self._parse_item(item)
            if card_data:
                results.append(card_data)
        
        return results
    
    def _parse_item(self, item):
        """개별 아이템 파싱"""
        try:
            # 제목
            title_elem = item.find('div', class_='s-item__title')
            if not title_elem:
                title_elem = item.find('h3', class_='s-item__title')
            
            if not title_elem or 'Shop on eBay' in title_elem.get_text():
                return None
            
            title = title_elem.get_text(strip=True)
            
            # 가격
            price_elem = item.find('span', class_='s-item__price')
            if not price_elem:
                return None
            
            price = self._extract_price(price_elem.get_text())
            if price == 0.0:
                return None
            
            # URL
            link_elem = item.find('a', class_='s-item__link')
            url = link_elem.get('href') if link_elem else None
            
            # 이미지
            img_elem = item.find('img', class_='s-item__image-img')
            if not img_elem:
                img_elem = item.find('img')
            image_url = img_elem.get('src') if img_elem else None
            
            # 카드 상태
            condition = self._extract_condition(title)
            
            # 판매 날짜 (현재 시간으로 근사)
            sale_date = datetime.utcnow()
            
            return {
                'title': title,
                'price': price,
                'currency': 'USD',
                'sale_date': sale_date.isoformat(),
                'condition': condition,
                'url': url,
                'image_url': image_url
            }
            
        except Exception as e:
            # 개별 아이템 파싱 실패는 조용히 무시
            return None
    
    def _extract_price(self, price_text):
        """가격 텍스트에서 숫자 추출"""
        try:
            # $25.00, $1,234.56 등의 형태
            match = re.search(r'[\$]?([\d,]+\.?\d*)', price_text)
            if match:
                price_str = match.group(1).replace(',', '')
                return float(price_str)
        except:
            pass
        return 0.0
    
    def _extract_condition(self, title):
        """제목에서 카드 상태 추출"""
        title_lower = title.lower()
        
        conditions = [
            ('psa 10', 'PSA 10'),
            ('psa 9', 'PSA 9'),
            ('psa 8', 'PSA 8'),
            ('psa 7', 'PSA 7'),
            ('bgs 10', 'BGS 10'),
            ('bgs 9.5', 'BGS 9.5'),
            ('cgc 10', 'CGC 10'),
            ('cgc 9.5', 'CGC 9.5'),
            ('mint', 'Mint'),
            ('near mint', 'Near Mint'),
            ('nm', 'Near Mint'),
            ('excellent', 'Excellent'),
            ('lightly played', 'Lightly Played'),
            ('lp', 'Lightly Played'),
            ('played', 'Played'),
            ('good', 'Good'),
            ('damaged', 'Damaged'),
        ]
        
        for keyword, condition in conditions:
            if keyword in title_lower:
                return condition
        
        return 'Ungraded'


# 테스트 코드
if __name__ == "__main__":
    print("=" * 70)
    print("eBay 웹 스크래퍼 테스트")
    print("=" * 70)
    print("⚠️  실제로 eBay를 스크래핑합니다. (10-15초 소요)")
    print("=" * 70 + "\n")
    
    scraper = EbayScraper()
    
    # 테스트 검색
    test_card = "Pikachu"
    print(f"검색어: {test_card}\n")
    
    results = scraper.search_sold_cards(test_card, max_results=10)
    
    if results:
        print(f"\n{'='*70}")
        print(f"검색 결과: {len(results)}개")
        print("=" * 70 + "\n")
        
        print("[ 상위 5개 결과 ]\n")
        for idx, card in enumerate(results[:5], 1):
            print(f"{idx}. {card['title'][:60]}...")
            print(f"   💰 가격: ${card['price']:.2f}")
            print(f"   📊 상태: {card['condition']}")
            if card['image_url']:
                print(f"   🖼️  이미지: {card['image_url'][:50]}...")
            if card['url']:
                print(f"   🔗 URL: {card['url'][:50]}...")
            print()
        
        # 가격 통계
        prices = [card['price'] for card in results]
        print(f"{'='*70}")
        print("[ 가격 통계 ]")
        print(f"  개수: {len(prices)}개")
        print(f"  평균: ${sum(prices)/len(prices):.2f}")
        print(f"  최저: ${min(prices):.2f}")
        print(f"  최고: ${max(prices):.2f}")
        print("=" * 70)
        
    else:
        print("❌ 검색 결과가 없습니다.")
        print("\n가능한 원인:")
        print("  1. 네트워크 연결 문제")
        print("  2. eBay 페이지 구조 변경")
        print("  3. 검색어 오류")
    
    print("\n" + "=" * 70)
    print("✅ 테스트 완료!")
    print("=" * 70)