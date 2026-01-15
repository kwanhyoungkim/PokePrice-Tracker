from flask import Flask, render_template, request, jsonify
import requests
import os
import json
from dotenv import load_dotenv
from main import PokemonPriceApp

load_dotenv()

base_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(base_dir, 'frontend', 'static'),
    template_folder=os.path.join(base_dir, 'frontend', 'templates')
)

# 경로 설정
DB_PATH = os.path.join(base_dir, 'backend', 'data', 'pokemon_cards.db')
SETS_EN_PATH = os.path.join(base_dir, 'sets', 'en.json')
JSON_PATH = os.path.join(base_dir, 'backend', 'data', 'pokemon_names.json')

# DB 및 스크래퍼 로직 인스턴스
price_app = PokemonPriceApp()

TCGDEX_BASE_URL = 'https://api.tcgdex.net/v2'

# [변경 포인트 1] JSON 파일을 읽어 한글/영어/일본어 통합 맵 생성
def load_pokemon_names_comprehensive():
    if not os.path.exists(JSON_PATH):
        print(f"⚠️  경고: {JSON_PATH} 파일을 찾을 수 없습니다.")
        return {}
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 한글 이름을 키로 사용하고 영어와 일본어 이름을 값으로 가짐
            return {
                item['korean_name']: {
                    "en": item['english_name'],
                    "ja": item['japanese_name']
                } for item in data
            }
    except Exception as e:
        print(f"❌ JSON 로드 에러: {e}")
        return {}

# 전역 변수에 이름 매핑 저장
POKEMON_MASTER_MAP = load_pokemon_names_comprehensive()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search')
def search_cards():
    name_input = request.args.get('name', '').strip()
    raw_lang = (request.args.get('language') or request.args.get('lang') or 'EN').upper()
    target_lang = 'ja' if raw_lang == 'JP' else 'en'
    
    if not name_input:
        return jsonify([])

    # [변경 포인트 2] 마스터 맵에서 다국어 이름 추출
    # 입력값이 한글이 아닐 경우(영문 입력 등)를 대비해 기본값 설정
    name_info = POKEMON_MASTER_MAP.get(name_input)
    
    if name_info:
        english_name = name_info['en']
        japanese_name = name_info['ja']
    else:
        # 맵에 없을 경우 입력값 그대로 사용
        english_name = name_input
        japanese_name = name_input

    # 타겟 언어에 맞춰 검색 쿼리 결정
    api_query = japanese_name if target_lang == 'ja' else english_name
    
    print(f"🔍 [서버 로그] 수신: {raw_lang} | 타겟: {target_lang} | 검색어: {api_query}")

    try:
        url = f"{TCGDEX_BASE_URL}/{target_lang}/cards"
        params = {'name': api_query}
        response = requests.get(url, params=params, timeout=15)
        
        cards = []
        if response.status_code == 200:
            cards = response.json()

        # [보정 로직] 일본어 이름으로 검색 실패 시 영문 이름으로 재시도
        if not cards and target_lang == 'ja' and japanese_name != english_name:
            print(f"⚠️  일본어 검색 실패. 영문명({english_name})으로 재시도...")
            params = {'name': english_name}
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                cards = response.json()

        if not cards:
            return jsonify([])

        result = []
        for card in cards[:40]:
            card_set = card.get('set', {})
            image_url = ""
            if card.get('image'):
                image_url = f"{card.get('image')}/low.jpg"
                if target_lang == 'ja':
                    image_url = image_url.replace('/en/', '/ja/')

            result.append({
                'id': card.get('id'),
                'name': card.get('name'),
                'series': card_set.get('name', 'Unknown'),
                'series_id': card_set.get('id', '').upper(),
                'number': card.get('localId', '?'),
                'image_url': image_url,
                'language': target_lang 
            })
        return jsonify(result)
    except Exception as e:
        print(f"❌ 오류: {e}")
        return jsonify([])

@app.route('/api/price', methods=['POST'])
def get_prices():
    data = request.json
    name = data.get('name')
    number = data.get('number')
    series_id = data.get('series_id', '')
    lang = data.get('lang', 'en').lower()

    try:
        # 이베이 검색어 생성
        if lang == 'ja':
            ebay_query = f"Japanese {series_id} {name} {number} Pokemon Card"
        else:
            ebay_query = f"{name} {number} {series_id} Pokemon Card"

        print(f"🌐 [eBay 쿼리] 언어: {lang} | 최종 검색어: {ebay_query}")
        
        prices = price_app.scraper.fetch_recent_sales(ebay_query)
        
        if (not prices or len(prices) < 2) and lang == 'ja':
            ebay_query_alt = f"Japanese {series_id} {name} card"
            prices = price_app.scraper.fetch_recent_sales(ebay_query_alt)

        return jsonify(prices if prices else [])
    except Exception as e:
        print(f"❌ 시세 조회 오류: {e}")
        return jsonify([]), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)