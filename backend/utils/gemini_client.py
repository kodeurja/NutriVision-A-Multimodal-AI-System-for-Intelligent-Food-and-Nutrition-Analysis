import google.generativeai as genai
import os
import json
import urllib.parse
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class GeminiClient:
    def __init__(self):
        print("DEBUG: GeminiClient initialized with stable & verified models")
        # Prioritize 1.5-flash and 2.0-flash for best quota & performance
        self.model_candidates = [
            'models/gemini-1.5-flash',
            'models/gemini-2.0-flash',
            'models/gemini-flash-latest'
        ]
        self.text_only_models = [
            'models/gemini-1.5-flash',
            'models/gemini-2.0-flash'
        ]


    def detect_food_from_text(self, description):
        prompt = f"""
        You are an expert culinary and nutrition analyst. A user has described their meal: "{description}".
        
        INSTRUCTIONS:
        1. Identify all food items and beverages mentioned in the description.
        2. Provide a searchable noun and an estimated portion size (small/medium/large) for each.
        3. If no food is mentioned, return an empty list.
        
        Return ONLY a JSON object:
        {{
          "meal_name": "Specific Name of Dish",
          "items": [
            {{
              "food_name": "chicken breast",
              "portion": "medium",
              "confidence": 0.95
            }}
          ]
        }}
        
        If no food is detected, return: {{"meal_name": "No Food Detected", "items": []}}
        """
        
        last_error = None
        for model_name in self.text_only_models:
            try:
                print(f"DEBUG: Attempting text-only detection with model: {model_name}")
                import time
                time.sleep(1.0)
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                
                content = response.text.strip()
                print(f"DEBUG: Gemini raw text-only response: {content}")
                
                if content.startswith("```json"):
                    content = content[7:-3].strip()
                elif content.startswith("```"):
                    content = content[3:-3].strip()
                    
                return json.loads(content)
            except Exception as e:
                print(f"DEBUG: Model {model_name} failed: {e}")
                last_error = e
                continue
        
        raise last_error or Exception("All Gemini models failed for text detection.")

    def detect_food(self, image_path, user_description=None):
        img = Image.open(image_path)
        
        prompt = """
        You are an expert culinary and nutrition analyst. Analyze this photo with high precision.
        
        CRITICAL RULE:
        - If the image contains ONLY text (like a document, book, or receipt) and NO actual food, return an empty items list.
        - If the image contains NO food items at all (e.g., random objects, landscape, person), return an empty items list.
        - Only identify items that are clearly intended for human consumption as food or beverage.
        
        INSTRUCTIONS:
        1. Break down every dish into its core components (e.g., don't just say 'curry', identify 'chicken', 'gravy', 'potatoes').
        2. Pay extremely close attention to visual cues:
           - Grains: Identify specifically if it is Basmati rice, Brown rice, Quinoa, or a Roti/Naan type.
           - Textures: Look for specific dal types (e.g., yellow lentil vs black lentil), vegetable cuts, and protein types.
           - Garnishes: Even small amounts of oil, butter, or seeds should be considered.
        3. For each detected item, provide a searchable noun, portion size (small/medium/large), and confidence.
        
        Return ONLY a JSON object:
        {
          "meal_name": "Specific Name of Dish",
          "items": [
            {
              "food_name": "basmati rice",
              "portion": "medium",
              "confidence": 0.98
            }
          ]
        }
        
        If no food is detected, return: {"meal_name": "No Food Detected", "items": []}
        """
        
        if user_description:
            prompt += f"\n\nContext provided by the user: '{user_description}'. \nUse this context ONLY to help identify the items in the image. Do NOT use the user's text as the 'food_name' unless it is a simple food item name."

        last_error = None
        for model_name in self.model_candidates:
            try:
                # Add a small buffer between attempts
                import time
                time.sleep(1.2)
                
                print(f"DEBUG: Attempting detection with model: {model_name}")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content([prompt, img])
                
                content = response.text.strip()
                print(f"DEBUG: Gemini raw response from {model_name}: {content}")
                
                if content.startswith("```json"):
                    content = content[7:-3].strip()
                elif content.startswith("```"):
                    content = content[3:-3].strip()
                    
                return json.loads(content)
            except Exception as e:
                print(f"DEBUG: Model {model_name} failed: {e}")
                last_error = e
                import time
                time.sleep(2.0)
                continue
        
        raise last_error or Exception("All Gemini models failed to respond.")

    def get_suggestions(self, items_list):
        # Robust string construction for the prompt
        try:
            items_str = ", ".join([f"{i.get('portion', 'some')} {i.get('food_name', 'food')}" if isinstance(i, dict) else str(i) for i in items_list])
        except:
            items_str = "this meal"
            
        prompt = f"""
        Given the following meal items: {items_str}.
        Provide exactly 3 healthier alternatives or smart suggestions for this meal.
        
        Return ONLY a JSON array of objects:
        [
          {{
            "title": "Moong Dal Cheela",
            "description": "A high-protein, low-GI alternative to rice dosa made from soaked yellow lentils. Rich in fiber and essential minerals.",
            "visual_prompt": "professional food photography of a Moong Dal Cheela, thin golden-brown lentil crepe, served on a stone plate with green chutney, natural lighting, high detail"
          }},
          ...
        ]
        
        CRITICAL INSTRUCTION FOR 'visual_prompt':
        - The 'visual_prompt' MUST be a highly detailed, 1:1 professional photography prompt that EXACTLY describes the dish from the 'title' and 'description'.
        - Start the prompt with "High-end food photography of...".
        - Include specific ingredients mentioned in the 'description' (e.g., if you suggest 'topped with walnuts', the visual_prompt MUST include 'topped with walnuts').
        - Detail the environment: plating style (e.g., rustic wooden board, minimalist white ceramic), lighting (e.g., soft natural side light), and background (e.g., blurred kitchen background).
        - Ensure NO TEXT, NO GRAPHICS, and NO PEOPLE are in the prompt.
        - The prompt must be so accurate that the generated image could be used in a professional menu for that specific suggestion.
        """
        
        suggestions = []
        for model_name in self.model_candidates:
            try:
                import time
                time.sleep(3.0) # Larger buffer before suggestions to reset quota window
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                content = response.text.strip()
                
                if content.startswith("```json"):
                    content = content[7:-3].strip()
                elif content.startswith("```"):
                    content = content[3:-3].strip()
                
                raw_suggestions = json.loads(content)
                if not isinstance(raw_suggestions, list):
                    continue
                
                # Sanitize and ensure 3 suggestions
                for s in raw_suggestions:
                    if isinstance(s, dict) and "title" in s and "description" in s:
                        # Add persistence logic
                        vis_prompt = s.get('visual_prompt', f"professional food photography of {s['title']}, gourmet plating, high resolution")
                        image_url = self._get_persistent_image(vis_prompt, len(suggestions) + 1)
                        suggestions.append({
                            "title": s["title"],
                            "description": s["description"],
                            "image_url": image_url
                        })
                    if len(suggestions) >= 3:
                        break
                
                if len(suggestions) >= 3:
                    return suggestions[:3]
            except Exception as e:
                print(f"DEBUG: Model {model_name} failed in suggestions: {e}")
                continue
                
        # Fallback if AI fails or returns < 3
        fallbacks = [
            {"title": "Fresh Garden Salad", "description": "High fiber and low calories with seasonal greens."},
            {"title": "Sprouted Moong Bowl", "description": "High protein and iron-rich snack."},
            {"title": "Greek Yogurt with Berries", "description": "High protein and probiotic-rich snack."}
        ]
        
        final_suggestions = []
        for i, fb in enumerate(fallbacks):
            if i < len(suggestions):
                final_suggestions.append(suggestions[i])
            else:
                prompt = f"High-end food photography of {fb['title']}, {fb['description']}, gourmet plating, soft natural lighting, photorealistic, 8k"
                fb["image_url"] = self._get_persistent_image(prompt, i + 1)
                final_suggestions.append(fb)
        
        return final_suggestions[:3]

    def _get_persistent_image(self, prompt, index):
        """Generates an image via Pollinations and saves it locally for persistence with robust retries."""
        import requests
        import time
        import random
        
        # Add high-quality photography enhancers
        quality_prompt = f"{prompt}, professional food photography, minimalist plating, highly detailed, photorealistic, cinematic lighting, 8k, sharp focus"
        encoded_prompt = urllib.parse.quote(quality_prompt)
        negative_prompt = "cartoon, anime, illustration, watermark, blurry, text"
        encoded_negative = urllib.parse.quote(negative_prompt)
        
        filename = f"suggestion_{index}.png"
        filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/static/generated", filename))
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        for attempt in range(3):
            try:
                # Add spacing to avoid rate limits on 2nd and 3rd sequential requests
                if index > 1:
                    time.sleep(1.2 * index) # Staggered sleep

                # Using unique seeds per attempt to bypass cache/limit issues
                seed = int(time.time()) + random.randint(100, 999) + index
                pollinations_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=400&height=300&nologo=true&negative={encoded_negative}&seed={seed}"
                
                response = requests.get(pollinations_url, timeout=15)
                if response.status_code == 200:
                    # Basic check if the image is valid and not an error placeholder (error images are usually very small)
                    if len(response.content) > 10000:
                        with open(filepath, "wb") as f:
                            f.write(response.content)
                        return f"/static/generated/{filename}?v={int(time.time())}"
                    else:
                        print(f"DEBUG: Attempt {attempt+1} returned small/invalid image for {prompt}")
            except Exception as e:
                print(f"DEBUG: Attempt {attempt+1} failed for image generation: {e}")
            
            # Wait before retry
            time.sleep(1.0)
            
        # Final fallback to direct URL if all retries fail
        return pollinations_url
