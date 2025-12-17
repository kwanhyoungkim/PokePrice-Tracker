import requests
import json
import time

# ------------------------------
# API URL 정의
# ------------------------------
SET_LIST_URL = "https://cardmon-reboot1.du.r.appspot.com/pg-poke-load-setlist"
CARD_LIST_URL = "https://cardmon-reboot1.du.r.appspot.com/pg-poke-load-cardinfo-one-setname"

HEADERS = {
    "Content-Type": "application/json"
}

# ------------------------------
# 세트 목록 가져오기
# ------------------------------
def fetch_set_list():
    print("📌 세트 목록 가져오는 중...")

    response = requests.post(SET_LIST_URL, json={}, headers=HEADERS)
    response.raise_for_status()

    data = response.json()

    # 실제 세트 목록 구조에 따라 key 조정 필요할 수 있음
    return data.get("setList", data)   # 안전하게 처리


# ------------------------------
# 세트명으로 카드 목록 가져오기
# ------------------------------
def fetch_cards_by_set(set_name):
    payload = {
        "setName": set_name,
        "lan": "ko"    # 한글판
    }

    response = requests.post(CARD_LIST_URL, json=payload, headers=HEADERS)

    if response.status_code != 200:
        print(f"❌ 세트 요청 실패: {set_name} - {response.status_code}")
        return []

    try:
        return response.json().get("cardList", [])
    except:
        print(f"⚠ JSON 파싱 실패 - 세트명: {set_name}")
        print(response.text)
        return []


# ------------------------------
# 전체 카드 스크래핑
# ------------------------------
def scrape_all_korean_cards():
    set_list = fetch_set_list()
    print(f"📌 총 세트 수: {len(set_list)}")

    all_cards = []

    for idx, s in enumerate(set_list, start=1):
        set_name = s.get("setNameKo") or s.get("setName")  # 키 구조에 맞게 조정
        if not set_name:
            continue

        print(f"\n[{idx}/{len(set_list)}] 세트 수집 중 → {set_name}")

        card_list = fetch_cards_by_set(set_name)

        for card in card_list:
            # 필요한 정보만 추출해서 저장
            card_entry = {
                "name": card.get("nameKo") or card.get("name"),
                "series": set_name,
                "cardNumber": card.get("cardNumber"),
            }
            all_cards.append(card_entry)

        time.sleep(0.3)  # 서버 부담 최소화

    return all_cards


# ------------------------------
# 실행 및 저장
# ------------------------------
def main():
    cards = scrape_all_korean_cards()

    print(f"\n📦 총 수집된 카드 수 : {len(cards)}")

    with open("all_korean_pokemon_cards.json", "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)

    print("\n✅ 저장 완료 → all_korean_pokemon_cards.json")


if __name__ == "__main__":
    main()
