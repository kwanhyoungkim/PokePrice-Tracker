"""
카드 데이터를 저장하는 Postgres(도커 컨테이너) 연결 헬퍼.

로컬 JSON 파일(backend/data/all_cards_en.json 등)을 통째로 메모리에 올리는 대신,
docker-compose.yml 로 띄운 Postgres 컨테이너에 카드 데이터를 적재해두고 그때그때 쿼리한다.

먼저 영문판(cards_en 테이블)만 이 방식으로 전환한다. 일본판은 당분간 기존 방식(로컬 JSON)을
그대로 사용한다.
"""

import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Postgres 커넥션을 새로 열어서 반환한다. 사용 후 반드시 close() 해줄 것."""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5433"),
        dbname=os.getenv("POSTGRES_DB", "pokeprice"),
        user=os.getenv("POSTGRES_USER", "pokeprice"),
        password=os.getenv("POSTGRES_PASSWORD", "pokeprice"),
    )


CARDS_EN_SCHEMA = """
CREATE TABLE IF NOT EXISTS cards_en (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    series TEXT,
    series_id TEXT,
    number TEXT,
    rarity TEXT,
    image TEXT
);
CREATE INDEX IF NOT EXISTS idx_cards_en_name_lower ON cards_en (LOWER(name));
"""


def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute(CARDS_EN_SCHEMA)
    conn.commit()


def search_cards_en(name_query: str, limit: int = 200):
    """영문 카드 이름에 name_query(부분 문자열, 대소문자 무관)가 포함된 카드를 조회한다.

    반환 형식은 기존 app.py가 로컬 JSON에서 만들던 딕셔너리와 동일하게 맞춘다.
    """
    if not name_query:
        return []

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, name, series, series_id, number, image
                FROM cards_en
                WHERE LOWER(name) LIKE %s
                LIMIT %s
                """,
                (f"%{name_query.lower()}%", limit),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "series": row["series"],
            "series_id": row["series_id"],
            "number": row["number"],
            "image_url": row["image"],
            "language": "en",
        }
        for row in rows
    ]
