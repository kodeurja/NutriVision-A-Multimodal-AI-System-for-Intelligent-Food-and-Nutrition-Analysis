from app import app, db
from models import User, Meal
import requests
import json

def debug_it():
    with app.app_context():
        # Get the latest meal
        meal = Meal.query.order_by(Meal.id.desc()).first()
        if not meal:
            print("No meals found in DB.")
            return
        
        print(f"Testing download for meal_id: {meal.id}")
        
        # We can't easily use the routing here because of Flask-Login
        # But we can call the function directly if we mock current_user
        from flask_login import login_user
        from flask import url_for
        
        # Mocking current_user is hard without a request context
        # Let's just test the PDF generation logic directly
        m_dict = meal.to_dict()
        items_list = m_dict.get('items', [])
        totals = m_dict.get('totals', {})
        
        from fpdf import FPDF
        from datetime import datetime
        
        class PDFReport(FPDF):
            def header(self):
                self.set_font('Helvetica', 'B', 20)
                self.cell(0, 10, 'AI Nutrition Scanner Report', ln=True, align='C')
            def footer(self):
                pass

        def clean_text(text):
            if not text: return ""
            replacements = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'}
            for u_char, r_char in replacements.items():
                text = text.replace(u_char, r_char)
            return text.encode('latin-1', 'replace').decode('latin-1')

        pdf = PDFReport()
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 10, clean_text(f"Meal: {m_dict.get('meal_name', 'Unknown')}"), ln=True)
        
        try:
            out = pdf.output()
            print(f"Success! Generated {len(out)} bytes.")
            # Save it locally for inspection
            with open("debug_report.pdf", "wb") as f:
                f.write(out)
            print("Saved as debug_report.pdf")
        except Exception as e:
            print(f"Generation failed: {e}")

if __name__ == "__main__":
    debug_it()
