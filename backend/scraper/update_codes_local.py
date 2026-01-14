import json
import os
import re

def update_codes_from_local_json(target_path, sets_en_path):
    """
    target_path: 보정할 파일 (pokemon_series_us_info.json)
    sets_en_path: 기준 데이터 (sets/en.json)
    """
    # 1. 파일 존재 여부 확인
    if not os.path.exists(target_path) or not os.path.exists(sets_en_path):
        print(f"❌ 파일을 찾을 수 없습니다.\n대상: {target_path}\n기준: {sets_en_path}")
        return

    # 2. 데이터 로드
    with open(target_path, 'r', encoding='utf-8') as f:
        target_data = json.load(f)
    
    with open(sets_en_path, 'r', encoding='utf-8') as f:
        # GitHub 데이터는 바로 리스트 형태이거나 {"data": []} 형태일 수 있습니다.
        sets_base = json.load(f)
        if isinstance(sets_base, dict):
            sets_base = sets_base.get('data', sets_base)

    print(f"📦 로컬 데이터 로드 완료: 기준 세트 {len(sets_base)}개")

    # 3. 매칭 및 코드 업데이트
    updated_count = 0
    for item in target_data:
        # 기존 파일의 세트 이름
        local_name = item.get('series_name_us', '').lower().replace('—', '-').strip()
        
        for s in sets_base:
            api_name = s.get('name', '').lower().replace('—', '-').strip()
            
            # 이름이 정확히 일치하거나 중요한 키워드가 포함된 경우
            if local_name == api_name or (len(local_name) > 5 and local_name in api_name):
                raw_id = s.get('id', '').upper() # 예: sv5
                
                # 숫자 앞에 0을 붙여 SV05 형태로 정제 (선택 사항)
                match = re.match(r"([A-Z]+)(\d+)", raw_id)
                if match:
                    prefix, num = match.groups()
                    item['series_code'] = f"{prefix}{int(num):02d}"
                else:
                    item['series_code'] = raw_id
                
                updated_count += 1
                break
    
    # 4. 결과 저장
    with open(target_path, 'w', encoding='utf-8') as f:
        json.dump(target_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 업데이트 완료: 총 {updated_count}개의 세트 코드 매칭 성공")

if __name__ == "__main__":
    # 1. 내가 보정하고 싶은 파일 (기존에 스크래핑한 파일)
    TARGET = 'backend/data/pokemon_series_us_info.json'
    
    # 2. 방금 GitHub에서 복사해온 기준 데이터 파일
    BASE_EN = 'sets/en.json' # 폴더 이름/파일명
    
    update_codes_from_local_json(TARGET, BASE_EN)