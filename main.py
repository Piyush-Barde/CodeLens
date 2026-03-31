from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel

app = FastAPI()

# Custom Exception for clearer System Observability
class ResourceNotFoundError(Exception):
    def __init__(self, resource: str, identifier: str):
        self.resource = resource
        self.identifier = identifier

@app.exception_handler(ResourceNotFoundError)
async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "ERR_RESOURCE_MISSING",
            "message": f"{exc.resource} with ID '{exc.identifier}' does not exist.",
            "context": {"id": exc.identifier, "type": exc.resource}
        },
    )

# --- MOCK DATA LAYER ---
MODELS_DB = {"churn-v1": {"name": "Churn Prediction", "type": "xgboost"}}

# --- ENDPOINTS ---

@app.get("/models", response_model=List[dict])
async def get_models(type: Optional[str] = None):
    """
    CRITIQUE FIX: If filter returns nothing, return 200 + []. 
    NEVER 404 for an empty collection.
    """
    results = [m for m in MODELS_DB.values() if not type or m["type"] == type]
    return results

@app.get("/models/{model_id}")
async def get_model(model_id: str):
    """
    CRITIQUE FIX: 404 only for specific missing IDs.
    """
    if model_id not in MODELS_DB:
        raise ResourceNotFoundError(resource="Model", identifier=model_id)
    return MODELS_DB[model_id]

@app.post("/predict/{model_id}")
async def predict(model_id: str, features: dict):
    """
    CRITIQUE FIX: Differentiate between missing model (404) 
    and bad input data (422/400).
    """
    if model_id not in MODELS_DB:
        raise ResourceNotFoundError(resource="Model", identifier=model_id)
    
    # Check for specific feature logic
    if "user_id" not in features:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing 'user_id' in feature set."
        )
    
    return {"prediction": 0.85, "model": model_id}