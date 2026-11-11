# Relatório do CU05: consultar previsão preditiva

Implementação do CU05 (seção 6.4.5 do TC), feita em 11/11/2026 conforme o `estudos/lstm/pedido-cu05.md` (revisado em 11/11) e o plano aprovado no chat. Três commits, nesta ordem:

| Commit | O que é |
|---|---|
| `1dcefd6` | `docs: documentação do TC (CU05 a CU08, diagramas, protótipos e pedidos)`: a documentação que estava fora do Git, antes do plano do pré-requisito |
| `d1bb779` | `refactor: retira a RN07 (iLvl), renumera a RN28 para RN07 e corrige o texto da tela de cobertura`: o pré-requisito (`pedido-correcoes-orientacao.md`), seção 1 |
| `9c9e4cc` | `feat(CU05): consultar previsão preditiva (C1 a C3)`: 29 arquivos, com os testes, as capturas e a documentação |

**Decisões pedidas ao autor antes de implementar:**
- **Destravar o ambiente:** sim. O worker estava em loop desde 21/10, e sem a importação diária não haveria predições recentes para conferir no navegador.
- **Item elegível ainda não avaliado:** é o item fora de `projecao_item`, ou com o motivo "deixou de ser elegível", mas que atende agora à RN02 e à RN27. Vale o **FA4** ("em avaliação"), um caso que o CU05 não cobre.

## 1. Pré-requisito: correções da orientação (`d1bb779`)

A RN07 do nível de item saiu do TC na revisão de 02/11, e a antiga RN28 (gatilho do alerta) passou a ser a RN07.

- **Código:**
  - saíram o campo `ilvl_minimo`, a variável `MODELO_ILVL_MINIMO`, a coluna `equipamento_obsoleto_rn07`, o `rn07_ativa` e o aviso "RN07 desligada" do resumo do treinamento;
  - um item é elegível à projeção quando atende à RN02 e à RN27.
- **Comportamento:** não muda, porque a regra nunca foi ligada.
- **Versões antigas:** os `normalizacao.json` das v1 a v5 ainda têm a chave antiga e continuam carregando com a mesma assinatura. Isso foi conferido com o código novo, no container.
- **Documentação:**
  - RN07 → gatilho do alerta em `regras-de-negocio.md`, no CU08 e no README;
  - o mapeamento RF ↔ RN da seção 3.6.2 do TC;
  - os atores do TC (só Usuário e Admin);
  - o CU05 a CU08 marcados como "texto igual ao do TC";
  - a regra 1 do `CLAUDE.md`, que passou a incluir o CU05 a CU08.
- **Tela de Cobertura:** a frase que contradizia a RN27 foi trocada por "Os itens inaptos não participam do ajuste dos pesos do modelo, mas podem ter a projeção liberada se atenderem à RN27 e à RN10."
- **Testes:** nenhuma função foi criada nem apagada. A busca por `RN07|rn07|ilvl_minimo|ILVL_MINIMO` em `backend/` e `frontend/` não encontra nada.

## 2. O que o CU05 implementa

### Backend

| Arquivo | O que faz |
|---|---|
| `src/controllers/item_controller.py` | `GET /api/items/{item_id}/projection`, sem autenticação, região US. Uma falha de banco, inclusive ao abrir a sessão, responde 503 com a mensagem do FE1 |
| `src/services/projecao_service.py` | O fluxo do C1: a situação do item, a escolha da série, as predições a exibir, o preço de partida, a variação, o erro típico e os textos |
| `src/repositories/projecao_repository.py` | Só SQL: a versão vigente, `projecao_item`, `predicao_diaria`, o preço diário de D e os critérios da RN02 e da RN27 |
| `src/services/mensagens.py` | Os textos exatos do FA1 ao FA7, do FE1 e do passo 7 |
| `src/models/api_models.py` | `ProjecaoDoItemResponse`, `PredicaoDoDia` e `AvisoDaProjecao` (Pydantic) |
| `backend/.env.example` | `PROJECAO_DESATUALIZADA_DIAS=2` (FA7) |

Da situação no banco ao fluxo, como na tabela das observações do CU05:

| Situação no banco | Fluxo | `situacao` na resposta |
|---|---|---|
| sem versão vigente na região | FA1 | `MODELO_NAO_TREINADO` |
| fora de `projecao_item`, ou "deixou de ser elegível": os critérios são recalculados | FA2 (RN02 ou RN27; se os dois falham, a RN02) ou FA4, se os dois passam | `NAO_ELEGIVEL` ou `EM_AVALIACAO` |
| `IGNORADA` ("série insuficiente") | FA2, com a mensagem da RN27 | `NAO_ELEGIVEL` |
| `BLOQUEADA`, "acima do limiar" ou "não supera o ingênuo" | FA3 | `REPROVADA` |
| `BLOQUEADA`, "avaliação insuficiente" | FA4 | `EM_AVALIACAO` |
| `BLOQUEADA`, "degradação" | FA5 | `SUSPENSA` |
| `LIBERADA`, sem predição da vigente com dia previsto a partir de hoje | FA6 | `NAO_DISPONIVEL` |
| `LIBERADA`, com o dia de referência mais de 2 dias atrás do último dia encerrado | FA7 | `DISPONIVEL`, com `desatualizada` |
| `LIBERADA`, com predições recentes | fluxo principal | `DISPONIVEL` |

- **Série exibida:** a liberada. Havendo mais de uma, a de maior quantidade média ofertada.
- **Predições:** as do dia de referência D mais recente da versão vigente, só com dias previstos a partir de hoje (UTC).
- **Ponto de partida e variação:** o preço diário da Undermine em D, o mesmo que o C3 usou como base da previsão.
- **Erro típico:** o `mdape` de `projecao_item`, arredondado.

### Frontend

| Arquivo | O que faz |
|---|---|
| `app/item/[id]/page.tsx` | O botão "Projeção" na barra das janelas, só com a projeção disponível; o dia em destaque; a seção da projeção, que só aparece com o histórico na tela (pré-condição) |
| `components/PriceChart.tsx` | A linha tracejada (token `--color-projection`, `#A78BFA`), a faixa "Próximos 7 dias", a legenda, os rótulos dos dias previstos em roxo e o ponto em destaque. Sem projeção, é o gráfico do CU04 |
| `components/TooltipDaProjecao.tsx` | A dica do dia previsto (C2) e a escolha entre ela e a dica do histórico, no ponto de partida (C2-FA1) |
| `components/ProjecaoDoItem.tsx` | Os textos, o alerta do FA7 e a tabela; ou a mensagem do FA1 ao FA6 e do FE1 no lugar da projeção |
| `lib/projecaoDoItem.ts`, `lib/useProjecaoDoItem.ts` e `lib/graficoDoItem.ts` | A chamada à API, a escolha do C3 no `sessionStorage` (com try/catch) e a junção do histórico com a projeção, que define o eixo e a escala |

A regra de negócio fica toda no backend. A tela só apresenta a situação e os textos que recebe e converte de Cobre para Ouro, Prata e Cobre com o `moeda.ts` (RN01).

## 3. Como a tela usa o modelo (ligação com a orientação de 30/10)

O CU05 fecha o caminho que o orientador pediu: histórico → limpeza → variáveis → normalização → treino → salvamento → inferência → gráfico.

1. O CU11-C1/C2 treina e **salva** cada versão em `backend/modelos/vN/`: `modelo.keras`, `normalizacao.json` e `treino.json`.
2. O CU11-C3 roda todo dia, **carrega o modelo salvo**, prepara a entrada com a normalização da própria versão, prevê os 7 dias, desfaz a normalização (em Cobre) e grava em `predicao_diaria`. É a inferência, separada do treino e feita em lote.
3. A API do CU05 **não carrega a rede**: só lê `predicao_diaria`, então a consulta do usuário é leve.
4. A tela desenha a projeção em continuação ao histórico, no mesmo formato dele: um ponto por dia, às 00:00 UTC, em Cobre.

O teste `test_cu05_c1_ponta_a_ponta_treino_consolidacao_e_projecao`, no container do `modelo`, percorre o caminho inteiro com dados sintéticos: treina, salva, consolida e chama a API. Ele confere que as predições devolvidas são as gravadas e que o preço de partida é a base do C3.

## 4. Testes

**Resultado das suítes** (11/11/2026):

| Suíte | Executados | Aprovados | Com falha |
|---|---|---|---|
| Backend no host (`pytest`) | 335 (+ 5 módulos ignorados, os de `tests/modelo`) | 335 | 0 |
| Container do `modelo` (`modelo-testes`) | 50 | 50 | 0 |
| Frontend (`npm test`) | 46 | 46 | 0 |

O `npm run lint` deu 0 erros, com o aviso do `<img>` que já existia, e o `npx tsc --noEmit` passou limpo. Os testes do CU04 não foram alterados e continuam passando.

**Funções de teste do CU05** (para o Quadro 82):

| Cenário | Backend | Container | Frontend | Total |
|---|---|---|---|---|
| C1 | 9 | 2 | 4 | 15 |
| C2 | 0 | 0 | 3 | 3 |
| C3 | 0 | 0 | 2 | 2 |
| **CU05** | **9** | **2** | **9** | **20** |

- **`it.each` do frontend:** no C1, os FA1 a FA6 são um único `it.each` com 6 casos, cada um com o nome do fluxo. Contando os casos, o CU05 tem 25 testes, e é esse o número que entra em `docs/plano-de-testes-por-fluxo.md`.
- **Container:**
  - `test_cu05_c1_fa2_criterio_da_api_igual_ao_do_selecao`: para cada série e item, inclusive nos limites de 50 unidades e de 60 dias, a RN02 e a RN27 recalculadas pela API em SQL dão o mesmo resultado que o `selecionar` do CU11;
  - `test_cu05_c1_ponta_a_ponta_treino_consolidacao_e_projecao`: o caminho da seção 3.
- **Outros casos de uso:** não mudaram em relação a 22/10, exceto o CU11, de 60 para 66, por causa do commit `c5e3d88`.

## 5. Conferência no navegador (Quadro 75)

Os itens foram escolhidos no banco real:
- **liberado:** Bismuth (210931), com MdAPE de 9,7%;
- **bloqueado:** Lesser Cosmic Essence (34056), "acima do limiar";
- **não elegível:** Teebu's Scorching Straight Sword (159840), fora de `projecao_item` e com pouca quantidade ofertada.

**Com a data de hoje (11/11):**
- o bloqueado mostra o FA3;
- o não elegível mostra o FA2, com a mensagem da RN02;
- o liberado mostra o FA6, porque as últimas predições são de D = 20/10 (seção 6).

**Com as predições reais, vistas como em 21/10/2026:** um script fora do repositório (no scratchpad) sobe a mesma API, sem mudanças no código, com o relógio fixado em 21/10 12:00 UTC e o histórico limitado a esse instante. É a tela como estaria em 21/10, o dia seguinte à última consolidação real. Todos os números são reais: são as predições da v1, de D = 20/10.

| Cenário | Resultado esperado (Quadro 75) | Obtido |
|---|---|---|
| C1 | A projeção dos próximos 7 dias em continuação ao histórico, com a tabela e o erro típico, ou o motivo da indisponibilidade | **Sim.** Linha tracejada a partir de 8g 19s (20/10), faixa "Próximos 7 dias", legenda, tabela de 21 a 27/10 (de −7,3% a −15,2%), "Erro mediano de 10% nas previsões deste item" e o aviso. Os três motivos (FA2, FA3 e FA6) aparecem no lugar da projeção, com o histórico mantido |
| C2 | A data, o preço previsto e a variação do dia selecionado, identificados como projeção | **Sim.** "PROJEÇÃO · 24/10/2026 · dia inteiro · Preço previsto: 6g 99s 36c · Variação: −14,6% sobre 8g 19s". O ponto e a linha da tabela se destacam juntos, apontando por qualquer um dos dois, e no ponto de partida vale a dica do histórico |
| C3 | Ocultar e voltar a exibir a linha e a tabela, com a escala recalculada e a escolha mantida na sessão | **Sim.** Ao ocultar, o eixo volta a terminar no histórico; a escolha continua depois de recarregar a página; ao exibir de novo, o eixo vai até 27/10 |

O console do navegador não teve erros na carga limpa da tela.

**Capturas** (PNG, escala 2, em `docs/capturas/`), com os dados vistos como em 21/10:
- `cu05-c1-liberado.png`: pode substituir o protótipo do RF04 no TC, com a legenda dizendo que é a tela como em 21/10/2026;
- `cu05-c1-bloqueado.png` e `cu05-c1-nao-elegivel.png`;
- `cu05-c2-tooltip.png`: a dica do dia 24/10;
- `cu05-c3-oculta.png`.

## 6. Ambiente e problemas encontrados

- **A Undermine Exchange responde HTTP 403 à importação diária.**
  - O worker foi reconstruído (`docker-compose up --build -d worker`) e saiu do loop do `Can't locate revision '0010'`; a coleta horária da Blizzard voltou.
  - Ao subir, ele rodou a importação diária perdida, que falhou com 403 em todos os itens (CU10-C1-FE1). A série diária continua parada em 20/10.
  - Por isso o C3 não tem dia novo para prever, e o C2 retreina com os mesmos dados: a v7, de 11/11 às 12:47 UTC, deu "MANTIDO", com o mesmo MdAPE da v6 (19,04%).
  - Não foi feita nenhuma tentativa de contornar o bloqueio. **É decisão do autor.**
- **O serviço `modelo` foi reconstruído** depois do retreinamento, com a `d1bb779`. O log de início já não cita a RN07.
- **Corrida na inicialização do banco da API** (problema antigo, fora do CU05): logo depois de subir a API, as requisições simultâneas da primeira tela disputam o `init_db` preguiçoso, e o Alembic falha (`KeyError: 'script'`); as seguintes funcionam. A correção foi aberta como tarefa à parte e está em andamento noutra sessão. Até lá, abrir qualquer tela uma vez antes da demonstração.
- **Recharts e "movimento reduzido":** com essa preferência ligada no sistema, a animação do Recharts zerava o tracejado da linha da projeção. Por isso a animação dessa linha está desligada.
- **Tooltip a partir da tabela:** o `defaultIndex` do Recharts 3 só vale na montagem e não acompanha o mouse na tabela. Quando o destaque vem da tabela, a dica é desenhada junto ao ponto destacado; quando vem do gráfico, vale a dica do Recharts.

## 7. Decisões e pendências para o TC

**Decisões:**
1. **Elegível ainda não avaliado:** é o item fora de `projecao_item`, ou com "deixou de ser elegível", mas que atende agora à RN02 e à RN27. Mostra o **FA4** (decisão do autor).
2. **FA7:** a projeção está desatualizada quando o dia de referência fica mais de `PROJECAO_DESATUALIZADA_DIAS` (2) dias atrás do último dia encerrado (hoje − 1, UTC), como no pedido. O texto do cenário diz "geradas há mais de 2 dias"; vale alinhar.
3. **Linha de origem:** "Projeção gerada em DD/MM/AAAA, a partir do menor preço diário de DD/MM/AAAA" vem do protótipo do RF04, porque o cenário não define esse texto. As duas datas estão em UTC.
4. **C3:** com a projeção oculta, somem a linha, a faixa, a legenda, os textos e a tabela.
5. **API e rede:** a API não executa a rede; só lê as predições do C3. Isso pode entrar no texto do CU05 ou do capítulo de implementação, como resposta ao ponto da orientação sobre separar treino e inferência.

**Pendências:**
- **A Undermine (seção 6):** sem a série diária, não há projeção nova para mostrar na banca.
- **"Mudanças no RF04" do CU05:** a seção ainda lista RN02, RN03, RN10, RN13, RN17 e RN27, e o mapeamento novo do TC é RN02, RN10, RN13 e RN27.
- **Pendências da orientação fora deste pedido:**
  - a qualidade como one-hot (teste no estudo, sistema e retreino);
  - o texto das variáveis 15 e 16 em linhas próprias, com a explicação do embedding;
  - o teste de profundidade (duas LSTMs);
  - o 32 da camada densa na configuração;
  - os slides de salvamento → inferência → gráfico no roteiro e na apresentação.
