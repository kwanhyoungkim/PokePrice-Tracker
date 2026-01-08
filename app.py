from flask import Flask, render_template, request, jsonify
import requests
import os
import json
import sqlite3 # DB 접속을 위해 추가
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

# DB 및 스크래퍼 로직을 담은 클래스 인스턴스
price_app = PokemonPriceApp()

POKEMON_TCG_API_KEY = os.getenv('POKEMON_TCG_API_KEY')
POKEMON_TCG_BASE_URL = 'https://api.pokemontcg.io/v2'

# 1. 로컬 DB 검색 함수 정의 (app.py 내부에 직접 배치)
def find_cards_from_db(en_name):
    """로컬 SQLite DB에서 영어 이름으로 카드를 검색합니다."""
    try:
        if not os.path.exists(DB_PATH):
            print(f"❌ DB 파일을 찾을 수 없습니다: {DB_PATH}")
            return []
            
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 영어 이름으로 검색
        query = "SELECT * FROM pokemon_cards WHERE card_name_en LIKE ?"
        cursor.execute(query, (f"%{en_name}%",))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                'name': row['card_name_en'],
                'set_name': row['series_name_en'],
                'number': row['card_number'],
                'image_url': row['image_url']
            })
        return results
    except Exception as e:
        print(f"[ERROR] DB 조회 실패: {e}")
        return []

# 2. 한영 이름 매핑 데이터 로드
def load_pokemon_names():
    json_path = os.path.join(base_dir, 'backend', 'data', 'pokemon_names.json')
    if not os.path.exists(json_path):
        print(f"❌ 파일을 찾을 수 없습니다: {json_path}")
        return {}

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 매핑 사전 생성
            mapping = {item['korean_name']: item['english_name'] for item in data}
            print(f"✅ JSON 로드 완료: {len(mapping)}개의 포켓몬 이름")
            return mapping
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

    # [수정] POKEMON_NAME_MAP을 사용하여 한글 -> 영어 변환
    search_name_en = POKEMON_NAME_MAP.get(name_input, name_input)

    # 1. 먼저 로컬 DB에서 검색
    print(f"[INFO] 로컬 DB 검색 시도: {name_input} ({search_name_en})")
    try:
        local_results = find_cards_from_db(search_name_en) 
        
        if local_results:
            print(f"✅ 로컬 DB에서 {len(local_results)}개 발견")
            formatted_local = []
            for card in local_results:
                formatted_local.append({
                    'id': f"{card['name']}-{card['number']}",
                    'name': card['name'],
                    'series': card['set_name'],
                    'number': card['number'],
                    'image_url': card['image_url']
                })
            return jsonify(formatted_local)
    except Exception as e:
        print(f"[WARN] 로컬 DB 검색 중 오류 발생: {e}")

    # 2. 로컬 DB에 결과가 없거나 실패했을 때만 외부 API 호출
    try:
        headers = {'X-Api-Key': POKEMON_TCG_API_KEY} if POKEMON_TCG_API_KEY else {}
        params = {'q': f'name:"{search_name_en}*"', 'pageSize': 20}

        print(f"🌐 외부 API 호출 중 (Timeout 40s)...")
        response = requests.get(
            f'{POKEMON_TCG_BASE_URL}/cards',
            headers=headers,
            params=params,
            timeout=40
        )
        
        data = response.json()
        cards = data.get('data', [])
        
        result = []
        for card in cards:
            result.append({
                'id': card.get('id'),
                'name': card.get('name'),
                'series': card.get('set', {}).get('name', 'Unknown'),
                'number': card.get('number', '?'),
                'image_url': card.get('images', {}).get('small', '')
            })
        return jsonify(result)

    except Exception as e:
        print(f"[ERROR] 외부 API 오류: {e}")
        return jsonify({'error': '데이터를 가져오는 중 오류가 발생했습니다.'}), 503
    
@app.route('/api/price', methods=['POST'])
def get_prices():
    data = request.json
    if not data:
        return jsonify({'error': '데이터가 없습니다.'}), 400

    try:
        prices = price_app.get_ebay_prices(data)
        return jsonify(prices)
    except Exception as e:
        print(f"[ERROR] 시세 조회 API 오류: {e}")
        return jsonify({'error': '시세 정보를 가져오지 못했습니다.'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
    