# Pedido – correções da orientação: retirada da RN07 (iLvl), RN28 → RN07 e texto da tela de Cobertura Histórica

**Contexto.** Na revisão do orientador (02/11), a RN07 (Relevância de Equipamento, filtro por nível de item) saiu do TC. Ela nunca chegou a ser ligada (`MODELO_ILVL_MINIMO` sempre vazio) e, na prática, só commodities passam pela RN02, então não tinha efeito. Para não deixar um buraco na numeração, a antiga **RN28 (Gatilho e Disparo Único do Alerta) passou a ser a RN07**. O TC já está assim. Este pedido alinha o código e a documentação do repositório com o TC, e corrige o texto da tela de Cobertura Histórica, que contradiz a RN27.

**Lembretes do CLAUDE.md:**

- não leia nem altere arquivos `.env`. Variáveis de ambiente só em `backend/.env.example`;
- há alterações minhas ainda não commitadas, como as de `docs/casos-de-uso/README.md` e `estudos/lstm/ROTEIRO.md`. Preserve-as: não use `checkout`, `restore`, `stash` ou `reset`.

**Antes do plano**, faça o commit da documentação que está fora do Git ou alterada sem commit em `docs/` e em `estudos/lstm/`, conforme o `git status`. Isso inclui:

- os arquivos do CU05 a CU08;
- os diagramas, os protótipos (com `docs/prototipos/codigo/`) e o cronograma;
- os documentos de alterações do TC e o próprio TC (`docs/TCII-…docx`), como as versões do TCI que já estão no Git;
- os pedidos, inclusive este;
- as alterações em `docs/casos-de-uso/README.md` e `estudos/lstm/ROTEIRO.md`.

**Não inclua** `.claude/` nem `Claude outputs/`. Mensagem: `docs: documentação do TC (CU05 a CU08, diagramas, protótipos e pedidos)`. Assim, o commit deste pedido fica só com as correções.

**Fora do escopo:** os scripts de estudo em `estudos/lstm/` (por exemplo, a opção `--ilvl-minimo` e o `README.md` de lá), o `ROTEIRO.md`, os pedidos já executados e os relatórios das etapas ficam como estão. São o registro do que foi feito na época. Os pedidos novos (`pedido-cu05.md`, revisado em 11/11, `pedido-cu06-cu07.md`, `pedido-cu08.md` e `pedido-testes-final-2.md`) já estão atualizados: não mexa neles. Eles serão executados depois deste.

---

## 1. Retirar a RN07 (iLvl) do código

A regra sai por completo: um item é **elegível à projeção** quando atende à RN02 (liquidez) e à RN27 (histórico mínimo). O conjunto de treinamento continua sendo os elegíveis aptos (RN15).

1. **`backend/src/ml/configuracao.py`:**
   - remova o campo `ilvl_minimo` (linha 57), a leitura de `MODELO_ILVL_MINIMO` (linha 118) e a atribuição (linha 140);
   - o comentário da linha 53 passa a ser "Elegíveis à projeção: RN02 (liquidez) e RN27 (histórico mínimo)";
   - confira se `PADROES_DAS_VERSOES_ANTIGAS` cita `ilvl_minimo` e, se citar, tire. Os artefatos já gravados têm essa chave no `normalizacao.json`. O `de_dict` ignora campos desconhecidos, mas confirme que uma versão antiga continua carregando, de preferência com um teste.
2. **`backend/src/ml/selecao.py`:**
   - tire a RN07 da docstring (linha 5) e da docstring da linha 65, que fica "(RN02, RN27 e RN15)";
   - remova a coluna `equipamento_obsoleto_rn07` (linhas 70 e 87 a 94), e `elegivel` passa a ser `liquido_rn02 & historico_rn27` (linha 96);
   - tire a RN07 do log (linhas 109 a 112) e o campo `rn07_ativa` de `Selecao` (linhas 33 e 115);
   - remova `CLASSES_EQUIPAMENTO` se não for usado em mais nada.
   - **Atenção:** a classe e o nível do item continuam sendo usados como variáveis do modelo (variáveis 6, 15 e 16 do quadro de variáveis). Só o filtro sai. Não remova a leitura de `items.metadata_info`.
3. **`backend/src/ml/treinamento_inicial.py`:** remova `AVISO_RN07_DESLIGADA` (linhas 47 e 48) e o aviso correspondente (linhas 273 a 277). A docstring passa a citar só o aviso da série diária desatualizada.
4. **`backend/src/modelo_worker.py`:** tire a RN07 do log de início (linhas 224 e 225).
5. **`backend/src/models/treinamento_api_models.py`:** a description de `itens_elegiveis` (linha 48) passa a ser "RN02 e RN27.".
6. **Docstrings que citam o "filtro da RN07":** `backend/src/scraper/populate_item_details.py` (linhas 4 e 82) e `backend/tests/scraper/test_atributos_itens.py` (linha 3). Os atributos continuam sendo coletados, agora só para as variáveis do modelo.
7. **`backend/.env.example`:** remova as linhas 92 e 93 (o comentário da RN07 e `MODELO_ILVL_MINIMO=`). Veja também se algum `docker-compose.yml` repassa `MODELO_ILVL_MINIMO` e, se repassar, tire. Se o meu `.env` tiver a variável, ela só passa a ser ignorada. Não mexa nele.
8. **Testes.** **Não apague funções de teste; ajuste-as.** As contagens de funções por caso de uso estão no capítulo 10 do TC.
   - `backend/tests/modelo/test_cu11_c1_treinamento.py`, linha 47: tire `and "RN07 desligada" in resumo.avisos` e confira os avisos que o resumo passa a ter nesse cenário.
   - `backend/tests/modelo/test_cu11_regras_do_modelo.py`, linhas 402 a 426:
     - a docstring fica sem a RN07;
     - remova `assert not sem_rn07.rn07_ativa` e o trecho `com_rn07`;
     - renomeie `sem_rn07` para `selecao`;
     - mantenha os itens 3 e 4 (armadura de nível 200 e arma de nível 700) com uma asserção explícita de que **equipamentos continuam elegíveis qualquer que seja o nível de item**.
9. **Conferência:** depois das mudanças, `grep -rn -E "RN07|rn07|ilvl_minimo|ILVL_MINIMO"` em `backend/` e `frontend/` (fora de `node_modules`) não deve encontrar nada.

## 2. Documentação do repositório: RN07 (iLvl) sai, RN28 vira RN07

O TC é a referência. As linhas abaixo são do TC atual.

1. **`docs/regras-de-negocio.md`:**
   - substitua a linha da RN07 por:

     | RN07 | Gatilho e Disparo Único do Alerta | Um alerta de compra é atingido quando o valor de mercado do item for igual ou inferior ao preço-alvo, e um alerta de venda, quando for igual ou superior ao preço-alvo. Os alertas ativos são verificados a cada ciclo de ingestão dos dados de mercado, de 60 em 60 minutos, exceto os dos itens cujo registro no ciclo foi marcado como anomalia de volume. Ao ser atingido, o alerta gera uma única notificação e passa à situação "Disparado", na qual permanece até ser reativado pelo usuário, evitando notificações repetidas enquanto o preço se mantiver além do alvo. | RF05, RF06 |

   - a seção "Mapeamento RF/RNF ↔ RN" passa a ser igual à seção 3.6.2 do TC:
     - RF01 (Autenticação de Usuário): Validado por RN11, RN18, RN19, RN20, RN21, RN22.
     - RF02 (Busca de Itens): Não possui regras de negócio associadas.
     - RF03 (Visualização de Histórico): Processado via RN06, RN09.
     - RF04 (Projeção Preditiva com ML): Estritamente governado por RN02, RN10, RN13, RN27.
     - RF05 (Configuração de Alertas): Limitado por RN07, RN08, RN12, RN20.
     - RF06 (Disparo de Notificações Ativa): Validado por RN06, RN07, RN12, RN18, RN20.
     - RF07 (Ingestão de Dados via Providers): Validado por RN04, RN05, RN06, RN09, RN11, RN14.
     - RF08 (Retreinamento do Modelo): Validado por RN02, RN03, RN10, RN13, RN15, RN17, RN24, RN25, RN26, RN27.
     - RF09 (Gestão de Itens Favoritos): Validado por RN06, RN09, RN20.
     - RF10 (Sanitização e Padronização de Dados): Validado por RN01, RN12.
     - RNF01 / RNF04 / RNF07 (Performance e Confiabilidade): Garantidos por RN09, RN13, RN14.
     - RF11 (Ingestão do Histórico Passado): Validado por RN11, RN15, RN16, RN17, RN23.
     - RF12 (Treinamento Inicial do Modelo): Estritamente governado por RN02, RN03, RN10, RN15, RN16, RN17, RN24, RN25, RN27.
2. **`docs/requisitos.md`:**
   - a linha "Regras de negócio" de cada RF deve seguir a lista acima (por exemplo, RF04: "RN02; RN10; RN13; RN27"; RF08: "RN02; RN03; RN10; RN13; RN15; RN17; RN24; RN25; RN26; RN27");
   - na descrição do RF08, o trecho "ignorando itens sem volume de negociação suficiente e focando em equipamentos que ainda tenham relevância no jogo (iLvl)" passa a ser "e ignorando itens sem quantidade ofertada suficiente".
3. **`docs/casos-de-uso/CU05-consultar-previsao-preditiva.md`:**
   - remova a RN07 da linha 23;
   - o FA2 (linhas 56 e 57) fica como no TC:
     - 2.1: "No passo 2, o sistema identifica que o item não atende a um dos critérios de elegibilidade à projeção (RN02 ou RN27)."
     - 2.2: "O sistema exibe, no lugar da projeção, a mensagem do critério não atendido: "Projeção indisponível: este item tem pouca quantidade ofertada para uma previsão confiável" (RN02) ou "Projeção indisponível: este item ainda não tem histórico suficiente para a previsão" (RN27)."
   - tire a RN07 das listas das linhas 157 e 184;
   - na lista de testes, `test_cu05_c1_fa2_item_nao_elegivel_rn02_rn27_rn07` passa a ser `test_cu05_c1_fa2_item_nao_elegivel_rn02_rn27`.
4. **`docs/casos-de-uso/CU11-treinar-modelo.md`:**
   - remova a RN07 da linha 24;
   - alinhe as listas de RNs das linhas 37 a 40, 55, 70 e 88 com o mapeamento acima;
   - o conceito "Item Elegível à Projeção" (linha 45) passa a ser "Item que atende ao filtro de liquidez (RN02) e ao histórico mínimo para projeção (RN27), …";
   - tire a RN07 das linhas 329 e 378 e remova a linha 380 e a linha de `MODELO_ILVL_MINIMO` da tabela de valores configuráveis (linha 473).
5. **`docs/casos-de-uso/CU08-manter-notificacoes.md`:**
   - RN28 → RN07 nas linhas 28, 30 e 125;
   - na linha 123, "**RN28 – Gatilho e Disparo Único do Alerta (nova):**" passa a ser "**RN07 – Gatilho e Disparo Único do Alerta:**";
   - na lista de testes, `rn28` vira `rn07` nos nomes: `test_cu08_c1_fluxo_principal_dispara_alerta_de_compra_e_de_venda_rn07` e `test_rn07_alerta_dispara_uma_unica_vez`.
6. **`docs/casos-de-uso/README.md`** (preserve as minhas alterações não commitadas):
   - na relação de casos de uso, a coluna de atores fica como no Quadro 23 do TC: CU08 "Usuário", CU09 "Admin", CU10 "Admin" e CU11 "Admin";
   - a seção "Atores (seção 6.3)" passa a ter o texto do TC:

     > A plataforma Goblin Ledger conta com dois atores:
     >
     > - Usuário: a plataforma é voltada para ele, para que possa analisar os preços, o histórico e a previsão dos itens em leilão, manter os itens favoritos e os alertas de preço e consultar as suas notificações;
     > - Admin: tem a responsabilidade de cadastrar os dados de mercado e os dados passados dos itens e de iniciar o treinamento do modelo preditivo. No sistema, é um usuário com o papel de administrador, atribuído diretamente no banco de dados, sem tela de gestão de papéis (Apêndice C).
     >
     > As rotinas automáticas, como a coleta dos dados de mercado de hora em hora, a importação diária do histórico, o retreinamento semanal e a consolidação diária do modelo e a verificação dos alertas a cada ciclo de ingestão, não são representadas como atores. São execuções agendadas do próprio sistema, descritas nos cenários dos casos de uso a que pertencem, no campo Ativação.

   - em "Escopo da implementação atual", a frase sobre o CU05 a CU08 passa a ser: "CU05, CU06, CU07 e CU08 estão especificados nos arquivos `CU05-consultar-previsao-preditiva.md`, `CU06-manter-favoritos.md`, `CU07-manter-alerta.md` e `CU08-manter-notificacoes.md`, com o texto igual ao do TC (seções 6.4.5 a 6.4.8), e serão implementados pelos pedidos `estudos/lstm/pedido-cu05.md`, `pedido-cu06-cu07.md` e `pedido-cu08.md`. A RN08 (limite de 20 alertas ativos) e a RN07 (gatilho e disparo único do alerta, antiga RN28) prevalecem sobre `regras-de-negocio.md`."
7. **Situação do CU05 a CU08 e atores nos arquivos dos casos de uso:**
   - no início de `CU05-…`, `CU06-…`, `CU07-…` e `CU08-…`, troque o aviso "PROVISÓRIO (20/10/2026) …" por "> Texto igual ao do TC (seção 6.4.x), conferido em 11/11/2026.", com a seção de cada um (6.4.5 a 6.4.8). No CU05, a linha "Situação no código" passa a citar o pedido `estudos/lstm/pedido-cu05.md` revisado;
   - no campo "Atores" dos cenários, siga o TC, que só tem dois atores: CU08 (C1 a C3) "Usuário"; CU09, CU10 e CU11 "Admin". O Provider continua citado no texto como componente da arquitetura.
8. **`CLAUDE.md`:**
   - na regra 1, inclua o CU05, o CU06, o CU07 e o CU08 entre os casos de uso que podem ser implementados, especificados nos arquivos de `docs/casos-de-uso/` (texto igual ao do TC), e tire a frase "CU05, CU06, CU07 e CU08 não estão especificados — não implemente, nem "adiante" partes deles (…)";
   - na "Ordem sugerida", acrescente "→ CU05 → CU06 + CU07 → CU08".
9. Faça uma busca final por `RN28` e por `RN07` em `docs/` (fora dos `.docx` e dos relatórios das etapas). Toda RN07 restante deve ser a do gatilho do alerta.

## 3. Tela de Cobertura Histórica

Em `frontend/app/admin/cobertura/page.tsx` (linha 100), a frase "Os itens inaptos continuam com a predição bloqueada." contradiz a RN27: um item inapto ao treinamento (RN15) pode ter a projeção liberada. Troque a frase por:

> Os itens inaptos não participam do ajuste dos pesos do modelo, mas podem ter a projeção liberada se atenderem à RN27 e à RN10.

O resto do parágrafo não muda. Se algum teste do front conferir esse texto, ajuste-o.

## 4. Arquivos que já deixei no repositório (entram no commit da documentação, antes do plano)

- `docs/diagramas-atualizados/`: `cu08c01`, `cu09c01`, `cu09c02`, `cu10c01` e `cu10c02` (`.png` e `.svg`). São os diagramas de atividades sem a raia Provider e com a RN07 no lugar da RN28.
- `docs/prototipos/rf11-cobertura.png`: a tela de Cobertura Histórica já com o texto novo.
- `docs/Alterações do TC - Diagramas sem a Raia Provider e Tela de Cobertura (para colar).docx`.
- `docs/prototipos/codigo/`: o código dos protótipos do TC, só como referência visual para os pedidos do CU05 a CU08 (veja o `README.md` de lá).
- `estudos/lstm/`: `pedido-cu05.md` (revisado), `pedido-cu06-cu07.md`, `pedido-cu08.md`, `pedido-testes-final-2.md` e este pedido.
## 5. Testes e commit

1. Rode:
   - a suíte do back-end, como de costume;
   - os testes do serviço do modelo: `docker compose --profile testes run --rm modelo-testes`;
   - `npm test`, `npm run lint` e `npx tsc --noEmit` na pasta `frontend`.
2. Faça o commit das correções na branch atual: `refactor: retira a RN07 (iLvl), renumera a RN28 para RN07 e corrige o texto da tela de cobertura`.

## O que devolver

1. A lista de arquivos alterados.
2. O resultado de cada suíte (executados, aprovados, com falha).
3. A quantidade de **funções** de teste por caso de uso e cenário, somando o back-end e o serviço do modelo, e se alguma contagem mudou em relação à execução final do capítulo 10 (`pedido-testes-final.md`).
4. O resultado da busca final do passo 1.9 e do passo 2.9.
