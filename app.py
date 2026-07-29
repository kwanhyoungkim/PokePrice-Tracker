from flask import Flask, render_template, request, jsonify
import requests
import os
import json
from dotenv import load_dotenv
from main import PokemonPriceApp
from backend.scraper.tcg_pocket_filter import is_tcg_pocket_set
from backend.database.db import search_cards_en

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
# ⚠️ 영문판 카드 데이터는 더 이상 로컬 JSON을 통째로 메모리에 올리지 않는다.
# docker-compose.yml 로 띄운 Postgres 컨테이너(cards_en 테이블)를 대신 조회한다.
# (backend/database/load_en_cards.py 로 최초 1회 적재 필요, README 참고)
# 일본판은 아직 이 방식으로 전환하지 않아 기존처럼 로컬 JSON을 그대로 사용한다.

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
    if target_lang == 'ja':
        for c in CARDS_JP_LOCAL:
            c_name = c.get('name', '').lower()
            if (jp_name and jp_name in c_name) or (eng_name in c_name):
                final_results[c.get('id')] = {
                    'id': c.get('id'), 'name': c.get('name'), 'series': c.get('series'),
                    'series_id': c.get('series_id'), 'number': c.get('number'),
                    'image_url': c.get('image'), 'language': 'ja'
                }
    else:
        # 영문판은 로컬 JSON 대신 Postgres(도커 컨테이너)에서 조회한다.
        try:
            for card in search_cards_en(eng_name):
                final_results[card['id']] = card
        except Exception as e:
            print(f"❌ Postgres 조회 오류 (cards_en): {e}")

    # 3. (일본판 한정) TCGdex API '전체 카드' 요약 엔드포인트로 로컬 JSON 누락분 보완
    #    영문판은 Postgres(cards_en)가 이미 series->sets->cards 전체 순회 + Pocket 필터를
    #    거쳐 최신 상태로 채워져 있으므로 이 요약 엔드포인트를 추가로 병합하지 않는다.
    #    (이 요약 엔드포인트는 set 정보가 부실할 때가 있어 Pocket 필터가 못 걸러내고
    #     영문판 검색 결과에 Pocket 카드가 다시 섞여 들어오는 원인이었음)
    if target_lang == 'ja':
        try:
            api_lang = 'ja'
            url = f"https://api.tcgdex.net/v2/{api_lang}/cards"

            res = requests.get(url, params={'name': jp_name}, timeout=5)

            if res.status_code == 200:
                for card in res.json():
                    cid = card.get('id')
                    if cid not in final_results:
                        set_info = card.get('set', {}) or {}
                        # Pokemon TCG Pocket(모바일 게임) 세트는 실물 카드가 아니므로 제외
                        if is_tcg_pocket_set(set_id=set_info.get('id'), set_obj=set_info):
                            continue
                        c_name_api = card.get('name', '').lower()
                        if (jp_name and jp_name in c_name_api) or (eng_name in c_name_api):
                            img = card.get('image')
                            final_results[cid] = {
                                'id': cid,
                                'name': card.get('name'),
                                'series': set_info.get('name'),
                                'series_id': set_info.get('id'),
                                'number': card.get('localId'),
                                'image_url': f"{img}/low.jpg" if img else "",
                                'language': api_lang
                            }

            if len(final_results) < 15:
                res_fb = requests.get(url, params={'name': eng_name}, timeout=5)
                if res_fb.status_code == 200:
                    for card in res_fb.json():
                        cid = card.get('id')
                        if cid not in final_results:
                            set_info = card.get('set', {}) or {}
                            # Pokemon TCG Pocket(모바일 게임) 세트는 실물 카드가 아니므로 제외
                            if is_tcg_pocket_set(set_id=set_info.get('id'), set_obj=set_info):
                                continue
                            # 이름 매칭 검증(1차 검색과 동일 기준) 없이 그대로 추가되던 버그도 함께 수정
                            c_name_api = card.get('name', '').lower()
                            if not ((jp_name and jp_name in c_name_api) or (eng_name in c_name_api)):
                                continue
                            img = card.get('image')
                            final_results[cid] = {
                                'id': cid, 'name': card.get('name'),
                                'series': set_info.get('name'),
                                'series_id': set_info.get('id'),
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