"""POST /register, POST /verify, GET /download/<token>.

Browsers get HTML (result.html). Clients sending Accept: application/json
(or ?format=json) get JSON.
"""
import logging
from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, render_template, request, send_from_directory, url_for
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.exc import IntegrityError

from backend.services.detector import verify_file
from backend.services.files import UploadError, discard, save_upload
from backend.services.provenance import create_record, get_record, reserve_id
from database.db import session_scope
from watermark.embed import SUPPORTED_KINDS, embed_watermark
from watermark.id_generator import is_valid_id

bp = Blueprint("api", __name__)
log = logging.getLogger(__name__)

DOWNLOAD_MAX_AGE = 24 * 3600  # seconds a download link stays valid


def _wants_json() -> bool:
    return request.args.get("format") == "json" or request.accept_mimetypes.best == "application/json"


def _fail(page: str, message: str, status: int = 400):
    if _wants_json():
        return jsonify(success=False, error=message), status
    return render_template(page, error=message), status


def _clean(key: str, limit: int) -> str:
    value = (request.form.get(key) or "").strip()[:limit]
    return "".join(ch for ch in value if ch.isprintable())


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="modelledger-download")


def _watermarked_dir() -> Path:
    return Path(current_app.config["UPLOAD_FOLDER"]) / "watermarked"


@bp.post("/register")
def register():
    page = "register.html"
    storage = request.files.get("file")
    if storage is None or not storage.filename:
        return _fail(page, "Choose a file to register.")

    model_name = _clean("model_name", 120)
    generator_name = _clean("generator_name", 120)
    creator = _clean("creator", 120)
    description = _clean("description", 500)
    if not (model_name and generator_name and creator):
        return _fail(page, "Model or source, generator and creator are required.")

    saved = None
    try:
        try:
            saved = save_upload(storage, current_app.config["UPLOAD_FOLDER"], current_app.config["ALLOWED_EXTENSIONS"])
        except UploadError as exc:
            return _fail(page, str(exc))

        if saved.kind not in SUPPORTED_KINDS:
            return _fail(page, f"Watermarking for {saved.kind} files isn't enabled yet.")

        with session_scope() as session:
            wm_id = reserve_id(session)

        try:
            out_path = embed_watermark(saved.path, saved.kind, wm_id, _watermarked_dir())
        except Exception:
            log.exception("Embedding failed")
            return _fail(page, "Couldn't embed the watermark in this file. Try a different file.", 500)

        try:
            with session_scope() as session:
                row = create_record(
                    session,
                    watermark_id=wm_id,
                    original_filename=saved.filename,
                    media_kind=saved.kind,
                    original_sha256=saved.sha256,
                    model_name=model_name,
                    generator_name=generator_name,
                    creator=creator,
                    description=description,
                )
                data = row.to_dict()
        except IntegrityError:
            discard(out_path)
            return _fail(page, "That ID was just taken by another registration. Please try again.", 409)

        data["download_url"] = url_for("api.download", token=_serializer().dumps(wm_id))

        if _wants_json():
            return jsonify(
                success=True,
                watermark_id=wm_id,
                message="File registered successfully",
                download_url=data["download_url"],
            )
        return render_template("result.html", mode="register", r=data)
    finally:
        if saved:
            discard(saved.path)


@bp.post("/verify")
def verify():
    page = "verify.html"
    storage = request.files.get("file")
    if storage is None or not storage.filename:
        return _fail(page, "Choose a file to verify.")

    saved = None
    try:
        try:
            saved = save_upload(storage, current_app.config["UPLOAD_FOLDER"], current_app.config["ALLOWED_EXTENSIONS"])
        except UploadError as exc:
            return _fail(page, str(exc))

        if saved.kind not in SUPPORTED_KINDS:
            return _fail(page, f"Verification for {saved.kind} files isn't enabled yet.")

        try:
            result = verify_file(saved.path, saved.kind)
        except Exception:
            log.exception("Verification failed")
            return _fail(page, "Couldn't read this file for verification.", 500)

        record = result["record"]
        if _wants_json():
            return jsonify(
                state=result["state"],
                watermark_detected=result["watermark_id"] is not None,
                watermark_id=result["watermark_id"],
                provenance_found=record is not None,
                model=record["model_name"] if record else None,
                generator=record["generator_name"] if record else None,
            )
        return render_template(
            "result.html",
            mode="verify",
            r={**result, "filename": saved.filename, "sha256": saved.sha256},
        )
    finally:
        if saved:
            discard(saved.path)


@bp.get("/download/<token>")
def download(token):
    try:
        wm_id = _serializer().loads(token, max_age=DOWNLOAD_MAX_AGE)
    except BadSignature:
        abort(404)
    if not is_valid_id(wm_id):
        abort(404)

    folder = _watermarked_dir()
    found = next(folder.glob(f"{wm_id}.*"), None)  # wm_id is validated hex, so the glob is safe
    if found is None:
        abort(404)

    with session_scope() as session:
        row = get_record(session, wm_id)
        original = row.original_filename if row else None
    if original is None:
        abort(404)

    return send_from_directory(
        folder, found.name, as_attachment=True,
        download_name=f"{Path(original).stem}-modelledger{found.suffix}",
    )