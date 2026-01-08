import json
import os
import re
import requests
from bs4 import BeautifulSoup

URL = "https://en.wikipedia.org/wiki/List_of_Pok%C3%A9mon_Trading_Card_Game_sets"

def scrape_comprehensive_sets(url):
    series_data = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        print(f"🌐 페이지 접속 중: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. [텍스트 기반 추출] 1~4세대의 제목(h3, h4)에서 세트명 가져오기
        # 위키피디아의 세트 설명 제목들은 보통 h3 또는 h4 태그입니다.
        headings = soup.find_all(['h3', 'h4'])
        print(f"🔍 텍스트 제목 태그 {len(headings)}개 분석 중...")

        for head in headings:
            # 제목 텍스트 정리 (주석 [edit] 제거)
            set_name = head.get_text(strip=True).replace('[edit]', '')
            
            # 너무 짧거나 세트 이름이 아닌 것들 필터링
            if len(set_name) < 2 or "Generation" in set_name or "sets" in set_name.lower():
                continue
            
            # 해당 세트가 속한 시대(Era) 찾기
            parent_era = head.find_previous('h2')
            era_title = parent_era.get_text(strip=True).replace('[edit]', '') if parent_era else "Classic"

            # 출시일 추정 (제목 바로 아래 문단에서 연도 찾기)
            release_date = "Unknown"
            next_p = head.find_next('p')
            if next_p:
                date_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}', next_p.get_text())
                if date_match:
                    release_date = date_match.group(0)

            series_data.append({
                "series_name_us": set_name,
                "release_date_us": release_date,
                "era": era_title,
                "type": "Text-based"
            })

        # 2. [테이블 기반 추출] 5세대 이후의 테이블 데이터 가져오기
        tables = soup.find_all('table', class_='wikitable')
        print(f"🔍 테이블 {len(tables)}개 분석 중...")

        for table in tables:
            parent_era = table.find_previous('h2')
            era_title = parent_era.get_text(strip=True).replace('[edit]', '') if parent_era else "Modern"
            
            rows = table.find_all('tr')
            for row in rows[1:]:
                cols = row.find_all(['td', 'th'])
                if len(cols) < 2: continue
                
                # 첫 번째 또는 두 번째 칸에서 이름 추출 (숫자 제외)
                name1 = re.sub(r'\[.*?\]', '', cols[0].get_text(strip=True))
                name2 = re.sub(r'\[.*?\]', '', cols[1].get_text(strip=True))
                
                final_name = name2 if re.match(r'^\d+(\.\d+)?$', name1) else name1
                
                if final_name in ["English name", "Set", "Name", ""] or len(final_name) < 2:
                    continue

                # 출시일 찾기
                r_date = "Unknown"
                for col in reversed(cols):
                    txt = col.get_text(strip=True)
                    if re.search(r'\d{4}', txt):
                        r_date = re.sub(r'\[.*?\]', '', txt)
                        break

                series_data.append({
                    "series_name_us": final_name,
                    "release_date_us": r_date,
                    "era": era_title,
                    "type": "Table-based"
                })

        return series_data

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return []

def finalize(data):
    if not data: return
    
    # 중복 제거 및 정제
    unique_data = []
    seen = set()
    for item in data:
        name = item['series_name_us']
        if name not in seen:
            seen.add(name)
            unique_data.append(item)

    # 저장
    output_path = os.path.join(os.getcwd(), 'backend/data/pokemon_series_us_info.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(unique_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 수집 완료! 총 {len(unique_data)}개 세트 저장됨.")
    print(f"📍 1세대 확인: {unique_data[0]['series_name_us']} ({unique_data[0]['release_date_us']})")

if __name__ == "__main__":
    all_data = scrape_comprehensive_sets(URL)
    finalize(all_data)