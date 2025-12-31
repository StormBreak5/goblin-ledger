# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import auctions

app = FastAPI(title="Goblin Ledger API", version="0.2.0")

# --- Configuração de CORS ---
origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Inclui as rotas separadas ---
app.include_router(auctions.router)

@app.get("/")
def read_root():
    return {"status": "online", "message": "Goblin Ledger Backend - Architecture Ready"}