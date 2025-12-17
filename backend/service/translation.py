import json
import os

POKEMON_JSON = os.path.join(os.path.dirname(__file__), "../data/pokemon_names.json")

with open(POKEMON_JSON, "r", encoding="utf-8") as f:
    POKEMON_MAP = json.load(f)

def translate_to_english(name: str) -> str:
    """간단한 한글 → 영어 카드 이름 변환"""
    name = name.strip().lower()

    for korean, english in POKEMON_MAP.items():
        if korean.lower() in name:
            return english

    return name