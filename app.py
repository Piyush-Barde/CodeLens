import os
import json
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from supabase import create_client

# 1. Load environment variables
load_dotenv()

app = FastAPI()

# 2. Handle Static Files (For your /image folder)
if os.path.exists("image"):
    app.mount("/image", StaticFiles(directory="image"), name="image")

# 3. Middleware (Allow frontend communication)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Initialize API Clients
# Hard-fail if keys are missing to avoid confusing 500 errors later
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not all([GEMINI_KEY, SUPABASE_URL, SUPABASE_KEY]):
    print("CRITICAL ERROR: Missing API keys in .env file.")

client = genai.Client(api_key=GEMINI_KEY, http_options={'api_version': 'v1'})
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class CodeRequest(BaseModel):
    code: str

# --- ROUTES ---

@app.get("/")
async def read_root():
    """Serves the index.html file as the home page."""
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"error": "index.html not found. Check your file structure."}

@app.post("/explain")
async def explain_code(request: CodeRequest):
    # Normalize code (strip whitespace) to improve cache hit rate
    input_code = request.code.strip()
    
    try:
        # A. Check Supabase Cache FIRST
        cached = supabase.table("code_logs").select("*").eq("code_content", input_code).execute()
        if cached.data:
            return {
                "explanation": json.loads(cached.data[0]['explanation']), 
                "cached": True
            }

        # B. AI Prompt Setup
        prompt = f"""
        Analyze this code and return ONLY a JSON object. Do not include markdown formatting or backticks.
        JSON Structure:
        {{
            "overview": "brief summary",
            "steps": ["step 1", "step 2"],
            "time_complexity": "O(n)",
            "space_complexity": "O(1)",
            "suggestions": ["improvement 1"]
        }}
        Code:
        {input_code}
        """
        
        # C. Request from Gemini with Retry Logic for 429 Errors
        response_text = None
        for attempt in range(3):  # Try up to 3 times
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash-lite", 
                    contents=prompt
                )
                response_text = response.text
                break 
            except Exception as e:
                # If we hit a rate limit, wait and retry
                if "429" in str(e) and attempt < 2:
                    wait_time = (attempt + 1) * 2  # Wait 2s, then 4s
                    print(f"Rate limited. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                raise e # Re-raise if it's not a 429 or we're out of retries

        if not response_text:
            raise HTTPException(status_code=500, detail="Failed to get response from AI.")

        # D. Parse and Clean Response
        clean_json = response_text.replace("```json", "").replace("```", "").strip()
        explanation_data = json.loads(clean_json)
        
        # E. Store in Cache (Supabase)
        supabase.table("code_logs").insert({
            "code_content": input_code,
            "explanation": json.dumps(explanation_data)
        }).execute()
        
        return {"explanation": explanation_data, "cached": False}
        
    except Exception as e:
        error_str = str(e)
        print(f"Server Error: {error_str}")
        
        # Specific error for the frontend to handle
        if "429" in error_str:
            raise HTTPException(
                status_code=429, 
                detail="Gemini API Quota Exceeded. Please wait a minute before trying again."
            )
        
        raise HTTPException(status_code=500, detail="An internal server error occurred.")