from flask import Flask, render_template, request, jsonify
import requests
import os
import json  # JSON 파일을 읽기 위해 추가
from dotenv import load_dotenv

load_dotenv()

base_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(base_dir, 'frontend', 'static'),
    template_folder=os.path.join(base_dir, 'frontend', 'templates')
)

POKEMON_TCG_API_KEY = os.getenv('POKEMON_TCG_API_KEY')
POKEMON_TCG_BASE_URL = 'https://api.pokemontcg.io/v2'

# --- [추가] JSON 파일을 읽어와서 매핑 사전 만들기 ---
def load_pokemon_names():
    json_path = os.path.join(base_dir,'backend', 'data', 'pokemon_names.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # {'한글이름': '영어이름'} 형태의 딕셔너리로 변환
            return {item['korean_name']: item['english_name'] for item in data}
    except Exception as e:
        print(f"❌ JSON 로드 실패: {e}")
        return {}

POKEMON_NAME_MAP = load_pokemon_names()
print(f"✅ 포켓몬 이름 {len(POKEMON_NAME_MAP)}개 로드 완료")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search')
def search_cards():
    name_input = request.args.get('name', '').strip()
    if not name_input:
        return jsonify({'error': '검색어를 입력해주세요'}), 400

    # JSON 매핑 사용
    search_name = POKEMON_NAME_MAP.get(name_input, name_input)
    print(f"[DEBUG] 입력: {name_input} -> 변환: {search_name}")

    try:
        headers = {'X-Api-Key': POKEMON_TCG_API_KEY} if POKEMON_TCG_API_KEY else {}
        params = {'q': f'name:"{search_name}*"', 'pageSize': 20}

        response = requests.get(
            f'{POKEMON_TCG_BASE_URL}/cards',
            headers=headers,
            params=params,
            timeout=20
        )

        if response.status_code != 200:
            print(f"[ERROR] API 응답 코드: {response.status_code}")
            return jsonify({'error': 'API 호출 실패'}), 500

        data = response.json()
        cards = data.get('data', [])
        
        result = []
        for card in cards:
            # .get()을 사용하여 데이터가 없더라도 500 에러가 나지 않게 방어
            images = card.get('images', {})
            card_set = card.get('set', {})
            
            result.append({
                'id': card.get('id'),
                'name': card.get('name'),
                'series': card_set.get('name', 'Unknown'), # 세트 이름 안전하게 가져오기
                'number': card.get('number', '?'),
                'image_url': images.get('small', ''),
                'image_url_large': images.get('large', ''),
                'rarity': card.get('rarity', 'N/A'),
                'tcg_id': card.get('id') # id와 동일하게 설정
            })
        
        return jsonify(result)

    except Exception as e:
        # 터미널에 정확히 어떤 줄에서 어떤 에러가 났는지 출력합니다.
        print(f"[ERROR] 검색 중 상세 오류: {str(e)}") 
        return jsonify({'error': f'서버 오류: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)