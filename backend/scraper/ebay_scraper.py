import os
import requests
import base64
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class EbayScraper:
    def __init__(self):
        self.client_id = os.getenv("EBAY_CLIENT_ID")
        self.client_secret = os.getenv("EBAY_CLIENT_SECRET")
        self.auth_token = self._get_access_token()

    def _get_access_token(self):
        url = "https://api.ebay.com/identity/v1/oauth2/token"
        if not self.client_id or not self.client_secret:
            return None

        auth_str = f"{self.client_id}:{self.client_secret}"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_auth}"
        }
        data = {"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}
        
        try:
            response = requests.post(url, headers=headers, data=data)
            return response.json().get("access_token")
        except:
            return None

    def fetch_recent_sales(self, query):
        # 토큰이 없으면 빈 리스트를 반환하여 500 에러 방지
        if not self.auth_token:
            self.auth_token = self._get_access_token()
        
        if not self.auth_token:
            return [] 

        url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
        }
        params = {"q": query, "limit": 5, "sort": "newlyListed"}

        try:
            response = requests.get(url, headers=headers, params=params)
            # 응답이 정상이 아닐 경우 빈 리스트 반환
            if response.status_code != 200:
                return []
                
            data = response.json()
            items = data.get("itemSummaries", [])
            results = []
            
            for item in items:
                raw_date = item.get("itemCreationDate", "")
                formatted_date = raw_date[:10] if raw_date else "Recent"
                
                results.append({
                    "title": item.get("title", "No Title"),
                    "price": item.get("price", {}).get("value", "0"),
                    "currency": item.get("price", {}).get("currency", "USD"),
                    "sold_date": formatted_date
                })
            return results
        except Exception as e:
            print(f"Scraper Error: {e}")
            return [] # 에러 발생 시 빈 리스트 반환하여 500 에러 방지