import os
import json
import requests
import base64
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------
# 1. 설정 (Production 키를 여기에 입력하세요)
# ----------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data") 

EBAY_CLIENT_ID = "-checkpok-PRD-2e06b92ff-8869a355" # 실제 Production App ID
EBAY_CLIENT_SECRET = "PRD-e06b92ffdeeb-28e5-4a7e-a878-1583" # 실제 Production Cert ID

EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

pokemon_data = load_json("pokemon_names.json")

# ----------------------------------------------------------------
# 2. 토큰 발급 (Production)
# ----------------------------------------------------------------
def get_production_token():
    auth_str = f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_auth}"
    }
    data = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope"
    }
    
    response = requests.post(EBAY_TOKEN_URL, headers=headers, data=data)
    if response.status_code == 200:
        return response.json().get("access_token")
    return None

# ----------------------------------------------------------------
# 3. API 엔드포인트
# ----------------------------------------------------------------
class SearchRequest(BaseModel):
    lang: str
    pokemon_name: str
    series_name: Optional[str] = ""
    card_number: Optional[str] = ""

@app.post("/api/search-ebay-price")
async def search_ebay_price(req: SearchRequest):
    # [A] 이름 번역
    en_pokemon = req.pokemon_name
    if req.lang == 'ko':
        for p in pokemon_data:
            val_kr = p.get('kr') or p.get('name_kr')
            val_en = p.get('en') or p.get('name_en')
            if val_kr and val_kr.strip() == req.pokemon_name.strip():
                en_pokemon = val_en
                break

    # [B] 검색 쿼리 정제 (공백 제거 및 최적화)
    query_parts = [en_pokemon, req.series_name, req.card_number, "pokemon card"]
    # 빈 문자열을 제외하고 공백 하나로 합침
    clean_query = " ".join([p.strip() for p in query_parts if p and p.strip()])
    # 불필요한 묶음 상품 제외 키워드 추가
    ebay_query = f"{clean_query} -lot -set -bulk"
    
    print(f"📡 실제 이베이 요청 쿼리: {ebay_query}")

    token = get_production_token()
    if not token:
        raise HTTPException(status_code=500, detail="이베이 인증 실패")

    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }
    
    # [C] 검색 파라미터 조정 (검색 결과가 너무 없으면 filter를 느슨하게)
    params = {
        "q": ebay_query,
        "limit": 10
    }

    try:
        response = requests.get(EBAY_SEARCH_URL, headers=headers, params=params)
        ebay_data = response.json()
        
        items = ebay_data.get("itemSummaries", [])
        results = []
        for item in items:
            results.append({
                "title": item.get("title"),
                "price": item.get("price", {}).get("value"),
                "currency": item.get("price", {}).get("currency"),
                "image": item.get("image", {}).get("imageUrl") if "image" in item else None,
                "item_url": item.get("itemWebUrl")
            })

        return {
            "status": "success",
            "search_keyword_used": en_pokemon,
            "query": ebay_query,
            "total_found": ebay_data.get("total", 0),
            "prices": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)