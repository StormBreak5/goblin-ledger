# CU08 – Manter Notificações

> Texto igual ao do TC (seção 6.4.8), conferido em 11/11/2026.

## Descrição

Este caso de uso tem como principal função verificar, a cada ciclo de ingestão dos dados de mercado, os alertas de preço ativos, disparar as notificações dos alertas atingidos pela interface web e por e-mail, conforme o canal escolhido pelo usuário, e permitir que o usuário consulte as suas notificações.

- **Requisitos associados:** RF06 – Disparo de Notificações Ativa
- **Cenários:**
  - Cenário 01 – Verificar alertas e disparar notificações
  - Cenário 02 – Enviar notificação por e-mail
  - Cenário 03 – Consultar notificações

## CU08 - C1 – Manter Notificações - Cenário Verificar Alertas e Disparar Notificações

- **Objetivo:** Identificar os alertas de preço cujo gatilho foi atingido pelo valor de mercado mais recente dos itens e registrar as notificações correspondentes.
- **Pré-condição:** Deve existir ao menos um alerta de preço com a situação "Ativo".
- **Pós-condição:** Os alertas atingidos ficam com a situação "Disparado" e as suas notificações ficam registradas.
- **Atores:** Usuário
- **Ativação:** O sistema conclui a consolidação de um ciclo de ingestão dos dados de mercado (CU09 - Cenário 03).

### Fluxo principal

1. O sistema conclui a consolidação de um ciclo de ingestão dos dados de mercado.
2. O sistema recupera os alertas ativos dos itens atualizados no ciclo.
3. O sistema recupera o valor de mercado atual de cada item (RN06).
4. O sistema verifica, para cada alerta, se o gatilho foi atingido (RN07).
5. O sistema registra a notificação do alerta atingido, com o item, o tipo de gatilho, o preço-alvo, o valor de mercado que o atingiu, o canal e a data e a hora.
6. O sistema altera a situação do alerta para "Disparado" (RN07).
7. O sistema encaminha as notificações com o canal e-mail para o envio (Cenário 02).
8. Após processar todos os alertas, o sistema registra em log a conclusão da verificação.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Nenhum alerta atingido

- **1.1** No passo 4, o sistema identifica que nenhum alerta foi atingido.
- **1.2** Retorna ao passo 8 do fluxo principal.

#### Fluxo Alternativo 2 - Item com volume anômalo

- **2.1** No passo 3, o sistema identifica que o registro do item no ciclo foi marcado como anomalia de volume (RN12).
- **2.2** O sistema não verifica os alertas do item nesse ciclo.
- **2.3** Retorna ao passo 3 do fluxo principal para os demais itens.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** Nos passos 2, 5 ou 6, o sistema não consegue acessar ou gravar os dados devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema desfaz os registros da verificação e registra a falha em log.
- **1.3** O sistema repete a verificação no próximo ciclo de ingestão.
- **1.4** Fim.

## CU08 - C2 – Manter Notificações - Cenário Enviar Notificação por E-mail

- **Objetivo:** Enviar ao e-mail cadastrado do usuário a notificação de um alerta disparado.
- **Pré-condição:** Deve existir uma notificação com o canal e-mail ainda não enviada (Cenário 01).
- **Pós-condição:** O e-mail é enviado e a notificação registra a data e a hora do envio.
- **Atores:** Usuário
- **Ativação:** O sistema registra uma notificação com o canal e-mail (Cenário 01).

### Fluxo principal

1. O sistema recupera as notificações com o canal e-mail ainda não enviadas.
2. O sistema monta a mensagem com o nome do item, o tipo de gatilho, o preço-alvo e o valor de mercado que o atingiu, convertidos em Ouro, Prata e Cobre (RN01), e o link para a tela de detalhes do item.
3. O sistema envia a mensagem ao e-mail cadastrado do usuário (RN18).
4. O sistema registra a data e a hora do envio na notificação.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Falha no envio do e-mail

- **1.1** No passo 3, o servidor de e-mail não aceita a mensagem.
- **1.2** O sistema mantém a notificação como pendente e tenta o envio novamente no próximo ciclo de ingestão.
- **1.3** Após a terceira tentativa sem sucesso, o sistema marca o envio da notificação como "Falhou" e registra a falha em log.
- **1.4** Fim.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** Nos passos 1 ou 4, o sistema não consegue acessar ou gravar os dados devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema registra a falha em log e processa as notificações pendentes no próximo ciclo de ingestão.
- **1.3** Fim.

## CU08 - C3 – Manter Notificações - Cenário Consultar Notificações

- **Objetivo:** Permitir que o usuário visualize as notificações dos seus alertas disparados e as marque como lidas.
- **Pré-condição:** O usuário deve estar autenticado.
- **Pós-condição:** O usuário visualiza as suas notificações, e as exibidas ficam marcadas como lidas.
- **Atores:** Usuário
- **Ativação:** O usuário aciona o ícone de sino no cabeçalho da aplicação.

### Fluxo principal

1. O sistema exibe no cabeçalho o ícone de sino com a quantidade de notificações não lidas do usuário.
2. O usuário aciona o ícone de sino.
3. O sistema recupera as notificações do usuário com o canal tela, da mais recente para a mais antiga.
4. O sistema exibe a lista das notificações, com o item, o tipo de gatilho, o preço-alvo, o valor de mercado que o atingiu e a data e a hora, destacando as não lidas.
5. O sistema marca as notificações exibidas como lidas e zera o contador do ícone de sino.
6. O sistema exibe a tela de detalhes do item da notificação que o usuário selecionar.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Nenhuma notificação

- **1.1** No passo 3, o sistema não encontra notificações do usuário.
- **1.2** O sistema exibe a mensagem: "Você não tem notificações".
- **1.3** Fim.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** Nos passos 3 ou 5, o sistema não consegue acessar ou gravar os dados devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema exibe a mensagem: "Não foi possível carregar as notificações no momento. Tente novamente mais tarde".
- **1.3** Fim.

## Observações para a implementação

- **RN07 – Gatilho e Disparo Único do Alerta:** Um alerta de compra é atingido quando o valor de mercado do item (RN06) for igual ou inferior ao preço-alvo, e um alerta de venda, quando for igual ou superior ao preço-alvo. Os alertas ativos são verificados a cada ciclo de ingestão dos dados de mercado, exceto os dos itens cujo registro no ciclo foi marcado como anomalia de volume (RN12). Ao ser atingido, o alerta gera uma única notificação e passa à situação "Disparado", na qual permanece até ser reativado pelo usuário, evitando notificações repetidas enquanto o preço se mantiver além do alvo. (RF05, RF06)
- **Tabela:** `notificacao` (id, alerta, usuário, item, tipo, preço-alvo, valor de mercado que atingiu, canal, data e hora do disparo, lida em, envio do e-mail: pendente/enviado/falhou, tentativas, enviado em), com exclusão em cascata pela conta (RN20). Tipos, como no MR (seção 7.2 do TC): id_notificacao INTEGER (PK), id_alerta INTEGER (FK), id_usuario INTEGER (FK), item_id INTEGER, tipo VARCHAR(10), preco_alvo e valor_mercado BIGINT, canal VARCHAR(20), disparada_em TIMESTAMPTZ, lida_em TIMESTAMPTZ (nulo), envio_email VARCHAR(8) (nulo quando o canal é só tela), tentativas_email SMALLINT, enviada_em TIMESTAMPTZ (nulo).
- **Disparo (C1):** chamado pelo worker ao fim de cada ciclo consolidado do CU09-C3, na mesma rotina, com os itens do ciclo. Regra do gatilho na RN07; itens com anomalia de volume (RN12) no ciclo ficam de fora.
- **E-mail (C2):** reaproveita o serviço de e-mail do CU02-C2 (Mailpit no ambiente local). Até 3 tentativas (`NOTIFICACAO_EMAIL_TENTATIVAS`), uma por ciclo.
- **Tela (C3):** sino no cabeçalho para o usuário autenticado, com o contador de não lidas; a lista abre num painel. O contador é consultado ao carregar a página e a cada 5 minutos.
- **API (sugestão):** `GET /notifications` (lista, marca as exibidas como lidas) e `GET /notifications/unread-count`, autenticados.
- **Testes (um por fluxo):** `test_cu08_c1_fluxo_principal_dispara_alerta_de_compra_e_de_venda_rn07`, `test_cu08_c1_fa1_nenhum_alerta_atingido`, `test_cu08_c1_fa2_item_com_volume_anomalo_rn12`, `test_cu08_c1_fe1_falha_desfaz_a_verificacao`, `test_cu08_c2_fluxo_principal_envia_email_rn18`, `test_cu08_c2_fa1_falha_no_envio_tenta_ate_3_vezes`, `test_cu08_c2_fe1_falha_no_banco`, `test_cu08_c3_fluxo_principal_lista_e_marca_como_lidas`, `test_cu08_c3_fa1_nenhuma_notificacao`, `test_cu08_c3_fe1_falha_no_banco`, `test_rn07_alerta_dispara_uma_unica_vez`.
