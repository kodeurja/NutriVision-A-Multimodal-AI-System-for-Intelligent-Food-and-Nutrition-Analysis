# AI Nutrition Scanner 🍱

AI Nutrition Scanner is a multimodal web application that converts meal photos into estimated nutrition reports. It uses Gemini 1.5 Flash for food detection, Gemini 1.5 Pro for smart suggestions, and the Nutritionix API for verified nutrient data.

## Features
- **Meal Recognition**: Detect multiple food items from a single photo.
- **Portion Estimation**: Automatically estimates portion sizes (Small/Medium/Large).
- **Interactive Editor**: Edit detected items and adjust portions to recalculate nutrition instantly.
- **Smart Suggestions**: Healthier alternatives suggested by Gemini Pro.
- **Daily Summary**: Track your nutrients throughout the day on a sleek dashboard.
- **Premium UI**: Modern glassmorphism design with a dark theme.

## Tech Stack
- **Backend**: Flask (Python)
- **AI Models**: Google Gemini 1.5 Flash & Pro
- **Nutrition Database**: Nutritionix API
- **Storage**: SQLite (SQLAlchemy)
- **Frontend**: Vanilla JavaScript + CSS (Glassmorphism)

## Setup Instructions

### 1. Prerequisite API Keys
You will need:
- **Google Gemini API Key**: Get it from [Google AI Studio](https://aistudio.google.com/).
- **Nutritionix API Credentials**: Sign up at [Nutritionix API](https://www.nutritionix.com/business/api) to get an `App ID` and `API Key`.

### 2. Installation
1. Clone or download this repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the root directory and add your keys (see `.env.template`):
   ```env
   GEMINI_API_KEY=your_key
   NUTRITIONIX_APP_ID=your_id
   NUTRITIONIX_API_KEY=your_key
   FLASK_SECRET_KEY=something_random
   DATABASE_URL=sqlite:///nutrition_scanner.db
   ```

### 3. Running the App
```bash
python app.py
```
The app will be available at `http://127.0.0.1:5000`.

## Important Note
Food photo recognition is an estimation. Calories may vary based on ingredients and cooking methods. Always use the "Recalculate" feature if detection is not exact.

## Project Structure
- `app.py`: Main Flask application.
- `models.py`: Database schema.
- `utils/`: Utility clients for Gemini and Nutritionix.
- `static/js/app.js`: Frontend logic.
- `static/css/styles.css`: UI Styling.
- `templates/index.html`: Main SPA layout.
- `uploads/`: Directory for uploaded meal photos.
