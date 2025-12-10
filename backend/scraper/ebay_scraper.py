import requests
from bs4 import BeautifulSoup
import re
import time
import random
from requests.exceptions import RequestException

class EbayScraper:
    BASE_URL = (
        "https://www.ebay.com/sch/i.html"
        "?_nkw={query}"
        "&LH_Sold=1"
        "&LH_Complete=1"
        "&_sop=13"  # Recently sold
    )

    # ⭐ User-Agent 리스트를 추가하여 요청 시마다 랜덤 선택
    USER_AGENT_LIST = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1"
    ]

    def fetch_recent_sales(self, query: str, limit: int = 10):
        """eBay 최근 판매 시세 스크래핑"""
        url = self.BASE_URL.format(query=query.replace(" ", "+"))
        
        # ⭐ 요청 시마다 랜덤 User-Agent 설정
        headers = {"User-Agent": random.choice(self.USER_AGENT_LIST)}
        
        # ⭐ 스크래핑 차단 회피를 위한 무작위 지연 시간 추가 (1초에서 3초)
        time.sleep(random.uniform(1, 3))

        try:
            # ⭐ 타임아웃 5초 설정 및 요청 예외 처리 강화
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status() # 4xx, 5xx 상태 코드 시 HTTPError 예외 발생
            
        except RequestException as e:
            # 네트워크 오류, 타임아웃, HTTP 오류 등 모든 요청 관련 예외 처리
            # ⭐ 터미널에 에러 원인 출력
            print(f"Ebay Scraper Network/HTTP Error: {e}")
            # ⭐ 상위 함수로 예외를 전달하기 위해 raise
            raise e
            
        # ... (이하 스크래핑 로직)
        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.select(".s-item")

        results = []
        # ... (나머지 스크래핑, price_tag, date_tag 처리 로직 유지)

        for item in items[:limit]:
            title_tag = item.select_one(".s-item__title")
            price_tag = item.select_one(".s-item__price")
            # ⭐ SOLD 태그는 .s-item__title--tagblock 대신 더 범용적인 선택자를 사용하거나,
            #    여기서는 단순히 .POSITIVE를 사용했던 원본 코드를 유지합니다.
            date_tag = item.select_one(".s-item__title--tagblock .POSITIVE") 

            if not (title_tag and price_tag):
                continue

            title = title_tag.get_text(strip=True)
            price = self._clean_price(price_tag.get_text(strip=True))
            date = date_tag.get_text(strip=True) if date_tag else "Unknown"

            results.append({
                "title": title,
                "price": price,
                "date": date
            })

        return results

    def _clean_price(self, raw_price: str):
        """$199.99 → 199.99 숫자로 변환"""
        cleaned = re.sub(r"[^\d.]", "", raw_price)
        try:
            return float(cleaned)
        except ValueError:
            return None