from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app import db
from app.models.lost_report import LostReport
from app.models.found_report import FoundReport
from app.models.match_result import MatchResult
from app.models.notification import Notification
from app.models.recovery_request import RecoveryRequest
portal_bp = Blueprint("portal", __name__)

def report_data(r):
    return {"id":r.id,"report_code":r.report_code,"item_name":r.item_name,"category":r.category,"description":r.description,"status":r.status,"created_at":r.created_at.isoformat()}

def visible_match(m):
    return m.lost_report.user_id == current_user.id or current_user.role == "staff"

def match_data(m):
    return {"id":m.id,"lost_report":report_data(m.lost_report),"found_item_name":m.found_report.item_name,"found_category":m.found_report.category,"fusion_score":m.fusion_score,"image_similarity":m.image_similarity,"text_similarity":m.text_similarity,"location_similarity":m.location_similarity}

@portal_bp.get("/reports/mine")
@login_required
def mine():
    return jsonify({"lost":[report_data(x) for x in LostReport.query.filter_by(user_id=current_user.id).all()],"found":[report_data(x) for x in FoundReport.query.filter_by(user_id=current_user.id).all()]})

@portal_bp.get("/matches")
@login_required
def matches():
    return jsonify([match_data(m) for m in MatchResult.query.join(LostReport).filter(LostReport.user_id==current_user.id).order_by(MatchResult.fusion_score.desc()).all()])

@portal_bp.get("/matches/<int:match_id>")
@login_required
def match_detail(match_id):
    m=db.get_or_404(MatchResult,match_id)
    if not visible_match(m):return jsonify({"error":"Forbidden"}),403
    return jsonify(match_data(m))

@portal_bp.get("/notifications")
@login_required
def notifications():
    return jsonify([{"id":n.id,"title":n.title,"message":n.message,"is_read":n.is_read} for n in Notification.query.filter_by(user_id=current_user.id).all()])

@portal_bp.post("/notifications/<int:notification_id>/read")
@login_required
def mark_read(notification_id):
    n=db.get_or_404(Notification,notification_id)
    if n.user_id!=current_user.id:return jsonify({"error":"Forbidden"}),403
    n.is_read=True;db.session.commit();return jsonify({"ok":True})

@portal_bp.post("/matches/<int:match_id>/interest")
@login_required
def interest(match_id):
    m=db.get_or_404(MatchResult,match_id)
    if m.lost_report.user_id!=current_user.id:return jsonify({"error":"Forbidden"}),403
    existing=RecoveryRequest.query.filter_by(match_id=m.id,requester_id=current_user.id).first()
    if existing:return jsonify({"id":existing.id,"status":existing.status})
    r=RecoveryRequest(match_id=m.id,requester_id=current_user.id);db.session.add(r);db.session.commit()
    return jsonify({"id":r.id,"status":r.status}),201

@portal_bp.get("/recovery-requests")
@login_required
def recovery_requests():
    return jsonify([{"id":r.id,"match_id":r.match_id,"status":r.status} for r in RecoveryRequest.query.filter_by(requester_id=current_user.id).all()])

@portal_bp.post("/staff/found/<int:report_id>/confirm-deposit")
@login_required
def confirm_deposit(report_id):
    if current_user.role!="staff":return jsonify({"error":"Staff only"}),403
    r=db.get_or_404(FoundReport,report_id)
    if r.custody_status!="AWAITING_DEPOSIT_CONFIRMATION":return jsonify({"error":"Not awaiting deposit"}),409
    r.custody_status="DEPOSIT_CONFIRMED";db.session.commit();return jsonify({"ok":True})
