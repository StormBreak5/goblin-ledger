# Interface Contracts: wow-token-price

Como este projeto é um "Worker (Agendador)" de background puro que não serve endpoints HTTP diretamente para o mundo exterior e não expõe bibliotecas, **não existem Contratos de Interface (APIs de Input) públicos expostos a serem documentados aqui**.

## Interações com Contratos Externos (Consumo Direto)

O Worker fará chamadas `Read-Only` para os Contratos Externos (API Oficial do World of Warcraft).

* **OAuth Token Gen**: Endpoint `/oauth/token` na API da Battle.net via Client Credentials.
* **Dynamic Index Endpoint**: Endpoint de WoW Token regional `/data/wow/token/index`. O layout esperado retornado obrigatoriamente terá as chaves `price` (Int) e `last_updated_timestamp` (Int UTC), onde Pydantic Models forçarão e validarão rigorosamente este contrato de entrada externa.
