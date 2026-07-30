"""
backend/data/all_cards_jp.json 을 읽어서 Postgres(도커 컨테이너)의 cards_jp 테이블에 적재한다.

사용법 (프로젝트 루트에서):
    docker compose up -d          # Postgres 컨테이너 기동
    python3 backend/database/load_jp_cards.py

이미 적재된 카드(id 동일)는 최신 내용으로 덮어쓴다(UPSERT). 적재가 끝나면
backend/data/all_cards_jp.json 파일은 더 이상 앱 실행에 필요하지 않다
(app.py가 이제 이 DB를 직접 조회한다).
"""

import json
import os
import time

import psycopg2.extras

from db import ensure_schema, get_connection

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
CARDS_JP_JSON = os.path.join(DATA_DIR, "all_cards_jp.json")


def wait_for_db(retries: int = 20, delay: float = 1.5):
    """docker compose up 직후에는 Postgres가 아직 뜨는 중일 수 있어서 재시도한다."""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            conn = get_connection()
            conn.close()
            return
        except Exception as e:
            last_error = e
            print(f"⏳ DB 연결 대기 중... ({attempt}/{retries})")
            time.sleep(delay)
    raise RuntimeError(f"❌ Postgres에 연결하지 못했습니다. docker compose up -d 를 먼저 실행했는지 확인하세요.\n{last_error}")


def load_cards():
    if not os.path.exists(CARDS_JP_JSON):
        print(f"❌ {CARDS_JP_JSON} 파일이 없습니다. 먼저 backend/scraper/pokellector_jp_scraper.py 를 실행해주세요.")
        return

    with open(CARDS_JP_JSON, "r", encoding="utf-8") as f:
        cards = json.load(f)

    print(f"📦 {len(cards):,}장의 일본판 카드를 Postgres에 적재합니다...")

    wait_for_db()
    conn = get_connection()
    try:
        ensure_schema(conn)

        rows = [
            (
                c.get("id"),
                c.get("name"),
                c.get("jp_name"),
                c.get("series"),
                c.get("series_id"),
                c.get("number"),
                c.get("rarity"),
                c.get("image"),
            )
            for c in cards
            if c.get("id")
        ]

        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO cards_jp (id, name, jp_name, series, series_id, number, rarity, image)
                VALUES %s
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    jp_name = EXCLUDED.jp_name,
                    series = EXCLUDED.series,
                    series_id = EXCLUDED.series_id,
                    number = EXCLUDED.number,
                    rarity = EXCLUDED.rarity,
                    image = EXCLUDED.image
                """,
                rows,
                page_size=1000,
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM cards_jp")
            total = cur.fetchone()[0]

        print(f"✅ 적재 완료! cards_jp 테이블 총 {total:,}행")
    finally:
        conn.close()


if __name__ == "__main__":
    load_cards()
