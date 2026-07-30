"""
카드/시리즈 데이터를 저장하는 Postgres(도커 컨테이너) 연결 헬퍼.

로컬 JSON 파일(backend/data/all_cards_en.json, all_cards_jp.json,
pokemon_series_us_info.json, pokemon_series_jp_info.json)을 통째로 메모리에
올리는 대신, docker-compose.yml 로 띄운 Postgres 컨테이너에 적재해두고
그때그때 쿼리한다.

- cards_en: 영문판 카드
- cards_jp: 일본판 카드 (jp.pokellector.com 기반, 실제 일본어 카드명 포함)
- series_us: 영문 시리즈/세트 정보
- series_jp: 일본 시리즈 정보
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

CARDS_JP_SCHEMA = """
CREATE TABLE IF NOT EXISTS cards_jp (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    jp_name TEXT,
    series TEXT,
    series_id TEXT,
    number TEXT,
    rarity TEXT,
    image TEXT
);
CREATE INDEX IF NOT EXISTS idx_cards_jp_name_lower ON cards_jp (LOWER(name));
CREATE INDEX IF NOT EXISTS idx_cards_jp_jpname_lower ON cards_jp (LOWER(jp_name));
"""

SERIES_US_SCHEMA = """
CREATE TABLE IF NOT EXISTS series_us (
    set_id TEXT PRIMARY KEY,
    set_name_us TEXT,
    series_name_us TEXT,
    logo_url TEXT,
    symbol_url TEXT,
    card_count INTEGER,
    type TEXT
);
"""

SERIES_JP_SCHEMA = """
CREATE TABLE IF NOT EXISTS series_jp (
    set_id TEXT PRIMARY KEY,
    set_name TEXT,
    series_group TEXT
);
"""
# set_id 는 jp.pokellector.com 의 세트 슬러그로, cards_jp.series_id 와 동일한 값이다.
# series_group 은 jp.pokellector.com/sets 페이지의 헤더(예: "Scarlet & Violet Series",
# "Mega Series")로 묶인 시리즈(시대) 이름이다.
# (예전에는 pokemon_series_jp_info.json 을 썼는데, 그 파일의 series_code 는 시대마다
#  1번부터 다시 매겨지는 값이라 신뢰할 수 없어서 jp.pokellector.com 기준으로 교체했다)


def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute(CARDS_EN_SCHEMA)
        cur.execute(CARDS_JP_SCHEMA)
        cur.execute(SERIES_US_SCHEMA)
        cur.execute(SERIES_JP_SCHEMA)
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


def search_cards_jp(name_query: str, jp_name_query: str = "", limit: int = 200):
    """일본판 카드를 조회한다. name_query(영문/로마자 이름)와 jp_name_query(실제 일본어
    카드명) 둘 중 하나라도 부분 일치하면 반환한다.

    반환 형식은 기존 app.py가 로컬 JSON(all_cards_jp.json)에서 만들던 딕셔너리와
    동일하게 맞춘다.
    """
    if not name_query and not jp_name_query:
        return []

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            conditions = []
            params = []

            if name_query:
                conditions.append("LOWER(name) LIKE %s")
                params.append(f"%{name_query.lower()}%")
            if jp_name_query:
                conditions.append("LOWER(jp_name) LIKE %s")
                params.append(f"%{jp_name_query.lower()}%")

            where_clause = " OR ".join(conditions)
            params.append(limit)

            cur.execute(
                f"""
                SELECT id, name, jp_name, series, series_id, number, rarity, image
                FROM cards_jp
                WHERE {where_clause}
                LIMIT %s
                """,
                params,
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "jp_name": row["jp_name"],
            "series": row["series"],
            "series_id": row["series_id"],
            "number": row["number"],
            "rarity": row["rarity"],
            "image_url": row["image"],
            "language": "ja",
        }
        for row in rows
    ]
