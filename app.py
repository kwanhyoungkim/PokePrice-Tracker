import os
from flask import Flask, render_template, request, jsonify
from backend.service.search_service import SearchService
from backend.scraper.ebay_scraper import EbayScraper

app = Flask(__name__, template_folder='frontend/templates', static_folder='frontend/static')

# 1. 경로 설정
base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, "backend/data/pokemon_cards.db")

# 2. 객체 초기화
# EbayScraper는 .env에서 API 키를 읽어 토큰을 생성합니다.
scraper = EbayScraper()
service = SearchService(db_path, scraper)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search', methods=['GET'])
def search_cards():
    query = request.args.get('name', '')
    if not query:
        return jsonify([])
    try:
        results = service.search_card_list(query)
        return jsonify(results)
    except Exception as e:
        print(f"Error in /api/search: {e}")
        return jsonify([]), 500

@app.route('/api/price', methods=['POST'])
def get_price():
    try:
        data = request.json
        if not data:
            return jsonify([])
            
        # 이베이 시세 조회 (SearchService에서 쿼리 최적화 수행)
        prices = service.get_ebay_prices(
            data.get('name'), 
            data.get('series'), 
            data.get('number')
        )
        return jsonify(prices if prices else [])
    except Exception as e:
        print(f"Error in /api/price: {e}")
        return jsonify([]), 200 # 프론트 엔드 오류 방지를 위해 200으로 전송

if __name__ == '__main__':
    app.run(debug=True, port=5000)