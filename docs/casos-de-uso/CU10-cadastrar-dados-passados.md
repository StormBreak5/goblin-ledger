# CU10 – Cadastrar Dados Passados

> Fonte: documento do TC *TCII-N2-IND-Itzac Albertin-Guiliano Rangel Alves* (Google Drive), exportado em 06/10/2026, já com as atualizações pós-implementação. O documento do TC é a fonte da verdade: se houver divergência, atualize este arquivo a partir dele.

**Situação no código (06/10/2026):** Implementado (C1 a C3), com as telas do Admin; commits `4213e36`, `117c63b`, `6c8d7d8`, `1f3eb01`, `2e70b04` e `81b0a6b`. Testes em `backend/tests/integration/test_cu10_*.py`, `backend/tests/scraper/` e `backend/tests/unit/test_cu10_*.py`.

**Atualização (19/10/2026): importação diária.** O worker roda todo dia a importação incremental do C1 para os reinos monitorados (`HISTORICO_IMPORTACAO_DIARIA_CRON`, padrão 02:00 UTC), com a mesma rotina da recuperação de 48 h, que continua como estava. A série diária da Undermine é a única que o CU11 usa (RN16), e sem isso ela parava de crescer com o worker no ar. Nenhuma importação grava o agregado diário da data UTC corrente, que ainda está em formação. Na importação incremental, o agregado diário já gravado dentro da janela incremental (2 dias) é regravado se a fonte trouxer outro valor; isso corrigiu o 19/10/2026, gravado às 02:11 UTC só com as primeiras horas do dia. Para rodar uma vez: `python -m src.worker --importacao-diaria`.

## Descrição

Este caso de uso tem como principal função carregar para o banco de dados o histórico retroativo de preços dos itens e as datas das grandes atualizações do jogo, obtidos de fontes de terceiros, harmonizando-os ao padrão do sistema e verificando se cada item possui histórico suficiente para o treinamento inicial do modelo preditivo.

- **Requisitos associados:** RF11 – Ingestão do Histórico Passado do Preço de Itens
- **Cenários:**
  - Cenário 01 – Importar histórico de preços
  - Cenário 02 – Registrar eventos de atualização do jogo
  - Cenário 03 – Validar cobertura histórica dos itens

## Regras de negócio dos requisitos associados

(Conforme o campo "Regras de Negócio" dos quadros dos RFs; texto completo em `docs/regras-de-negocio.md`.)

- **RN11 – Validação de Domínio Geográfico:** O sistema só aceita o cadastro de contas e a ingestão de dados de mercado das regiões Ocidentais: US e EU.
- **RN15 – Volume Mínimo para Treinamento Inicial:** O modelo preditivo de um item só pode ser processado e ativado (RF12) se a base de dados contiver um período histórico contínuo predeterminado de mínimo 6 meses de registros consolidados para o respectivo ativo. Itens sem histórico mínimo terão a predição bloqueada. O período mínimo corresponde a 180 dias contínuos, e lacunas de até 3 dias sem registros não interrompem a continuidade do período.
- **RN16 – Harmonização de Dados de Terceiros:** Dados históricos retroativos obtidos via extração externa (Undermine Exchange, web scraping) devem obrigatoriamente ser convertidos, tipados e higienizados para o exato padrão relacional do SGBD do sistema e da padronização de moeda, garantindo a integridade do dataset antes do treinamento inicial. Cada registro identifica a sua origem e a sua granularidade (diária ou horária).
- **RN17 – Marcação Estocástica de Eventos:** Datas de grandes atualizações sistêmicas do jogo (patches/expansões) mapeadas no banco histórico devem ser injetadas como variáveis categóricas para o algoritmo. Isso impede que o modelo interprete quedas abruptas de preço causadas por obsolescência de itens como flutuações naturais de mercado. Além de patches e expansões, são registrados como eventos as temporadas, os eventos sazonais e os eventos recorrentes do jogo.
- **RN23 – Controle de Ritmo na Extração de Fontes de Terceiros:** A extração de dados de fontes de terceiros deve respeitar a cota de requisições definida pela fonte ou, na ausência de cota formal, um intervalo mínimo entre requisições consecutivas, evitando sobrecarregar o serviço de terceiros e o bloqueio do acesso.

## CU10 - C1 – Cadastrar Dados Passados - Cenário Importar Histórico de Preços

- **Objetivo:** Carregar para o banco de dados o histórico retroativo de preços dos itens obtido de fontes de terceiros, viabilizando o treinamento inicial do modelo preditivo.
- **Pré-condição:** O Admin deve possuir acesso às funções administrativas da plataforma.
- **Pós-condição:** O histórico retroativo é harmonizado ao padrão do sistema e persistido no banco de dados.
- **Atores:** Admin
- **Ativação:** O Admin solicita a importação de histórico retroativo de preços.

### Fluxo principal

1. O Admin informa a região e a relação de itens cujo histórico será importado.
2. O sistema valida a região e os identificadores dos itens informados.
3. O Provider obtém, na Undermine Exchange, o arquivo de dados de cada item, que contém o seu histórico diário de preços e, aproximadamente, os registros horários dos últimos 14 dias.
4. O Provider decodifica o arquivo binário, extraindo a data, o preço e a quantidade de cada registro.
5. O sistema converte os registros para o padrão relacional do banco de dados, tipando cada campo.
6. O sistema converte os valores financeiros para a unidade Cobre.
7. O sistema descarta os registros inconsistentes, como datas anteriores a 2004 ou posteriores ao dia seguinte e preços ou quantidades negativos.
8. O sistema desconsidera os registros já existentes na base para o mesmo item e a mesma data.
9. O sistema persiste os registros harmonizados no banco de dados.
10. O sistema apresenta ao Admin o resumo da importação, com a quantidade de registros importados, descartados e duplicados.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Dados de entrada inválidos

- **1.1** No passo 2, o sistema identifica que a região informada não pertence a US ou EU ou que algum identificador de item é inválido.
- **1.2** O sistema exibe a mensagem: " Região ou item inválido. Verifique os dados informados".
- **1.3** Retorna ao passo 1 do fluxo principal.

#### Fluxo Alternativo 2 - Item não cadastrado

- **2.1** No passo 4, o sistema identifica registros de um item que ainda não existe no banco de dados.
- **2.2** O sistema cadastra o novo item com o seu identificador e nome.
- **2.3** Retorna ao passo 5 do fluxo principal.

#### Fluxo Alternativo 3 - Limite de requisições da fonte atingido

- **3.1** No passo 3, o Provider respeita o intervalo mínimo definido entre requisições consecutivas à fonte.
- **3.2** O Provider aguarda o intervalo antes de solicitar o arquivo do próximo item.
- **3.3** Retorna ao passo 3 do fluxo principal.

#### Fluxo Alternativo 4 - Importação em andamento

- **4.1** No passo 2, o sistema identifica que já existe uma importação em andamento.
- **4.2** O sistema exibe a mensagem: "Já existe uma importação em andamento".
- **4.3** Fim.

### Fluxos de exceção

#### Fluxo Exceção 1 - Fonte de dados indisponível

- **1.1** No passo 3, o Provider não consegue obter os dados devido à indisponibilidade da fonte ou ao esgotamento do tempo limite de resposta (20 falhas consecutivas de rede, de tempo limite ou de resposta 429 ou 5xx).
- **1.2** O sistema mantém os registros já persistidos, registra a falha em log e exibe a mensagem: "Não foi possível obter os dados da fonte informada. Tente novamente mais tarde".
- **1.3** Fim.

#### Fluxo Exceção 2 - Falha na comunicação com o Banco de Dados

- **2.1** No passo 9, o sistema não consegue gravar os registros devido a uma falha interna de I/O ou queda de conexão.
- **2.2** O sistema desfaz a importação, sem persistir registros parciais.
- **2.3** O sistema exibe a mensagem: "Não foi possível concluir a importação no momento. Tente novamente mais tarde".
- **2.4** Fim.

#### Fluxo Exceção 3 - Formato do arquivo alterado

- **3.1** No passo 4, o Provider não consegue decodificar o arquivo porque o formato foi alterado pela fonte (3 arquivos ilegíveis consecutivos).
- **3.2** O sistema interrompe a importação, mantém os registros já persistidos e registra a falha em log.
- **3.3** O sistema exibe a mensagem: "Não foi possível interpretar os dados da fonte. Verifique se houve alteração no formato".
- **3.4** Fim.

## CU10 - C2 – Cadastrar Dados Passados - Cenário Registrar Eventos de Atualização do Jogo

- **Objetivo:** Registrar as datas dos eventos do jogo que influenciam os preços (expansões, patches, temporadas, eventos sazonais e eventos recorrentes) para que sejam utilizadas como variáveis categóricas pelo modelo preditivo.
- **Pré-condição:** O Admin deve possuir acesso às funções administrativas da plataforma.
- **Pós-condição:** Os eventos de atualização são registrados na base histórica e ficam disponíveis para o treinamento do modelo.
- **Atores:** Admin
- **Ativação:** O Admin solicita a extração dos eventos de atualização do jogo.

### Fluxo principal

1. O Admin seleciona a fonte dos eventos: expansões (Wikipedia), patches e eventos sazonais (Warcraft Wiki), temporadas (API da Blizzard) ou eventos recorrentes (regras de calendário).
2. O Provider extrai da fonte selecionada (por meio de web scraping, no caso das páginas) a relação de eventos com nome, versão, quando houver, e datas de início e término.
3. O sistema converte as datas extraídas para o formato padrão (DD/MM/AAAA).
4. O sistema verifica, para cada evento, se ele já está registrado na base histórica.
5. O sistema registra os novos eventos, classificando-os como expansão, patch, temporada, evento sazonal, recorrente ou outro.
6. O sistema apresenta ao Admin a relação de eventos registrados.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Evento já registrado

- **1.1** No passo 4, o sistema identifica que o evento já consta na base histórica.
- **1.2** O sistema ignora o evento e prossegue com os demais.
- **1.3** Retorna ao passo 4 do fluxo principal.

#### Fluxo Alternativo 2 - Cadastro manual do evento

- **2.1** No passo 1, o Admin opta por informar manualmente o nome, a versão e a data de lançamento do evento.
- **2.2** O sistema valida os dados informados (data no formato DD/MM/AAAA, entre 2004 e 2100, com término não anterior ao início).
- **2.3** Prossegue para o passo 3 do fluxo principal.

### Fluxos de exceção

#### Fluxo Exceção 1 - Estrutura da página alterada

- **1.1** No passo 2, o Provider não reconhece a estrutura da página informada, como em uma alteração no layout do site.
- **1.2** O sistema não registra eventos e grava a falha em log.
- **1.3** O sistema exibe a mensagem: "Não foi possível extrair os eventos da página informada. Verifique a fonte ou cadastre o evento manualmente".
- **1.4** Fim.

## CU10 - C3 – Cadastrar Dados Passados - Cenário Validar Cobertura Histórica dos Itens

- **Objetivo:** Verificar se o histórico consolidado de cada item atende ao período contínuo mínimo exigido para o treinamento inicial, liberando ou mantendo bloqueada a sua predição.
- **Pré-condição:** O histórico retroativo de preços deve ter sido importado (Cenário 01).
- **Pós-condição:** Cada item é classificado como apto ou inapto ao treinamento inicial.
- **Atores:** Admin
- **Ativação:** O Admin solicita a validação da cobertura histórica dos itens.

### Fluxo principal

1. O Admin solicita a validação da cobertura histórica.
2. O sistema recupera, para cada item, os registros de preços consolidados no banco de dados.
3. O sistema calcula o maior período contínuo de registros do item, considerando os registros do item de qualquer região e origem, reduzidos a um por dia, e desconsiderando lacunas de até 3 dias sem registros.
4. O sistema verifica se o período contínuo atinge o mínimo de 6 meses (180 dias).
5. O sistema classifica o item como "Apto ao treinamento".
6. Após avaliar todos os itens, o sistema apresenta ao Admin a relação de itens aptos e inaptos, com o período contínuo de cada um.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Histórico insuficiente

- **1.1** No passo 4, o sistema identifica que o período contínuo do item é inferior a 6 meses (180 dias).
- **1.2** O sistema classifica o item como "Inapto ao treinamento" e mantém a sua predição bloqueada.
- **1.3** Retorna ao passo 2 do fluxo principal para os demais itens.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** Nos passos 2 ou 5, o sistema não consegue acessar os registros devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema exibe a mensagem: "Não foi possível concluir a validação no momento. Tente novamente mais tarde".
- **1.3** Fim.

## Observações para a implementação

Decisões já implementadas (com a variável de ambiente que as controla) e o que continua pendente. Detalhes em `docs/decisoes-e-pendencias.md`. Onde houver conflito com o texto acima, vale o que está aqui e o documento do TC deve ser corrigido.

- C1: a fonte são os arquivos `.bin` da Undermine Exchange, com histórico diário desde 09/2022 e cerca de 14 dias de registros horários.
- RN23: intervalo mínimo de 0,008 s entre requisições, com 50 em paralelo (`UNDERMINE_INTERVALO_MINIMO_SEGUNDOS`).
- C1-FE1 e C1-FE3: interrompem a importação depois de 20 falhas seguidas de rede, tempo limite, 429 ou 5xx (`IMPORTACAO_LIMITE_FALHAS_SEGUIDAS`) ou de 3 arquivos ilegíveis seguidos (`IMPORTACAO_LIMITE_ARQUIVOS_ILEGIVEIS`). Nos dois casos, o que já foi gravado é mantido. Já o FE2 desfaz a importação inteira.
- C1-FA4: só roda uma importação por vez (409). Uma execução "em andamento" há mais de 12 horas deixa de bloquear.
- Modos de importação:
  - a do Admin é exata: ignora o ETag e o filtro incremental, para contar os duplicados;
  - a recomposição de 48 horas (CU09-C1 FA3) é incremental e usa o ETag.
  - a importação diária (`HISTORICO_IMPORTACAO_DIARIA_CRON`, padrão `0 2 * * *`, em UTC; `off` desliga) é incremental como a recomposição e regrava o agregado diário que mudou na fonte dentro da janela incremental. Ela não conta para a regra das 48 horas;
  - nenhum modo grava o agregado diário da data UTC corrente (só dias encerrados). Quando o dia em aberto é adiado, o ETag do arquivo não avança, e a importação diária não usa o ETag: sem isso, o arquivo de um item sem leilões novos responderia 304 no dia seguinte e o dia, já encerrado, nunca seria gravado (aconteceu com 4.878 itens no 19/10/2026);
  - a importação e o ciclo da Blizzard (CU09) gravam em `historical_item_prices`; rodando juntos, podem entrar em deadlock no índice único (aconteceu na importação diária de 20/10/2026, desfeita depois de 6 minutos). A importação diária agendada espera a rodada de ingestão em andamento e a segura enquanto importa, como a recuperação de 48 h, e a importação incremental desfeita por deadlock é tentada de novo uma vez;
  - disparo perdido da importação diária: com o computador dormindo no horário, ela roda ao acordar, uma vez só (coalesce, sem limite de atraso, como o ciclo do worker). Desligado, o APScheduler não guarda o disparo; ao iniciar, o worker confere se o último disparo do cron tem importação incremental concluída depois dele e, se não tem, roda a importação na hora, uma vez.
- RN16: cada ponto tem `granularidade` (`DIARIA` = dia inteiro em UTC; `HORARIA` = instante) e `origem`.
- O arquivo de um item que só é commodity é um stub de 45 bytes sem preços. Ele é tratado como "sem dados", e a busca segue para o arquivo das commodities.
- C1-FA1: no TC, a mensagem aparece com um espaço depois da aspa (`" Região ou item inválido…`). O texto correto, que é o do código, não tem esse espaço: "Região ou item inválido. Verifique os dados informados".
- C2: há cinco fontes:
  - `EXPANSOES` (Wikipedia);
  - `PATCHES` (Warcraft Wiki, `Patch_history`);
  - `SAZONAIS` (Warcraft Wiki, `Holiday`);
  - `TEMPORADAS` (API da Blizzard, Mythic+ e PvP);
  - `RECORRENTES` (regras de calendário).
- C2: os tipos de evento são `EXPANSAO`, `PATCH`, `TEMPORADA`, `EVENTO_SAZONAL`, `RECORRENTE` e `OUTRO`. A chave do evento é (tipo, nome, data de início, região), com a região `GLOBAL` para eventos sem região.
- C2: a mesma página não é lida de novo em menos de 10 minutos (`EVENTOS_INTERVALO_MINIMO_MINUTOS`). Os eventos recorrentes são gerados de 2022 (`EVENTOS_ANO_INICIAL`) até 1 ano à frente (`EVENTOS_ANOS_A_FRENTE`). Só as páginas conhecidas são lidas; outro endereço cai no FE1.
- C2: o reinício semanal dos EUA é toda terça-feira. O texto da fonte no código diz "7:00 PDT", mas a Warcraft Wiki dá 15:00 UTC, que corresponde a 8:00 PDT. Como o evento é gravado por data, só o texto precisa de correção.
- **Pendente (decisão do autor):** reinício semanal da EU, hoje às quartas-feiras (`EVENTOS_REINICIO_SEMANAL_EU`, `off` desliga). Também Noblegarden e Lunar Festival, gerados por regra e marcados "(aproximado)". As datas oficiais podem ser cadastradas pelo C2-FA2.
- C3: mínimo de 180 dias contínuos (`COBERTURA_MINIMO_DIAS`), com lacunas de até 3 dias toleradas (`COBERTURA_LACUNA_MAXIMA_DIAS`). Entram os registros de qualquer região, origem e granularidade, reduzidos a um por dia. A Ficha do WoW fica de fora. O resultado vai para a tabela `aptidao_treinamento`, que é substituída a cada validação.
- **Pendente (para o CU11):**
  - a Undermine não tem dados de 28/06 a 01/07/2024 (4 dias), o que parte em duas a série de todo item longo quando a lacuna tolerada é de 3 dias;
  - o preço da Undermine é o menor preço, e o do ciclo da Blizzard é o 1º quartil (RN06); o CU11 deve separar as séries por `origem` e tratar a emenda entre elas.
- **Pendente (teste):** o C1-FA4 entrou no documento depois da implementação. Renomear `test_cu10_c1_so_uma_importacao_roda_por_vez` para `test_cu10_c1_fa4_importacao_em_andamento` e regerar o plano de testes.
