# CU09 – Cadastrar Dados de Mercado

> Fonte: documento do TC *TCII-N2-IND-Itzac Albertin-Guiliano Rangel Alves* (Google Drive), exportado em 06/10/2026, já com as atualizações pós-implementação. O documento do TC é a fonte da verdade: se houver divergência, atualize este arquivo a partir dele.

**Situação no código (06/10/2026):** Implementado (C1 a C4), com a tela do Admin; commits `37ac6f2`, `e91f0c1` e `cb3173c`, mais as correções `7bf596e` e `cb7c37c`. Testes em `backend/tests/integration/test_cu09_*.py` e `backend/tests/unit/test_cu09_*.py`.

## Descrição

Este caso de uso tem como principal função coletar periodicamente os dados de leilões da Casa de Leilões por meio do Provider, sanitizá-los, padronizá-los e consolidá-los no banco de dados, mantendo atualizada a base que alimenta a busca, a visualização de histórico e o treinamento do modelo preditivo.

- **Requisitos associados:** RF07 – Ingestão de Dados via Providers; RF10 – Sanitização e Padronização de Dados
- **Cenários:**
  - Cenário 01 – Coletar dados de mercado
  - Cenário 02 – Sanitizar e padronizar os dados
  - Cenário 03 – Consolidar e persistir os dados
  - Cenário 04 – Executar ingestão manual

## Regras de negócio dos requisitos associados

(Conforme o campo "Regras de Negócio" dos quadros dos RFs; texto completo em `docs/regras-de-negocio.md`.)

- **RN01 – Padronização de Moeda Base:** O sistema deve somente armazenar valores financeiros em banco de dados na unidade "Cobre" (inteiro absoluto). 1 Ouro = 10000 Cobre; 1 Prata = 100 Cobre.
- **RN04 – Janela de Retenção e Expiração de Dados:** Leilões extraídos da API que não tenham sido atualizados nos últimos 48 horas (tempo máximo de duração de um leilão no jogo) devem ser classificados como "Expirados" ou "Vendidos", encerrando sua influência na cotação em tempo real, mas sendo mantidos no banco de dados sumarizado para compor o histórico de longo prazo. Os leilões classificados como "Expirados" ou "Vendidos" permanecem no detalhamento de leilões por 7 dias; após esse prazo, permanecem somente no histórico consolidado.
- **RN05 – Ciclo de Consumo da API (Restrição de Rate Limit):** O sistema não pode realizar requisições à API oficial da Blizzard Entertainment em intervalos menores que 60 minutos para o mesmo endpoint de Auction House, respeitando as políticas de uso da desenvolvedora e garantindo que o IP do servidor não sofra bloqueios temporários.
- **RN06 – Cálculo de Valor de Mercado:** O "Preço Atual" exibido no dashboard não deve ser o lance mais baixo isolado (Minimum Buyout), que pode ser uma anomalia temporal, mas sim o primeiro quartil (25%) dos preços dos leilões ativos daquele item, garantindo uma representação realista do custo de aquisição para o usuário. O primeiro quartil é ponderado pela quantidade de cada leilão e calculado sobre o preço unitário de compra imediata (Buyout); leilões que possuem somente lance (Bid) não entram no cálculo.
- **RN09 – Frescor dos Dados (Cache TTL):** O sistema deve classificar e alertar sobre a latência da informação exibida. Os dados são considerados desatualizados quando a última coleta do mercado do item ocorreu há mais de 24 horas ou quando a última coleta falhou (RN14).
- **RN11 – Validação de Domínio Geográfico:** O sistema só aceita o cadastro de contas e a ingestão de dados de mercado das regiões Ocidentais: US e EU.
- **RN12 – Filtro de Anomalia de Volume:** O sistema deve identificar injeções artificiais de itens por bots. É considerado anômalo o volume de um item superior a 10 vezes a mediana dos volumes dos 7 dias anteriores, com piso de 100 unidades e com no mínimo 24 registros anteriores. O registro é marcado como anomalia e mantido no banco de dados.
- **RN14 – Isolamento de Falhas do Provider:** Caso o Provider de um jogo específico apresente falha de comunicação ou retorno de erro 5xx prolongado, o sistema não deve interromper o dashboard principal, devendo exibir uma flag de 'Dados Desatualizados' para o mercado daquele Provider específico.

## CU09 - C1 – Cadastrar Dados de Mercado - Cenário Coletar Dados de Mercado

- **Objetivo:** Obter da API oficial do provedor do jogo, por meio do Provider, os dados mais recentes de leilões dos reinos monitorados.
- **Pré-condição:** Os Providers devem estar configurados com as credenciais de acesso à API e com a relação de jogos e reinos a serem monitorados.
- **Pós-condição:** O payload bruto de leilões é coletado e encaminhado para a etapa de sanitização.
- **Atores:** Provider
- **Ativação:** O agendador de tarefas dispara a rotina de ingestão ao completar o intervalo de coleta.

### Fluxo principal

1. O agendador de tarefas dispara a rotina de ingestão.
2. O sistema verifica se o intervalo mínimo de 60 minutos desde a última requisição ao endpoint da Casa de Leilões foi respeitado.
3. O Provider obtém o token de acesso junto à API do provedor do jogo.
4. O Provider requisita os dados de leilões de cada reino monitorado das regiões US e EU.
5. O Provider obtém o payload completo de leilões de cada reino.
6. O sistema registra a data e a hora da coleta.
7. O Provider encaminha o payload bruto para a etapa de sanitização (Cenário 02).

### Fluxos alternativos

#### Fluxo Alternativo 1 - Intervalo mínimo não atingido

- **1.1** No passo 2, o sistema identifica que a última requisição ao endpoint ocorreu há menos de 60 minutos.
- **1.2** O sistema cancela a execução e reagenda a coleta para o próximo ciclo.
- **1.3** Fim.

#### Fluxo Alternativo 2 - Reino fora do domínio geográfico

- **2.1** No passo 4, o sistema identifica um reino configurado que não pertence às regiões US ou EU.
- **2.2** O sistema ignora o reino e registra a ocorrência em log.
- **2.3** Retorna ao passo 4 do fluxo principal para os demais reinos.

#### Fluxo Alternativo 3 - Recomposição do histórico após falha prolongada

- **3.1** No passo 1, o sistema identifica que nenhuma fonte coletou dados de mercado com sucesso nas últimas 48 horas.
- **3.2** O sistema recompõe o histórico do período pela Undermine Exchange (CU10 - Cenário 01) antes de prosseguir com o ciclo, sem repetir a recomposição em menos de 6 horas.
- **3.3** Retorna ao passo 2 do fluxo principal.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com a API

- **1.1** Nos passos 3, 4 ou 5, a API retorna erro de servidor (5xx) ou não responde dentro do tempo limite.
- **1.2** O Provider realiza novas tentativas de requisição, até três vezes, com esperas de 5, 15 e 45 segundos, somente para erros de rede e 5xx.
- **1.3** Persistindo a falha, o sistema isola o erro, mantém os dados do ciclo anterior e ativa a sinalização "Dados Desatualizados" para o mercado do Provider.
- **1.4** O sistema registra a falha em log.
- **1.5** Fim.

## CU09 - C2 – Cadastrar Dados de Mercado - Cenário Sanitizar e Padronizar os Dados

- **Objetivo:** Transformar o payload bruto recebido do Provider em registros íntegros e padronizados, prontos para o armazenamento persistente.
- **Pré-condição:** O payload bruto deve ter sido coletado pelo Provider (Cenário 01).
- **Pós-condição:** Os registros de leilões são padronizados em Cobre, livres de anomalias estruturais, e encaminhados para consolidação.
- **Atores:** Provider
- **Ativação:** O sistema recebe o payload bruto encaminhado pelo Provider.

### Fluxo principal

1. O sistema valida a estrutura do payload recebido em relação ao formato esperado da API.
2. O sistema descarta os registros estruturalmente inválidos, como campos obrigatórios ausentes ou tipos de dado incompatíveis.
3. O sistema converte todos os valores financeiros para a unidade Cobre, considerando 1 Ouro = 10000 Cobre e 1 Prata = 100 Cobre.
4. O sistema identifica volumes anômalos característicos de injeção artificial de itens por bots e os marca como anomalia, conforme o critério da RN12.
5. O sistema encaminha os registros padronizados para a etapa de consolidação (Cenário 03).

### Fluxos alternativos

#### Fluxo Alternativo 1 - Taxa de descarte elevada

- **1.1** No passo 2, o sistema identifica que a proporção de registros descartados ultrapassa o limite de 5% do lote.
- **1.2** O sistema registra o lote em log para auditoria.
- **1.3** Retorna ao passo 3 do fluxo principal.

### Fluxos de exceção

#### Fluxo Exceção 1 - Payload fora do formato esperado

- **1.1** No passo 1, o sistema identifica que a estrutura do payload não corresponde ao formato esperado, como em uma alteração na API.
- **1.2** O sistema descarta o payload integralmente, sem persistir dados.
- **1.3** O sistema mantém os dados do ciclo anterior e ativa a sinalização "Dados Desatualizados" para o mercado do Provider.
- **1.4** O sistema registra o erro em log.
- **1.5** Fim.

## CU09 - C3 – Cadastrar Dados de Mercado - Cenário Consolidar e Persistir os Dados

- **Objetivo:** Registrar os leilões padronizados no banco de dados e atualizar o valor de mercado de cada item.
- **Pré-condição:** Os registros devem ter sido sanitizados e padronizados (Cenário 02).
- **Pós-condição:** Os leilões do ciclo são persistidos, os leilões encerrados são classificados e o valor de mercado dos itens é atualizado.
- **Atores:** Provider
- **Ativação:** O sistema recebe os registros padronizados da etapa de sanitização.

### Fluxo principal

1. O sistema identifica, para cada registro, o item correspondente no banco de dados.
2. O sistema registra os leilões ativos do ciclo de coleta.
3. O sistema classifica como "Expirado/Vendido" os leilões sem atualização há mais de 48 horas, mantendo-os no histórico.
4. O sistema calcula o valor de mercado de cada item a partir do primeiro quartil (25%) dos preços dos seus leilões ativos.
5. O sistema atualiza a data e a hora da última atualização do mercado, utilizada na verificação de frescor dos dados.
6. O sistema confirma a transação e registra a conclusão do ciclo de ingestão.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Item não cadastrado

- **1.1** No passo 1, o sistema não localiza o item correspondente ao registro no banco de dados.
- **1.2** O sistema cadastra o novo item com o seu identificador e com o nome provisório "Item {identificador}"; o nome e o ícone definitivos são obtidos posteriormente na API de dados do jogo.
- **1.3** Retorna ao passo 2 do fluxo principal.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** Nos passos 2 a 6, o sistema não consegue gravar os dados devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema desfaz a transação, mantendo os dados do ciclo anterior.
- **1.3** O sistema ativa a sinalização "Dados Desatualizados" para o mercado do Provider e registra a falha em log.
- **1.4** Fim.

## CU09 - C4 – Cadastrar Dados de Mercado - Cenário Executar Ingestão Manual

- **Objetivo:** Permitir que o Admin dispare manualmente um ciclo de ingestão, como no reprocessamento de uma coleta que falhou.
- **Pré-condição:** O Admin deve possuir acesso às funções administrativas da plataforma.
- **Pós-condição:** Um ciclo completo de ingestão é executado e o seu resultado é apresentado ao Admin.
- **Atores:** Admin
- **Ativação:** O Admin solicita a execução manual da rotina de ingestão.

### Fluxo principal

1. O Admin solicita a execução manual da ingestão, informando a região ou o reino desejado.
2. O sistema verifica se o intervalo mínimo de 60 minutos desde a última requisição ao endpoint foi respeitado.
3. O sistema executa a coleta, a sanitização e a consolidação dos dados (Cenários 01, 02 e 03).
4. O sistema apresenta ao Admin o resumo do ciclo, contendo a quantidade de registros coletados, descartados e de itens atualizados.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Intervalo mínimo não atingido

- **1.1** No passo 2, o sistema identifica que a última requisição ao endpoint ocorreu há menos de 60 minutos.
- **1.2** O sistema informa ao Admin o horário a partir do qual uma nova coleta será permitida.
- **1.3** Fim.

#### Fluxo Alternativo 2 - Região inválida

- **2.1** No passo 1, o Admin informa uma região que não pertence a US ou EU ou que não possui mercados monitorados.
- **2.2** O sistema exibe a mensagem: "Informe uma região válida (US ou EU) com mercados monitorados".
- **2.3** Retorna ao passo 1 do fluxo principal.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha durante o ciclo de ingestão

- **1.1** No passo 3, alguma das etapas do ciclo é interrompida por falha, conforme os fluxos de exceção dos Cenários 01, 02 ou 03.
- **1.2** O sistema apresenta ao Admin a etapa em que a falha ocorreu e o erro registrado em log.
- **1.3** Fim.

## Observações para a implementação

Decisões já implementadas (com a variável de ambiente que as controla) e o que continua pendente. Detalhes em `docs/decisoes-e-pendencias.md`. Onde houver conflito com o texto acima, vale o que está aqui e o documento do TC deve ser corrigido.

- Mercados monitorados: `MONITORED_REALMS` (padrão `us:3209`). As commodities de cada região entram automaticamente, com o reino 32512 (US) e 32513 (EU). **O id 32513 não foi verificado:** confirme antes de monitorar um reino da EU.
- RN05: o intervalo de 60 minutos por endpoint fica gravado no banco e vale também para a coleta manual (C4).
- Agendamento: ao iniciar, coleta na hora se a última coleta tem mais de 60 minutos; senão, agenda para a última + 60 minutos. A Ficha do WoW tem job próprio, a cada 15 minutos (RF07).
- C1-FA3 (recomposição): se nenhuma fonte coletou com sucesso nas últimas 48 horas, o histórico é recomposto pela Undermine Exchange antes do ciclo. A recomposição não se repete em menos de 6 horas.
- C1-FE1: só há nova tentativa em erro de rede e 5xx, com esperas de 5, 15 e 45 s, respeitando o `Retry-After` (até 60 s). Um 4xx não é tentado de novo.
- RN12 (C2, passo 4): volume acima de 10 vezes a mediana dos 7 dias anteriores, com piso de 100 unidades e pelo menos 24 pontos anteriores (`INGESTAO_ANOMALIA_FATOR`, `INGESTAO_ANOMALIA_VOLUME_MINIMO`).
- C2-FA1: limite de descarte de 5% do lote (`INGESTAO_LIMITE_DESCARTE`). Leilões Expirado/Vendido ficam 7 dias (`INGESTAO_RETENCAO_LEILOES_DIAS`, RN04).
- RN06: primeiro quartil ponderado pela quantidade, calculado sobre o preço unitário de compra imediata. Leilões que têm só lance ficam de fora.
- C3-FA1: o item novo recebe o nome provisório "Item {id}"; o nome e o ícone vêm depois, pela API de dados do jogo.
- C4: o usuário sem papel de Admin recebe "Acesso restrito ao administrador". Esse texto não está no documento, porque a pré-condição do cenário já exige o Admin.
- **Pendente (testes):** os fluxos C1-FA3 e C4-FA2 entraram no documento depois da implementação, e os testes deles ainda estão como "regra". Renomear `test_cu09_c1_ativacao_backfill_antes_do_ciclo_apos_48h` para `test_cu09_c1_fa3_...` e `test_cu09_c4_regiao_fora_de_us_eu_e_recusada_rn11` para `test_cu09_c4_fa2_...`. Conferir também se o FA2 cobre a região sem mercados monitorados. Depois, regerar o plano de testes.
- **Pendente (antes do CU11, decisão do autor):** alinhar o esquema ao MR. Hoje `items.id` é UUID, mas `leilao.item_id` e `historical_item_prices.item_id` são o id numérico do WoW e não têm chave estrangeira. A região é `us` numa tabela e o id do reino (`3209`, `32512`) na outra. As commodities vindas da Undermine são gravadas com `3209`, e as do ciclo da Blizzard com `32512`.
- **Pendente (decisão do autor):** importar automaticamente o histórico dos itens recém-cadastrados pelo ciclo. Hoje isso só acontece pela importação do Admin ou pela recomposição de 48 horas.
