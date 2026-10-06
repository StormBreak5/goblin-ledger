# Decisões e pendências da implementação (para atualizar o documento do TC)

> Gerado em 29/09/2026 a partir do trabalho feito nesta etapa (CU01 a CU04, CU09 e CU10) e do histórico de commits. Reúne o que o
> documento **não definia** e foi decidido durante a implementação, o que foi decidido **por você**, o que ficou **pendente** e onde
> o código **diverge** do documento ou do MR. Cada item indica a variável de ambiente ou o arquivo onde o valor pode ser mudado.

**Legenda:** **[Autor]** decidido por você · **[Adotada]** sugestão minha, implementada e configurável, aguardando sua confirmação ·
**[Documento]** já definido no TC · **[Pendente]** precisa da sua decisão · **[Divergência]** o código difere do documento/MR.

## 1. Situação

| Caso de uso | Situação | Commits principais |
|---|---|---|
| CU03 – Buscar Itens | Implementado (C1 a C3) | `3aeff24` |
| CU01 – Manter Usuário e CU02 – Realizar Login | Implementados (C1 a C3 e C1 a C4) | `98670a6`, `64245e7` |
| CU09 – Cadastrar Dados de Mercado | Implementado (C1 a C4), com a tela do Admin | `37ac6f2`, `e91f0c1`, `cb3173c` |
| CU10 – Cadastrar Dados Passados | Implementado (C1 a C3), com as telas do Admin | `4213e36`, `117c63b`, `6c8d7d8`, `1f3eb01`, `2e70b04`, `81b0a6b` |
| CU04 – Visualizar Histórico | Implementado (C1 a C3) | `5e43cb0`, `6e818f0`, `069ae95`, `debe195` |
| Correções posteriores | Granularidade do ciclo horário, stub de commodities, fuso de exibição, Ficha do WoW, Docker | `7bf596e`, `cb7c37c`, `e3da628`, `bf7e25a`, `d930d4a`, `b5acb9f`, `4545791` |

Não implementados por não estarem especificados: **CU05, CU06, CU07, CU08 e CU11**, e a **lista de favoritos** citada na ativação
do CU04-C1. Testes: 290 no backend (`pytest`) e 32 no frontend (`npm test`); os 238 que têm identificador de fluxo (um por fluxo) estão listados em `docs/plano-de-testes-por-fluxo.md`.
As linhas "Situação no código" dos arquivos `docs/casos-de-uso/*.md` estão desatualizadas e podem ser reescritas a partir da tabela acima.

## 2. O que precisa da sua confirmação

| # | Assunto | Situação hoje | Decisão necessária |
|---|---|---|---|
| 1 | **Fuso horário** | O banco guarda UTC (regra do `CLAUDE.md`) e as telas convertem para o fuso de quem vê (GMT-3). Você pediu para converter a importação para GMT-3; **não reescrevi os horários gravados**: o erro visto era só de exibição (a API mandava o horário sem marca de fuso e o navegador o lia como local). | Confirmar que basta a conversão na exibição. Reescrever o banco em GMT-3 deslocaria ~23 milhões de linhas e desalinharia o dia diário da Undermine (00:00 UTC). |
| 2 | **Reinício semanal da Europa** | Quarta-feira (sugestão), `EVENTOS_REINICIO_SEMANAL_EU` (`off` desliga). Você informou só o dos EUA. | Confirmar o dia. |
| 3 | **Noblegarden e Lunar Festival** | A Warcraft Wiki só diz que "variam". Gerados por regra e marcados "(aproximado)": início na Páscoa (7 dias) e no Ano Novo Lunar (14 dias, tabela de 2020 a 2030). | Confirmar ou trocar por datas oficiais (o cadastro manual do C2-FA2 cobre). |
| 4 | **Tolerância de lacuna do CU10-C3** | 3 dias (`COBERTURA_LACUNA_MAXIMA_DIAS`). A Undermine não tem dados de 28/06 a 01/07/2024 (4 dias, todos os itens), o que parte a série de todo item longo em dois períodos. | Manter 3 ou subir para 4, que junta as séries (~1.480 dias). |
| 5 | **Bid e Buyout no CU04-C3** | O objetivo do cenário cita Bid, Buyout e Volume; o banco só guarda valor de mercado e volume (leilões brutos ficam 7 dias). A dica mostra data, hora, preço e volume. | Corrigir o texto do TC, ou guardar Bid/Buyout por ciclo (muda esquema e ingestão). |
| 6 | **Data da última atualização na lista do CU03** | A API devolve `last_auction_update`, mas a lista mostra só nome e ícone (pendência do próprio documento). | Mostrar ou não. |
| 7 | **Alinhamento do MR** | `items` usa UUID e o `external_item_id` em texto; `item_prices` e `historical_item_prices` usam o id numérico do WoW; a "região" é `us` numa tabela e o id do reino conectado (`3209`, `32512`) na outra. | Padronizar (D13/D14 do MR) antes do CU11. |
| 8 | **Ficha do WoW sem caso de uso** | Tem série própria (`item_prices`), job de 15 min, histórico de 14 dias importado da Undermine. Não pertence a nenhum CU detalhado. | Dizer em qual RF/CU entra no TC. |
| 9 | **Itens novos entram sem histórico** | O ciclo horário cadastra itens que ainda não existem (na primeira coleta real, `items` passou de 17.709 para 21.090, ou seja, 3.381 novos). Muitos são equipamentos raros com poucos dias na Undermine; os demais ficam curtos até acumular. O aviso "Dados limitados" (CU04-C2-FA1) cobre isso. | Se quiser, o worker importa da Undermine o histórico dos itens recém-cadastrados (hoje só a Admin ou a recuperação de 48 h). |
| 10 | **Séries de origens diferentes no mesmo gráfico** | O preço da Undermine é o menor preço; o do ciclo da Blizzard é o valor de mercado (1º quartil, RN06). | O CU11 deve separar por `origem`. Definir como tratar a emenda das séries. |
| 11 | **Termos das fontes** | `robots.txt` da Undermine bloqueia `/data/` (você decidiu manter os `.bin`); a Warcraft Wiki declara `ai-train=no` (aceito para ler só o HTML, 1 requisição); a Wikipedia é CC BY-SA (a fonte é citada em cada registro); a API da Blizzard tem cota de 36.000 requisições por hora. | Registrar no TC como risco e mitigação (ritmo limitado, `User-Agent` identificado, leitura mínima). |

## 3. Decisões por caso de uso

### CU01 – Manter Usuário

| Decisão | Valor | Origem |
|---|---|---|
| Papel do Admin | Coluna `role` com `usuario` e `admin`, sem tela de gestão: a promoção é feita no banco | **[Autor]** (pendência do documento) |
| Regras de senha | Mínimo de 8 caracteres (`PASSWORD_MIN_LENGTH`), máximo 255; custo do bcrypt 12 (`BCRYPT_ROUNDS`). O documento não define complexidade | **[Adotada]** |
| Campos | E-mail até 150 caracteres, região US ou EU (RN11) | **[Documento]** |
| `usuario` no MR | Segue o MR com `regiao` acrescentada, `nome_usuario` omitido (o formulário não o tem) e e-mail com 150 caracteres | **[Divergência]** sugerida ao MR |
| Exclusão da conta | Remoção atômica, com chaves estrangeiras `ON DELETE CASCADE` (RN20); senha atual exigida (RN19) | **[Documento]** |

### CU02 – Realizar Login

| Decisão | Valor | Origem |
|---|---|---|
| Mecanismo de sessão | JWT com validade de 24 h, não renovável; a sessão fica na tabela `sessao` e o logout a revoga | **[Autor]** |
| Segredo do JWT | `JWT_SECRET`, sem valor fixo no código. Sem ele a API usa um segredo temporário (aviso no log) e as sessões se perdem a cada reinício | **[Adotada]** |
| Bloqueio | 5 falhas seguidas por e-mail bloqueiam por 15 min (RN21), inclusive e-mails sem conta, para não revelar se o e-mail existe | **[Documento]** e detalhe **[Adotada]** |
| Recuperação de senha | Link de uso único de 10 min; um novo link invalida os anteriores (RN22); a resposta é a mesma para e-mail cadastrado ou não | **[Documento]** |
| Envio de e-mail | SMTP por variáveis de ambiente; Mailpit no `docker-compose.yml` para desenvolvimento (`http://localhost:8025`) | **[Autor]** (sugestão do documento) |
| Inatividade (C4-FA1) | Vale só a expiração de 24 h do JWT: não há prazo de inatividade separado | **[Adotada]** |

### CU03 – Buscar Itens

| Decisão | Valor |
|---|---|
| Termo | Mínimo de 3 e máximo de 100 caracteres (RF02); só números = identificador do item; letras e números = busca por nome (C2-FA2) |
| Nome | Sem considerar acentuação nem caixa (extensão `unaccent` do PostgreSQL) |
| Paginação | 10 por página, no máximo 50 |
| Data da última atualização | Devolvida pela API a partir de `historical_item_prices` e não exibida (ver item 6 da seção 2) |

### CU09 – Cadastrar Dados de Mercado

| Decisão | Valor | Origem |
|---|---|---|
| Mercados monitorados | `MONITORED_REALMS` (padrão `us:3209`); as commodities de cada região entram automaticamente, com o "reino" convencionado 32512 (US) e 32513 (EU; este id não foi verificado na Undermine) | **[Adotada]** |
| Intervalo mínimo por endpoint | 60 min (RN05), gravado no banco; vale também para a coleta manual do Admin | **[Documento]** |
| Agendamento | Ao iniciar, coleta na hora se a última passou de 60 min; senão agenda "última + 60 min". Só a Ficha do WoW roda a cada 15 min | **[Autor]** |
| Cadeia de rodadas | A rodada horária agenda a seguinte ao terminar e **nunca é descartada por atraso** (`misfire_grace_time=None`): se o PC suspender o Docker por dias, ela roda ao acordar e a recuperação de 48 h é avaliada. Um vigia a cada 5 min retoma a cadeia se ela se perder, e uma trava impede duas rodadas ao mesmo tempo. Defeito corrigido em 06/10/2026: com tolerância de 1 h, uma rodada atrasada por 2,5 dias foi descartada e a coleta horária parou sem aviso | **[Adotada]** |
| Recuperação | Se nenhuma fonte (Blizzard ou Undermine) coletou com sucesso nas últimas 48 h, o histórico é recomposto pela Undermine antes do ciclo; não se repete em menos de 6 h | **[Autor]** (a regra) e **[Adotada]** (as 6 h) |
| Tentativas | Só erro de rede e 5xx, com esperas de 5, 15 e 45 s e respeito ao `Retry-After` (até 60 s); a falha mantém os dados anteriores e ativa "Dados Desatualizados" (RN14) | **[Adotada]** |
| RN12 (volume anômalo) | Mais de 10 vezes a mediana de 7 dias, com piso de 100 unidades e pelo menos 24 pontos anteriores (`INGESTAO_ANOMALIA_*`) | **[Adotada]** (pendência do documento) |
| C2-FA1 (descarte alto) | Lote com mais de 5% descartado vai para o log (`INGESTAO_LIMITE_DESCARTE`) | **[Adotada]** (pendência do documento) |
| Retenção | Leilões Expirado/Vendido ficam 7 dias (`INGESTAO_RETENCAO_LEILOES_DIAS`); o histórico horário permanece | **[Adotada]** |
| Valor de mercado (RN06) | 1º quartil ponderado pela quantidade do preço unitário de compra imediata; leilões só com lance ficam de fora | **[Documento]** |
| Item desconhecido (C3-FA1) | Cadastrado com nome provisório "Item {id}"; nome e ícone vêm depois da API de dados do jogo | **[Adotada]** |
| Textos não definidos | "Acesso restrito ao administrador", "Informe uma região válida (US ou EU) com mercados monitorados" e as mensagens de falha do C4 | **[Adotada]** |
| Chaves | `leilao.item_id` e `historical_item_prices.item_id` sem chave estrangeira, até `items` ser alinhada ao MR | **[Divergência]** |

### CU10 – Cadastrar Dados Passados

**C1 – Importar histórico de preços**

| Decisão | Valor | Origem |
|---|---|---|
| Fonte | Arquivos `.bin` da Undermine Exchange (diário desde 09/2022 e ~14 dias de snapshots horários) | **[Autor]** |
| RN23 | Intervalo mínimo entre requisições de 0,008 s (~125 por segundo) com 50 em paralelo, o ritmo que já existia (`UNDERMINE_INTERVALO_MINIMO_SEGUNDOS`) | **[Autor]** (manter o ritmo) |
| FE1 / FE3 | 20 falhas de rede, tempo limite, 429 ou 5xx **seguidas** interrompem como "fonte indisponível" (`IMPORTACAO_LIMITE_FALHAS_SEGUIDAS`); 3 arquivos ilegíveis seguidos interrompem como "formato alterado" (`IMPORTACAO_LIMITE_ARQUIVOS_ILEGIVEIS`). Os dois **mantêm** o que já foi gravado | **[Adotada]** |
| FE2 | Falha de banco desfaz a importação inteira | **[Documento]** |
| Concorrência | Uma importação por vez (409 "Já existe uma importação em andamento"); uma execução "em andamento" há mais de 12 h deixa de bloquear | **[Adotada]** |
| Modos | Importação do Admin: exata (ignora o ETag e o filtro incremental, para contar os duplicados). Recuperação de 48 h: incremental e usa o ETag. Só a recuperação conta como "backfill" na regra de 48 h | **[Adotada]** |
| Granularidade (RN16) | Cada ponto tem `granularidade` `DIARIA` (dia inteiro em UTC) ou `HORARIA` (instante). O parser lia o tempo dos snapshots como minutos, mas são **segundos**: cerca de 1 milhão de pontos por execução eram descartados. Corrigido e validado contra um arquivo real | **[Adotada]** |
| Descarte (passo 7) | Data anterior a 2004 ou depois de amanhã, preço ou quantidade negativos | **[Adotada]** |
| Stub de commodity | O arquivo do reino de um item que só é commodity existe (HTTP 200) mas é um stub de 45 bytes sem preços; agora isso é tratado como "sem dados" e a busca segue para as commodities. 6.099 itens ativos tinham só o stub gravado como ponto real e ficavam inaptos; a reimportação (9.481 itens, 12.626.591 registros, 723 s) devolveu o histórico deles; as linhas-stub (preço e quantidade 0) foram apagadas, com backup | **[Adotada]** |
| Ficha do WoW | Fora da importação de itens (tem série e job próprios) | **[Adotada]** |
| FA1 do documento | Vale o texto das Observações: "Região ou item inválido. Verifique os dados informados" | **[Documento]** |

**C2 – Registrar eventos de atualização do jogo** (você pediu "todos os eventos possíveis" que influenciam os preços)

| Decisão | Valor | Origem |
|---|---|---|
| Fontes (5) | `EXPANSOES` (Wikipedia, tabela de expansões; Battle for Azeroth é 13/08/2018 nessa fonte), `PATCHES` (Warcraft Wiki, `Patch_history`, pré-patch pela descrição da linha), `SAZONAIS` (Warcraft Wiki, `Holiday`), `TEMPORADAS` (API da Blizzard, Mythic+ e PvP, com início e fim), `RECORRENTES` (regras de calendário). O Wowhead carrega os eventos por JavaScript e não serve | **[Autor]** (patches e expansões) e **[Adotada]** (o desenho) |
| Reinício semanal dos EUA | Toda terça-feira às 7:00 PDT | **[Autor]** |
| Outras regras | Feira de Negrilua: primeiro domingo do mês, uma semana. Posto de Troca: virada no dia 1º | **[Adotada]** (Warcraft Wiki) |
| Tipos | `EXPANSAO`, `PATCH`, `TEMPORADA`, `EVENTO_SAZONAL`, `RECORRENTE`, `OUTRO` | **[Adotada]** |
| Chave do evento | (tipo, nome, data de início, região); região `GLOBAL` para o evento sem região | **[Adotada]** |
| Intervalo | A mesma página de terceiros não é lida de novo em menos de 10 minutos (`EVENTOS_INTERVALO_MINIMO_MINUTOS`) | **[Adotada]** |
| Anos gerados | De 2022 (`EVENTOS_ANO_INICIAL`) até 1 ano à frente (`EVENTOS_ANOS_A_FRENTE`): ~770 eventos recorrentes | **[Adotada]** |
| Endereço da página | Só as páginas conhecidas (Wikipedia e Warcraft Wiki) são lidas; outro endereço é tratado como página não reconhecida (FE1) e nem chega a ser consultado | **[Adotada]** |
| Textos não definidos | Fonte inválida (422), leitura recente (429), falha de banco | **[Adotada]** |
| Cadastro manual (FA2) | Data em DD/MM/AAAA entre 2004 e 2100; término não pode ser anterior ao início; evento repetido é ignorado | **[Adotada]** |

**C3 – Validar cobertura histórica**

| Decisão | Valor | Origem |
|---|---|---|
| Mínimo (RN15) | 180 dias contínuos = "6 meses" (`COBERTURA_MINIMO_DIAS`) | **[Adotada]** |
| "Desconsiderando lacunas" | Dias separados por até 3 dias sem registro pertencem ao mesmo período (`COBERTURA_LACUNA_MAXIMA_DIAS`); vale o maior período (no empate, o mais recente) | **[Adotada]** (ver item 4 da seção 2) |
| Base do cálculo | Os registros do item de qualquer região, origem ou granularidade, reduzidos a um por dia | **[Adotada]** |
| Itens avaliados | Itens ativos do WoW, menos a Ficha; o resultado fica em `aptidao_treinamento`, substituído a cada validação, para o CU11 ler | **[Adotada]** |
| Resultado real (29/09/2026) | 19.289 aptos e 1.800 inaptos de 21.089 itens (antes da correção do stub eram 10.711 e 10.378) | fato |

### CU04 – Visualizar Histórico

| Decisão | Valor | Origem |
|---|---|---|
| "Dados Desatualizados" (limiar) | 24 h (`DADOS_DESATUALIZADOS_HORAS`); o documento sugeria 2 h | **[Autor]** |
| Frescor | Compara com o último ciclo do **mercado do item** (o do ponto mais recente da Blizzard; commodities em 32512): desatualizado se o mercado está sinalizado por falha (RN14) ou passou do limiar. Ficha do WoW: idade do último preço | **[Adotada]** |
| Preço do cabeçalho | Valor de mercado (RN06) em destaque e menor preço logo abaixo (some quando igual, como na Ficha) | **[Autor]** |
| Janelas | 14D, 30D, 90D, 365D e ALL; valor ilegível volta a 14D | **[Adotada]** |
| "Dados limitados" (C2-FA1) | O primeiro ponto da série inteira cai depois do início da janela, com tolerância de 1 dia (o ponto diário é 00:00 UTC); nunca em ALL; uma janela sem nenhum ponto de um item com histórico antigo usa o texto do C1-FA2 | **[Adotada]** |
| Falha ao trocar a janela (C2-FE1) | Toast e a janela anterior mantida; a tela de erro do C1-FE1 só vale na primeira carga | **[Documento]** |
| Dica do ponto (C3) | Data e hora exata e valores em Ouro/Prata/Cobre (`12g 49s 30c`, RN01); volume ausente vira "N/D"; numa série sem volume (Ficha) a linha não aparece; conversão que falha omite a dica e registra no console | **[Autor]** e **[Adotada]** |
| Ponto diário | É o dia inteiro em UTC: mostra a data em UTC e "dia inteiro" (em GMT-3 cairia no dia anterior às 21:00) | **[Adotada]** |
| Avisos | Os textos vêm do backend (`avisos`), a única fonte, para o frontend não ter regra de negócio | **[Adotada]** |

## 4. Ficha do WoW (fora dos casos de uso detalhados)

- **Armazenamento:** tabela `item_prices` (preço em Cobre, região `us`). Não entra em `historical_item_prices` nem em `leilao`, e a validação de cobertura a exclui.
- **Preço atual:** job de 15 min pela API da Blizzard **[Autor]**. O instante do ponto passou a ser o do preço na Blizzard (`last_updated_timestamp`, que muda a cada 20 min), e não o da coleta; a chave (item, região, instante) é única (migração 0006), então a mesma leitura não se repete.
- **Histórico:** importado uma vez de `token-us.bin` da Undermine: 1.007 pontos a cada 20 min, cerca de 14 dias (`python -m src.scraper.token_history`). Você decidiu **não** manter a atualização por essa fonte: daqui em diante só a API da Blizzard. Não há histórico da Ficha antes de 15/09/2026 além de 4 registros isolados de 16/06.
- **Formato do arquivo** (decifrado e conferido byte a byte): cabeçalho (`u8` versão 1, `u32` instante atual, `u32` preço atual, `u16` N) e N registros (`u32` instante, `u32` preço), com o preço em unidades de 100 cobre.

## 5. Decisões transversais

| Assunto | Decisão |
|---|---|
| Datas e horas | UTC no backend. As telas convertem para o fuso de quem vê. A API marca o instante com fuso explícito (`Z`) |
| Dinheiro (RN01) | Sempre em Cobre (inteiro); a conversão para Ouro/Prata/Cobre é só da exibição (`frontend/lib/moeda.ts`) |
| Migrações (Alembic) | 0001 baseline (banco antigo é reconhecido), 0002 autenticação, 0003 ingestão de mercado, 0004 dados passados, 0005 correção da granularidade do ciclo horário, 0006 preço da Ficha único por instante. As migrações rodam ao subir a API e o worker |
| Docker | O worker ficou em loop por duas razões: a porta do `.env` (5435) não vale dentro da rede do compose (o `docker-compose.yml` já sobrescreve para 5432) e a imagem nova instalou o SQLAlchemy 2.1, cujo driver padrão é o psycopg 3. Correção: `postgresql+psycopg2://` explícito e `sqlalchemy>=2.0,<2.1` |
| Testes do frontend | Vitest 3 + Testing Library (não havia executor). O Rollup nativo é bloqueado pela política de Controle de Aplicativo do Windows desta máquina; foi trocado pela versão WASM via `overrides` no `package.json` |
| Ambiente local | Os testes rodam contra um PostgreSQL temporário (o banco real nunca é lido nem alterado por eles). A API sobe com `--reload`; reiniciar sem `JWT_SECRET` derruba as sessões |

## 6. Divergências entre o documento/MR e o código

**Não constam no MR** (criadas por necessidade da implementação; sugerido incluí-las no documento):
`ciclo_ingestao`, `estado_mercado` (CU09), `evento_jogo`, `extracao_evento` (CU10-C2), `aptidao_treinamento` (CU10-C3), `sessao`,
`token_recuperacao`, `tentativa_login` (CU01/CU02, conferir contra o MR), as colunas `origem`, `anomalia` e `granularidade` de
`historical_item_prices`, e as colunas de resumo de `scraper_execution_logs` (quem disparou, região, itens e registros por resultado, etapa da falha).

**Correções sugeridas ao texto do documento** (as Observações de cada caso de uso já as listam; resumo):
- CU10-C1: FA1 pelo texto das Observações; FA3 é o controle de ritmo (RN23); FE2 ocorre no passo 9 (gravação); FE3 termina em "Fim".
- CU09: o título do caso de uso e do requisito cita "Dados de Mercado"; o CU10 é "Dados Passados".
- CU04-C1 passo 3: "preço mais baixo" → valor de mercado (RN06), com o menor preço como informação secundária.
- CU04-C2-FA1 e C1-FA2: tirar o espaço final dentro das aspas (`… período selecionado. `).
- CU04-C3: o objetivo cita Bid e Buyout, que não existem no banco (ver item 5 da seção 2).
- CU04-C1-FA1: o limiar é 24 h (a sugestão era 2 h).

## 7. Achados sobre os dados (úteis para o CU11)

- **Apagão da Undermine** de 28/06 a 01/07/2024 (4 dias sem nenhum item).
- **Stub de commodities:** o arquivo do reino de 6.099 itens ativos era um stub de 45 bytes; o sistema o gravava como ponto real (preço 0) e o histórico verdadeiro nunca era buscado (corrigido e reimportado).
- **Itens novos:** o ciclo horário cadastra itens que não existiam no banco; o histórico deles é curto e a maioria dos 1.800 inaptos de hoje tem entre 90 e 179 dias (1.216) ou entre 2 e 89 dias (583); o Pet Cage (82800) não tem arquivo na Undermine. Não conferi item a item se são realmente curtos.
- **Volume anômalo:** a série de volume tem trechos com valores muito altos (por exemplo, 20 a 22/09 no Nightshade); a RN12 marca as anomalias só nos pontos do ciclo da Blizzard.
- **Medidas diferentes:** o preço da Undermine é o menor preço; o do ciclo é o 1º quartil (RN06). No mesmo horário os dois valores diferem.
- **Região das commodities:** a Undermine guarda o histórico delas no arquivo do reino 32512, mas o sistema o grava com a chave do reino (`3209`), enquanto o ciclo da Blizzard grava com `32512`.

## 8. Variáveis de ambiente novas ou usadas nesta etapa

| Variável | Padrão | Uso |
|---|---|---|
| `BLIZZARD_CLIENT_ID`, `BLIZZARD_CLIENT_SECRET` | — | API oficial da Blizzard |
| `MONITORED_REALMS` | `us:3209` | Mercados do ciclo horário |
| `INGESTAO_LIMITE_DESCARTE` / `_RETENCAO_LEILOES_DIAS` / `_ANOMALIA_FATOR` / `_ANOMALIA_VOLUME_MINIMO` | 0,05 / 7 / 10 / 100 | CU09 |
| `JWT_SECRET`, `PASSWORD_MIN_LENGTH`, `BCRYPT_ROUNDS` | — / 8 / 12 | CU01 e CU02 |
| `FRONTEND_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS` | Mailpit local | CU02-C2 |
| `UNDERMINE_INTERVALO_MINIMO_SEGUNDOS` | 0,008 | RN23 |
| `IMPORTACAO_LIMITE_FALHAS_SEGUIDAS` / `_ARQUIVOS_ILEGIVEIS` | 20 / 3 | CU10-C1 FE1 e FE3 |
| `EVENTOS_ANO_INICIAL` / `_ANOS_A_FRENTE` / `_REINICIO_SEMANAL_EU` / `_INTERVALO_MINIMO_MINUTOS` / `_CONTATO` | 2022 / 1 / wednesday / 10 / vazio | CU10-C2 |
| `COBERTURA_MINIMO_DIAS` / `_LACUNA_MAXIMA_DIAS` | 180 / 3 | CU10-C3 |
| `DADOS_DESATUALIZADOS_HORAS` | 24 | CU04-C1-FA1 |
