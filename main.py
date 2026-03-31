import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from supabase import create_client, Client

# --- Configuration & Initialization ---
load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not all([GEMINI_KEY, SUPABASE_URL, SUPABASE_KEY]):
    print("❌ ERROR: Missing environment variables in .env.")
    sys.exit(1)

# Initialize Clients with stable v1 API
client = genai.Client(api_key=GEMINI_KEY, http_options={'api_version': 'v1'})
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Core Logic Functions ---

def analyze_code(user_code: str, language: str = "Python"):
    """
    Sends code to Gemini 2.5 Flash for a newbie-friendly breakdown.
    """
    prompt = f"""
    Act as an elite Software Engineering Tutor. 
    Analyze this {language} snippet for a absolute beginner.
    
    Structure your response EXACTLY as follows:
    1. **High-Level Concept**: What is the goal of this code in 1 sentence?
    2. **Line-by-Line Logic**: 
       - [Line #]: [Code] -> [Plain English explanation of what's happening]
    3. **The 'Key Takeaway'**: What core programming concept does this demonstrate?
    
    Code to analyze:
    {user_code}
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text if response.text else "⚠️ Analysis failed to generate text."
    except Exception as e:
        return f"❌ Gemini Error: {str(e)}"

def save_interaction(snippet: str, explanation: str):
    """
    Logs the query and result into Supabase for your project's 'History' feature.
    """
    try:
        data = {
            "code_content": snippet,
            "explanation": explanation,
            "created_at": datetime.utcnow().isoformat()
        }
        # Ensure you have created a table named 'code_logs' in Supabase dashboard
        supabase.table("code_logs").insert(data).execute()
        return True
    except Exception as e:
        print(f"⚠️ Supabase Logging Failed: {e}")
        return False

# --- Main Execution Flow ---

def main():
    print("--- CodeLens: Newbie Logic Analyzer ---")
    
    # 1. Simulating User Input (In future, this comes from your frontend/index.html)
    sample_code = """
    items = [1, 2, 3]
    for i in items:
        print(i * 2)
    """
    
    print("\n[Step 1] Analyzing code...")
    explanation = analyze_code(sample_code)
    print("\n--- ANALYSIS RESULT ---")
    print(explanation)
    
    # 2. Log to Database
    print("\n[Step 2] Saving to Supabase...")
    if save_interaction(sample_code, explanation):
        print("✅ Successfully logged to database.")

if __name__ == "__main__":
    main()