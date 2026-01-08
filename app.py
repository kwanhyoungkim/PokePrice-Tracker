from flask import Flask, render_template, request, jsonify
import requests
import os
import json
from dotenv import load_dotenv
from main import PokemonPriceApp  # main.py의 클래스 임포트

load_dotenv()

base_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(base_dir, 'frontend', 'static'),
    template_folder=os.path.join(base_dir, 'frontend', 'templates')
)

# DB 및 스크래퍼 로직을 담은 클래스 인스턴스
price_app = PokemonPriceApp()

POKEMON_TCG_API_KEY = os.getenv('POKEMON_TCG_API_KEY')
POKEMON_TCG_BASE_URL = 'https://api.pokemontcg.io/v2'

# 한영 이름 매핑 데이터 로드 (TCG API 검색용)
def load_pokemon_names():
    json_path = os.path.join(base_dir, 'backend', 'data', 'pokemon_names.json')
    try:
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {item['korean_name']: item['english_name'] for item in data}
    except Exception as e:
        print(f"❌ JSON 로드 실패: {e}")
    return {}

POKEMON_NAME_MAP = load_pokemon_names()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search')
def search_cards():
    """프론트엔드의 searchCards() 함수와 통신"""
    name_input = request.args.get('name', '').strip()
    if not name_input:
        return jsonify({'error': '검색어를 입력해주세요'}), 400

    # 1. 한글 이름을 영어로 변환 (예: 갸라도스 -> Gyarados)
    search_name = POKEMON_NAME_MAP.get(name_input, name_input)
    
    try:
        headers = {'X-Api-Key': POKEMON_TCG_API_KEY} if POKEMON_TCG_API_KEY else {}
        params = {'q': f'name:"{search_name}*"', 'pageSize': 20}

        response = requests.get(
            f'{POKEMON_TCG_BASE_URL}/cards',
            headers=headers,
            params=params,
            timeout=20
        )

        data = response.json()
        cards = data.get('data', [])
        
        # 2. 프론트엔드 main.js의 card.image_url, card.series 등 이름에 맞춰 데이터 가공
        result = []
        for card in cards:
            result.append({
                'id': card.get('id'),
                'name': card.get('name'),
                'series': card.get('set', {}).get('name', 'Unknown'),
                'number': card.get('number', '?'),
                'image_url': card.get('images', {}).get('small', ''),
                'image_url_large': card.get('images', {}).get('large', ''),
                'rarity': card.get('rarity', 'N/A')
            })
        return jsonify(result)
    except Exception as e:
        print(f"[ERROR] 검색 API 오류: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/price', methods=['POST'])
def get_prices():
    """프론트엔드의 getPrices() 함수와 통신하여 이베이 시세 반환"""
    data = request.json
    if not data:
        return jsonify({'error': '데이터가 없습니다.'}), 400

    try:
        # main.py에 정의된 get_ebay_prices 메서드 호출
        prices = price_app.get_ebay_prices(data)
        return jsonify(prices)
    except Exception as e:
        print(f"[ERROR] 시세 조회 API 오류: {e}")
        return jsonify({'error': '시세 정보를 가져오지 못했습니다.'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)