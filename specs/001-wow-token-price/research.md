# Research: wow-token-price

## 1. Blizzard API Integration (WoW Token)

**Decision**: Utilizar o "Client Credentials Grant" do OAuth2 da Blizzard e o endpoint de tokens dinâmicos.
**Rationale**: Como nosso worker é um sistema de background que não requer acesso aos dados pessoais de um jogador específico, o fluxo de *Client Credentials* é o padrão da indústria e da Blizzard para comunicações server-to-server. A API `https://us.api.blizzard.com/data/wow/token/index?namespace=dynamic-us&locale=en_US` fornece o último preço de venda (em Cobre, que deve ser dividido por 10.000 para virar Ouro) atualizado constantemente. A biblioteca Pydantic modelará facilmente o response JSON.
**Alternatives considered**: Usar scraping na web (ilegal sob os T.O.S da Blizzard, muito frágil).

## 2. Docker & Database Stack

**Decision**: `docker-compose.yml` local na raiz do projeto contendo um container para `postgres:16-alpine` e um container `python-worker`.
**Rationale**: Isola as dependências do host, facilitando a execução universal do pipeline. O Alpine garante imagens leves.
**Alternatives considered**: Usar SQLite (não viável para alta concorrência caso o projeto escale rápido para dezenas de itens futuros rodando em paralelo multithread).

## 3. Worker Scheduling

**Decision**: Utilizar um looper simples nativo (ex: módulo `schedule` do Python ou até loops baseados em `asyncio.sleep`) com logs padrão (`logging`).
**Rationale**: Como o objetivo primário é capturar as atualizações da ficha, a Blizzard atualiza esse valor na casa dos ~20 minutos geralmente. Um loop nativo requerindo a cada 10 minutos com o `schedule` dispensa a sobrecarga de importar frameworks pesados de tarefas temporizadas.
**Alternatives considered**: Celery + Redis ou Apache Airflow (excessivamente pesado para 1 única tarefa de scraping neste momento - Overengineering).
