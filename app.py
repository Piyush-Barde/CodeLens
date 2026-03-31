from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, json
from dotenv import load_dotenv
from google import genai
from supabase import create_client

# 1. Load env first
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Initialize clients
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"), http_options={'api_version': 'v1'})
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class CodeRequest(BaseModel):
    code: str

# --- ROOT ROUTE (Moved outside and made clear) ---
@app.get("/")
def read_root():
    return {"message": "Server is up and running!"}

@app.post("/explain")
async def explain_code(request: CodeRequest):
    try:
        # Check Supabase Cache
        cached = supabase.table("code_logs").select("*").eq("code_content", request.code).execute()
        if cached.data:
            return {"explanation": json.loads(cached.data[0]['explanation']), "cached": True}

        # Ask Gemini
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
        
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        
        # Clean JSON string
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        explanation_data = json.loads(clean_json)
        
        # Cache result
        supabase.table("code_logs").insert({
            "code_content": request.code,
            "explanation": json.dumps(explanation_data)
        }).execute()
        
        return {"explanation": explanation_data, "cached": False}
        
    except Exception as e:
        print(f"Error: {e}")
        # Return the actual error to debug faster
        raise HTTPException(status_code=500, detail=str(e))