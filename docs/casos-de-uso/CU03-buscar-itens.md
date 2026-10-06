# CU03 – Buscar Itens

> Fonte: documento do TC *TCII-N2-IND-Itzac Albertin-Guiliano Rangel Alves* (Google Drive), exportado em 06/10/2026, já com as atualizações pós-implementação. O documento do TC é a fonte da verdade: se houver divergência, atualize este arquivo a partir dele.

**Situação no código (06/10/2026):** Implementado (C1 a C3), commit `3aeff24`. Testes em `backend/tests/integration/test_cu03_buscar_itens.py`.

## Descrição

Este caso de uso tem como principal função permitir que o usuário localize um item da Casa de Leilões por nome ou identificador, apresentando a relação de itens correspondentes ao termo pesquisado, de modo a servir como ponto de entrada para a análise histórica e preditiva do ativo.

- **Requisitos associados:** RF02 - Busca de Itens
- **Cenários:**
  - Cenário 01 – Pesquisar item por nome
  - Cenário 02 – Pesquisar item por identificador (ID)
  - Cenário 03 – Selecionar item do resultado da busca

## Regras de negócio dos requisitos associados

(Conforme o campo "Regras de Negócio" dos quadros dos RFs; texto completo em `docs/regras-de-negocio.md`.)


## CU03 - C1 – Buscar Itens - Cenário Pesquisar Item por Nome

- **Objetivo:** Exibir a relação de itens da Casa de Leilões cujo nome corresponde, total ou parcialmente, ao termo digitado pelo usuário.
- **Pré-condição:** O sistema deve possuir itens cadastrados.
- **Pós-condição:** O usuário visualiza a lista de itens correspondentes ao termo pesquisado.
- **Atores:** Usuário
- **Ativação:** O usuário digita um termo na barra de pesquisa.

### Fluxo principal

1. O usuário digita o termo de busca, de até 100 caracteres alfanuméricos, na barra de pesquisa.
2. O sistema normaliza o termo digitado, desconsiderando acentuação e diferenças entre maiúsculas e minúsculas.
3. O sistema consulta no banco de dados os itens cujo nome corresponde ao termo informado.
4. O sistema recupera, para cada item localizado, a data da última atualização do leilão.
5. O sistema apresenta a relação de itens localizados, paginada (10 itens por página), contendo nome e ícone de cada item.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Termo de busca insuficiente

- **1.1** No passo 1, o usuário confirma a busca com menos de três caracteres.
- **1.2** O sistema não executa a consulta e exibe a mensagem: "Digite ao menos três caracteres para pesquisar".
- **1.3** Retorna ao passo 1 do fluxo principal.

#### Fluxo Alternativo 2 - Nenhum item localizado

- **2.1** No passo 3, o sistema não encontra itens correspondentes ao termo informado.
- **2.2** O sistema exibe a mensagem: "Nenhum item encontrado para o termo pesquisado" .
- **2.3** Fim.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** O sistema não consegue executar a consulta devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema exibe a mensagem: "Não foi possível realizar a busca no momento. Tente novamente mais tarde".
- **1.3** Fim.

## CU03 - C2 – Buscar Itens - Cenário Pesquisar Item por Identificador

- **Objetivo:** Localizar diretamente um item específico a partir do seu identificador numérico na Casa de Leilões.
- **Pré-condição:** O sistema deve possuir itens cadastrados no banco de dados.
- **Pós-condição:** O usuário visualiza o item correspondente ao identificador informado.
- **Atores:** Usuário
- **Ativação:** O usuário informa um identificador numérico na barra de pesquisa e confirma a busca.

### Fluxo principal

1. O usuário informa o identificador do item na barra de pesquisa.
2. O sistema reconhece o termo como numérico e o interpreta como identificador de item.
3. O sistema consulta no banco de dados o item correspondente ao identificador informado.
4. O sistema recupera, para o item localizado, a data da última atualização do leilão.
5. O sistema apresenta o item localizado como resultado único da busca.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Identificador inexistente

- **1.1** No passo 3, o sistema não localiza item cadastrado para o identificador informado.
- **1.2** O sistema exibe a mensagem: "Nenhum item corresponde ao identificador informado".
- **1.3** Fim.

#### Fluxo Alternativo 2 - Termo ambíguo

- **2.1** No passo 2, o sistema identifica que o termo informado contém caracteres numéricos e alfabéticos.
- **2.2** O sistema trata o termo como busca textual.
- **2.3** Prossegue conforme o Cenário 01 do presente caso de uso.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** O sistema não consegue executar a consulta devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema exibe a mensagem: "Não foi possível realizar a busca no momento. Tente novamente mais tarde".
- **1.3** Fim.

## CU03 - C3 – Buscar Itens - Cenário Selecionar Item do Resultado da Busca

- **Objetivo:** Encaminhar o usuário para a análise histórica e preditiva do item escolhido na relação de resultados.
- **Pré-condição:** O usuário deve estar visualizando a relação de itens retornada por uma busca.
- **Pós-condição:** O sistema apresenta a tela de detalhes do item selecionado.
- **Atores:** Usuário
- **Ativação:** O usuário clica sobre um item da relação de resultados.

### Fluxo principal

1. O usuário clica sobre o nome ou o ícone de um item na relação de resultados.
2. O sistema registra o identificador do item selecionado.
3. O sistema encaminha o usuário para a tela de detalhes do item.
4. O sistema aciona o caso de uso CU04 – Visualizar Histórico.

### Fluxos de exceção

#### Fluxo Exceção 1 - Item removido durante a navegação

- **1.1** No passo 3, o sistema não localiza mais o item selecionado no banco de dados.
- **1.2** O sistema exibe a mensagem: "Item indisponível. Realize uma nova busca".
- **1.3** O sistema retorna o usuário à tela de busca.
- **1.4** Fim.

## Observações para a implementação

Decisões já implementadas (com a variável de ambiente que as controla) e o que continua pendente. Detalhes em `docs/decisoes-e-pendencias.md`. Onde houver conflito com o texto acima, vale o que está aqui e o documento do TC deve ser corrigido.

- Termo de busca: de 3 a 100 caracteres. Só números é tratado como identificador do item (C2); letras e números é tratado como busca por nome (C2-FA2).
- A busca por nome desconsidera acentuação e maiúsculas/minúsculas (extensão `unaccent` do PostgreSQL). A paginação é de 10 itens por página, com no máximo 50.
- A API devolve `last_auction_update` (passo 4), mas a lista mostra só nome e ícone (passo 5), como descreve o documento.
- O RF02 não tem regra de negócio associada (Quadro 10).
