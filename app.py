from flask import Flask, render_template, request, jsonify
import os
import json
from dotenv import load_dotenv
from main import PokemonPriceApp
from backend.database.db import search_cards_en, search_cards_jp

load_dotenv()

base_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(base_dir, 'frontend', 'static'),
    template_folder=os.path.join(base_dir, 'frontend', 'templates')
)

# 경로 설정
JSON_PATH = os.path.join(base_dir, 'backend', 'data', 'pokemon_names.json')
# ⚠️ 영문판/일본판 카드 데이터는 더 이상 로컬 JSON을 통째로 메모리에 올리지 않는다.
# docker-compose.yml 로 띄운 Postgres 컨테이너(cards_en, cards_jp 테이블)를 대신 조회한다.
# (backend/database/load_en_cards.py, load_jp_cards.py 로 최초 1회 적재 필요, README 참고)

# DB 및 스크래퍼 로직 인스턴스
price_app = PokemonPriceApp()

def load_json_file(file_path):
    if not os.path.exists(file_path):
        print(f"⚠️  경고: {file_path} 없음")
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 로드 에러: {e}")
        return []

# 데이터 사전 로드 (검색 속도 향상)
POKEMON_MASTER_MAP = {item['korean_name']: item for item in load_json_file(JSON_PATH)}

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

    # 1. 이름 정보 확보
    name_info = POKEMON_MASTER_MAP.get(name_input)
    eng_name = name_info.get('english_name', '').lower() if name_info else name_input.lower()
    jp_name = name_info.get('japanese_name', '') if name_info else ""

    final_results = {}

    # 2. Postgres(도커 컨테이너)에서 조회한다. 영문판/일본판 둘 다 이제 로컬 JSON을
    #    직접 읽지 않고 cards_en / cards_jp 테이블을 쓴다. 두 테이블 모두 세트를
    #    전부 순회(+ Pocket 필터)해서 만든 데이터라 TCGdex 요약 엔드포인트로 별도
    #    보완할 필요가 없다(요약 엔드포인트는 set 정보가 부실해 Pocket 필터가
    #    못 걸러내는 경우가 있어 오히려 Pocket 카드가 섞여 들어오는 원인이었음).
    if target_lang == 'ja':
        try:
            for card in search_cards_jp(eng_name, jp_name):
                final_results[card['id']] = card
        except Exception as e:
            print(f"❌ Postgres 조회 오류 (cards_jp): {e}")
    else:
        try:
            for card in search_cards_en(eng_name):
                final_results[card['id']] = card
        except Exception as e:
            print(f"❌ Postgres 조회 오류 (cards_en): {e}")

    return jsonify(list(final_results.values()))

@app.route('/api/price', methods=['POST'])
def get_prices():
    data = request.json
    name = data.get('name')
    number = data.get('number')
    series_id = data.get('series_id', '')
    lang = data.get('lang', 'en').lower()

    try:
        prefix = "Japanese " if lang == 'ja' else ""
        ebay_query = f"{prefix} {series_id} {name} {number} Pokemon Card"
        
        print(f"🌐 [eBay 쿼리] {ebay_query}")
        prices = price_app.scraper.fetch_recent_sales(ebay_query)
        
        if not prices or len(prices) < 2:
            alt_query = f"{prefix}{name} {series_id} card"
            prices = price_app.scraper.fetch_recent_sales(alt_query)

        return jsonify(prices if prices else [])
    except Exception as e:
        print(f"❌ 가격 조회 오류: {e}")
        return jsonify([]), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)