from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from src.repositories.database import init_db
from src.controllers.item_controller import router as item_router
from src.controllers.usuario_controller import router as usuario_router
from src.controllers.auth_controller import router as auth_router
from src.controllers.mercado_controller import router as mercado_router
from src.controllers.admin_historico_controller import router as historico_router
from src.controllers.admin_eventos_controller import router as eventos_router

# Load environment variables
load_dotenv()

# Initialize Database
init_db()

app = FastAPI(
    title="Goblin Ledger API",
    description="API para acessar os dados históricos do World of Warcraft",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(item_router, prefix="/api")
app.include_router(usuario_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(mercado_router, prefix="/api")
app.include_router(historico_router, prefix="/api")
app.include_router(eventos_router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Goblin Ledger API is running!"}
