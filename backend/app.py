import sys
import os
sys.path.append(os.path.dirname(__file__))
from flask import Flask
from backend.api.routes import bp as api_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(api_bp, url_prefix="/api")
    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)