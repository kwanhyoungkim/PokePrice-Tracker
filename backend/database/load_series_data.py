"""
backend/data/pokemon_series_us_info.json, pokemon_series_jp_info.json 을 읽어서
Postgres(도커 컨테이너)의 series_us / series_jp 테이블에 적재한다.

사용법 (프로젝트 루트에서):
    docker compose up -d          # Postgres 컨테이너 기동
    python3 backend/database/load_series_data.py

이미 적재된 항목(PK 동일)은 최신 내용으로 덮어쓴다(UPSERT). 적재가 끝나면
pokemon_series_us_info.json / pokemon_series_jp_info.json 파일은 더 이상
앱 실행에 필요하지 않다.
"""

import json
import os
import time

import psycopg2.extras

from db import ensure_schema, get_connection

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
SERIES_US_JSON = os.path.join(DATA_DIR, "pokemon_series_us_info.json")
SERIES_JP_JSON = os.path.join(DATA_DIR, "pokemon_series_jp_info.json")


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
    items = _load_json(SERIES_JP_JSON)
    if not items:
        return

    rows = [
        (
            item.get("series_code"),
            item.get("series_name_jp"),
            item.get("series_name_en"),
            item.get("release_date"),
            item.get("era"),
        )
        for item in items
        if item.get("series_code")
    ]

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO series_jp (series_code, series_name_jp, series_name_en, release_date, era)
            VALUES %s
            ON CONFLICT (series_code, era) DO UPDATE SET
                series_name_jp = EXCLUDED.series_name_jp,
                series_name_en = EXCLUDED.series_name_en,
                release_date = EXCLUDED.release_date
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
