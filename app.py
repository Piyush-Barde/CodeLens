from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, json
from dotenv import load_dotenv
from google import genai
from supabase import create_client

load_dotenv()
app = FastAPI()

# CRITICAL: Allow your HTML to talk to your Python server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"), http_options={'api_version': 'v1'})
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class CodeRequest(BaseModel):
    code: str

@app.post("/explain") # Changed from /analyze to /explain to match your HTML fetch
async def explain_code(request: CodeRequest):
    try:
        # 1. Check Supabase Cache first (Saves Money/Time)
        cached = supabase.table("code_logs").select("*").eq("code_content", request.code).execute()
        if cached.data:
            return {"explanation": json.loads(cached.data[0]['explanation']), "cached": True}

        # 2. If not cached, ask Gemini for STRUCTURED JSON
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
        
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        # Clean the response in case Gemini adds markdown backticks
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        explanation_data = json.loads(clean_json)
        
        # 3. Cache the result
        supabase.table("code_logs").insert({
            "code_content": request.code,
            "explanation": json.dumps(explanation_data)
        }).execute()
        
        return {"explanation": explanation_data, "cached": False}
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))