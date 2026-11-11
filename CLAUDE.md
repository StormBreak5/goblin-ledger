# Goblin Ledger — instruções para o Claude Code

Aplicação web de inteligência de mercado para a Casa de Leilões (Auction House) do World of Warcraft: coleta preços, guarda séries históricas e, futuramente, gera previsões com Machine Learning. É o Trabalho de Curso (Sistemas de Informação — UEG) de Itzac Albertin. **Cada decisão de implementação precisa ser rastreável até o documento do TC.**

## Fonte da verdade

A especificação está em `docs/` (exportada do documento do TC no Google Drive):

- `docs/casos-de-uso/README.md` — relação de casos de uso, atores, glossário e **escopo atual**.
- `docs/casos-de-uso/CUxx-*.md` — um arquivo por caso de uso detalhado, com cenários, fluxo principal, fluxos alternativos e de exceção, a situação atual no código e **observações para a implementação**.
- `docs/requisitos.md` — RFs, RNFs e o quadro detalhado de cada RF (variáveis, tamanhos, domínios e RNs).
- `docs/regras-de-negocio.md` — RN01 a RN23.

Regras:

1. **Implemente somente os casos de uso detalhados em `docs/casos-de-uso/`: CU01 a CU11** (CU05, CU06, CU07 e CU08 especificados em `docs/casos-de-uso/CU05-…` a `CU08-…`, com o texto igual ao do TC; CU11 provisório: especificado em `docs/casos-de-uso/CU11-treinar-modelo.md`, com a v4 do documento de alterações; as RNs desse arquivo prevalecem sobre `docs/regras-de-negocio.md` e `docs/requisitos.md`).
2. Cada fluxo (principal, alternativo e de exceção) de cada cenário deve ter comportamento correspondente no código. Mensagens exibidas ao usuário devem usar **exatamente** o texto do cenário.
3. Não invente regra de negócio. Os pontos marcados como **Decisão pendente** nas observações de cada CU devem ser perguntados ao autor antes de implementar (ou implementados com a sugestão indicada, deixando o valor configurável e avisando no resumo final).
4. Se encontrar divergência entre o documento e o código, siga o documento e avise. Se encontrar divergência dentro do próprio documento, siga a seção "Observações para a implementação" do CU.

## Stack e estrutura

- **Backend** (`backend/`): Python 3.11+, FastAPI (`src/main.py`, API em `http://127.0.0.1:8000`), SQLAlchemy 2, Pydantic 2, APScheduler (`src/worker.py`), aiohttp/requests. PostgreSQL 16 via Docker.
  - `src/controllers/` rotas FastAPI · `src/services/` regras de negócio e clientes externos · `src/repositories/` acesso a dados · `src/models/` modelos ORM e Pydantic · `src/scraper/` backfill da Undermine Exchange (CU10) · `src/ml/` pipeline do modelo preditivo (CU11, porte de `estudos/lstm/`), executado só pelo serviço `modelo` (`src/modelo_worker.py`, `Dockerfile.modelo`).
- **Frontend** (`frontend/`): Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4, Recharts.
- `specs/` contém especificações antigas do Spec Kit (001 e 002). Servem de histórico; em caso de conflito, vale `docs/`.
- **Ignore** a pasta `.agent/` (skills de terceiros sem relação com o projeto) e a pasta `scratch/`.

## Comandos

```bash
# Banco + worker (a partir de backend/)
docker-compose up --build -d          # Postgres exposto em localhost:5435
docker-compose logs -f worker

# API local (a partir de backend/, com DB_HOST=localhost e DB_PORT=5435)
uvicorn src.main:app --reload

# Testes do backend (a partir de backend/; pytest.ini define pythonpath=src e testpaths=tests)
pytest

# CU11: serviço `modelo` (pandas + TensorFlow, imagem própria) e os testes do pipeline, que só rodam nele
# (no host, tests/modelo/ aparece como ignorado). A partir de backend/:
docker-compose up --build -d modelo
docker-compose logs -f modelo
docker-compose run --rm modelo-testes
# CU11-C2: retreinamento pelo mesmo caminho do agendador (sem região: todas com modelo vigente); --aguardar espera o fim
docker-compose exec modelo python -m src.modelo_worker --retreinar US --aguardar
# CU11-C3: consolidação diária das predições agora, como o agendador (MODELO_CONSOLIDACAO_CRON, 03:00 UTC)
docker-compose exec modelo python -m src.modelo_worker --consolidar
# CU10-C1: importação diária do histórico da Undermine, uma vez (o worker a agenda em HISTORICO_IMPORTACAO_DIARIA_CRON)
docker-compose exec worker python src/worker.py --importacao-diaria

# Frontend (a partir de frontend/)
npm run dev
npm run lint
npx tsc --noEmit
```

Não leia nem altere arquivos `.env` (contêm credenciais). Para novas variáveis, atualize `backend/.env.example`.

## Convenções

- Siga `.specify/memory/constitution.md`: type hints explícitos e Pydantic nas bordas da API; TypeScript strict sem `any`; regra de negócio no backend, nunca nos componentes.
- **RN01:** todo valor monetário é armazenado como inteiro em Cobre (1 Ouro = 10000 Cobre; 1 Prata = 100 Cobre). A conversão para Ouro/Prata/Cobre acontece só na exibição.
- Datas e horas em UTC no backend.
- **Rastreabilidade:** cite o caso de uso e a regra nas docstrings das funções que os implementam (ex.: `"""CU02-C1 / RN21: bloqueio após tentativas malsucedidas."""`).
- **Testes, um por fluxo**, nomeados com o identificador do documento, por exemplo:
  - `test_cu01_c1_fluxo_principal_cadastra_usuario`
  - `test_cu01_c1_fa2_email_ja_cadastrado_rn18`
  - `test_cu02_c1_fa3_conta_bloqueada_rn21`
  - `test_cu10_c1_fe3_formato_do_arquivo_alterado`
  Esses testes compõem o "Plano de testes" do TC; não os agrupe de forma que um fluxo fique sem teste próprio.
- **Banco de dados:** o `init_db()` usa `Base.metadata.create_all`, que não altera tabelas existentes. Antes de criar ou alterar tabelas, introduza migrações com **Alembic** (migração inicial refletindo o esquema atual) e passe a usá-las.
- Pontos conhecidos de atenção no esquema atual: `items.id` é UUID, mas `item_prices.item_id` e `historical_item_prices.item_id` são inteiros (ID externo); região aparece como `"us"` em uma tabela e como ID de reino conectado (`"3209"`, `"32512"`) em outra. Proponha a padronização antes de implementar o CU09.

## Forma de trabalho

1. Trabalhe **um caso de uso por vez**, sempre começando em modo de planejamento: leia o arquivo do CU, as RNs citadas e o código relacionado; proponha arquivos a criar/alterar e a lista de testes (um por fluxo); espere aprovação.
2. Implemente, rode `pytest` (e `npm run lint` / `npx tsc --noEmit` quando mexer no frontend) e só então conclua.
3. Um commit por caso de uso (ou por cenário, se for grande), com mensagem citando o CU, por exemplo `feat(CU02): bloqueio por tentativas (RN21)`.
4. Ao terminar um CU, liste o que ficou pendente e quais decisões foram tomadas, para que o autor atualize o documento do TC.

Ordem sugerida: CU03 (ajustes) → CU01 + CU02 → CU10 → CU09 → CU04 (verificação dos fluxos alternativos, que dependem do CU09) → CU11 (C1 → C2 → C3) → CU05 → CU06 + CU07 → CU08.
