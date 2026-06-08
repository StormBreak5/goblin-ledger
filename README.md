# Goblin Ledger 💰

O **Goblin Ledger** é uma aplicação focada em análise preditiva de economias virtuais, com foco inicial no acompanhamento e armazenamento do preço da **Ficha de WoW (WoW Token)** na Casa de Leilões do World of Warcraft.

O objetivo do projeto é coletar, de forma automatizada e não-intrusiva, o valor em ouro (Gold) da Ficha de WoW através da API oficial da Blizzard, salvando os dados em um banco de dados PostgreSQL isolado para futuras análises de mercado. O ecossistema é extensível para rastrear outros itens in-game futuramente.

---

## 🏗 Estrutura do Projeto

O repositório é divido nas seguintes partes principais:

- `/backend`: Contém o Worker em Python responsável por se comunicar com a API da Blizzard (`api_client.py`), gerenciar a autenticação Oauth e salvar periodicamente os dados coletados no banco de dados.
- `/frontend`: Aplicação Web desenvolvida em **Next.js** para visualização e análise dos dados coletados (em desenvolvimento).
- `/specs`: Contém as especificações detalhadas do projeto, histórias de usuário e requisitos técnicos iniciais.

## 🛠 Tecnologias Utilizadas

- **Backend:** Python 3.11+, SQLAlchemy, Requests
- **Frontend:** Next.js, React, TypeScript
- **Banco de Dados:** PostgreSQL 16
- **Infraestrutura:** Docker e Docker Compose

---

## 🚀 Como Executar o Projeto (Quickstart)

### Pré-requisitos
- **Docker** e **Docker Compose** instalados na sua máquina.
- **Credenciais da API da Blizzard** (Você precisará de um `Client ID` e um `Client Secret` gerados no [Portal de Desenvolvedores da Battle.net](https://develop.battle.net/)).

### 1. Configurar Variáveis de Ambiente

Navegue até a pasta `backend/` e crie um arquivo chamado `.env` (você pode usar o `.env.example` como base):

```env
BLIZZARD_CLIENT_ID="seu-client-id-aqui"
BLIZZARD_CLIENT_SECRET="seu-client-secret-aqui"

# Configurações do Banco de Dados (Docker)
DB_HOST="db"
DB_USER="goblin"
DB_PASS="goblin_password"
DB_NAME="goblinledger"
```

### 2. Iniciar os Serviços com Docker

Na raiz do diretório `backend/`, execute o comando para construir e subir os containers em background:

```bash
cd backend
docker-compose up --build -d
```

Isso fará com que o **Docker** inicialize dois containers:
1. `goblinledger-db`: O banco de dados PostgreSQL.
2. `goblinledger-worker`: O worker em Python que coleta os preços da Blizzard e insere no banco.

### 3. Sincronização Automática de Itens (Auto-Bootstrap)

O sistema agora é inteligente e dinâmico. Quando o worker é iniciado pela primeira vez e detecta que o banco de dados está vazio, ele realiza um **Auto-Bootstrap**:
- Ele conecta-se na API da Blizzard e extrai todos os itens ativamente comercializados na Casa de Leilões no momento (~15.000 itens).
- Isso garante que apenas itens com liquidez e valor comercial real sejam rastreados (ignorando itens inúteis, lixo ou vinculados).
- Esses itens são armazenados em uma tabela genérica pronta para expansão futura para outros jogos.

### 4. Acompanhar os Logs do Worker

Para verificar o processo de Auto-Bootstrap e se o Worker está capturando os preços em tempo real corretamente, você pode visualizar os logs:

```bash
docker-compose logs -f worker
```

### 5. Executar o Coletor de Histórico (Backfill)

Caso queira carregar dados históricos do passado (para todos os ~15.000 itens descobertos pelo Bootstrap) e treinar modelos preditivos, você pode executar o script de *backfill*. Ele consome a API do Undermine Exchange.

Entre na raiz do `backend` e execute o script dentro do container:

```bash
docker-compose exec worker python src/scraper/backfill.py --region US
```

---

## 📖 Documentação Adicional

Para mais detalhes sobre as regras de negócio, modelagem do banco de dados e arquitetura, consulte a pasta [`/specs/001-wow-token-price`](./specs/001-wow-token-price/). O planejamento completo e a monografia base estão disponíveis no documento PDF na raiz do repositório.

## 📝 Licença

Livre para uso de estudos e pesquisa acadêmica.
