from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, List
import os
from nl2sql.generator import NL2SQLGenerator  # LangChain version
from nl2sql.langchain_agent import LangChainSQLAgent
from nl2sql.validator import QueryValidator
from nl2sql.executor import QueryExecutor

# Initialize FastAPI app
app = FastAPI(
    title="NL2SQL E-Commerce API",
    description="Natural Language to SQL Query Generator for E-Commerce Database",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
db_config = {
    'host': os.getenv('DB_HOST', 'database'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'ecommerce'),
    'user': os.getenv('DB_USER', 'user'),
    'password': os.getenv('DB_PASSWORD', 'password')
}

model_name = os.getenv('MODEL_NAME', 'llama3.1:8b')

# Global instances
generator = None
sql_agent = None  # LangChain agent
validator = None
executor = None

@app.on_event("startup")
async def startup_event():
    """Initialize components on startup"""
    global generator, sql_agent, validator, executor
    
    print("🚀 Starting NL2SQL API with LangChain...")
    
    # Initialize generator
    generator = NL2SQLGenerator(model_name=model_name)
    
    # Initialize LangChain agent (advanced)
    db_uri = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
    sql_agent = LangChainSQLAgent(model_name=model_name, db_uri=db_uri)
    
    # Initialize validator
    validator = QueryValidator(generator.schema)
    
    # Initialize executor
    executor = QueryExecutor(db_config)
    
    print("✓ All components initialized successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if executor:
        executor.close()
    print("✓ API shutdown complete")

# Request/Response Models
class NL2SQLRequest(BaseModel):
    question: str
    execute: bool = False
    strategy: str = "detailed"

class NL2SQLResponse(BaseModel):
    sql_query: str
    validation_passed: bool
    execution_success: Optional[bool] = None
    results: Optional[List[Dict]] = None
    generation_time_ms: float
    execution_time_ms: Optional[float] = None
    error: Optional[str] = None

class ValidateRequest(BaseModel):
    sql_query: str

class ValidateResponse(BaseModel):
    is_valid: bool
    error_message: Optional[str] = None
    validation_details: Dict

class SchemaResponse(BaseModel):
    tables: Dict[str, Dict]
    total_tables: int

# API Endpoints

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "NL2SQL E-Commerce API",
        "version": "1.0.0",
        "endpoints": {
            "nl2sql": "POST /api/nl2sql",
            "validate": "POST /api/validate",
            "schema": "GET /api/schema",
            "stats": "GET /api/stats"
        },
        "docs": "/docs"
    }

@app.post("/api/nl2sql", response_model=NL2SQLResponse)
async def generate_and_execute_sql(request: NL2SQLRequest):
    """
    Generate SQL from natural language and optionally execute it
    
    - **question**: Natural language question
    - **execute**: Whether to execute the generated query
    - **strategy**: Prompt strategy ("detailed" or "concise")
    """
    import time
    
    try:
        # Generate SQL
        gen_start = time.time()
        sql_query = generator.generate_sql(request.question, strategy=request.strategy)
        generation_time = (time.time() - gen_start) * 1000
        
        # Validate SQL
        is_valid, error_msg, validation_details = validator.validate(sql_query)
        
        response = NL2SQLResponse(
            sql_query=sql_query,
            validation_passed=is_valid,
            generation_time_ms=round(generation_time, 2)
        )
        
        if not is_valid:
            response.error = error_msg
            return response
        
        # Execute if requested
        if request.execute:
            success, results, error, exec_metrics = executor.execute(sql_query)
            
            response.execution_success = success
            response.execution_time_ms = exec_metrics.get('execution_time_ms', 0)
            
            if success:
                response.results = results
            else:
                response.error = error
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/validate", response_model=ValidateResponse)
async def validate_sql(request: ValidateRequest):
    """
    Validate a SQL query without executing it
    
    - **sql_query**: SQL query to validate
    """
    try:
        is_valid, error_msg, validation_details = validator.validate(request.sql_query)
        
        return ValidateResponse(
            is_valid=is_valid,
            error_message=error_msg if not is_valid else None,
            validation_details=validation_details
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/schema", response_model=SchemaResponse)
async def get_schema():
    """
    Get database schema information
    
    Returns information about all tables, columns, and relationships
    """
    try:
        return SchemaResponse(
            tables=generator.schema,
            total_tables=len(generator.schema)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_statistics():
    """
    Get execution statistics
    
    Returns metrics about query execution performance
    """
    try:
        stats = executor.get_statistics()
        return {
            "execution_stats": stats,
            "model": model_name
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/stats/reset")
async def reset_statistics():
    """Reset execution statistics"""
    try:
        executor.reset_statistics()
        return {"message": "Statistics reset successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model": model_name,
        "database": "connected" if executor and executor.connection else "disconnected"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)