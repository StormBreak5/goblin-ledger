# CU04 – Visualizar Histórico

> Fonte: documento do TC *TCII-N2-IND-Itzac Albertin-Guiliano Rangel Alves* (Google Drive), exportado em 06/10/2026, já com as atualizações pós-implementação. O documento do TC é a fonte da verdade: se houver divergência, atualize este arquivo a partir dele.

**Situação no código (06/10/2026):** Implementado (C1 a C3), commits `5e43cb0`, `6e818f0`, `069ae95` e `debe195`. Testes no backend (`test_cu04_visualizar_historico.py`) e no frontend (`frontend/tests/cu04-visualizar-historico.test.tsx`).

## Descrição

Este caso de uso tem como principal função permitir que o usuário visualize gráficos interativos exibindo a série temporal histórica de preços e o volume de negociação de um item específico da Casa de Leilões.

- **Requisitos associados:** RF03 - Visualização de Histórico
- **Cenários:**
  - Cenário 01 - Renderizar histórico de preços
  - Cenário 02 - Alterar janela de tempo do gráfico
  - Cenário 03 - Inspecionar detalhes de um ponto temporal

## Regras de negócio dos requisitos associados

(Conforme o campo "Regras de Negócio" dos quadros dos RFs; texto completo em `docs/regras-de-negocio.md`.)

- **RN06 – Cálculo de Valor de Mercado:** O "Preço Atual" exibido no dashboard não deve ser o lance mais baixo isolado (Minimum Buyout), que pode ser uma anomalia temporal, mas sim o primeiro quartil (25%) dos preços dos leilões ativos daquele item, garantindo uma representação realista do custo de aquisição para o usuário. O primeiro quartil é ponderado pela quantidade de cada leilão e calculado sobre o preço unitário de compra imediata (Buyout); leilões que possuem somente lance (Bid) não entram no cálculo.
- **RN09 – Frescor dos Dados (Cache TTL):** O sistema deve classificar e alertar sobre a latência da informação exibida. Os dados são considerados desatualizados quando a última coleta do mercado do item ocorreu há mais de 24 horas ou quando a última coleta falhou (RN14).

## CU04 - C1 – Visualizar Histórico - Cenário Renderizar Histórico de Preços

- **Objetivo:** Exibir o dashboard gráfico contendo o histórico temporal e o preço de mercado atualizado do item selecionado.
- **Pré-condição:** O sistema deve possuir dados históricos do item ingeridos e consolidados no banco de dados.
- **Pós-condição:** O usuário visualiza o gráfico interativo renderizado.
- **Atores:** Usuário
- **Ativação:** O usuário seleciona um item a partir do resultado de uma busca ou da sua lista de favoritos.

### Fluxo principal

1. O usuário clica sobre o nome ou ícone de um item na interface.
2. O sistema recupera a série temporal de preços e o volume do item no banco de dados.
3. O sistema mostra o valor de mercado atual do item (RN06) e, como informação secundária, o menor preço atual na Casa de Leilões.
4. O sistema verifica a latência dos dados recuperados comparando com o último ciclo de ingestão da API oficial.
5. O sistema renderiza o gráfico interativo exibindo as linhas de tendência e as barras de volume para o usuário.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Dados Desatualizados

- **1.1** No passo 4, o sistema identifica que a última sincronização ocorreu há mais tempo que o limiar aceitável de 24 horas (RN09).
- **1.2** O sistema renderiza o gráfico normalmente com os últimos dados disponíveis.
- **1.3** O sistema exibe uma flag ou alerta visual na tela informando "Dados Desatualizados".
- **1.4** Retorna ao passo 5 do fluxo principal.

#### Fluxo Alternativo 2 - Item sem Histórico Registrado

- **2.1** No passo 2, o sistema não encontra registros de leilões passados para o item selecionado.
- **2.2** O sistema exibe a mensagem: "Ainda não há dados históricos coletados suficientes para este item".
- **2.3** Fim.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** O sistema não consegue recuperar as informações devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema exibe a mensagem: "Não foi possível carregar o histórico de mercado no momento. Tente novamente mais tarde".
- **1.3** Fim.

## CU04 - C2 – Visualizar Histórico - Cenário Alterar Janela de Tempo do Gráfico

- **Objetivo:** Atualizar a exibição gráfica para refletir um período temporal específico desejado pelo usuário ('14D', '30D', '90D', '365D' ou 'ALL').
- **Pré-condição:** O usuário já deve estar visualizando a tela de histórico do item.
- **Pós-condição:** O gráfico é atualizado refletindo a nova janela de tempo.
- **Atores:** Usuário
- **Ativação:** O usuário clica em um dos botões de filtro de tempo na interface do dashboard.

### Fluxo principal

1. O usuário clica no filtro de tempo desejado.
2. O sistema recorta a série temporal para adequar os dados ao período selecionado.
3. O sistema recalcula a escala dos eixos X (tempo) e Y (valores em Ouro) para acomodar a nova amostragem.
4. O gráfico é re-renderizado na tela de forma reativa.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Dados insuficientes para o período selecionado

- **1.1** O sistema processa o recorte da série temporal, mas identifica que o histórico do item armazenado no banco de dados não cobre a totalidade do período solicitado.
- **1.2** O sistema ajusta automaticamente a escala do eixo X (tempo) para o limite máximo de dias disponíveis.
- **1.3** O sistema exibe um aviso na tela: "Dados limitados. Exibindo todo o histórico disponível para o período selecionado. ".
- **1.4** Retorna ao passo 4 do fluxo principal.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha ao recuperar nova janela de tempo

- **1.1** O sistema não consegue processar a nova requisição devido a uma falha de comunicação com o backend ou banco de dados.
- **1.2** O sistema exibe uma mensagem de erro em formato de toast ou pop-up: "Erro ao carregar novos dados. Mantendo a visualização atual. ".
- **1.3** O sistema aborta a re-renderização e mantém o gráfico na janela de tempo que já estava carregada anteriormente.
- **1.4** Fim.

## CU04 - C3 – Visualizar Histórico - Cenário Inspecionar detalhes de um ponto temporal

- **Objetivo:** Fornecer ao usuário os valores exatos de mercado (preço e volume) de um momento histórico específico.
- **Pré-condição:** O gráfico já deve estar renderizado na tela.
- **Pós-condição:** Os dados exatos do ponto focado são exibidos na tela.
- **Atores:** Usuário
- **Ativação:** O usuário sobrepõe o cursor do mouse (ou toca, em dispositivos móveis) sobre um ponto específico da linha do gráfico.

### Fluxo principal

1. O usuário repousa o cursor sobre um nó de dados (ponto no tempo) na linha do gráfico.
2. O sistema captura a coordenada temporal apontada pelo usuário.
3. O sistema exibe um tooltip contendo a data, hora exata, no fuso horário do usuário (nos registros diários, a data e a indicação "dia inteiro"), e os valores convertidos em Cobre, Prata ou Ouro.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Ponto temporal com dados corrompidos ou parciais

- **1.1** O usuário foca em um ponto do gráfico onde houve uma falha de ingestão prévia da API, resultando na ausência da informação de volume, mas mantendo a de Preço.
- **1.2** O sistema captura os dados do nó, identificando valores nulos para certas métricas.
- **1.3** O sistema exibe o tooltip com as métricas existentes e substitui os dados faltantes pela sigla "N/D" (Não Disponível), para não causar confusão visual.
- **1.4** Retorna ao passo 3 do fluxo principal.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na formatação da moeda base

- **1.1** O sistema tenta processar a conversão da métrica salva em "Cobre" para a exibição amigável em "Ouro/Prata", mas encontra um valor atípico que gera exceção de conversão.
- **1.2** O sistema previne a quebra da interface e omite a exibição do tooltip para aquele ponto específico.
- **1.3** O sistema registra a anomalia silenciosamente no log do console do navegador e o usuário pode tentar inspecionar outro ponto normalmente.
- **1.4** Fim.

## Observações para a implementação

Decisões já implementadas (com a variável de ambiente que as controla) e o que continua pendente. Detalhes em `docs/decisoes-e-pendencias.md`. Onde houver conflito com o texto acima, vale o que está aqui e o documento do TC deve ser corrigido.

- "Dados Desatualizados" (C1-FA1, RN09): limiar de 24 horas (`DADOS_DESATUALIZADOS_HORAS`). A comparação é com o último ciclo do mercado do item (commodities no reino 32512). A sinalização também aparece quando o último ciclo falhou (RN14). Para a Ficha do WoW, vale a idade do último preço.
- Cabeçalho: valor de mercado (RN06) em destaque e menor preço logo abaixo. O menor preço não aparece quando é igual ao valor de mercado.
- Janelas: 14D, 30D, 90D, 365D e ALL. Um valor ilegível volta a 14D.
- "Dados limitados" (C2-FA1): aparece quando o primeiro ponto da série cai depois do início da janela, com tolerância de 1 dia; nunca aparece em ALL. Uma janela sem pontos, de um item com histórico antigo, usa o texto do C1-FA2.
- C2-FE1: a falha ao trocar de janela mostra um toast e mantém a janela anterior. A tela de erro do C1-FE1 só aparece na primeira carga.
- Dica do ponto (C3): data e hora no fuso de quem vê. O ponto diário representa o dia inteiro em UTC, por isso mostra a data em UTC e "dia inteiro". Volume ausente aparece como "N/D"; numa série sem volume (a Ficha), a linha não aparece. Uma conversão que falha omite a dica e registra no console.
- Os textos dos avisos vêm do backend (`avisos`), para o frontend não ter regra de negócio.
- A ativação a partir da lista de favoritos depende do CU06, que não está especificado.
- **Pendente (teste):** `test_cu04_c2_a_janela_sem_pontos_de_um_item_com_historico_antigo_usa_o_texto_do_fa2` aparece no plano de testes como "C2 FA2", mas o C2 não tem FA2. Renomear para deixar claro que ele usa o texto do C1-FA2 e regerar `docs/plano-de-testes-por-fluxo.md`.
