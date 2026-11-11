# CU05 – Consultar Previsão Preditiva

> Texto igual ao do TC (seção 6.4.5), conferido em 11/11/2026.

**Situação no código:** não implementado. Usa as predições diárias gravadas pelo CU11 - Cenário 03 (commit `83bebfb`). Pedido de implementação: `estudos/lstm/pedido-cu05.md` (revisado em 11/11/2026).

## Descrição

Este caso de uso tem como principal função permitir que o usuário visualize, no gráfico do histórico de um item, a projeção do preço para os próximos 7 dias calculada pelo modelo preditivo, acompanhada do erro típico das previsões do item. A projeção só é exibida quando está liberada para o item; caso contrário, o sistema informa o motivo da indisponibilidade.

- **Requisitos associados:** RF04 – Projeção Preditiva
- **Cenários:**
  - Cenário 01 – Exibir projeção de preços
  - Cenário 02 – Inspecionar um dia da projeção
  - Cenário 03 – Ocultar ou exibir a projeção

## Regras de negócio

Conforme o quadro do RF04, com a RN13 acrescentada (ver "Mudanças no RF04", ao final):

- **RN01 – Padronização de Moeda Base:** os valores financeiros são armazenados em Cobre (1 Ouro = 10.000 Cobre; 1 Prata = 100 Cobre) e exibidos convertidos em Ouro, Prata e Cobre.
- **RN02 – Filtro de Liquidez para Modelagem Preditiva:** só itens com quantidade média ofertada superior a 50 unidades nos últimos 7 dias recebem projeção.
- **RN10 – Limiar de Precisão Preditiva:** a projeção só é exibida se o MdAPE do item no período de teste for de no máximo 15%, menor que o do modelo ingênuo e medido em pelo menos 30 dias de previsões avaliadas.
- **RN13 – Snapshot de Estado (Auditoria ML):** a projeção de um item cujo erro nos últimos 7 dias ultrapassa o limiar da RN10 é bloqueada até o próximo retreinamento.
- **RN27 – Histórico Mínimo para Projeção:** o item precisa de ao menos 60 dias de histórico diário.

## CU05 - C1 – Consultar Previsão Preditiva - Cenário Exibir Projeção de Preços

- **Objetivo:** Exibir, em continuação ao histórico do item, a projeção do menor preço diário para os próximos 7 dias, com a tabela dos valores previstos e o erro típico das previsões do item.
- **Pré-condição:** O histórico do item deve estar exibido na tela.
- **Pós-condição:** O usuário visualiza a projeção do item ou o motivo da sua indisponibilidade.
- **Atores:** Usuário
- **Ativação:** O usuário acessa a tela de detalhes de um item.

### Fluxo principal

1. O sistema exibe o histórico de preços do item.
2. O sistema verifica a situação da projeção do item.
3. O sistema recupera as predições mais recentes do item, geradas pelo modelo vigente, considerando somente os dias previstos a partir da data atual.
4. O sistema converte os preços previstos de Cobre para Ouro, Prata e Cobre.
5. O sistema exibe no gráfico a linha da projeção, tracejada e com cor distinta, a partir do último preço diário do item, e a identifica na legenda como "Projeção (menor preço diário)".
6. O sistema exibe, abaixo do gráfico, a tabela da projeção, com a data e o preço previsto de cada dia e a variação em relação ao último preço diário.
7. O sistema exibe, junto à projeção, a data em que ela foi gerada, o erro típico das previsões do item ("Erro mediano de X% nas previsões deste item") e o aviso "A projeção é uma estimativa estatística e não garante o preço futuro".

### Fluxos alternativos

#### Fluxo Alternativo 1 - Modelo preditivo não treinado

- **1.1** No passo 2, o sistema identifica que ainda não existe um modelo preditivo vigente para a região do item.
- **1.2** O sistema exibe, no lugar da projeção, a mensagem: "A projeção de preços ainda não está disponível".
- **1.3** Fim.

#### Fluxo Alternativo 2 - Item não elegível à projeção

- **2.1** No passo 2, o sistema identifica que o item não atende a um dos critérios de elegibilidade à projeção (RN02 ou RN27).
- **2.2** O sistema exibe, no lugar da projeção, a mensagem do critério não atendido: "Projeção indisponível: este item tem pouca quantidade ofertada para uma previsão confiável" (RN02) ou "Projeção indisponível: este item ainda não tem histórico suficiente para a previsão" (RN27).
- **2.3** Fim.

#### Fluxo Alternativo 3 - Projeção reprovada na avaliação

- **3.1** No passo 2, o sistema identifica que a projeção do item está bloqueada por não atingir o limiar mínimo de acurácia (RN10).
- **3.2** O sistema exibe, no lugar da projeção, a mensagem: "Projeção indisponível: as previsões deste item não atingiram a precisão mínima exigida".
- **3.3** Fim.

#### Fluxo Alternativo 4 - Projeção em avaliação

- **4.1** No passo 2, o sistema identifica que o item ainda não possui o mínimo de dias de previsões avaliadas (RN10).
- **4.2** O sistema exibe, no lugar da projeção, a mensagem: "A projeção deste item está em avaliação e será exibida quando houver dados suficientes para medir a sua precisão".
- **4.3** Fim.

#### Fluxo Alternativo 5 - Projeção suspensa por desempenho

- **5.1** No passo 2, o sistema identifica que a projeção do item foi bloqueada porque o erro das previsões recentes ultrapassou o limiar mínimo de acurácia (RN13).
- **5.2** O sistema exibe, no lugar da projeção, a mensagem: "A projeção deste item está suspensa porque as previsões recentes ficaram abaixo da precisão mínima. Ela será reavaliada na próxima atualização do modelo".
- **5.3** Fim.

#### Fluxo Alternativo 6 - Projeção não disponível

- **6.1** No passo 3, o sistema não encontra predições do modelo vigente para o item com dias previstos a partir da data atual, como logo após a liberação da projeção ou quando a predição do item não pôde ser gerada nas últimas atualizações diárias.
- **6.2** O sistema exibe, no lugar da projeção, a mensagem: "A projeção deste item não está disponível no momento".
- **6.3** Fim.

#### Fluxo Alternativo 7 - Projeção desatualizada

- **7.1** No passo 3, o sistema identifica que as predições mais recentes do item foram geradas há mais de 2 dias.
- **7.2** O sistema exibe somente os dias previstos a partir da data atual, a partir do preço diário do dia de referência da projeção, com o alerta visual "Projeção desatualizada".
- **7.3** Retorna ao passo 4 do fluxo principal.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** Nos passos 2 ou 3, o sistema não consegue recuperar as informações devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema mantém o histórico exibido e mostra, no lugar da projeção, a mensagem: "Não foi possível carregar a projeção no momento. Tente novamente mais tarde".
- **1.3** Fim.

## CU05 - C2 – Consultar Previsão Preditiva - Cenário Inspecionar um Dia da Projeção

- **Objetivo:** Fornecer ao usuário o preço previsto para um dia específico da projeção.
- **Pré-condição:** A projeção do item deve estar exibida no gráfico (Cenário 01).
- **Pós-condição:** Os valores previstos do dia focado são exibidos na tela.
- **Atores:** Usuário
- **Ativação:** O usuário sobrepõe o cursor do mouse (ou toca, em dispositivos móveis) sobre um ponto da linha da projeção ou sobre uma linha da tabela da projeção.

### Fluxo principal

1. O usuário repousa o cursor sobre um ponto da linha da projeção ou sobre uma linha da tabela da projeção.
2. O sistema identifica o dia previsto correspondente.
3. O sistema destaca o ponto no gráfico e a linha correspondente na tabela.
4. O sistema exibe um tooltip contendo a data prevista, com a indicação "dia inteiro", o preço previsto convertido em Ouro, Prata e Cobre, a variação em relação ao último preço diário e a indicação "Projeção".

### Fluxos alternativos

#### Fluxo Alternativo 1 - Ponto de partida da projeção

- **1.1** No passo 2, o sistema identifica que o ponto focado é o de partida da projeção, que corresponde ao último preço diário observado.
- **1.2** O sistema exibe o tooltip do histórico (CU04 - Cenário 03).
- **1.3** Fim.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na formatação da moeda base

- **1.1** O sistema tenta converter o preço previsto de Cobre para Ouro e Prata, mas encontra um valor atípico que gera exceção de conversão.
- **1.2** O sistema previne a quebra da interface e omite a exibição do tooltip para aquele dia.
- **1.3** O sistema registra a anomalia silenciosamente no log do console do navegador, e o usuário pode inspecionar outro dia normalmente.
- **1.4** Fim.

## CU05 - C3 – Consultar Previsão Preditiva - Cenário Ocultar ou Exibir a Projeção

- **Objetivo:** Permitir que o usuário oculte ou volte a exibir a projeção, para analisar somente o histórico do item.
- **Pré-condição:** A projeção do item deve estar disponível (Cenário 01).
- **Pós-condição:** O gráfico é exibido com ou sem a projeção, conforme a escolha do usuário.
- **Atores:** Usuário
- **Ativação:** O usuário aciona o controle "Projeção" do gráfico.

### Fluxo principal

1. O usuário aciona o controle "Projeção" com a projeção visível.
2. O sistema oculta a linha da projeção e a tabela da projeção.
3. O sistema recalcula a escala dos eixos do gráfico considerando somente o histórico.
4. O sistema mantém a escolha enquanto o usuário navegar pelas telas de itens, na mesma sessão do navegador.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Exibir novamente a projeção

- **1.1** No passo 1, o usuário aciona o controle "Projeção" com a projeção oculta.
- **1.2** O sistema exibe novamente a linha e a tabela da projeção.
- **1.3** O sistema recalcula a escala dos eixos do gráfico incluindo os 7 dias da projeção.
- **1.4** O sistema mantém a escolha enquanto o usuário navegar pelas telas de itens, na mesma sessão do navegador.
- **1.5** Fim.

## Mudanças no RF04 (Quadro 12 do TC)

- **Regras de negócio:** acrescentar a RN13, que bloqueia a exibição quando a projeção degrada. Fica: RN02; RN03; RN10; RN13; RN17; RN27. No Quadro 07, a RN13 passa a citar o RF04, e o mapeamento da seção 3.6.2 também ganha a RN13 na linha do RF04.
- **Variáveis:** hoje só há "ID do Item" e "Data da Projeção". Proposta:

  | Variável | Tipo de dado | Tamanho | Obrigatório | Domínio |
  | --- | --- | --- | --- | --- |
  | ID do Item | Inteiro | - | Sim | Numérico |
  | Data da Projeção | Data | - | Sim | DD/MM/AAAA |
  | Data Prevista | Data | - | Sim | Os 7 dias seguintes à data da projeção |
  | Preço Previsto | Inteiro | - | Sim | Valor em Cobre (RN01) |
  | Erro Típico do Item (MdAPE) | Decimal | - | Sim | Percentual |
  | Situação da Projeção do Item | Texto | 9 | Sim | 'Liberada', 'Bloqueada' ou 'Ignorada' |

- **Protótipo:** o RF02 e o RF03 têm protótipo no TC (Figuras 03 e 04). O RF04 deve ganhar o seu (seção 5.4.2), com a linha da projeção e a tabela.

## Observações para a implementação

- **Série e preço de partida:** a projeção é a do menor preço diário (série diária da Undermine, RN16), a mesma que o modelo usa. A linha começa no último preço diário do item, e não no valor de mercado do cabeçalho (RN06, primeiro quartil da coleta horária), que fica acima do menor preço. Por isso a legenda diz "menor preço diário". A variação da tabela e do tooltip é calculada sobre esse último preço diário.
- **Qual série:** a mesma região do histórico (hoje, US). Para as commodities, é a série de commodities da região. Para itens de reino com mais de uma série, vale a que tem projeção liberada; havendo mais de uma, a de maior quantidade média ofertada.
- **Predições exibidas:** as de `data_previsao` mais recente do item, geradas pela versão vigente do modelo, só com `data_prevista` a partir da data atual (UTC). São as linhas de `predicao_diaria` gravadas pelo CU11-C3. Normalmente são os 7 dias; numa projeção desatualizada (FA7), sobram menos.
- **Por que o FA6 acontece:** o C3 só prevê o item quando a janela de 30 dias termina no dia de referência e é válida. Um dia com o preço descartado pela RN03, ou sem preço, invalida a janela até sair dela. Na primeira consolidação (19/10/2026), 79 dos 1.307 liberados ficaram sem previsão por isso. Enquanto a última previsão ainda tiver dias futuros, vale o FA7; depois, o FA6.
- **Variação:** é calculada sobre o preço diário do dia de referência da projeção (`data_previsao`), que é o ponto de partida da linha.
- **Erro típico:** é o `mdape` de `projecao_item`, da última avaliação do item, arredondado para um número inteiro.
- **Situação e mensagem:** como no CU04, o texto vem do backend, e o frontend não tem regra de negócio.

  | Situação no banco | Fluxo |
  | --- | --- |
  | sem modelo vigente na região | FA1 |
  | item fora de `projecao_item`, ou "deixou de ser elegível" | FA2, com o critério atual recalculado (RN02 ou RN27) |
  | `IGNORADA` ("série insuficiente") | FA2, com a mensagem da RN27 |
  | `BLOQUEADA`, "acima do limiar" ou "não supera o ingênuo" | FA3 |
  | `BLOQUEADA`, "avaliação insuficiente" | FA4 |
  | `BLOQUEADA`, "degradação" | FA5 |
  | `LIBERADA`, sem predição da versão vigente com `data_prevista` a partir de hoje | FA6 |
  | `LIBERADA`, com `data_previsao` de mais de 2 dias e algum dia previsto a partir de hoje | FA7 |

- **API (sugestão):** `GET /items/{item_id}/projection`, sem autenticação, como o histórico. A resposta traz a situação, a mensagem, a data da projeção, o erro típico, o último preço diário (data e valor), as 7 predições (data prevista, preço em Cobre e variação) e o aviso de desatualizada. Uma falha de banco responde 503 com a mensagem do FE1.
- **Gráfico:** a linha da projeção é tracejada e tem cor própria, e a escala do eixo inclui os 7 dias. Ao trocar a janela de tempo (CU04-C2), a projeção continua presa ao fim do histórico. A escolha de ocultar (C3) fica guardada na sessão do navegador.
- **Valores configuráveis:** `PROJECAO_DESATUALIZADA_DIAS` = 2 (FA7).

### Testes (um por fluxo)

- C1:
  - `test_cu05_c1_fluxo_principal_exibe_a_projecao_dos_proximos_7_dias`
  - `test_cu05_c1_fa1_modelo_nao_treinado`
  - `test_cu05_c1_fa2_item_nao_elegivel_rn02_rn27`
  - `test_cu05_c1_fa3_projecao_reprovada_rn10`
  - `test_cu05_c1_fa4_projecao_em_avaliacao`
  - `test_cu05_c1_fa5_projecao_suspensa_rn13`
  - `test_cu05_c1_fa6_projecao_nao_disponivel`
  - `test_cu05_c1_fa7_projecao_desatualizada`
  - `test_cu05_c1_fe1_falha_no_banco`
- C2:
  - `test_cu05_c2_fluxo_principal_tooltip_do_dia_previsto`
  - `test_cu05_c2_fa1_ponto_de_partida_usa_o_tooltip_do_historico`
  - `test_cu05_c2_fe1_falha_na_conversao_omite_o_tooltip`
- C3:
  - `test_cu05_c3_fluxo_principal_oculta_a_projecao`
  - `test_cu05_c3_fa1_exibe_novamente_a_projecao`
