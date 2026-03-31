import os, hashlib, json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from supabase import create_client

app = FastAPI()

# 1. FIX THE CONNECTION (CORS)
# This allows your HTML file to talk to the Render backend.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 2. CLIENTS
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class CodeRequest(BaseModel):
    code: str

@app.post("/explain")
async def explain_code(req: CodeRequest):
    # Decision Layer: Hash the code
    code_hash = hashlib.sha256(req.code.strip().encode()).hexdigest()

    # Cache Check
    try:
        cached = supabase.table("code_cache").select("result").eq("id", code_hash).execute()
        if cached.data:
            # Match the frontend's expectation: { "source": "cache", "explanation": {...} }
            return {"source": "cache", "explanation": cached.data[0]["result"]}
    except: 
        pass 

    # AI Layer: Forced JSON Structure
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """Return JSON ONLY. 
                Structure: {
                  "overview": "brief summary",
                  "steps": ["step 1", "step 2"],
                  "time_complexity": "O(log N)", 
                  "space_complexity": "O(1)",
                  "suggestions": ["improvement 1"]
                }"""},
                {"role": "user", "content": req.code}
            ],
            response_format={"type": "json_object"}
        )
        
        ai_json = json.loads(response.choices[0].message.content)

        # Store in Supabase
        supabase.table("code_cache").insert({"id": code_hash, "result": ai_json}).execute()

        return {"source": "ai", "explanation": ai_json}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))