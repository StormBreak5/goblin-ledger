# 👺 Goblin Ledger: WoW Market Predictive Analysis

> **Trabalho de Conclusão de Curso (TCC) - Sistemas de Informação**
> **Autor:** Itzac Albertin
> **Status:** Em Desenvolvimento Ativo | Fase 1 ✅ | Fase 2 🔄 (50%)

---

## 1. Visão Geral do Projeto

**Goblin Ledger** é uma aplicação Fullstack de *Business Intelligence* e *Data Science* voltada para a economia virtual do jogo *World of Warcraft*.

O sistema coleta dados históricos da Casa de Leilões (Auction House), processa essas informações e utiliza algoritmos de **Machine Learning (Séries Temporais)** para prever a flutuação de preços de commodities, auxiliando jogadores na tomada de decisão (compra/venda).

### Objetivos Principais
1.  **ETL:** Extração automatizada e diária de dados da API oficial da Blizzard.
2.  **ML:** Previsão de preços futuros utilizando o modelo *Facebook Prophet* ou *ARIMA*.
3.  **Dashboard:** Visualização interativa dos dados (Histórico vs. Previsão).

---

## 2. Stack Tecnológica

### Backend (Processamento e API)
* **Linguagem:** Python 3.10+
* **Framework API:** FastAPI 0.128.0 (Performance e Documentação automática via Swagger).
* **Server ASGI:** Uvicorn 0.40.0
* **Validação de Dados:** Pydantic 2.12.5
* **HTTP Client:** Requests (para consumir API da Blizzard)
* **Variáveis de Ambiente:** Python-dotenv
* **Banco de Dados:** *A implementar* (PostgreSQL + SQLAlchemy)
* **Machine Learning:** *A implementar* (Facebook Prophet ou ARIMA)

### Frontend (Interface)
* **Framework:** Next.js 16.1.1 (App Router)
* **Linguagem:** TypeScript 5.x
* **Estilização:** Tailwind CSS 4.x
* **Runtime:** React 19.2.3
* **Linter:** ESLint 9.x
* **Gráficos:** *A implementar* (Recharts ou Chart.js)
* **Ícones:** *A implementar* (Lucide React)

---

## 3. Arquitetura do Sistema

O projeto segue uma arquitetura desacoplada (Microserviços leves):

1.  **Coletor (Worker):** Script Python agendado (Cronjob) que consome a API da Blizzard e salva no Banco de Dados.
2.  **API Server:** Expõe os endpoints REST para o frontend consumir dados.
3.  **ML Engine:** Módulo que lê o banco, treina o modelo e salva as previsões futuras.
4.  **Client:** Aplicação Next.js que renderiza os dados para o usuário final.

---

## 4. Identidade Visual (Paleta "Cartel de Engenharia")

O projeto utiliza um tema *Dark Mode* para alto contraste em visualização de dados.

| Cor | Hex | Variável Tailwind | Uso |
| :--- | :--- | :--- | :--- |
| **Dark Blue** | `#0F172A` | `bg-slate-900` | Fundo Principal da Aplicação |
| **Card Blue** | `#1E293B` | `bg-slate-800` | Fundo de Cards/Painéis |
| **Goblin Green**| `#10B981` | `text-emerald-500` | Lucro, Botões de Ação, Tendência de Alta |
| **Gold** | `#F59E0B` | `text-amber-500` | Previsão, Ouro, Ícones de Destaque |
| **Danger Red** | `#EF4444` | `text-red-500` | Prejuízo, Tendência de Baixa, Erros |
| **Text Primary**| `#F8FAFC` | `text-slate-50` | Títulos, Cabeçalhos e Corpo Principal |
| **Text Muted** | `#94A3B8` | `text-slate-400` | Legendas de eixos, Datas, Textos secundários |

---

## 5. Estrutura de Diretórios (Implementação Atual)

```bash
/goblin-ledger
│
├── /backend                 # Tudo relacionado a Python
│   ├── /api                 # ✅ Endpoints (Routes) do FastAPI
│   │   └── auctions.py      # Rotas de leilões
│   │
│   ├── /services            # ✅ Lógica de negócio
│   │   └── auction_service.py
│   │
│   ├── /etl                 # ✅ Scripts de Extração de Dados
│   │   └── collector.py     # Script que consome API da Blizzard
│   │
│   ├── /data                # ✅ Dados Mock (Dev)
│   │   └── mock_auctions.json
│   │
│   ├── main.py              # ✅ Entrypoint da API FastAPI
│   ├── requirements.txt     # ✅ Dependências Python
│   ├── .env                 # ✅ Variáveis de ambiente (NÃO COMMITAR)
│   └── .env.example         # Template de configuração
│
├── /frontend                # Tudo relacionado a Next.js
│   ├── /app                 # ✅ Páginas (Next.js 16 App Router)
│   │   ├── page.tsx         # Página principal com tabela de leilões
│   │   ├── layout.tsx       # Layout global
│   │   └── globals.css      # Estilos globais (Tailwind)
│   │
│   ├── /types               # ✅ Definições TypeScript
│   │   └── auction.ts       # Interface AuctionItem
│   │
│   ├── /public              # Arquivos estáticos
│   ├── package.json         # ✅ Dependências JS
│   └── tsconfig.json        # Configuração TypeScript
│
└── README.md

📝 Nota: Pastas /core, /models, /schemas, /ml, /components e /lib serão criadas 
conforme o projeto evolui para as próximas fases.
```

---

## 6. Status Atual da Implementação

### ✅ Fase 1: Configuração de Ambiente - **COMPLETA**
- [x] Backend FastAPI configurado e rodando
- [x] Frontend Next.js 16 configurado e rodando
- [x] Integração Backend ↔ Frontend funcionando
- [x] CORS configurado
- [x] Tailwind CSS v4 implementado com paleta de cores do projeto

### 🔄 Fase 2: ETL e Coleta de Dados - **EM PROGRESSO**
- [x] Script `collector.py` criado
- [x] Autenticação com API da Blizzard implementada
- [x] Dados mock para desenvolvimento (`mock_auctions.json`)
- [ ] Agendamento automático (Cronjob)
- [ ] Persistência em banco de dados

### 📊 Endpoints da API Disponíveis

**Base URL:** `http://localhost:8000`

| Método | Endpoint | Descrição | Status |
|--------|----------|-----------|--------|
| `GET` | `/` | Health check da API | ✅ |
| `GET` | `/api/auctions` | Lista todos os leilões | ✅ |
| `GET` | `/api/auctions/stats` | Estatísticas do mercado | ✅ |

### 🎨 Interface Implementada

- **Página Principal:** Tabela interativa de leilões com:
  - Nome do item (mock)
  - Preço em Gold
  - Quantidade disponível
  - Tempo restante com badge colorido
  - Contador de leilões rastreados
  - Design dark mode com paleta "Cartel de Engenharia"

### 🚀 Como Executar o Projeto

#### Backend (FastAPI)
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn main:app --reload
```
Acesse: `http://localhost:8000`

#### Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
```
Acesse: `http://localhost:3000`

---

## 7. Convenções e Regras de Desenvolvimento

### Git & Versionamento
* **Branches:**
    * `main`: Versão estável (Produção).
    * `develop`: Versão de desenvolvimento (Integração).
    * `feat/nome-da-funcionalidade`: Para novas features.
    * `fix/nome-do-bug`: Para correções.
* **Commits (Conventional Commits):**
    * `feat: adiciona componente de gráfico`
    * `fix: corrige erro na conexão com banco`
    * `docs: atualiza readme`
    * `chore: atualização de dependências`

### Code Style
* **Python:** Seguir PEP8. Variáveis em `snake_case`.
* **TypeScript/JS:** Seguir ESLint padrão. Variáveis e Funções em `camelCase`. Componentes React em `PascalCase`.

---

## 8. Roadmap Macro

- [x] **Fase 1:** Configuração de Ambiente e "Hello World" (Back e Front). ✅ **COMPLETA**
  - Backend FastAPI rodando em `localhost:8000`
  - Frontend Next.js 16 rodando em `localhost:3000`
  - Integração funcionando com dados mock
  
- [x] **Fase 2:** Script ETL funcional salvando dados reais da Blizzard. 🔄 **50% COMPLETA**
  - Script de coleta criado e testado
  - Autenticação OAuth2 implementada
  - Falta: Persistência em banco de dados e agendamento
  
- [ ] **Fase 3:** Criação da API REST básica (Listar itens).
  - Endpoints básicos já criados (GET auctions, GET stats)
  - Falta: Modelos ORM, schemas Pydantic, validações
  
- [ ] **Fase 4:** Implementação do Algoritmo de IA (Notebook → Script).
  - Pasta `/ml` ainda não criada
  - Modelo Prophet ou ARIMA a ser implementado
  
- [ ] **Fase 5:** Frontend: Construção do Dashboard e Gráficos.
  - Interface básica implementada
  - Falta: Componentes reutilizáveis, gráficos (Recharts), filtros
  
- [ ] **Fase 6:** Integração Final e Polimento.
  - Deploy, otimizações, documentação final

---

## 9. Tecnologias Utilizadas (Versões Atuais)

### Backend
- **Python:** 3.10+
- **FastAPI:** 0.128.0
- **Uvicorn:** 0.40.0
- **Pydantic:** 2.12.5
- **Requests:** (para ETL)
- **Python-dotenv:** (variáveis de ambiente)

### Frontend
- **Next.js:** 16.1.1
- **React:** 19.2.3
- **TypeScript:** 5.x
- **Tailwind CSS:** 4.x
- **ESLint:** 9.x

### Próximas Adições
- PostgreSQL / SQLAlchemy (Banco de Dados)
- Facebook Prophet ou Scikit-learn (Machine Learning)
- Recharts (Visualização de dados)
- Lucide React (Ícones)