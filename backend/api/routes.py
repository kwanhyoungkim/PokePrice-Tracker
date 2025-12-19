from flask import Blueprint, request, jsonify
from backend.service.search_service import search_card_prices
from requests.exceptions import RequestException

bp = Blueprint("api", __name__)

@bp.route("/price", methods=["GET"])
def get_price():
    card_name = request.args.get("name")

    if not card_name:
        return jsonify({"error": "name parameter is required"}), 400

    try:
        results = search_card_prices(card_name)
        
        # search_card_prices가 내부적으로 오류 JSON을 반환한 경우 처리
        if isinstance(results, dict) and results.get("error"):
            # 오류 내용이 503과 관련 있다면 503 상태 코드를 반환
            return jsonify(results), 503
        
        # 정상 결과
        return jsonify(results)
    
    # ⭐ RequestException을 잡아 외부 API 연결 실패로 간주하고 503 반환
    except RequestException as e:
        print(f"RequestException caught in routes: {e}") 
        return jsonify({"error": "Service temporarily unavailable due to external API connection failure."}), 503
    
    # ⭐ 기타 예상치 못한 내부 서버 오류는 500으로 처리
    except Exception as e:
        print(f"Unexpected Internal Server Error: {e}")
        return jsonify({"error": "An unexpected internal server error occurred."}), 500