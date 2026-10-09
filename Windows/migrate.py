import json
import mimetypes
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from google import genai
from google.genai import types

# Input directory containing recipe files and output directory for JSON results (Windows paths)
INPUT_PATH = Path(r"C:\your\data\folder\to\recipeconverter")
OUTPUT_DIR = Path(r"C:\your\data\folder\to\nextcloudcookbook")

# File to track request timestamps for the 24-hour RPD limit
RPD_LOG_FILE = Path(__file__).parent / ".rpd_log.json" if "__file__" in globals() else Path(".rpd_log.json")
MAX_RPD = 20
WINDOW_SECONDS = 86400  # 24 hours in seconds

# Set up Gemini API client
API_KEY = ""
client = genai.Client(api_key=API_KEY)

# Prompt template defining schema mapping and conversion rules
PROMPT_TEMPLATE = """
You are a precision recipe data converter. Read the attached cookbook page or document and convert it into a clean Nextcloud Cookbook JSON.

EXPECTED JSON SCHEMA:
{
  "name": "Recipe Title",
  "description": "Exact intro text after the title",
  "recipeCategory": "recipeCategory like Gebäck",
  "keywords": "keywords like Zimtknoten, Backen, Plunderteig, Gebäck",
  "recipeIngredient": [
    "1 Rezept Plunderteig (s. S. 203)",
    "100g weiche Butter"
  ],
  "recipeInstructions": [
    "Instruction text for step 1",
    "Instruction text for step 2"
  ],
  "tool": [
    "tools like Backblech",
    "Backpapier"
  ],
  "recipeYield": 30,
  "prepTime": "PT20M",
  "cookTime": "PT25M",
  "totalTime": "PT3H10M"
}

STRICT CONVERSION RULES:
1. Read all German text accurately directly from the file.
2. Separate ingredients and instructions clearly.
3. Do NOT include prefixes like 'e.x.' or 'Step 1:' in the output strings.
4. Keep recipeIngredient as a flat array of strings.
5. Keep recipeInstructions as a flat array of strings.
6. Extract yields as integer numbers (e.g. 30).
7. For the 'description' extract ONLY the pure editorial intro text right beneath the title. DO NOT include ingredient lists, amounts, instructions, or section titles like 'Für die Füllung' inside description.
8. Ignore sidebars, variants, or alternative recipes (e.g. text starting with 'VARIANTE'). Focus strictly on the main recipe.
9. Do not skip sentences in the instructions. Combine all main instruction paragraphs completely.
10. Ensure sub-ingredients like 'Mehl für die Arbeitsfläche' are strictly mapped to recipeIngredient, never to recipeInstructions.
11. Calculate 'totalTime' by summing prep time, baking time, and any resting or rising times. Use ISO 8601 duration format.
12. Return ONLY raw JSON without markdown code blocks.
"""

def get_recent_requests() -> list:
    """
    Returns the list of timestamps for requests made in the last 24 hours.
    """
    if not RPD_LOG_FILE.exists():
        return []
    try:
        with open(RPD_LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            now = time.time()
            return [ts for ts in data if isinstance(ts, (int, float)) and (now - ts) < WINDOW_SECONDS]
    except Exception:
        return []

def record_request():
    """
    Records the current timestamp to enforce the 24-hour RPD limit across script runs.
    """
    recent = get_recent_requests()
    recent.append(time.time())
    try:
        with open(RPD_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(recent, f)
    except Exception as e:
        print(f"Warning: Could not update RPD log file: {e}")

def normalize_nextcloud_recipe(raw_data: dict) -> dict:
    """
    Cleans and structures raw JSON extracted from Gemini to strictly match the Nextcloud Cookbook schema.
    """
    # Generate dynamic UTC ISO 8601 timestamp (e.g., 2026-10-09T14:49:09+00:00)
    formatted_date = datetime.now(timezone.utc).isoformat()

    def clean_duration(val):
        """Sanitizes duration strings into valid ISO format."""
        if isinstance(val, dict):
            raw_val = val.get("value", "")
            return raw_val.lstrip("+") if isinstance(raw_val, str) else None
        if isinstance(val, str) and "-" in val:
            return val.split("-")[-1]
        return val if isinstance(val, str) else None

    # Convert keywords list to a comma-separated string if necessary
    keywords = raw_data.get("keywords", "")
    if isinstance(keywords, list):
        keywords = ",".join(str(k) for k in keywords)

    # Process and sanitize the ingredients list
    ingredients = raw_data.get("recipeIngredient") or raw_data.get("recipeIngredients") or []
    clean_ingredients = []
    if isinstance(ingredients, list):
        for item in ingredients:
            if isinstance(item, str):
                clean_ingredients.append(item.strip())
            elif isinstance(item, dict):
                qty = item.get("quantity", "")
                unit = item.get("unit", "")
                name = item.get("name", item.get("ingredient", ""))
                combined = " ".join(part for part in [qty, unit, name] if part).strip()
                if combined:
                    clean_ingredients.append(combined)

    # Process and sanitize the instruction steps
    instructions = raw_data.get("recipeInstructions", [])
    clean_instructions = []
    if isinstance(instructions, list):
        for item in instructions:
            if isinstance(item, str):
                clean_instructions.append(item.strip())
            elif isinstance(item, dict):
                text = item.get("stepDescription") or item.get("text") or " ".join(str(v) for v in item.values())
                clean_instructions.append(text.strip())

    # Extract numerical value for recipe yield
    yield_val = raw_data.get("recipeYield")
    if isinstance(yield_val, str):
        numbers = re.findall(r'\d+', yield_val)
        yield_val = int(numbers[0]) if numbers else 1

    # Return fully formatted schema object
    return {
        "cookTime": clean_duration(raw_data.get("cookTime")),
        "dateCreated": formatted_date,
        "dateModified": formatted_date,
        "datePublished": formatted_date,
        "description": str(raw_data.get("description", "")),
        "keywords": str(keywords),
        "name": str(raw_data.get("name", "Unbenanntes Rezept")),
        "nutrition": {"@type": "NutritionInformation"},
        "printImage": True,
        "prepTime": clean_duration(raw_data.get("prepTime")),
        "recipeCategory": str(raw_data.get("recipeCategory", "Gebäck")),
        "recipeIngredient": clean_ingredients,
        "recipeInstructions": clean_instructions,
        "recipeYield": yield_val if yield_val is not None else 1,
        "tool": raw_data.get("tool", []) if isinstance(raw_data.get("tool"), list) else [],
        "totalTime": clean_duration(raw_data.get("totalTime")),
        "@context": "http://schema.org",
        "@type": "Recipe"
    }

def get_mime_type(file_path: Path) -> str:
    """
    Detects the MIME type of the given file path with explicit fallbacks for images and document formats.
    """
    mime, _ = mimetypes.guess_type(file_path)
    if mime:
        return mime
    
    ext = file_path.suffix.lower()
    fallback_mimes = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.webp': 'image/webp',
        '.heic': 'image/heic',
        '.heif': 'image/heif',
        '.pdf': 'application/pdf',
        '.txt': 'text/plain',
        '.text': 'text/plain',
        '.md': 'text/markdown',
        '.markdown': 'text/markdown',
        '.html': 'text/html',
        '.htm': 'text/html',
        '.csv': 'text/csv',
        '.rtf': 'text/rtf',
    }
    return fallback_mimes.get(ext, "application/octet-stream")

def process_single_file(file_path: Path, current: int, total: int) -> bool:
    """
    Uploads a file via Files API, queries Gemini, saves JSON, and deletes the uploaded asset and local source.
    Returns False if processing was stopped due to rate limits.
    """
    recent_requests = get_recent_requests()
    if len(recent_requests) >= MAX_RPD:
        print(f"[{current}/{total}] RPD limit reached ({MAX_RPD} requests in the last 24 hours). Stopping execution.")
        return False

    print(f"[{current}/{total}] Processing file via Gemini API: {file_path.name}")
    
    uploaded_file = None
    try:
        mime_type = get_mime_type(file_path)

        # Upload file via Files API
        uploaded_file = client.files.upload(
            file=file_path,
            config=types.UploadFileConfig(mime_type=mime_type)
        )

        # Call Gemini model with forced JSON output mime type
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=[
                uploaded_file,
                PROMPT_TEMPLATE
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        # Record successful request timestamp
        record_request()

        content = response.text.strip() if response.text else ""
        
        # Try parsing JSON string directly
        try:
            raw_recipe_data = json.loads(content)
        except json.JSONDecodeError as json_err:
            print(f"[{current}/{total}] Error: Response is not valid JSON!")
            print(f"JSON Parse Error: {json_err}")
            print("--- RAW OUTPUT FROM GEMINI START ---")
            print(content)
            print("--- RAW OUTPUT FROM GEMINI END ---\n")
            return True
            
        # Parse and format recipe structure
        recipe_data = normalize_nextcloud_recipe(raw_recipe_data)
        
        # Build target directory name based on recipe title
        raw_name = recipe_data.get('name', 'Unbenanntes_Rezept')
        clean_folder_name = "".join([c for c in raw_name if c.isalnum() or c in (' ', '_')]).strip()
        
        target_folder = OUTPUT_DIR / clean_folder_name
        target_folder.mkdir(parents=True, exist_ok=True)
        
        # Save JSON output file
        json_path = target_folder / "recipe.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(recipe_data, f, ensure_ascii=False, indent=2)
            
        print(f"[{current}/{total}] Successfully generated: {json_path}")

        # Delete original local file after successful conversion
        file_path.unlink()
        print(f"[{current}/{total}] Deleted original file: {file_path.name}\n")

    except Exception as e:
        print(f"[{current}/{total}] Error processing file {file_path.name}: {e}\n")
    finally:
        # Clean up remote file from Gemini servers
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception as cleanup_err:
                print(f"Could not delete remote file {uploaded_file.name}: {cleanup_err}")

    return True

def main():
    """
    Main loop to process all recipe files in batch mode.
    """
    valid_extensions = (
        '.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif',
        '.pdf', '.txt', '.text', '.md', '.markdown', '.html', '.htm', '.csv', '.rtf'
    )

    if INPUT_PATH.is_file():
        process_single_file(INPUT_PATH, 1, 1)
    elif INPUT_PATH.is_dir():
        files = [f for f in INPUT_PATH.iterdir() if f.is_file() and f.suffix.lower() in valid_extensions]
        
        if not files:
            print("No supported input files found.")
            return

        total_files = len(files)
        print(f"Starting batch processing of {total_files} files via Gemini API...\n")

        for index, file_item in enumerate(files, start=1):
            success = process_single_file(file_item, index, total_files)
            if not success:
                break
            
            # Pause 12 seconds between files to respect rate limits (5 RPM)
            if index < total_files:
                print("Waiting 12 seconds to enforce rate limit (5 RPM)...")
                time.sleep(12)

        print("Finished processing loop.")
    else:
        print(f"Path not found: {INPUT_PATH}")

if __name__ == "__main__":
    main()