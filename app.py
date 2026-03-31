import os
import json
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

# 2. Handle Static Files (This allows images in your /image folder to load)
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
# Note: Ensure these keys are set in your deployment's Environment Variables
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

client = genai.Client(api_key=GEMINI_KEY, http_options={'api_version': 'v1'})
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class CodeRequest(BaseModel):
    code: str

# --- ROUTES ---

@app.get("/")
async def read_root():
    """
    Serves the actual website frontend. 
    This replaces the 'Server is running' JSON message with your HTML.
    """
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"error": "index.html not found in root directory"}

@app.post("/explain")
async def explain_code(request: CodeRequest):
    try:
        # A. Check Supabase Cache (Saves API Quota)
        cached = supabase.table("code_logs").select("*").eq("code_content", request.code).execute()
        if cached.data:
            return {
                "explanation": json.loads(cached.data[0]['explanation']), 
                "cached": True
            }

        # B. Request explanation from Gemini
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
        {request.code}
        """
        
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=prompt
        )
        
        # C. Parse and Clean Response
        raw_text = response.text
        clean_json = raw_text.replace("```json", "").replace("```", "").strip()
        explanation_data = json.loads(clean_json)
        
        # D. Store in Cache
        supabase.table("code_logs").insert({
            "code_content": request.code,
            "explanation": json.dumps(explanation_data)
        }).execute()
        
        return {"explanation": explanation_data, "cached": False}
        
    except Exception as e:
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))