import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models.found_report import FoundReport

found_bp = Blueprint("found", __name__)
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@found_bp.post("/")
@login_required
def create_found_report():
    if "image" not in request.files:
        return jsonify({"error": "Item image is required."}), 400
    image = request.files["image"]
    if not image.filename:
        return jsonify({"error": "Please select an image."}), 400
    if not allowed_file(image.filename):
        return jsonify({"error": "Only JPG, JPEG and PNG images are allowed."}), 400
    item_name = (request.form.get("item_name") or "").strip()
    category = (request.form.get("category") or "").strip()
    if not item_name or not category:
        return jsonify({"error": "Item name and category are required."}), 400
    custody_status = request.form.get("custody_status", "LEFT_WHERE_FOUND")
    allowed_custody = {"LEFT_WHERE_FOUND", "TEMPORARILY_HOLDING", "AWAITING_DEPOSIT_CONFIRMATION"}
    if custody_status not in allowed_custody:
        return jsonify({"error": "Invalid custody status."}), 400
    from app.services.integration import store_image, make_location
    try:
        unique_filename = store_image(image)
        location_id = make_location(request.form)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    report = FoundReport(
        report_code="TEMP", user_id=current_user.id,
        item_name=item_name, category=category,
        description=request.form.get("description"),
        image_path=unique_filename, location_id=location_id, custody_status=custody_status
    )
    try:
        db.session.add(report)
        db.session.flush()
        report.report_code = f"F{report.id:03d}"
        db.session.commit()
        from app.services.integration import match_new_report
        match_new_report(report, "found")
        return jsonify({"message": "Found item reported successfully",
                        "report_code": report.report_code,
                        "custody_status": report.custody_status}), 201
    except Exception:
        db.session.rollback()

        current_app.logger.exception("Could not save found report")
        return jsonify({"error": "Could not save found report."}), 500
