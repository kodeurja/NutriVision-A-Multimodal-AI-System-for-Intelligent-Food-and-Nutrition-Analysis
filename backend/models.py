from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone
import json

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    meals = db.relationship('Meal', backref='user', lazy=True)

class Meal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    meal_name = db.Column(db.String(100), nullable=True)
    image_path = db.Column(db.String(255), nullable=True)
    items_json = db.Column(db.Text, nullable=False)  # JSON string of detected items
    totals_json = db.Column(db.Text, nullable=False) # JSON string of total nutrients
    suggestions = db.Column(db.Text, nullable=True)   # Smart suggestions text

    def to_dict(self):
        try:
            items = json.loads(self.items_json) if self.items_json else []
        except:
            items = []
            
        try:
            totals = json.loads(self.totals_json) if self.totals_json else {"calories": 0, "carbs": 0, "protein": 0, "fat": 0}
        except:
            totals = {"calories": 0, "carbs": 0, "protein": 0, "fat": 0}

        if not self.meal_name and items:
            name = ", ".join([i.get("food_name", "Unknown").capitalize() for i in items[:3]])
            if len(items) > 3: name += "..."
        else:
            name = self.meal_name or "Unknown Meal"

        try:
            suggestions = json.loads(self.suggestions) if self.suggestions else []
        except:
            suggestions = self.suggestions or ""

        return {
            "id": self.id,
            "date_time": self.date_time.isoformat() + "Z",
            "meal_name": name,
            "image_path": self.image_path,
            "items": items,
            "totals": totals,
            "suggestions": suggestions
        }
