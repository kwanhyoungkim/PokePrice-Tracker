from backend.scraper.ebay_scraper import EbayScraper
# requests.exceptions를 import할 필요 없음 (routes.py에서 처리함)

def search_card_prices(card_name: str):
    """카드 이름으로 eBay 최근 시세 조회"""
    scraper = EbayScraper()
    
    # eBay 검색용 쿼리 구성
    query = f"{card_name} Pokemon card"
    
    # ⭐ 이제 scraper 내부에서 예외가 발생하면 routes.py로 전달됩니다.
    results = scraper.fetch_recent_sales(query)

    # 에러 처리 (스크래퍼가 JSON을 반환한 경우만 처리)
    if isinstance(results, dict) and results.get("error"):
        return {"error": results["error"]}

    # 정상 결과
    return {
        "card_name": card_name,
        "count": len(results),
        "results": results
    }