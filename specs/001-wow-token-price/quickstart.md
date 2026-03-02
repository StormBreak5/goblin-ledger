# Quickstart: wow-token-price

## Pré-requisitos
- Docker & Docker Compose
- Credenciais da API da Blizzard (Client ID e Secret de um client em https://develop.battle.net/)
- Python 3.11+ e `uv` (opcionalmente) se for rodar o background worker localmente sem docker para debug.

## 1. Configurar Variáveis de Ambiente
Na raiz de `backend/`, crie o arquivo `.env`:

```env
BLIZZARD_CLIENT_ID="seu-cliente-aqui"
BLIZZARD_CLIENT_SECRET="seu-segredo-aqui"
DB_HOST="db"
DB_USER="goblin"
DB_PASS="goblin_password"
DB_NAME="goblinledger"
```

## 2. Iniciar o Banco de Dados e o Worker Simultaneamente
Dentro da raiz da pasta interna `backend/`:

`docker-compose up --build -d`

Isso vai instanciar a imagem do PostgreSQL isolada (montando o volume na sua máquina se configurado) e iniciará o container rodando o `worker.py` e logará no output se o fetching inicial foi gravado com sucesso.

Para ver os logs rodando e atestando que o scraping periodicamente está salvando:
`docker-compose logs -f worker`
