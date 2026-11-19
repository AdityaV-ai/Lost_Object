from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from sqlalchemy import or_
from app import db
from app.models.user import User

auth_bp = Blueprint("auth", __name__)

@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not name or not email or len(password) < 8:
        return jsonify({"error": "Name, email and a password of at least 8 characters are required."}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email is already registered."}), 409
    user = User(name=name, email=email, role="user")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return jsonify({"message": "Registration successful", "user": {
        "id": user.id, "name": user.name, "email": user.email, "role": user.role
    }}), 201

@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password."}), 401
    login_user(user)
    return jsonify({"message": "Login successful", "user": {
        "id": user.id, "name": user.name, "email": user.email, "role": user.role
    }})

@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logged out successfully"})

@auth_bp.get("/me")
@login_required
def me():
    return jsonify({"id": current_user.id, "name": current_user.name,
                    "email": current_user.email, "role": current_user.role})
