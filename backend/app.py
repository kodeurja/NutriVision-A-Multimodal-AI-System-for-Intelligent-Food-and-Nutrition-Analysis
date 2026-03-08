import os
import io
import json
import traceback
from datetime import datetime, timezone
from fpdf import FPDF
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, Meal, User
from utils.gemini_client import GeminiClient
from utils.edamam_client import EdamamUSDAClient

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__, 
            template_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend/templates')),
            static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend/static')))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///nutrition_scanner.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("FLASK_SECRET_KEY", "dev-secret")
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

gemini = GeminiClient()
nutrition_service = EdamamUSDAClient()

# Ensure upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

with app.app_context():
    db.create_all()

# --- PDF Generation Utils ---
class PDFReport(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 20)
        self.set_text_color(40, 48, 68)
        self.cell(0, 10, 'AI Nutrition Scanner Report', ln=True, align='C')
        self.ln(10)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M")} | Page {self.page_no()}', 0, 0, 'C')

def clean_pdf_text(text):
    if not text: return ""
    # Map common unicode to latin1/ascii equivalents
    replacements = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2026": "..."
    }
    for u_char, r_char in replacements.items():
        text = text.replace(u_char, r_char)
    # Final safety: ASCII only for the internal Helvetica font
    return text.encode('ascii', 'ignore').decode('ascii')

@app.route('/test_pdf')
def test_pdf():
    """Public route to test PDF generation and delivery."""
    try:
        pdf = PDFReport()
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 16)
        pdf.cell(0, 10, "PDF Delivery Test", ln=True, align='C')
        pdf.set_font('Helvetica', '', 12)
        pdf.ln(10)
        pdf.multi_cell(0, 10, "This is a test PDF to verify that your browser can receive and save files from this server.")
        
        pdf_bytes = pdf.output()
        buffer = io.BytesIO(pdf_bytes)
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name="test_delivery.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        return f"Test Failed: {str(e)}", 500

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        print(f"DEBUG: Login attempt for {email}")
        
        if not email or not password:
            flash('Email and password are required.')
            return render_template('login.html')

        user = User.query.filter_by(email=email).first()
        
        if user:
            print(f"DEBUG: User found in DB: {user.email}")
            try:
                if check_password_hash(user.password_hash, password):
                    print(f"DEBUG: Password match! Logging in user.")
                    success = login_user(user)
                    print(f"DEBUG: login_user success: {success}")
                    return redirect(url_for('index'))
                else:
                    print(f"DEBUG: Password mismatch.")
            except Exception as e:
                print(f"ERROR: An unexpected error occurred during login for user {email}: {e}")
                traceback.print_exc()
                flash('An unexpected error occurred during login. Please try again.')
                return render_template('login.html')
        else:
            print(f"DEBUG: User not found in database.")
        
        flash('Invalid email or password.')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        print(f"DEBUG: Signup attempt for {email}")

        if not email or not password:
            flash('Email and password are required.')
            return render_template('signup.html')
        
        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            print(f"DEBUG: Signup failed - email already exists.")
            flash('Email already exists.')
            return redirect(url_for('signup'))
        
        try:
            new_user = User(
                email=email,
                password_hash=generate_password_hash(password)
            )
            db.session.add(new_user)
            db.session.commit()
            print(f"DEBUG: User created successfully: {new_user.email}")
            
            login_user(new_user)
            print(f"DEBUG: User logged in after signup, redirecting to index")
            return redirect(url_for('index'))
        except Exception as e:
            print(f"DEBUG: Error during signup: {e}")
            db.session.rollback()
            flash('An error occurred during signup.')
            
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/analyze_meal', methods=['POST'])
@login_required
def analyze_meal():
    image_file = request.files.get('image')
    description = request.form.get('description', '').strip()
    
    if not image_file and not description:
        return jsonify({"error": "Please upload an image or enter a description."}), 400
    
    filepath = None
    if image_file and image_file.filename != '':
        filename = secure_filename(f"{datetime.now().timestamp()}_{image_file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(filepath)
    
    # 1. Detect food items using Gemini Flash
    try:
        if filepath:
            detection_result = gemini.detect_food(filepath, description)
        else:
            detection_result = gemini.detect_food_from_text(description)
            
        items = detection_result.get("items", [])
        meal_name = detection_result.get("meal_name", "Unknown Meal")
        print(f"DEBUG: Detected items: {items}")
        
        if not items:
            return jsonify({"error": "No food items detected. Please provide a clearer image or description."}), 400
            
    except Exception as e:
        print(f"ERROR in Gemini Detection: {e}")
        return jsonify({"error": f"Food detection failed: {str(e)}"}), 500
    
    # 2. Fetch nutrition data using Edamam
    try:
        nutrition_data = nutrition_service.calculate_total_nutrition(items)
        print(f"DEBUG: Nutrition data: {nutrition_data}")
    except Exception as e:
        print(f"ERROR in Nutrition Service: {e}")
        return jsonify({"error": f"Nutrition calculation failed: {str(e)}"}), 500
    
    # 3. Get smart suggestions using Gemini Pro
    try:
        suggestions = gemini.get_suggestions(items)
    except Exception as e:
        print(f"ERROR in Gemini Suggestions: {e}")
        suggestions = "No suggestions available at this time."
    
    # 4. Save to DB
    try:
        new_meal = Meal(
            user_id=current_user.id,
            image_path=filepath, # Can be None for text-only
            meal_name=meal_name,
            items_json=json.dumps(nutrition_data["items"]),
            totals_json=json.dumps(nutrition_data["totals"]),
            suggestions=json.dumps(suggestions)
        )
        db.session.add(new_meal)
        db.session.commit()
    except Exception as e:
        print(f"ERROR saving to DB: {e}")
        return jsonify({"error": "Database error saving meal"}), 500
    
    return jsonify({
        "meal_id": new_meal.id,
        "image_url": f"/uploads/{os.path.basename(filepath)}" if filepath else None,
        "items": nutrition_data["items"],
        "totals": nutrition_data["totals"],
        "suggestions": suggestions
    })

@app.route('/recalculate_nutrition', methods=['POST'])
@login_required
def recalculate_nutrition():
    data = request.json
    meal_id = data.get("meal_id")
    updated_items = data.get("items")
    
    if not updated_items:
        return jsonify({"error": "No items provided"}), 400
    
    # Re-calculate using Edamam
    nutrition_data = nutrition_service.calculate_total_nutrition(updated_items)
    
    # Update DB if meal_id exists
    if meal_id:
        meal = Meal.query.filter_by(id=meal_id, user_id=current_user.id).first()
        if meal:
            meal.items_json = json.dumps(nutrition_data["items"])
            meal.totals_json = json.dumps(nutrition_data["totals"])
            db.session.commit()
            
    return jsonify({
        "items": nutrition_data["items"],
        "totals": nutrition_data["totals"]
    })

@app.route('/daily_summary', methods=['GET'])
@login_required
def daily_summary():
    today = datetime.now(timezone.utc).date()
    # Get all meals for history table, latest first
    all_meals = Meal.query.filter_by(user_id=current_user.id).order_by(Meal.date_time.desc()).all()
    # Filter today's meals for the dashboard totals
    today_meals = [m for m in all_meals if m.date_time.date() == today]
    
    total_calories = 0
    total_carbs = 0
    total_protein = 0
    total_fat = 0
    
    # Calculate totals for today specifically
    for meal in today_meals:
        m_dict = meal.to_dict()
        total_calories += m_dict["totals"]["calories"]
        total_carbs += m_dict["totals"]["carbs"]
        total_protein += m_dict["totals"]["protein"]
        total_fat += m_dict["totals"]["fat"]
        
    meal_list = [meal.to_dict() for meal in all_meals]
        
    return jsonify({
        "meals": meal_list,
        "daily_totals": {
            "calories": round(total_calories),
            "carbs": round(total_carbs, 1),
            "protein": round(total_protein, 1),
            "fat": round(total_fat, 1)
        }
    })

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    # Basic security check: ensure user owns the meal with this image
    meal = Meal.query.filter_by(image_path=os.path.join(app.config['UPLOAD_FOLDER'], filename), user_id=current_user.id).first()
    if not meal:
        return jsonify({"error": "Unauthorized"}), 403
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/download_report/<int:meal_id>')
@login_required
def download_report(meal_id):
    print(f"DEBUG: PDF Download requested for meal_id: {meal_id} by user: {current_user.id}")
    meal = Meal.query.filter_by(id=meal_id, user_id=current_user.id).first()
    if not meal:
        print(f"DEBUG: Download failed - Meal {meal_id} not found for user {current_user.id}")
        return "Meal not found", 404
        
    m_dict = meal.to_dict()
    items_list = m_dict.get('items', [])
    totals = m_dict.get('totals', {})
    
    try:
        pdf = PDFReport()
        pdf.add_page()
        
        # Meal Info
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 10, clean_pdf_text(f"Meal: {m_dict.get('meal_name', 'Unknown')}"), ln=True)
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 8, clean_pdf_text(f"Date: {m_dict.get('date_time', 'Unknown')}"), ln=True)
        pdf.ln(5)
        
        # Table Header
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(60, 10, "Item Name", 1, 0, 'C', 1)
        pdf.cell(30, 10, "Portion", 1, 0, 'C', 1)
        pdf.cell(25, 10, "Calories", 1, 0, 'C', 1)
        pdf.cell(25, 10, "Protein (g)", 1, 0, 'C', 1)
        pdf.cell(25, 10, "Carbs (g)", 1, 0, 'C', 1)
        pdf.cell(25, 10, "Fat (g)", 1, 1, 'C', 1)
        
        # Table Body
        pdf.set_font('Helvetica', '', 9)
        for item in items_list:
            pdf.cell(60, 8, clean_pdf_text(item.get('food_name', 'Item')[:30]), 1)
            pdf.cell(30, 8, item.get('portion', 'medium'), 1, 0, 'C')
            pdf.cell(25, 8, str(item.get('calories', 0)), 1, 0, 'C')
            pdf.cell(25, 8, str(item.get('protein', 0)), 1, 0, 'C')
            pdf.cell(25, 8, str(item.get('carbs', 0)), 1, 0, 'C')
            pdf.cell(25, 8, str(item.get('fat', 0)), 1, 1, 'C')
            
        pdf.ln(10)
        
        # Totals Section
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_fill_color(230, 245, 230)
        pdf.cell(0, 10, "Nutritional Summary", ln=True, fill=True)
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 8, clean_pdf_text(f"Total Calories: {totals.get('calories', 0)} kcal ({totals.get('calorie_range', 'N/A')})"), ln=True)
        pdf.cell(0, 8, clean_pdf_text(f"Total Protein: {totals.get('protein', 0)}g"), ln=True)
        pdf.cell(0, 8, clean_pdf_text(f"Total Carbohydrates: {totals.get('carbs', 0)}g"), ln=True)
        pdf.cell(0, 8, clean_pdf_text(f"Total Fats: {totals.get('fat', 0)}g"), ln=True)
        
        pdf.ln(10)
        
        # Suggestions
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_fill_color(245, 230, 230)
        pdf.cell(0, 10, "Smart AI Suggestions", ln=True, fill=True)
        pdf.set_font('Helvetica', 'I', 10)
        
        suggestions_raw = m_dict.get('suggestions', [])
        suggestions_text = ""
        if isinstance(suggestions_raw, list):
            for i, s in enumerate(suggestions_raw):
                if isinstance(s, dict):
                    title = s.get('title', 'Suggestion')
                    desc = s.get('description', '')
                    suggestions_text += f"{i+1}. {title}: {desc}\n\n"
                else:
                    suggestions_text += f"{i+1}. {str(s)}\n\n"
        else:
            suggestions_text = str(suggestions_raw)
            
        pdf.multi_cell(0, 8, clean_pdf_text(suggestions_text or 'No suggestions available.'))
        
        # Generate PDF bytes
        pdf_bytes = pdf.output()
        print(f"DEBUG: PDF generated, size: {len(pdf_bytes)} bytes")
        
        # Create a bytes buffer
        buffer = io.BytesIO(pdf_bytes)
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"meal_report_{meal_id}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"FATAL ERROR in PDF generation: {e}")
        import traceback
        traceback.print_exc()
        return f"Error generating PDF: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
