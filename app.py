import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template

from backend.api.routes import bp
from database.db import init_db

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="frontend/templates",
        static_folder="frontend/static",
    )

    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
    app.config["DATABASE_URL"] = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'modelledger.db'}")
    app.config["UPLOAD_FOLDER"] = str(BASE_DIR / "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB
    app.config["ALLOWED_EXTENSIONS"] = {"image": {"png", "jpg", "jpeg", "webp"}}

    init_db(app)
    app.register_blueprint(bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/register")
    def register_page():
        return render_template("register.html")

    @app.get("/verify")
    def verify_page():
        return render_template("verify.html")

    @app.errorhandler(413)
    def too_large(_e):
        return "File too large (max 10 MB).", 413

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)