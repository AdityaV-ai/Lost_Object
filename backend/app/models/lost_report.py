from datetime import datetime, timezone
from app import db

class LostReport(db.Model):
    __tablename__ = "lost_reports"
    id = db.Column(db.Integer, primary_key=True)
    report_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    item_name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    image_path = db.Column(db.String(500))
    colour = db.Column(db.String(80))
    brand = db.Column(db.String(120))
    model = db.Column(db.String(120))
    distinguishing_features = db.Column(db.Text)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"))
    status = db.Column(db.String(30), nullable=False, default="ACTIVE")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    user = db.relationship("User", backref="lost_reports")
    location = db.relationship("Location")
