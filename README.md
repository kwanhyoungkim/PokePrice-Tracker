### 📊 PokePrice-Tracker
다국어(한글, 영어, 일본어) 포켓몬 카드 검색 및 이베이(eBay) 최근 낙찰가를 기반으로 실시간 시세를 조회하는 웹 어플리케이션입니다.

### 🚀 주요 기능 (Key Features)
##### 다국어 통합 검색
한글 이름(예: '기라티나') 입력 시 자동으로 영어(Giratina) 및 일본어(ギラティナ)로 변환하여 검색을 수행합니다.

##### 하이브리드 데이터 로드
로컬 JSON 데이터베이스(all_cards_en.json, all_cards_jp.json)와 TCGdex API를 동시 조회하여 누락 없는 방대한 카드 정보를 제공합니다.

##### 실시간 시세 분석
eBay API 스크래퍼를 통해 최근 24시간~최근 판매된 데이터의 평균가, 최고가, 최저가를 계산하여 반환합니다.

##### 특수 시리즈 지원
swsh10.5와 같은 소수점 ID를 가진 스페셜 세트(Crown Zenith 등)도 정확하게 인식하고 분류합니다.

### 🛠 기술 스택 (Tech Stack)
##### Backend
- Python
- Flask

##### Frontend
- HTML5
- CSS3
- JavaScript (Vanilla JS)

##### Data & APIs

- TCGdex API (다국어 데이터 및 세트 정보)

- Pokemon TCG API (영문 상세 데이터 및 이미지)

- eBay Sales Data (Web Scraping)

- Environment: Python-dotenv (환경 변수 관리)

### 📂 Project Structure
```plaintext
.
├── app.py
├── main.py
├── .env
├── backend/
│   ├── data/
│   │   ├── pokemon_names.json
│   │   ├── all_cards_en.json
│   │   ├── all_cards_jp.json
│   │   ├── pokemon_series_info.json
│   │   ├── pokemon_series_jp_info.json
│   │   └── pokemon_series_us_info.json
│   │
│   ├── scraper/
│   │   ├── ebay_scraper.py
│   │   ├── all_card_en_scraper.py
│   │   ├── all_card_jp_scraper.py
│   │   ├── all_card_kor_scraper.py
│   │   ├── pokemon_card_series_kor_scraper.py
│   │   ├── pokemon_card_series_jp_scraper.py
│   │   ├── pokemon_card_series_us_scraper.py
│   │   ├── pokemon_name_scraper_api.py
│   │   ├── pokemon_tcg_api_scraper.py
│   │   ├── import_local_data.py
│   │   └── update_codes_local.py
│   │
│   └── data/
│       └── search_translator.py
│
├── frontend/
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/main.js
│   └── templates/index.html
│
└── pokemon-tcg-data/
    ├── cards/
    ├── decks/
    └── sets/
```


### 🧠 주요 파일 및 역할

| 구분 | 파일 | 설명 |
|---|---|---|
| Server | `app.py` | Flask 메인 서버, 검색 요청 처리 |
| Core | `main.py` | 앱 초기화 및 서비스 조합 |
| Config | `.env` | API Key 및 환경 변수 |
| Scraper | `ebay_scraper.py` | eBay 실거래 시세 수집 |
| API | `pokemon_tcg_api_scraper.py` | Pokémon TCG API 연동 |
| Data | `pokemon_names.json` | 포켓몬 다국어 이름 매핑 |
| Frontend | `index.html` | 검색 UI 템플릿 |

### 🔍 Data Collection & Scraping Layer

eBay

ebay_scraper.py – 실거래 완료 데이터 기반 시세 수집

Pokémon TCG API

pokemon_tcg_api_scraper.py – 공식 카드/이미지 메타데이터

Multilingual Card Data

all_card_en_scraper.py - 영문버전 카드정보 스크래퍼

all_card_jp_scraper.py - 일어버전 카드정보 스크래퍼

all_card_kor_scraper.py - 한글버전 카드정보 스크래퍼

Series Metadata

pokemon_card_series_*_scraper.py - 각 언어별 시리즈 정보 스크래퍼

### 🔍 핵심 로직: 통합 검색 (Unified Search)
사용자가 입력한 한글 포켓몬명을 기반으로 로컬 데이터와 API 데이터를 병합하는 알고리즘을 사용합니다.

Python

#### 1. 한글명 -> 타겟 언어명 변환
```
name_info = POKEMON_MASTER_MAP.get(name_input)
    if name_info:
        search_query = name_info.get('japanese_name' if target_lang == 'ja' else 'english_name')
    else:
        search_query = name_input
```

#### 2. 로컬 파일(JSON) 검색
```
local_matches = [c for c in CARDS_EN_LOCAL if search_query.lower() in c['name'].lower()]
```

#### 3. TCGdex API 호출 및 데이터 병합 (중복 제거)
```
final_results[card_id] = { ...merged_data... }
```

### 📈 시세 조회 방식 (Pricing Logic)
카드 선택 시 eBay에서 다음과 같은 쿼리로 검색하여 가장 신뢰도 높은 시세를 추출합니다.
```
영문: {Card Name} {Number} {Series ID} Pokemon Card

일문: Japanese {Series ID} {Card Name} {Number} Pokemon Card
```
### 💡 설치 및 실행 방법
저장소 클론:
```
git clone https://github.com/kwanhyoungkim/PokePrice-Tracker.git
```
의존성 설치:
```
pip install -r requirements.txt
```
서버 실행:
```
python app.py
접속: http://localhost:5001
```
### 📝 라이선스 및 데이터 출처
본 프로젝트는 개인 학습 및 시세 확인을 목적으로 제작되었습니다.

Data Credits: TCGdex, Pokemon TCG API, eBay