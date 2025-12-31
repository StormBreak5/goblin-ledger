import json
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Goblin Ledger API", version="0.1.0")

#Configuração de CORS
origins = [
    "http://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "online", "message": "Goblin Ledger Backend - Modo Dev"}

@app.get("/api/auctions")
def get_auctions():
    """Leilões mockados temporariamente"""

    try:
        file_path = os.path.join(os.path.dirname(__file__), 'data', 'mock_auctions.json')
        with open(file_path, 'r') as f:
            data = json.load(f)
        return data
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo de leilões não encontrado")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Erro ao decodificar o arquivo JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
def get_stats():
    """Estadísticas mockadas temporariamente"""
    file_path = os.path.join(os.path.dirname(__file__), 'data', 'mock_auctions.json')
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    total_gold = sum(item['buyout'] for item in data) / 10000
    return {
        "total_items": len(data),
        "market_cap_gold": total_gold
    }