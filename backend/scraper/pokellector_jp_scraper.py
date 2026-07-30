"""
일본판 포켓몬 카드 전체 데이터를 jp.pokellector.com 에서 처음부터 다시 수집하는 스크래퍼.

[배경]
기존 all_cards_jp.json 은 TCGdex API 기반이었는데, 카드의 약 60%(4,862/8,159)가
image 필드가 비어 있는 문제가 있었다(TCGdex 쪽 데이터 자체 누락이라 우리 쪽에서
고칠 수 없었음).

대안으로 artofpkm.com, serebii.net 도 검토했지만:
- artofpkm.com: 카드 번호/레어도 정보가 없고, 이미지가 만료되는 Rails 서명 URL.
- serebii.net: 이미지는 고정 URL이라 좋았지만, 세트 표에 적힌 카드 수와 실제
  카드 수(시크릿레어 포함)가 안 맞고, 일부 카드 항목 자체가 비어있어 결번이 생김.

jp.pokellector.com 은:
- https://jp.pokellector.com/sets 에 1996년 Vending Series부터 최신 세트까지
  전체 세트 목록이 슬러그(예: White-Flare-Expansion)와 함께 정리되어 있고
- 세트별 카드 목록 페이지(/{세트슬러그}/) 한 페이지에 시크릿레어까지 포함한
  전체 카드 링크가 다 나와 있어서(페이지네이션 없음), 번호를 추측할 필요 없이
  실제 존재하는 카드 URL만 그대로 따라가면 된다.
- 카드 상세 페이지에 영문(로마자) 이름, **실제 일본어 이름**, 레어도, 세트명,
  카드 번호, 그리고 만료되지 않는 고정 이미지 URL(den-cards.pokellector.com)이
  전부 있다.
- "Pokemon TCG Pocket"(모바일 게임)은 이 사이트의 세트 목록에 포함되어 있지
  않아서 별도 필터링이 필요 없다.

이 스크립트를 실행하면 기존 backend/data/all_cards_jp.json 을 완전히 새 데이터로
덮어쓴다(기존 데이터 삭제 후 처음부터 재수집).

⚠️ 전체 일본판 역사상 모든 세트를 대상으로 하기 때문에 카드 수가 15,000장 이상일
수 있고, 세트 목록 페이지 1회 + 카드 1장당 상세 페이지 1회씩 요청하므로 전체
실행에 상당한 시간이 걸린다(체감상 1시간 이상 가능). 중간에 Ctrl+C로 중단해도
그때까지 수집한 데이터는 체크포인트에 저장되고, --retry-failed 로 실패한
카드만 재시도할 수 있다.

사용법:
    python3 backend/scraper/pokellector_jp_scraper.py              # 전체 새로 수집
    python3 backend/scraper/pokellector_jp_scraper.py --retry-failed  # 실패한 것만 재시도
"""

import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup

POKELLECTOR_BASE = "https://jp.pokellector.com"
SETS_INDEX_URL = f"{POKELLECTOR_BASE}/sets"

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "all_cards_jp.json")
CHECKPOINT_FILE = os.path.join(DATA_DIR, "all_cards_jp.partial.json")
FAILED_FILE = os.path.join(DATA_DIR, "all_cards_jp.failed.json")

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PokePriceTracker/1.0; personal project card data sync)"
}

SET_LINK_RE = re.compile(r"^/([A-Za-z0-9\-]+-Expansion)/?$")
CARD_LINK_RE = re.compile(r"^/([A-Za-z0-9\-]+-Expansion)/([A-Za-z0-9\-]+-Card-\d+)/?$")


def fetch_set_list(timeout: int = 20, verbose: bool = True):
    """https://jp.pokellector.com/sets 에서 전체 세트 목록을 [{"slug", "name"}] 로 반환한다."""
    res = requests.get(SETS_INDEX_URL, headers=REQUEST_HEADERS, timeout=timeout)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    sets = []
    seen = set()
    for a in soup.find_all("a", href=True):
        m = SET_LINK_RE.match(a["href"])
        if not m:
            continue
        slug = m.group(1)
        if slug in seen:
            continue
        seen.add(slug)
        name = a.get_text(strip=True) or a.get("title", "") or slug
        sets.append({"slug": slug, "name": name})

    if verbose:
        print(f"📚 세트 {len(sets):,}개 확인")
    return sets


def fetch_set_cards(slug: str, timeout: int = 20):
    """세트 목록 페이지에서 실제 존재하는 카드 상세 URL들을 그대로 수집한다.
    (번호를 추측하지 않고, 페이지에 실제로 걸려있는 링크만 사용하므로 결번이 없다)"""
    url = f"{POKELLECTOR_BASE}/{slug}/"
    res = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    cards = []
    seen = set()
    for a in soup.find_all("a", href=True):
        m = CARD_LINK_RE.match(a["href"])
        if not m or m.group(1) != slug:
            continue
        card_path = f"/{m.group(1)}/{m.group(2)}"
        if card_path in seen:
            continue
        seen.add(card_path)
        cards.append(card_path)

    return cards


def fetch_card(card_path: str, timeout: int = 15):
    """카드 상세 페이지를 받아와 표준 스키마 dict로 변환한다. 실패 시 None."""
    url = f"{POKELLECTOR_BASE}{card_path}"
    res = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
    if res.status_code != 200:
        return None

    soup = BeautifulSoup(res.text, "html.parser")

    og_image = soup.find("meta", attrs={"property": "og:image"})
    image_url = og_image["content"].strip() if og_image and og_image.get("content") else ""

    og_title = soup.find("meta", attrs={"property": "og:title"})
    raw_title = og_title["content"] if og_title and og_title.get("content") else ""
    # og:title 형식 예: "Sewaddle - White Flare #1"
    name = raw_title.split(" - ")[0].strip() if raw_title else ""

    if not name:
        return None

    page_text = soup.get_text("\n")

    jp_name = ""
    jp_match = re.search(r"JPN:\s*\n?\s*([^\n]+)", page_text)
    if jp_match:
        jp_name = jp_match.group(1).strip()

    rarity = ""
    rarity_match = re.search(r"Rarity:\s*\n?\s*([^\n]+)", page_text)
    if rarity_match:
        rarity = rarity_match.group(1).strip()

    # 카드 번호는 URL 끝 "-Card-123" 에서 뽑아낸다 (본문의 "X/Y" 표기보다 안정적)
    number_match = re.search(r"-Card-(\d+)$", card_path)
    number = number_match.group(1) if number_match else ""

    series_name = ""
    series_match = re.search(r"» ([^»\n]+?) »?\s*$", page_text.split("\n\n")[0]) if page_text else None

    slug = card_path.strip("/").split("/")[0]

    return {
        "id": f"{slug}-{number}" if number else card_path.strip("/").replace("/", "-"),
        "name": name,
        "jp_name": jp_name,
        "series": series_name,
        "series_id": slug,
        "number": number,
        "rarity": rarity,
        "image": image_url,
    }


def _save_checkpoint(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _save_failed(failed):
    os.makedirs(DATA_DIR, exist_ok=True)
    if failed:
        with open(FAILED_FILE, "w", encoding="utf-8") as f:
            json.dump(failed, f, ensure_ascii=False)
    elif os.path.exists(FAILED_FILE):
        os.remove(FAILED_FILE)


def save_to_json(data):
    """수집된 데이터로 backend/data/all_cards_jp.json 을 통째로 덮어쓴다."""
    if not data:
        print("❌ 저장할 데이터가 없습니다.")
        return False

    os.makedirs(DATA_DIR, exist_ok=True)
    unique = {item["id"]: item for item in data}
    final_list = list(unique.values())

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_list, f, indent=2, ensure_ascii=False)

    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

    print("\n" + "=" * 70)
    print(f"✅ 저장 완료: {OUTPUT_FILE} (기존 데이터 전체 교체)")
    print(f"   총 수집 카드: {len(final_list):,}개")
    print("=" * 70)
    return True


def run():
    print("=" * 70)
    print("🇯🇵 일본판 포켓몬 카드 전체 데이터 재수집 (출처: jp.pokellector.com)")
    print("=" * 70)

    sets = fetch_set_list()

    all_cards = []
    failed = []
    processed = 0

    try:
        for idx, set_info in enumerate(sets, start=1):
            slug = set_info["slug"]
            series_display_name = set_info["name"]

            try:
                card_paths = fetch_set_cards(slug)
            except Exception as e:
                print(f"⚠️  세트 '{slug}' 카드 목록 조회 실패: {e}")
                continue

            print(
                f"📦 [{idx}/{len(sets)}] {series_display_name} ({slug}) - "
                f"카드 {len(card_paths):,}장 발견"
            )

            for card_path in card_paths:
                processed += 1
                try:
                    card = fetch_card(card_path)
                    if card:
                        if not card.get("series"):
                            card["series"] = series_display_name
                        all_cards.append(card)
                    else:
                        failed.append(card_path)
                except Exception as e:
                    print(f"⚠️  {card_path} 수집 오류: {e}")
                    failed.append(card_path)

                if processed % 200 == 0:
                    print(f"   🚀 누적 진행: {processed:,}장 처리 | 수집: {len(all_cards):,} | 실패: {len(failed):,}")

                if processed % 1000 == 0:
                    _save_checkpoint(all_cards)
                    _save_failed(failed)

                time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n\n🛑 중단됨! 지금까지 수집된 데이터를 저장합니다...")

    _save_failed(failed)
    if failed:
        print(
            f"\n⚠️  {len(failed):,}장은 수집에 실패했습니다. 아래 명령으로 재시도할 수 있습니다:\n"
            f"    python3 {os.path.basename(__file__)} --retry-failed"
        )

    save_to_json(all_cards)


def retry_failed():
    if not os.path.exists(FAILED_FILE):
        print("✅ 재시도할 실패 항목이 없습니다.")
        return

    with open(FAILED_FILE, "r", encoding="utf-8") as f:
        failed = json.load(f)

    if not failed:
        print("✅ 재시도할 실패 항목이 없습니다.")
        return

    existing = []
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)

    print(f"🔁 이전 실행에서 실패한 {len(failed):,}개 카드를 재시도합니다...")

    sets_by_slug = {s["slug"]: s["name"] for s in fetch_set_list(verbose=False)}

    still_failed = []
    recovered = 0

    for idx, card_path in enumerate(failed, start=1):
        slug = card_path.strip("/").split("/")[0]
        series_display_name = sets_by_slug.get(slug, slug)
        try:
            card = fetch_card(card_path)
            if card:
                if not card.get("series"):
                    card["series"] = series_display_name
                existing.append(card)
                recovered += 1
            else:
                still_failed.append(card_path)
        except Exception as e:
            print(f"⚠️  재시도 실패 {card_path}: {e}")
            still_failed.append(card_path)

        if idx % 50 == 0 or idx == len(failed):
            print(f"   재시도 진행: {idx}/{len(failed)} | 복구: {recovered} | 여전히 실패: {len(still_failed)}")

        time.sleep(0.1)

    save_to_json(existing)
    _save_failed(still_failed)

    print(f"\n✅ 재시도 완료: {recovered:,}개 복구, {len(still_failed):,}개는 여전히 실패로 남았습니다.")
    if still_failed:
        print(f"   (다시 '--retry-failed' 를 실행하면 남은 {len(still_failed):,}개만 재도전합니다.)")


if __name__ == "__main__":
    import sys

    start_time = time.time()

    if "--retry-failed" in sys.argv:
        retry_failed()
    else:
        run()

    elapsed = time.time() - start_time
    print(f"\n⏱️  총 소요 시간: {elapsed / 60:.2f}분")
