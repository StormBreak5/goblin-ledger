# 👺 Goblin Ledger: WoW Market Predictive Analysis

> **Trabalho de Conclusão de Curso (TCC) - Sistemas de Informação**
> **Autor:** Itzac Albertin
> **Status:** Em Desenvolvimento (Fase de Planejamento)

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
* **Framework API:** FastAPI (Performance e Documentação automática via Swagger).
* **Ciência de Dados:** Pandas, Numpy.
* **Machine Learning:** Facebook Prophet (ou Scikit-learn).
* **Banco de Dados:** PostgreSQL (Produção) / SQLite (Dev).
* **ORM:** SQLAlchemy ou Tortoise-ORM.

### Frontend (Interface)
* **Framework:** Next.js 14+ (App Router).
* **Linguagem:** TypeScript.
* **Estilização:** Tailwind CSS.
* **Gráficos:** Recharts ou Chart.js.
* **Ícones:** Lucide React.

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

## 5. Estrutura de Diretórios Sugerida

```bash
/goblin-ledger
│
├── /backend                 # Tudo relacionado a Python
│   ├── /app
│   │   ├── /api             # Endpoints (Routes) do FastAPI
│   │   ├── /core            # Configs (Env variables, DB connect)
│   │   ├── /models          # Modelos do Banco de Dados (ORM)
│   │   ├── /schemas         # Modelos Pydantic (Validação)
│   │   ├── /services        # Lógica de negócio
│   │   └── main.py          # Entrypoint da API
│   │
│   ├── /etl                 # Scripts de Extração de Dados
│   │   └── collector.py     # Script que bate na Blizzard
│   │
│   ├── /ml                  # Inteligência Artificial
│   │   └── forecaster.py    # Lógica do Prophet/Treinamento
│   │
│   ├── requirements.txt     # Dependências Python
│   └── .env                 # Segredos (NÃO COMMITAR)
│
├── /frontend                # Tudo relacionado a Next.js
│   ├── /src
│   │   ├── /app             # Páginas (Next.js App Router)
│   │   ├── /components      # Componentes Reutilizáveis (Cards, Charts)
│   │   ├── /lib             # Funções utilitárias (API fetch wrapper)
│   │   └── /types           # Definições TypeScript
│   │
│   ├── tailwind.config.ts   # Configuração de Cores
│   └── package.json         # Dependências JS
│
└── README.md
```

---

## 6. Convenções e Regras de Desenvolvimento

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

## 7. Roadmap Macro

- [ ] **Fase 1:** Configuração de Ambiente e "Hello World" (Back e Front).
- [ ] **Fase 2:** Script ETL funcional salvando dados reais da Blizzard.
- [ ] **Fase 3:** Criação da API REST básica (Listar itens).
- [ ] **Fase 4:** Implementação do Algoritmo de IA (Notebook -> Script).
- [ ] **Fase 5:** Frontend: Construção do Dashboard e Gráficos.
- [ ] **Fase 6:** Integração Final e Polimento.