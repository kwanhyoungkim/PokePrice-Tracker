import os
import requests
import base64
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

class EbayScraper:
    def __init__(self):
        self.client_id = os.getenv("EBAY_CLIENT_ID")
        self.client_secret = os.getenv("EBAY_CLIENT_SECRET")
        self.auth_token = self._get_access_token()

    def _get_access_token(self):
        """eBay OAuth 2.0 Access Token 가져오기"""
        url = "https://api.ebay.com/identity/v1/oauth2/token"
        
        # Client ID와 Secret을 Base64로 인코딩
        auth_str = f"{self.client_id}:{self.client_secret}"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_auth}"
        }
        
        data = {
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope" # 공개 데이터 조회용 스코프
        }
        
        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            return response.json().get("access_token")
        except Exception as e:
            print(f"❌ eBay 인증 토큰 획득 실패: {e}")
            return None

    def fetch_recent_sales(self, query):
        """특정 쿼리로 최근 판매된 아이템 검색"""
        if not self.auth_token:
            return {"error": "인증 토큰이 없습니다."}

        # eBay Browse API 엔드포인트
        # 필터: 판매 완료된 항목(lastSoldDate) 위주로 검색
        url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"  # 미국 이베이 기준
        }
        
        params = {
            "q": query,
            "limit": 10,  # 최신순 10개만
            "filter": "buyingOptions:{FIXED_PRICE}", # 경매 제외 고정가 판매 위주 (선택사항)
            "sort": "newlyListed" # 최신 항목순
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            items = data.get("itemSummaries", [])
            results = []
            
            for item in items:
                results.append({
                    "title": item.get("title"),
                    "price": item.get("price", {}).get("value"),
                    "currency": item.get("price", {}).get("currency"),
                    "item_url": item.get("itemWebUrl"),
                    "image": item.get("image", {}).get("imageUrl"),
                    "condition": item.get("condition")
                })
            
            return results

        except Exception as e:
            return {"error": f"eBay 검색 중 오류 발생: {str(e)}"}