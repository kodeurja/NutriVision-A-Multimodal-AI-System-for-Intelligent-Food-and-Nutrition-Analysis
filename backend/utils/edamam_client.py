import requests
import os
from dotenv import load_dotenv

load_dotenv()

class EdamamUSDAClient:
    def __init__(self):
        # Primary: Edamam keys
        self.edamam_app_id = os.getenv("EDAMAM_APP_ID")
        self.edamam_app_key = os.getenv("EDAMAM_APP_KEY")
        
        # Fallback to old Nutritionix names if they exist (common for users with old .env)
        if not self.edamam_app_id:
            self.edamam_app_id = os.getenv("NUTRITIONIX_APP_ID")
        if not self.edamam_app_key:
            self.edamam_app_key = os.getenv("NUTRITIONIX_API_KEY")

        self.usda_api_key = os.getenv("USDA_API_KEY")
        
        if not self.edamam_app_id or not self.edamam_app_key:
            print("WARNING: Edamam/Nutritionix API credentials missing in .env! Nutrition data will be zero.")
            print("Please ensure EDAMAM_APP_ID and EDAMAM_APP_KEY are set in your .env file.")
        
        if not self.usda_api_key:
            print("WARNING: USDA API key missing in .env! Fallback will not work.")

        # Edamam Nutrition Analysis API
        self.edamam_url = "https://api.edamam.com/api/nutrition-data"
        # USDA Search API
        self.usda_url = "https://api.nal.usda.gov/fdc/v1/foods/search"
        
    def get_edamam_data(self, food_query):
        """Fetches nutrition data from Edamam."""
        params = {
            "app_id": self.edamam_app_id,
            "app_key": self.edamam_app_key,
            "ingr": food_query
        }
        try:
            response = requests.get(self.edamam_url, params=params, timeout=10)
            print(f"DEBUG: Edamam status: {response.status_code} for {food_query}")
            
            if response.status_code == 429:
                return "RATE_LIMIT"
                
            response.raise_for_status()
            data = response.json()
            
            # Edamam returns calories: 0 if it doesn't recognize the food
            if data.get("calories", 0) > 0:
                print(f"DEBUG: Edamam matched {food_query} with {data['calories']} cals")
                return {
                    "calories": data.get("calories", 0),
                    "carbs": data.get("totalNutrients", {}).get("CHOCDF", {}).get("quantity", 0),
                    "protein": data.get("totalNutrients", {}).get("PROCNT", {}).get("quantity", 0),
                    "fat": data.get("totalNutrients", {}).get("FAT", {}).get("quantity", 0)
                }
            else:
                print(f"DEBUG: Edamam returned 0 calories for {food_query}")
        except Exception as e:
            print(f"DEBUG: Edamam error for {food_query}: {e}")
        return None

    def get_usda_data(self, food_name):
        """Fetches nutrition data from USDA FoodData Central."""
        params = {
            "api_key": self.usda_api_key,
            "query": food_name,
            "pageSize": 1
        }
        
        # Internal normalization for common misses
        search_query = food_name
        if search_query.lower() == "sambhar":
            search_query = "Sambar"
        
        params["query"] = search_query
        try:
            response = requests.get(self.usda_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            # print(f"DEBUG: USDA raw response: {data}") # Too large usually
            
            if data.get("foods") and len(data["foods"]) > 0:
                food = data["foods"][0]
                print(f"DEBUG: USDA matched {food_name} with '{food.get('description')}' from {food.get('dataType')}")
                nutrients = food.get("foodNutrients", [])
                
                # USDA returns nutrients per 100g/unit
                result = {"calories": 0, "carbs": 0, "protein": 0, "fat": 0}
                for n in nutrients:
                    # USDA field names differ by data type
                    name = n.get("nutrientName", "").lower()
                    val = n.get("value", 0)
                    if not name: continue
                    if "energy" in name: result["calories"] = val
                    elif "protein" in name: result["protein"] = val
                    elif "carbohydrate" in name: result["carbs"] = val
                    elif "total lipid" in name: result["fat"] = val
                
                return result
        except Exception as e:
            print(f"DEBUG: USDA error for {food_name}: {e}")
        return None

    def calculate_total_nutrition(self, items):
        total_calories = 0
        total_carbs = 0
        total_protein = 0
        total_fat = 0
        
        results = []
        
        portion_multipliers = {
            "small": 0.5,
            "medium": 1.0,
            "large": 1.5
        }
        
        for item in items:
            food_name = item.get("food_name")
            portion = item.get("portion", "medium")
            multiplier = portion_multipliers.get(portion, 1.0)
            
            print(f"DEBUG: Analyzing {portion} {food_name}...")
            
            # Helper to try Edamam with error code handling
            def try_edamam(query):
                res = self.get_edamam_data(query)
                return res

            # Attempt 1: Natural portion or cup
            nutrients = try_edamam(f"1 {portion} {food_name}")
            
            # Use a flag to track if we should keep trying Edamam
            is_rate_limited = (nutrients == "RATE_LIMIT")
            if is_rate_limited: nutrients = None

            if not nutrients and not is_rate_limited:
                nutrients = try_edamam(f"1 cup {food_name}")
                if nutrients == "RATE_LIMIT":
                    nutrients = None
                    is_rate_limited = True
            
            # Attempt 2: Simple name or 100g
            if not nutrients and not is_rate_limited:
                nutrients = try_edamam(food_name)
                if nutrients == "RATE_LIMIT":
                    nutrients = None
                    is_rate_limited = True

            if not nutrients and not is_rate_limited:
                nutrients = try_edamam(f"100g {food_name}")
                if nutrients == "RATE_LIMIT":
                    nutrients = None
                    is_rate_limited = True
            
            # Attempt 3: USDA as fallback (Always try if we don't have nutrients yet)
            if not nutrients:
                if is_rate_limited:
                    print(f"DEBUG: Edamam rate limit reached. Switching to USDA immediately for {food_name}")
                else:
                    print(f"DEBUG: Edamam attempts failed. Trying USDA for {food_name}")
                
                raw_nutrients = self.get_usda_data(food_name)
                if raw_nutrients:
                    # USDA is per 100g, assume a "medium" portion is ~250g/ml
                    unit_multiplier = 2.5 * multiplier 
                    nutrients = {k: v * unit_multiplier for k, v in raw_nutrients.items()}
            
            # Final desperate attempt: last word only
            if not nutrients and " " in food_name:
                short_name = food_name.split()[-1]
                print(f"DEBUG: All primary failed, trying final fallback with core name: {short_name}")
                # Don't try Edamam if already rate limited
                if not is_rate_limited:
                    nutrients = try_edamam(f"100g {short_name}")
                    if nutrients == "RATE_LIMIT": nutrients = None
                
                if not nutrients:
                    raw_nutrients = self.get_usda_data(short_name)
                    if raw_nutrients:
                        unit_multiplier = 2.5 * multiplier 
                        nutrients = {k: v * unit_multiplier for k, v in raw_nutrients.items()}
            
            if nutrients:
                item_nutrients = {
                    "food_name": food_name,
                    "portion": portion,
                    "calories": round(nutrients["calories"]),
                    "carbs": round(nutrients["carbs"], 1),
                    "protein": round(nutrients["protein"], 1),
                    "fat": round(nutrients["fat"], 1),
                    "confidence": item.get("confidence", 1.0)
                }
                results.append(item_nutrients)
                
                total_calories += item_nutrients["calories"]
                total_carbs += item_nutrients["carbs"]
                total_protein += item_nutrients["protein"]
                total_fat += item_nutrients["fat"]
            else:
                # Add it anyway with zero nutrients so user can edit it
                results.append({
                    "food_name": food_name,
                    "portion": portion,
                    "calories": 0,
                    "carbs": 0,
                    "protein": 0,
                    "fat": 0,
                    "confidence": item.get("confidence", 0.1)
                })
        
        # Calorie range logic (e.g., +/- 10%)
        calorie_min = round(total_calories * 0.9)
        calorie_max = round(total_calories * 1.1)
        
        return {
            "items": results,
            "totals": {
                "calories": round(total_calories),
                "calorie_range": f"{calorie_min}-{calorie_max}",
                "carbs": round(total_carbs, 1),
                "protein": round(total_protein, 1),
                "fat": round(total_fat, 1)
            }
        }
        