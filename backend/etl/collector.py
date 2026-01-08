import sys 
import os
import requests
import json
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from database import MarketHistory
from dotenv import load_dotenv

#função para carregar as variáveis de ambiente
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

CLIENT_ID = os.getenv('BLIZZARD_CLIENT_ID')
CLIENT_SECRET = os.getenv('BLIZZARD_CLIENT_SECRET')
REGION = os.getenv('BLIZZARD_REGION')
LOCALE = os.getenv('BLIZZARD_LOCALE')
CONNECTED_REALM_ID = 3209 #Azralon

def get_access_token():
    url = "https://oauth.battle.net/token"
    payload = {'grant_type': 'client_credentials'}
    auth = (CLIENT_ID, CLIENT_SECRET)

    print("Tentando autenticar...")
    response = requests.post(url, data=payload, auth=auth)

    if response.status_code == 200:
        print("Autenticado com sucesso!")
        return response.json()['access_token']
    else:
        print("Erro ao autenticar: ", {response.status_code})
        print(response.text)
        raise None

def get_auction_data(token):
    """Responsável por baixar o dump da Casa de Leilões (Azralon)"""
    url = f"https://{REGION}.api.blizzard.com/data/wow/connected-realm/{CONNECTED_REALM_ID}/auctions"
    
    params = {
        'namespace': f'dynamic-{REGION}',
        'locale': LOCALE,
        'access_token': token
    }

    print(f"Baixando dados do Reino {CONNECTED_REALM_ID} (Isso pode demorar alguns segundos)...")
    start_time = time.time()

    response = request.get(url, params=params)

    end_time = time.time()

    if response.status_code == 200:
        data = response.json()
        auctions = data.get('auctions', [])
        print(f"Dados baixados em {end_time - start_time:.2f} segundos.")
        print(f"Total de leilões encontrados: {len(auctions)}")
        return auctions
    else:
        print("Erro ao baixar dados: ", {response.status_code})
        print(response.text)
        raise None

def save_to_postgres(auctions_data):
    db = SessionLocal()
    init_db()
    
    print(f"Iniciando salvamento de {len(auctions_data)} registros no PostgreSQL...")

    batch = []
    captured_at = datetime.utcnow()

    for auction in auctions_data:
        price = auction.get('buyout') or aucion.get('unit_price', 0)
        if price > 0:
            record = MarketHistory(
                item_id=auction['item']['id'],
                price=price,
                quantity=auction['quantity'],
                captured_at=captured_at
            )
            batch.append(record)

    try:
        db.bulk_save_objects(batch)
        db.commit()
        print(f"Dados salvos com sucesso!")
    except Exception as e:
        print(f"Erro ao salvar: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERRO: Variáveis de ambiente não encontradas. Verifique o arquivo .env")    
        exit(0)
    
    token = get_access_token()

    if token: 
        auctions = get_auction_data(token)
        
        if auctions:
            save_to_postgres(auctions)
            sample_file = "auction_sample.json"
            with open(sample_file, 'w', encoding='utf-8') as f:
                json.dump(auctions[:5], f, indent=4)

            print(f"Sucesso! Um exemplo dos dados foi salvo em '{sample_file}'.")
            print("Abra esse arquivo para ver a estrutura dos dados que vamos trabalhar.")