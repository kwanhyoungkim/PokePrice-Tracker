"""
영문 시리즈(backend/data/pokemon_series_us_info.json)와 일본 시리즈 정보를
Postgres(도커 컨테이너)의 series_us / series_jp 테이블에 적재한다.

- series_us: backend/data/pokemon_series_us_info.json (로컬 파일) 을 읽어서 적재.
- series_jp: jp.pokellector.com/sets 를 직접 스크래핑해서 적재한다(로컬 파일 아님).
  예전에는 pokemon_series_jp_info.json 을 썼는데, 그 파일은 시리즈(시대)별로
  1번부터 다시 매겨지는 번호를 PK로 써서 신뢰할 수 없었다. jp.pokellector.com/sets
  페이지는 세트들을 "Scarlet & Violet Series", "Mega Series" 같은 실제 시리즈
  헤더로 묶어서 보여주므로, 이 헤더를 그대로 시리즈 정보로 사용한다
  (cards_jp.series_id 와 동일한 세트 슬러그를 키로 매칭할 수 있다).

사용법 (프로젝트 루트에서):
    docker compose up -d          # Postgres 컨테이너 기동
    python3 backend/database/load_series_data.py

이미 적재된 항목(PK 동일)은 최신 내용으로 덮어쓴다(UPSERT).
"""

import json
import os
import sys
import time

import psycopg2.extras

from db import ensure_schema, get_connection

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRAPER_DIR = os.path.join(_THIS_DIR, "..", "scraper")
sys.path.insert(0, _SCRAPER_DIR)

from pokellector_jp_scraper import fetch_set_list as fetch_jp_set_list  # noqa: E402

DATA_DIR = os.path.join(_THIS_DIR, "..", "data")
SERIES_US_JSON = os.path.join(DATA_DIR, "pokemon_series_us_info.json")


def wait_for_db(retries: int = 20, delay: float = 1.5):
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


def _load_json(path):
    if not os.path.exists(path):
        print(f"⚠️  {path} 파일이 없습니다. 건너뜁니다.")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_series_us(conn):
    items = _load_json(SERIES_US_JSON)
    if not items:
        return

    rows = [
        (
            item.get("set_id"),
            item.get("set_name_us"),
            item.get("series_name_us"),
            item.get("logo_url"),
            item.get("symbol_url"),
            item.get("card_count"),
            item.get("type"),
        )
        for item in items
        if item.get("set_id")
    ]

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO series_us (set_id, set_name_us, series_name_us, logo_url, symbol_url, card_count, type)
            VALUES %s
            ON CONFLICT (set_id) DO UPDATE SET
                set_name_us = EXCLUDED.set_name_us,
                series_name_us = EXCLUDED.series_name_us,
                logo_url = EXCLUDED.logo_url,
                symbol_url = EXCLUDED.symbol_url,
                card_count = EXCLUDED.card_count,
                type = EXCLUDED.type
            """,
            rows,
            page_size=500,
        )
    conn.commit()
    print(f"✅ series_us 적재 완료: {len(rows):,}건")


def load_series_jp(conn):
    print("🌐 jp.pokellector.com/sets 에서 일본 시리즈 정보를 가져오는 중...")
    items = fetch_jp_set_list(verbose=False)
    if not items:
        print("⚠️  일본 시리즈 정보를 가져오지 못했습니다.")
        return

    rows = [
        (
            item.get("slug"),
            item.get("name"),
            item.get("series_group"),
        )
        for item in items
        if item.get("slug")
    ]

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO series_jp (set_id, set_name, series_group)
            VALUES %s
            ON CONFLICT (set_id) DO UPDATE SET
                set_name = EXCLUDED.set_name,
                series_group = EXCLUDED.series_group
            """,
            rows,
            page_size=500,
        )
    conn.commit()
    print(f"✅ series_jp 적재 완료: {len(rows):,}건")


def run():
    wait_for_db()
    conn = get_connection()
    try:
        ensure_schema(conn)
        load_series_us(conn)
        load_series_jp(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    run()
