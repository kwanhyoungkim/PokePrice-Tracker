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
JSON_PATH = os.path.join(base_dir, 'backend', 'data', 'pokemon_names.json')
JSON_JP_PATH = os.path.join(base_dir, 'backend', 'data', 'all_cards_jp.json')
JSON_EN_PATH = os.path.join(base_dir, 'backend', 'data', 'all_cards_en.json')

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
CARDS_JP_LOCAL = load_json_file(JSON_JP_PATH)
CARDS_EN_LOCAL = load_json_file(JSON_EN_PATH)

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

    # 1. 한글 -> 타겟 언어로 변환 (기라티나 -> Giratina / ギラティナ)
    name_info = POKEMON_MASTER_MAP.get(name_input)
    if name_info:
        search_query = name_info.get('japanese_name' if target_lang == 'ja' else 'english_name')
    else:
        # 매핑 정보가 없으면 입력값 그대로 사용
        search_query = name_input

    print(f"🔍 [검색] 입력: {name_input} -> 쿼리: {search_query} ({target_lang})")

    final_results = {} # card_id를 키로 사용하여 중복 제거

    # 2. 로컬 JSON 데이터 우선 검색 (기라티나 등 파일에 있는 데이터 확보)
    local_source = CARDS_JP_LOCAL if target_lang == 'ja' else CARDS_EN_LOCAL
    
    for c in local_source:
        card_name = c.get('name', '').lower()
        if search_query.lower() in card_name:
            c_id = c.get('id')
            final_results[c_id] = {
                'id': c_id,
                'name': c.get('name'),
                'series': c.get('series', 'Unknown'),
                'series_id': c.get('series_id'),
                'number': c.get('number', '?'),
                'image_url': c.get('image'),
                'language': target_lang
            }

    # 3. TCGdex API 호출로 데이터 보강 (로컬에 없는 최신 카드 등)
    try:
        url = f"https://api.tcgdex.net/v2/{target_lang}/cards"
        params = {'name': search_query}
        response = requests.get(url, params=params, timeout=8)
        
        if response.status_code == 200:
            api_cards = response.json()
            for card in api_cards:
                card_id = card.get('id')
                # API 데이터로 정보 업데이트 (이미지 경로 등) 또는 신규 추가
                card_set = card.get('set', {})
                img_base = card.get('image')
                
                # 로컬에 이미 있더라도 API 데이터의 이미지가 더 정확할 수 있으므로 갱신
                final_results[card_id] = {
                    'id': card_id,
                    'name': card.get('name'),
                    'series': card_set.get('name', final_results.get(card_id, {}).get('series', 'Unknown')),
                    'series_id': card_set.get('id', final_results.get(card_id, {}).get('series_id')),
                    'number': card.get('localId', final_results.get(card_id, {}).get('number', '?')),
                    'image_url': f"{img_base}/low.jpg" if img_base else final_results.get(card_id, {}).get('image_url', ''),
                    'language': target_lang
                }
    except Exception as e:
        print(f"❌ API 호출 실패 (로컬 데이터로 대체): {e}")

    # 리스트로 변환 및 반환
    return jsonify(list(final_results.values()))

@app.route('/api/price', methods=['POST'])
def get_prices():
    data = request.json
    name = data.get('name')
    number = data.get('number')
    series_id = data.get('series_id', '')
    lang = data.get('lang', 'en').lower()

    try:
        # eBay 검색어 최적화 (일본판의 경우 'Japanese' 명시)
        prefix = "Japanese " if lang == 'ja' else ""
        ebay_query = f"{prefix} {series_id} {name} {number} Pokemon Card"
        
        print(f"🌐 [eBay 쿼리] {ebay_query}")
        prices = price_app.scraper.fetch_recent_sales(ebay_query)
        
        # 결과가 적을 경우 세부 번호 제외하고 재검색
        if not prices or len(prices) < 2:
            alt_query = f"{prefix}{name} {series_id} card"
            prices = price_app.scraper.fetch_recent_sales(alt_query)

        return jsonify(prices if prices else [])
    except Exception as e:
        print(f"❌ 가격 조회 오류: {e}")
        return jsonify([]), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)