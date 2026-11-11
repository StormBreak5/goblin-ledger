# CU06 – Manter Favoritos

> **PROVISÓRIO (20/10/2026).** Texto para o TC em `docs/Alterações do TC - CU06 a CU08 (para colar).docx`. Enquanto o TC e o `docs/` não forem reexportados, vale este arquivo.

## Descrição

Este caso de uso tem como principal função permitir que o usuário autenticado adicione itens à sua lista de favoritos, remova-os e visualize a lista, que funciona como um painel de acesso rápido aos itens que ele acompanha e é a base para a configuração dos alertas de preço.

- **Requisitos associados:** RF09 – Gestão de Itens Favoritos
- **Cenários:**
  - Cenário 01 – Adicionar item aos favoritos
  - Cenário 02 – Remover item dos favoritos
  - Cenário 03 – Visualizar lista de favoritos

## CU06 - C1 – Manter Favoritos - Cenário Adicionar Item aos Favoritos

- **Objetivo:** Incluir um item na lista de favoritos do usuário, para acesso rápido e para a configuração de alertas de preço.
- **Pré-condição:** A tela de detalhes do item deve estar aberta.
- **Pós-condição:** O item é registrado na lista de favoritos do usuário.
- **Atores:** Usuário
- **Ativação:** O usuário aciona o controle "Favoritar" na tela de detalhes do item.

### Fluxo principal

1. O usuário aciona o controle "Favoritar" na tela de detalhes do item.
2. O sistema verifica se o usuário está autenticado.
3. O sistema verifica se o item já está na lista de favoritos do usuário.
4. O sistema registra o item na lista de favoritos do usuário.
5. O sistema altera o controle para "Favoritado" e exibe a mensagem "Item adicionado aos favoritos".

### Fluxos alternativos

#### Fluxo Alternativo 1 - Usuário não autenticado

- **1.1** No passo 2, o sistema identifica que o usuário não está autenticado.
- **1.2** O sistema direciona o usuário à tela de login, com a mensagem "Entre na sua conta para favoritar itens".
- **1.3** Fim.

#### Fluxo Alternativo 2 - Item já favoritado

- **2.1** No passo 3, o sistema identifica que o item já está na lista de favoritos do usuário.
- **2.2** O sistema mantém o registro existente e exibe o controle como "Favoritado".
- **2.3** Fim.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** No passo 4, o sistema não consegue gravar o registro devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema exibe a mensagem: "Não foi possível atualizar os favoritos no momento. Tente novamente mais tarde".
- **1.3** Fim.

## CU06 - C2 – Manter Favoritos - Cenário Remover Item dos Favoritos

- **Objetivo:** Retirar um item da lista de favoritos do usuário, junto com os alertas de preço configurados para ele.
- **Pré-condição:** O usuário deve estar autenticado e o item deve estar na sua lista de favoritos.
- **Pós-condição:** O item e os seus alertas de preço são removidos da conta do usuário.
- **Atores:** Usuário
- **Ativação:** O usuário aciona o controle "Favoritado" na tela de detalhes do item ou a opção "Remover" na lista de favoritos.

### Fluxo principal

1. O usuário aciona a remoção do item da lista de favoritos.
2. O sistema verifica se há alertas de preço do usuário configurados para o item.
3. O sistema remove o item da lista de favoritos do usuário.
4. O sistema exibe a mensagem "Item removido dos favoritos" e atualiza a tela.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Item com alertas de preço

- **1.1** No passo 2, o sistema identifica que o usuário possui alertas de preço para o item.
- **1.2** O sistema exibe o aviso: "Este item possui alertas de preço, que também serão excluídos. Deseja continuar?".
- **1.3** O usuário confirma a remoção.
- **1.4** O sistema exclui os alertas de preço do item.
- **1.5** Retorna ao passo 3 do fluxo principal.

#### Fluxo Alternativo 2 - Remoção cancelada

- **2.1** No passo 1.3 do Fluxo Alternativo 1, o usuário cancela a remoção.
- **2.2** O sistema mantém o item na lista de favoritos e os seus alertas de preço.
- **2.3** Fim.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** No passo 3 ou no passo 1.4 do Fluxo Alternativo 1, o sistema não consegue remover os registros devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema desfaz as remoções e exibe a mensagem: "Não foi possível atualizar os favoritos no momento. Tente novamente mais tarde".
- **1.3** Fim.

## CU06 - C3 – Manter Favoritos - Cenário Visualizar Lista de Favoritos

- **Objetivo:** Exibir o painel de acesso rápido com os itens favoritos do usuário e a situação de mercado de cada um.
- **Pré-condição:** O usuário deve estar autenticado.
- **Pós-condição:** O usuário visualiza a sua lista de favoritos.
- **Atores:** Usuário
- **Ativação:** O usuário acessa a opção "Favoritos" no menu.

### Fluxo principal

1. O usuário acessa a opção "Favoritos" no menu.
2. O sistema recupera os itens da lista de favoritos do usuário.
3. O sistema recupera, para cada item, o valor de mercado atual (RN06), a variação em relação ao dia anterior e a quantidade de alertas de preço ativos.
4. O sistema exibe a lista dos itens favoritos em ordem alfabética, com o nome, o ícone, o valor de mercado convertido em Ouro, Prata e Cobre, a variação e os alertas ativos de cada item.
5. O sistema exibe a tela de detalhes do item que o usuário selecionar na lista.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Lista de favoritos vazia

- **1.1** No passo 2, o sistema não encontra itens na lista de favoritos do usuário.
- **1.2** O sistema exibe a mensagem: "Você ainda não tem itens favoritos. Use a busca para encontrar itens e favoritá-los".
- **1.3** Fim.

#### Fluxo Alternativo 2 - Dados desatualizados

- **2.1** No passo 3, o sistema identifica que a última coleta do mercado de um item ocorreu há mais de 24 horas ou falhou (RN09).
- **2.2** O sistema exibe o item normalmente, com a sinalização "Dados Desatualizados".
- **2.3** Retorna ao passo 4 do fluxo principal.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** Nos passos 2 ou 3, o sistema não consegue recuperar as informações devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema exibe a mensagem: "Não foi possível carregar os seus favoritos no momento. Tente novamente mais tarde".
- **1.3** Fim.

## Observações para a implementação

- **Tabela:** `favorito` (id do usuário, id do item, data de inclusão), com chave única (usuário, item) e exclusão em cascata pela conta do usuário (CU01-C3, RN20). A chave estrangeira já foi preparada no CU01. Tipos, como no MR (seção 7.2 do TC): id_usuario INTEGER (PK e FK para usuario), item_id INTEGER (PK), data_inclusao TIMESTAMPTZ.
- **API (sugestão):** `POST /favorites/{item_id}`, `DELETE /favorites/{item_id}` (com `?confirmar=true` quando houver alertas) e `GET /favorites`, todos autenticados. `GET /items/{item_id}` passa a informar se o item é favorito do usuário autenticado.
- **Variação:** valor de mercado atual (RN06) contra o valor de mercado de 24 horas antes, em percentual.
- **Telas:** controle "Favoritar"/"Favoritado" no cabeçalho da tela do item (CU04) e página `/favoritos`, acessível pelo menu. A ativação do CU04 pela lista de favoritos passa a valer.
- **Testes (um por fluxo):** `test_cu06_c1_fluxo_principal_adiciona_favorito`, `test_cu06_c1_fa1_usuario_nao_autenticado`, `test_cu06_c1_fa2_item_ja_favoritado`, `test_cu06_c1_fe1_falha_no_banco`, `test_cu06_c2_fluxo_principal_remove_favorito`, `test_cu06_c2_fa1_remove_os_alertas_do_item`, `test_cu06_c2_fa2_remocao_cancelada`, `test_cu06_c2_fe1_falha_desfaz_remocoes`, `test_cu06_c3_fluxo_principal_lista_favoritos`, `test_cu06_c3_fa1_lista_vazia`, `test_cu06_c3_fa2_dados_desatualizados_rn09`, `test_cu06_c3_fe1_falha_no_banco`.
