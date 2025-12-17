from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import json
import os
import time
import re
import math

# 설정
CARDS_PER_PAGE = 50
TCG_URL_BASE = f"https://www.tcgcollector.com/cards/intl?releaseDateOrder=newToOld&displayAs=images&cardsPerPage={CARDS_PER_PAGE}"
TIMEOUT = 120000


def scrape_tcgcollector_all_cards():
    """TCGCollector에서 모든 영문 카드 정보 스크래핑"""
    
    all_cards = []
    
    with sync_playwright() as p:
        print("="*70)
        print("TCGCollector 영문 포켓몬 카드 전체 스크래퍼")
        print("="*70)
        print("\n브라우저 시작 중...\n")
        
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.navigator.chrome = {runtime: {}};
        """)
        
        page = context.new_page()
        page.set_default_timeout(TIMEOUT)
        
        try:
            print(f"페이지 로딩: {TCG_URL_BASE}\n")
            page.goto(TCG_URL_BASE, wait_until='domcontentloaded', timeout=TIMEOUT)
            
            print("페이지 렌더링 대기 (15초)...\n")
            time.sleep(15)
            
            html = page.content()
            with open('tcgcollector_debug.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"✓ HTML 저장: tcgcollector_debug.html ({len(html):,} bytes)\n")
            
            soup = BeautifulSoup(html, 'html.parser')
            
            print("총 카드 수 확인 중...\n")
            
            total_cards = 0
            total_cards_text = None
            
            count_elem = soup.find('span', class_='card-count-text')
            if count_elem:
                total_cards_text = count_elem.get_text()
                print(f"방법1 발견: {total_cards_text}")
            
            if not total_cards_text:
                count_elem = soup.find(class_=lambda x: x and 'card-count' in str(x).lower())
                if count_elem:
                    total_cards_text = count_elem.get_text()
                    print(f"방법2 발견: {total_cards_text}")
            
            if not total_cards_text:
                all_text = soup.get_text()
                match = re.search(r'of\s+([\d,]+)\s+cards', all_text)
                if match:
                    total_cards_text = match.group()
                    print(f"방법3 발견: {total_cards_text}")
            
            if total_cards_text:
                match = re.search(r'([\d,]+)', total_cards_text)
                if match:
                    total_cards = int(match.group(1).replace(',', ''))
                    print(f"\n✅ 총 카드 수: {total_cards:,}개\n")
            
            if total_cards == 0:
                print("⚠️ 총 카드 수를 찾을 수 없습니다.")
                return []
            
            total_pages = math.ceil(total_cards / CARDS_PER_PAGE)
            print(f"총 페이지 수: {total_pages}페이지\n")
            
            for page_num in range(1, total_pages + 1):
                print(f"\n{'='*70}")
                print(f"페이지 {page_num}/{total_pages} 스크래핑 중... ({len(all_cards):,}개 수집)")
                print(f"{'='*70}\n")
                
                try:
                    current_url = f"{TCG_URL_BASE}&page={page_num}"
                    page.goto(current_url, wait_until='domcontentloaded', timeout=TIMEOUT)
                    time.sleep(5)
                    
                    try:
                        page.wait_for_selector('img.card-image-grid-item-image', timeout=10000)
                        print(f"  ✓ 카드 이미지 로드 완료")
                    except:
                        print(f"  ✗ 카드 이미지 로드 실패. 건너뜁니다.")
                        continue
                    
                    html = page.content()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    page_cards = []
                    
                    img_tags = soup.find_all('img', class_='card-image-grid-item-image')
                    print(f"  이미지 태그: {len(img_tags)}개 발견")
                    
                    for idx, img in enumerate(img_tags, 1):
                        try:
                            alt_text = img.get('alt', '')
                            
                            if not alt_text:
                                continue
                            
                            if page_num == 1 and idx <= 3:
                                print(f"  [디버그 {idx}] {alt_text}")
                            
                            match = re.match(r'^(.+?)\s*\((.+?)\s+(\d+/\d+)\)$', alt_text)
                            
                            if match:
                                card_name = match.group(1).strip()
                                series_name = match.group(2).strip()
                                card_number = match.group(3).strip()
                                
                                page_cards.append({
                                    'card_name_en': card_name,
                                    'series_name_en': series_name,
                                    'card_number': card_number
                                })
                            else:
                                if page_num == 1 and idx <= 3:
                                    print(f"    ✗ 패턴 불일치: {alt_text}")
                        
                        except Exception as e:
                            if page_num == 1 and idx <= 3:
                                print(f"    ✗ 오류: {e}")
                            continue
                    
                    all_cards.extend(page_cards)
                    print(f"  ✅ {len(page_cards)}개 카드 추출 (총 {len(all_cards):,}개)\n")
                    
                    if page_num % 10 == 0:
                        save_to_json(all_cards, file_name=f"pokemon_card_list_en_backup.json")
                        print(f"  [백업 저장] {page_num}페이지까지 저장\n")
                
                except PlaywrightTimeoutError:
                    print(f"  ✗ 페이지 {page_num} 타임아웃. 건너뜁니다.\n")
                    continue
                
                except Exception as e:
                    print(f"  ✗ 페이지 {page_num} 오류: {e}\n")
                    continue
            
            print(f"\n{'='*70}")
            print(f"✅ 총 {len(all_cards):,}개 카드 정보 수집 완료")
            print(f"{'='*70}\n")
            
            return all_cards
            
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}\n")
            import traceback
            traceback.print_exc()
            return []
            
        finally:
            browser.close()


def save_to_json(data, output_dir="backend/data", file_name="pokemon_card_list_en.json"):
    """JSON 파일로 저장 (중복 제거)"""
    if not data:
        print("저장할 데이터가 없습니다.")
        return False
    
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, file_name)
    
    unique_data = {}
    for item in data:
        key = (item['card_name_en'], item['card_name_en'], item['card_number'])
        unique_data[key] = item
    
    final_data = list(unique_data.values())
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)
    
    size = os.path.getsize(output_path) / 1024
    
    print(f"✅ 저장 완료: {output_path}")
    print(f"   데이터: {len(final_data):,}개 (중복 제거 후)")
    print(f"   크기: {size:.2f} KB\n")
    
    return True


def main():
    cards = scrape_tcgcollector_all_cards()
    
    if not cards:
        print("\n데이터 수집 실패")
        print("\n💡 해결 방법:")
        print("  1. tcgcollector_debug.html 파일을 브라우저로 열어 확인")
        print("  2. 페이지가 정상 로딩되는지 확인")
        return
    
    print("="*70)
    print("데이터 미리보기 (처음 10개)")
    print("="*70)
    for idx, card in enumerate(cards[:10], 1):
        print(f"\n{idx}. {card['card_name_en']}")
        print(f"   시리즈: {card['series_name_en']}")
        print(f"   번호: {card['card_number']}")
    
    print("\n" + "="*70)
    save_to_json(cards)
    
    print("="*70)
    print("JSON 샘플:")
    print("="*70)
    print(json.dumps(cards[:3], indent=2, ensure_ascii=False))
    
    print("\n" + "="*70)
    print("완료!")
    print("="*70)


if __name__ == '__main__':
    main()