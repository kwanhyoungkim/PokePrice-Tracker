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

    # 1. 이름 정보 확보
    name_info = POKEMON_MASTER_MAP.get(name_input)
    eng_name = name_info.get('english_name', '').lower() if name_info else name_input.lower()
    jp_name = name_info.get('japanese_name', '') if name_info else ""

    final_results = {}

    # 2. 로컬 데이터 검색 (강화된 매칭)
    local_source = CARDS_JP_LOCAL if target_lang == 'ja' else CARDS_EN_LOCAL
    for c in local_source:
        c_name = c.get('name', '').lower()
        # 일본어 모드: 가타카나 포함 OR 영어 이름 포함 (Zubat 등 대응)
        if target_lang == 'ja':
            if (jp_name and jp_name in c_name) or (eng_name in c_name):
                final_results[c.get('id')] = {
                    'id': c.get('id'), 'name': c.get('name'), 'series': c.get('series'),
                    'series_id': c.get('series_id'), 'number': c.get('number'),
                    'image_url': c.get('image'), 'language': 'ja'
                }
        else:
            if eng_name in c_name:
                final_results[c.get('id')] = {
                    'id': c.get('id'), 'name': c.get('name'), 'series': c.get('series'),
                    'series_id': c.get('series_id'), 'number': c.get('number'),
                    'image_url': c.get('image'), 'language': 'en'
                }

    # 3. TCGdex API '전체 카드' 엔드포인트 활용 (가장 확실한 방법)
    # 특정 이름을 검색어로 던지지 않고, 전체 리스트에서 필터링합니다.
    try:
        # 일본어 모드여도 영어 이름으로 등록된 경우가 많으므로 두 검색어 모두 활용
        api_lang = 'ja' if target_lang == 'ja' else 'en'
        # 주의: 여기서는 params={'name': ...} 을 빼고 호출한 뒤 내부에서 거릅니다.
        # (만약 데이터가 너무 많아 속도가 느리면 다시 params를 넣되, Fallback을 강화합니다)
        url = f"https://api.tcgdex.net/v2/{api_lang}/cards"
        
        # 속도를 위해 우선 검색어를 넣어서 시도
        res = requests.get(url, params={'name': jp_name if target_lang == 'ja' else eng_name}, timeout=5)
        
        if res.status_code == 200:
            for card in res.json():
                cid = card.get('id')
                if cid not in final_results:
                    # 한번 더 검증: 이름에 검색어가 들어있는지 확인
                    c_name_api = card.get('name', '').lower()
                    if (jp_name and jp_name in c_name_api) or (eng_name in c_name_api):
                        img = card.get('image')
                        final_results[cid] = {
                            'id': cid,
                            'name': card.get('name'),
                            'series': card.get('set', {}).get('name'),
                            'series_id': card.get('set', {}).get('id'),
                            'number': card.get('localId'),
                            'image_url': f"{img}/low.jpg" if img else "",
                            'language': api_lang
                        }

        # 🌟 보강: 결과가 여전히 너무 적으면 영문 엔드포인트에서 일본어 데이터를 강제 추출
        if target_lang == 'ja' and len(final_results) < 15:
            # 영문 이름으로 다시 한번 공격적으로 검색
            res_fb = requests.get(url, params={'name': eng_name}, timeout=5)
            if res_fb.status_code == 200:
                for card in res_fb.json():
                    cid = card.get('id')
                    if cid not in final_results:
                        img = card.get('image')
                        final_results[cid] = {
                            'id': cid, 'name': card.get('name'),
                            'series': card.get('set', {}).get('name'),
                            'series_id': card.get('set', {}).get('id'),
                            'number': card.get('localId'),
                            'image_url': f"{img}/low.jpg" if img else "",
                            'language': 'ja'
                        }
    except Exception as e:
        print(f"API Error: {e}")

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