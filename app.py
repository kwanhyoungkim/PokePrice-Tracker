from flask import Flask, render_template, request, jsonify
import requests
import os
import json
import sqlite3
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
SETS_EN_PATH = os.path.join(base_dir, 'sets', 'en.json') # 업로드한 en.json 경로

# DB 및 스크래퍼 로직을 담은 클래스 인스턴스
price_app = PokemonPriceApp()

POKEMON_TCG_API_KEY = os.getenv('POKEMON_TCG_API_KEY')
POKEMON_TCG_BASE_URL = 'https://api.pokemontcg.io/v2'

# --- 추가된 함수: en.json 로드 및 매핑 사전 생성 ---
def load_sets_data():
    sets_path = os.path.join(base_dir, 'sets', 'en.json')
    if not os.path.exists(SETS_EN_PATH):
        print(f"⚠️ {SETS_EN_PATH} 파일을 찾을 수 없습니다.")
        return {}
    try:
        with open(SETS_EN_PATH, 'r', encoding='utf-8') as f:
            sets_list = json.load(f)
            # 이름(소문자)을 키로 하여 전체 정보를 저장
            return {s['name'].lower(): s for s in sets_list}
    except Exception as e:
        print(f"❌ en.json 로드 실패: {e}")
        return {}

SET_MAPPING = load_sets_data()
# -----------------------------------------------

def find_cards_from_db(en_name):
    try:
        if not os.path.exists(DB_PATH):
            return []
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = "SELECT * FROM pokemon_cards WHERE card_name_en LIKE ?"
        cursor.execute(query, (f"%{en_name}%",))
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                'id': row['id'],
                'name': row['card_name_en'],
                'set_name': row['series_name_en'],
                'number': row['card_number'],
                'image_url': row['image_url']
            })
        return results
    except Exception as e:
        print(f"[ERROR] DB 조회 실패: {e}")
        return []

def load_pokemon_names():
    json_path = os.path.join(base_dir, 'backend', 'data', 'pokemon_names.json')
    if not os.path.exists(json_path):
        return {}
    try:
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
    name_input = request.args.get('name', '').strip()
    if not name_input:
        return jsonify({'error': '검색어를 입력해주세요'}), 400

    search_name_en = POKEMON_NAME_MAP.get(name_input, name_input)

    # 1. 외부 API를 기본으로 사용 (이미지를 위해)
    try:
        headers = {'X-Api-Key': POKEMON_TCG_API_KEY} if POKEMON_TCG_API_KEY else {}
        params = {'q': f'name:"{search_name_en}*"', 'pageSize': 240}
        
        response = requests.get(f'{POKEMON_TCG_BASE_URL}/cards', headers=headers, params=params, timeout=40)
        data = response.json()
        cards = data.get('data', [])
        
        result = []
        for card in cards:
            api_set_name = card.get('set', {}).get('name', 'Unknown')
            api_set_id = card.get('set', {}).get('id', '').upper()
            
            # [보정 로직] en.json에서 공식 정보 찾기
            set_info = SET_MAPPING.get(api_set_name.lower())
            
            display_series = api_set_name
            series_id = api_set_id
            
            if set_info:
                display_series = set_info['name']   # 예: Base
                series_id = set_info['id'].upper() # 예: BASE1

            result.append({
                'id': card.get('id'),
                'name': card.get('name'),
                'series': display_series,       # 화면에 표시될 세트 이름
                'series_id': series_id,         # 화면에 표시될 세트 ID (SV05 등)
                'number': card.get('number', '?'),
                'image_url': card.get('images', {}).get('small', '')
            })
        
        # 외부 API 결과가 있으면 반환
        if result:
            return jsonify(result)
            
    except Exception as e:
        print(f"[ERROR] 외부 API 오류: {e}")

    # 2. 외부 API 실패 시에만 로컬 DB 검색 결과 반환 (이미지 링크가 살아있는지 확인 필요)
    local_results = find_cards_from_db(search_name_en)
    formatted_local = []
    for card in local_results:
        formatted_local.append({
            'id': f"{card['name']}-{card['number']}",
            'name': card['name'],
            'number': card['number'],
            'image_url': card['image_url'],
            'series': card['set_name'],
            'series_id': "" # DB에는 ID 정보가 없을 경우 빈값
        })
    return jsonify(formatted_local)
    
@app.route('/api/price', methods=['POST'])
def get_prices():
    data = request.json
    name = data.get('name')
    series = data.get('series')
    series_id = data.get('series_id', '') # 프론트에서 받은 ID
    number = data.get('number')

    try:
        # 이베이 검색 쿼리 최적화: ID(SV05 등)가 있으면 검색 결과가 훨씬 정확해짐
        if series_id:
            ebay_query = f"{name} {number} {series_id} Pokemon card"
        else:
            clean_series = series.split('「')[0].strip()
            ebay_query = f"{name} {number} {clean_series} Pokemon card"
        
        print(f"🌐 이베이 조회 시작: {ebay_query}")
        prices = price_app.scraper.fetch_recent_sales(ebay_query)
        
        if not prices:
            # 실패 시 시리즈 정보를 빼고 재시도
            prices = price_app.scraper.fetch_recent_sales(f"{name} {number} pokemon card")

        if not prices:
            return jsonify({'error': '최근 거래 내역이 없습니다.'}), 404
            
        return jsonify(prices)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)