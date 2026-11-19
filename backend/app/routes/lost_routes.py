from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.lost_report import LostReport

lost_bp = Blueprint("lost", __name__)

@lost_bp.post("/")
@login_required
def create_lost_report():
    data = request.form if request.form else (request.get_json(silent=True) or {})
    item_name = (data.get("item_name") or "").strip()
    category = (data.get("category") or "").strip()
    if not (item_name or (data.get("description") or "").strip() or request.files.get("image")) or not category:
        return jsonify({"error": "Category and at least one of item name, description or image are required."}), 400
    from app.services.integration import store_image, make_location
    try:
        image_name = store_image(request.files.get("image"))
        location_id = make_location(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    report = LostReport(
        report_code="TEMP", user_id=current_user.id, image_path=image_name, location_id=location_id,
        item_name=item_name or "Unidentified item", category=category,
        description=data.get("description"),
        colour=data.get("colour"), brand=data.get("brand"),
        model=data.get("model"),
        distinguishing_features=data.get("distinguishing_features")
    )
    db.session.add(report)
    db.session.flush()
    report.report_code = f"L{report.id:03d}"
    db.session.commit()
    from app.services.integration import match_new_report
    match_new_report(report, "lost")
    return jsonify({"message": "Lost item reported successfully",
                    "report_code": report.report_code}), 201
