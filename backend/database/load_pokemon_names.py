"""
backend/data/pokemon_names.json 을 읽어서 Postgres(도커 컨테이너)의 pokemon_names 테이블에 적재한다.

사용법 (프로젝트 루트에서):
    docker compose up -d              # Postgres 컨테이너 기동
    python3 backend/database/load_pokemon_names.py

이미 적재된 이름(korean_name 동일)은 최신 내용으로 덮어쓴다(UPSERT). 적재가 끝나면
backend/data/pokemon_names.json 파일은 더 이상 앱 실행에 필요하지 않다
(app.py가 이제 이 DB를 직접 조회한다).
"""

import json
import os
import time

import psycopg2.extras

from db import ensure_schema, get_connection

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
POKEMON_NAMES_JSON = os.path.join(DATA_DIR, "pokemon_names.json")


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


def load_names():
    if not os.path.exists(POKEMON_NAMES_JSON):
        print(f"❌ {POKEMON_NAMES_JSON} 파일이 없습니다.")
        return

    with open(POKEMON_NAMES_JSON, "r", encoding="utf-8") as f:
        names = json.load(f)

    print(f"📦 {len(names):,}개의 포켓몬 이름 매핑을 Postgres에 적재합니다...")

    wait_for_db()
    conn = get_connection()
    try:
        ensure_schema(conn)

        rows = [
            (
                n.get("korean_name"),
                n.get("number"),
                n.get("english_name"),
                n.get("japanese_name"),
            )
            for n in names
            if n.get("korean_name")
        ]

        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO pokemon_names (korean_name, number, english_name, japanese_name)
                VALUES %s
                ON CONFLICT (korean_name) DO UPDATE SET
                    number = EXCLUDED.number,
                    english_name = EXCLUDED.english_name,
                    japanese_name = EXCLUDED.japanese_name
                """,
                rows,
                page_size=1000,
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM pokemon_names")
            total = cur.fetchone()[0]

        print(f"✅ 적재 완료! pokemon_names 테이블 총 {total:,}행")
    finally:
        conn.close()


if __name__ == "__main__":
    load_names()
