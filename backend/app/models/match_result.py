from datetime import datetime, timezone
from app import db

class MatchResult(db.Model):
    __tablename__ = "match_results"
    id = db.Column(db.Integer, primary_key=True)
    lost_report_id = db.Column(db.Integer, db.ForeignKey("lost_reports.id"), nullable=False)
    found_report_id = db.Column(db.Integer, db.ForeignKey("found_reports.id"), nullable=False)
    image_similarity = db.Column(db.Float)
    text_similarity = db.Column(db.Float)
    location_similarity = db.Column(db.Float)
    fusion_score = db.Column(db.Float)
    rank = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    lost_report = db.relationship("LostReport")
    found_report = db.relationship("FoundReport")
    __table_args__ = (db.UniqueConstraint("lost_report_id", "found_report_id", name="uq_lost_found_pair"),)
