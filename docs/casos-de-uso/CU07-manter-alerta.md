# CU07 – Manter Alerta

> Texto igual ao do TC (seção 6.4.7), conferido em 11/11/2026.

## Descrição

Este caso de uso tem como principal função permitir que o usuário autenticado crie, altere, reative e exclua alertas de preço para os itens da sua lista de favoritos, definindo o tipo de gatilho (compra ou venda), o preço-alvo e o canal pelo qual deseja ser notificado. Os alertas do item são exibidos e mantidos na seção "Alertas de preço" da tela de detalhes do item.

- **Requisitos associados:** RF05 – Configuração de Alertas
- **Cenários:**
  - Cenário 01 – Criar alerta de preço
  - Cenário 02 – Alterar ou reativar alerta de preço
  - Cenário 03 – Excluir alerta de preço

## CU07 - C1 – Manter Alerta - Cenário Criar Alerta de Preço

- **Objetivo:** Registrar um alerta que notifica o usuário quando o valor de mercado de um item da sua lista de favoritos atingir o preço-alvo definido.
- **Pré-condição:** O usuário deve estar autenticado e com a tela de detalhes do item aberta.
- **Pós-condição:** O alerta é registrado com a situação "Ativo".
- **Atores:** Usuário
- **Ativação:** O usuário aciona a opção "Criar alerta" na seção "Alertas de preço" da tela de detalhes do item.

### Fluxo principal

1. O usuário aciona a opção "Criar alerta" na tela de detalhes do item.
2. O sistema verifica se o item está na lista de favoritos do usuário.
3. O sistema verifica a quantidade de alertas ativos do usuário (RN08).
4. O sistema exibe o formulário do alerta, com o valor de mercado atual do item como referência (RN06).
5. O usuário informa o tipo de gatilho ("Compra", para ser avisado quando o preço cair até o alvo, ou "Venda", quando o preço subir até o alvo), o preço-alvo em Ouro, Prata e Cobre e o canal de notificação (tela, e-mail ou ambos).
6. O sistema valida os dados informados.
7. O sistema converte o preço-alvo para Cobre (RN01) e registra o alerta com a situação "Ativo".
8. O sistema exibe a mensagem "Alerta criado com sucesso" e o alerta na seção "Alertas de preço".

### Fluxos alternativos

#### Fluxo Alternativo 1 - Item fora da lista de favoritos

- **1.1** No passo 2, o sistema identifica que o item não está na lista de favoritos do usuário.
- **1.2** O sistema exibe a mensagem: "Para criar um alerta, adicione o item aos favoritos", com a opção de favoritá-lo.
- **1.3** O usuário favorita o item (CU06 - Cenário 01).
- **1.4** Retorna ao passo 3 do fluxo principal.

#### Fluxo Alternativo 2 - Limite de alertas atingido

- **2.1** No passo 3, o sistema identifica que o usuário já possui 20 alertas ativos (RN08).
- **2.2** O sistema exibe a mensagem: "Você atingiu o limite de 20 alertas ativos. Exclua um alerta para criar outro".
- **2.3** Fim.

#### Fluxo Alternativo 3 - Dados inválidos

- **3.1** No passo 6, o sistema identifica que o preço-alvo não foi informado ou não é maior que zero, ou que o tipo de gatilho ou o canal de notificação não foi escolhido.
- **3.2** O sistema exibe a mensagem: "Informe o tipo de gatilho, um preço-alvo maior que zero e o canal de notificação".
- **3.3** Retorna ao passo 5 do fluxo principal.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** No passo 7, o sistema não consegue gravar o alerta devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema exibe a mensagem: "Não foi possível salvar o alerta no momento. Tente novamente mais tarde".
- **1.3** Fim.

## CU07 - C2 – Manter Alerta - Cenário Alterar ou Reativar Alerta de Preço

- **Objetivo:** Permitir que o usuário altere o tipo de gatilho, o preço-alvo ou o canal de notificação de um alerta, ou reative um alerta que já foi disparado.
- **Pré-condição:** O usuário deve estar autenticado e possuir o alerta na seção "Alertas de preço" do item.
- **Pós-condição:** O alerta é atualizado com a situação "Ativo".
- **Atores:** Usuário
- **Ativação:** O usuário aciona a opção "Editar" de um alerta na seção "Alertas de preço" da tela de detalhes do item.

### Fluxo principal

1. O usuário aciona a opção "Editar" de um alerta.
2. O sistema exibe o formulário com os dados atuais do alerta e o valor de mercado atual do item (RN06).
3. O usuário altera o tipo de gatilho, o preço-alvo ou o canal de notificação.
4. O sistema valida os dados informados.
5. O sistema atualiza o alerta, com a situação "Ativo".
6. O sistema exibe a mensagem "Alerta atualizado com sucesso".

### Fluxos alternativos

#### Fluxo Alternativo 1 - Reativação de alerta disparado

- **1.1** No passo 1, o sistema identifica que o alerta está com a situação "Disparado".
- **1.2** O sistema verifica a quantidade de alertas ativos do usuário (RN08).
- **1.3** Retorna ao passo 2 do fluxo principal.

#### Fluxo Alternativo 2 - Limite de alertas atingido

- **2.1** No passo 1.2 do Fluxo Alternativo 1, o sistema identifica que o usuário já possui 20 alertas ativos (RN08).
- **2.2** O sistema exibe a mensagem: "Você atingiu o limite de 20 alertas ativos. Exclua um alerta para reativar este".
- **2.3** Fim.

#### Fluxo Alternativo 3 - Dados inválidos

- **3.1** No passo 4, o sistema identifica que o preço-alvo não foi informado ou não é maior que zero, ou que o tipo de gatilho ou o canal de notificação não foi escolhido.
- **3.2** O sistema exibe a mensagem: "Informe o tipo de gatilho, um preço-alvo maior que zero e o canal de notificação".
- **3.3** Retorna ao passo 3 do fluxo principal.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** No passo 5, o sistema não consegue gravar o alerta devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema mantém os dados anteriores do alerta e exibe a mensagem: "Não foi possível salvar o alerta no momento. Tente novamente mais tarde".
- **1.3** Fim.

## CU07 - C3 – Manter Alerta - Cenário Excluir Alerta de Preço

- **Objetivo:** Remover um alerta de preço do usuário.
- **Pré-condição:** O usuário deve estar autenticado e possuir o alerta na seção "Alertas de preço" do item.
- **Pós-condição:** O alerta é removido do banco de dados.
- **Atores:** Usuário
- **Ativação:** O usuário aciona a opção "Excluir" de um alerta na seção "Alertas de preço" da tela de detalhes do item.

### Fluxo principal

1. O usuário aciona a opção "Excluir" de um alerta.
2. O sistema solicita a confirmação: "Deseja excluir este alerta?".
3. O usuário confirma a exclusão.
4. O sistema remove o alerta.
5. O sistema exibe a mensagem "Alerta excluído com sucesso" e atualiza a seção "Alertas de preço".

### Fluxos alternativos

#### Fluxo Alternativo 1 - Exclusão cancelada

- **1.1** No passo 3, o usuário cancela a exclusão.
- **1.2** O sistema mantém o alerta.
- **1.3** Fim.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** No passo 4, o sistema não consegue remover o alerta devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema mantém o alerta e exibe a mensagem: "Não foi possível excluir o alerta no momento. Tente novamente mais tarde".
- **1.3** Fim.

## Observações para a implementação

- **RN08 – Cota de Alertas por Usuário (texto novo):** O sistema restringe a criação de rastreadores de preços visando performance. Cada usuário pode manter no máximo 20 alertas de preço ativos. Os alertas já disparados não contam para o limite enquanto não forem reativados pelo usuário. (RF05)
- **Tabela:** `alerta_preco` (id, usuário, item, tipo `COMPRA`/`VENDA`, preço-alvo em Cobre, canal `WEB`/`EMAIL`/`AMBOS`, situação `ATIVO`/`DISPARADO`, criado em, atualizado em, disparado em), com exclusão em cascata pela conta (RN20) e pelo favorito (CU06-C2). A chave estrangeira já foi preparada no CU01. Tipos, como no MR (seção 7.2 do TC): id_alerta INTEGER (PK), id_usuario INTEGER (FK), item_id INTEGER, tipo VARCHAR(10), preco_alvo BIGINT, canal VARCHAR(5), situacao VARCHAR(9), criado_em e atualizado_em TIMESTAMPTZ, disparado_em TIMESTAMPTZ (nulo).
- **Cota (RN08):** 20 alertas com a situação `ATIVO` por usuário (`ALERTAS_MAXIMO_ATIVOS`). Alertas disparados não contam até serem reativados.
- **API (sugestão):** `GET /items/{item_id}/alerts`, `POST /items/{item_id}/alerts`, `PUT /alerts/{id}` (alterar e reativar) e `DELETE /alerts/{id}`, todos autenticados e só sobre os alertas do próprio usuário.
- **Tela:** seção "Alertas de preço" na tela do item (CU04), só para o usuário autenticado; o preço-alvo é digitado em Ouro, Prata e Cobre e convertido para Cobre no backend (RN01).
- **Testes (um por fluxo):** `test_cu07_c1_fluxo_principal_cria_alerta`, `test_cu07_c1_fa1_item_fora_dos_favoritos`, `test_cu07_c1_fa2_limite_de_alertas_rn08`, `test_cu07_c1_fa3_dados_invalidos`, `test_cu07_c1_fe1_falha_no_banco`, `test_cu07_c2_fluxo_principal_altera_alerta`, `test_cu07_c2_fa1_reativa_alerta_disparado`, `test_cu07_c2_fa2_limite_na_reativacao_rn08`, `test_cu07_c2_fa3_dados_invalidos`, `test_cu07_c2_fe1_falha_mantem_dados`, `test_cu07_c3_fluxo_principal_exclui_alerta`, `test_cu07_c3_fa1_exclusao_cancelada`, `test_cu07_c3_fe1_falha_mantem_alerta`, `test_cu07_so_o_dono_altera_e_exclui_o_alerta`.
