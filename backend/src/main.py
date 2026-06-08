from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from src.repositories.database import init_db
from src.controllers.item_controller import router as item_router

# Load environment variables
load_dotenv()

# Initialize Database
init_db()

app = FastAPI(
    title="Goblin Ledger API",
    description="API para acessar os dados históricos do World of Warcraft",
    version="1.0.0"
)

# Set up CORS
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(item_router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Goblin Ledger API is running!"}
