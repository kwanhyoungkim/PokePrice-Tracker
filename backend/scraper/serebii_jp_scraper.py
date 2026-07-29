"""
일본판 포켓몬 카드 전체 데이터를 serebii.net 에서 처음부터 다시 수집하는 스크래퍼.

[배경]
기존 all_cards_jp.json 은 TCGdex API 기반이었는데, 카드의 약 60%(4,862/8,159)가
image 필드가 비어 있는 문제가 있었다(TCGdex 쪽 데이터 자체 누락이라 우리 쪽에서
고칠 수 없었음). artofpkm.com 도 검토했지만 카드 번호/레어도 같은 정보가 없고
이미지도 만료되는 서명 URL이라 부적합했다.

serebii.net 은:
- https://www.serebii.net/card/japanese.shtml 에 전체 세트 목록이 (세트명, 슬러그,
  카드 수, 발매일) 표로 깔끔하게 정리되어 있고
- 세트별 카드 상세 페이지(/card/{slug}/{번호}.shtml)의 이미지 URL이 고정형이라
  (artofpkm처럼 만료되는 서명 URL이 아님) 안정적으로 재사용 가능하다.
- "Pokemon TCG Pocket"(모바일 게임)은 이 목록에 아예 포함되어 있지 않아서
  별도 필터링이 필요 없다.

이 스크립트를 실행하면 기존 backend/data/all_cards_jp.json 을 통째로 새로
받아온 데이터로 덮어쓴다(요청대로 "기존 데이터 삭제 후 처음부터 재수집" 방식).

⚠️ 전체 일본판 역사상 모든 세트(1996년 VS/Neo 시절부터 최신 세트까지)를 대상으로
하기 때문에 카드 수가 15,000~20,000장 이상일 수 있고, 카드 1장당 상세 페이지를
개별 요청하므로 전체 실행에 상당한 시간이 걸린다(체감상 1시간 이상 가능).
중간에 Ctrl+C로 중단해도 그때까지 수집한 데이터는 체크포인트에 저장되고,
--retry-failed 로 실패한 카드만 재시도할 수 있다.

사용법:
    python3 backend/scraper/serebii_jp_scraper.py            # 전체 새로 수집
    python3 backend/scraper/serebii_jp_scraper.py --retry-failed  # 실패한 카드만 재시도
"""

import json
import os
import time

import requests
from bs4 import BeautifulSoup

SEREBII_BASE = "https://www.serebii.net"
SETS_INDEX_URL = f"{SEREBII_BASE}/card/japanese.shtml"

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "all_cards_jp.json")
CHECKPOINT_FILE = os.path.join(DATA_DIR, "all_cards_jp.partial.json")
FAILED_FILE = os.path.join(DATA_DIR, "all_cards_jp.failed.json")

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PokePriceTracker/1.0; personal project card data sync)"
}


def fetch_set_list(timeout: int = 20, verbose: bool = True):
    """https://www.serebii.net/card/japanese.shtml 의 세트 표를 파싱해서
    [{"slug": ..., "name": ..., "count": ...}, ...] 형태로 반환한다."""
    res = requests.get(SETS_INDEX_URL, headers=REQUEST_HEADERS, timeout=timeout)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    sets = []
    seen = set()

    for a in soup.select("table a[href^='/card/']"):
        # 세트 로고 이미지 링크와 세트명 텍스트 링크가 같은 href를 중복으로 가리키므로
        # 이미지가 없는(순수 텍스트) 링크만 사용한다.
        if a.find("img"):
            continue

        href = a.get("href", "")
        slug = href.strip("/").split("/")[-1]
        if not slug or "." in slug:
            continue

        tr = a.find_parent("tr")
        if not tr:
            continue
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue

        try:
            count = int(tds[2].get_text(strip=True))
        except ValueError:
            continue

        if slug in seen or count <= 0:
            continue
        seen.add(slug)

        name = a.get_text(strip=True)
        sets.append({"slug": slug, "name": name, "count": count})

    if verbose:
        total = sum(s["count"] for s in sets)
        print(f"📚 세트 {len(sets):,}개 확인, 총 카드 수(추정) {total:,}장")

    return sets


def clean_series_name(name: str) -> str:
    """serebii 세트명 끝에 붙는 ' - Jp' 같은 표기를 제거해서 보기 좋은 시리즈명으로 만든다."""
    for suffix in (" - Jp", " Jp"):
        if name.endswith(suffix):
            return name[: -len(suffix)].strip()
    return name


def fetch_card(slug: str, num: int, series_name: str, timeout: int = 15):
    """세트(slug)의 num번 카드 상세 페이지를 받아와 표준 스키마 dict로 변환한다.
    실패하거나 카드 이름을 못 찾으면 None을 반환한다."""
    url = f"{SEREBII_BASE}/card/{slug}/{num:03d}.shtml"
    res = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
    if res.status_code != 200:
        return None

    soup = BeautifulSoup(res.text, "html.parser")

    og_image = soup.find("meta", attrs={"property": "og:image"})
    image_url = og_image["content"].strip() if og_image and og_image.get("content") else ""

    og_title = soup.find("meta", attrs={"property": "og:title"})
    raw_title = og_title["content"] if og_title and og_title.get("content") else ""
    # og:title 형식 예: "Sewaddle  - White Flare - Jp - Serebii.net TCG"
    name = raw_title.split(" - ")[0].strip() if raw_title else ""

    if not name:
        return None

    return {
        "id": f"{slug}-{num:03d}",
        "name": name,
        "series": series_name,
        "series_id": slug,
        "number": str(num),
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
    print("🇯🇵 일본판 포켓몬 카드 전체 데이터 재수집 (출처: serebii.net)")
    print("=" * 70)

    sets = fetch_set_list()
    total_expected = sum(s["count"] for s in sets)

    all_cards = []
    failed = []
    processed = 0

    try:
        for set_info in sets:
            slug = set_info["slug"]
            series_name = clean_series_name(set_info["name"])
            count = set_info["count"]

            for num in range(1, count + 1):
                processed += 1
                try:
                    card = fetch_card(slug, num, series_name)
                    if card:
                        all_cards.append(card)
                    else:
                        failed.append([slug, num])
                except Exception as e:
                    print(f"⚠️  {slug} #{num} 수집 오류: {e}")
                    failed.append([slug, num])

                if processed % 100 == 0 or processed == total_expected:
                    print(
                        f"🚀 진행 중: {processed}/{total_expected} "
                        f"({processed / total_expected * 100:.1f}%) | "
                        f"수집: {len(all_cards):,} | 실패: {len(failed):,} | "
                        f"현재 세트: {series_name}"
                    )

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
    sets_by_slug = {s["slug"]: clean_series_name(s["name"]) for s in fetch_set_list(verbose=False)}

    still_failed = []
    recovered = 0

    for idx, (slug, num) in enumerate(failed, start=1):
        series_name = sets_by_slug.get(slug, slug)
        try:
            card = fetch_card(slug, num, series_name)
            if card:
                existing.append(card)
                recovered += 1
            else:
                still_failed.append([slug, num])
        except Exception as e:
            print(f"⚠️  재시도 실패 {slug} #{num}: {e}")
            still_failed.append([slug, num])

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
