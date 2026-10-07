# Etapa 1 do ROTEIRO: relatório da preparação para o treino

Gerado em 2026-10-06. O banco local foi lido até 2026-10-06. O CU11 não foi implementado e `docs/` não foi alterado.
Esta é a versão revisada: as pendências 1 a 6 da primeira versão já foram resolvidas com o autor (seção 5).

## 1. O que mudou no código

| Commit | O que faz |
|---|---|
| `e6193b1 fix(itens): sync preserva metadata_info` | `mesclar_metadata()` faz `base \|\| por_cima` em JSONB e trata NULL ou `null` como `{}`. O upsert diário do sync passa a mesclar, com o que já existe por cima. O `ChunkWriter` do CU10-C1 deixa de regravar o JSON lido no início da importação: agora mescla só `last_etag` e `source_region`. |
| `5319231 feat(itens): grava atributos do item para o modelo preditivo` | O `populate_item_details` grava `item_class_id`, `item_subclass_id`, `quality`, `level`, `sell_price` (Cobre) e `atributos_atualizados_em`, e passa a selecionar os itens sem `item_class_id`. 404 marca `atributos_indisponiveis` e o item não é consultado de novo; 429, 5xx e erros de rede ficam para a próxima execução. O ícone só é pedido para quem não tem e nunca é apagado. O log mostra o progresso por lote. |
| `013e136 feat(estudo): RN03 com EMA dos preços aceitos, pré-patches e commodity` | Estudo em `estudos/lstm/`: nova RN03 (seção 4.2), pré-patch pela versão maior, versão de patch repetida contada uma vez, `f_commodity` pela origem do arquivo, correção do aviso do NumPy 2.5 e versões testadas no `requirements.txt`. |

Testes: backend com **297 passando** (7 novos); estudo com **18 passando** (7 novos), sem nenhum `DeprecationWarning`.

O worker do Docker foi reconstruído com o código novo. O preenchimento único rodou dentro dele (`python -m src.scraper.populate_item_details`): 23.276 itens em ~15 min, a ~27 requisições/s, dentro dos limites de 100/s e 36 mil/h. Resultado: **23.137 gravados, 139 sem dados na API (404), 0 com erro**.

### Efeito do bug do sync na importação incremental (`importacao_historico.py`)

Todo dia o sync trocava o `metadata_info` dos ~20 mil itens do dump por `{"source": "ah_dump"}`. Na recuperação automática (incremental), `_alvos()` só mantém o `last_etag` se houver `source_region`, e as duas chaves sumiam. Na recuperação seguinte:

- não havia `If-None-Match`: todo arquivo era baixado inteiro, sem nenhum 304;
- sem a origem preferida, o reino 3209 era consultado antes das commodities. Isso dava duas requisições para cada um dos ~10,9 mil itens de commodity.

**Os dados não ficavam errados**: o corte por `load_last_seen` com a margem de 2 dias e o `ON CONFLICT` evitam duplicados. O custo era só tráfego e tempo. A importação pelo Admin (não incremental) já ignora o ETag e não era afetada. Também se perdia o `source` de quem cadastrou o item.

## 2. Cobertura dos atributos (`items.metadata_info`, 23.276 itens)

| Chave | Itens com valor | % |
|---|---|---|
| `item_class_id`, `item_subclass_id`, `quality`, `level`, `sell_price` | 23.137 cada | 99,40% |
| `atributos_atualizados_em` | 23.276 | 100% |
| `atributos_indisponiveis` | 139 | 0,60% |
| `last_etag` / `source_region` (CU10, preservados) | 22.865 | 98,23% |

- `sell_price`: 22.261 maiores que zero e 876 iguais a zero (sem piso).
- Qualidades: UNCOMMON 8.467, COMMON 5.717, RARE 4.579, POOR 2.718, EPIC 1.650, LEGENDARY 6.
- Os 67 itens com nome provisório estão entre os 139 indisponíveis. Antes eles eram consultados de novo a cada rodada.

## 3. Verificação dos dados (somente leitura)

**`historical_item_prices`** (UNDERMINE, DIARIA, sem anomalia):

| Medida | Valor |
|---|---|
| Período | 2022-09-04 a 2026-10-06 |
| Itens e linhas | 22.865 itens; 23.484.637 linhas |
| Séries (`region`) | 1: `3209` (US). As commodities da Undermine também ficam sob 3209. |
| Itens por região | US 22.865; EU 0 |
| Itens com ≥ 120 dias com dados | 22.428 |

**`aptidao_treinamento`:** a validação do CU10-C3 foi rodada de novo em 2026-10-06 23:17 UTC, pelo `CoberturaService.validar()`, o mesmo do endpoint do Admin. Agora são **23.275 itens: 20.557 aptos e 2.718 inaptos**. Antes eram 21.089 itens, com 19.289 aptos, validados em 2026-09-29.

**`evento_jogo`**, contagem desde set/2022:

| Tipo | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|
| PATCH | 2 | 6 | 8 | 6 | 5 |
| EXPANSAO | 1 | 0 | 1 | 0 | 1 |
| TEMPORADA | 2 | 4 | 4 | 4 | 4 |

EVENTO_SAZONAL e RECORRENTE vão até 2027.

- Expansões: Dragonflight (2022-11-28), The War Within (2024-08-26) e Midnight (2026-03-02).
- Temporadas de M+ e PvP completas até Midnight S2 (aberta).
- **Nenhum ano sem patch.** O maior intervalo entre patches é de 77 dias; a média, de 53.
- Pontos de atenção, tratados no estudo (seção 4.3):
  - versões repetidas: 9.2.5 em 2022-05-31 e 2022-08-02; 10.2.6 em 2024-03-19 e 2024-04-23. As segundas datas são inícios de temporada;
  - pré-patches sem rótulo no nome: 10.0.0 (2022-10-25) e 11.0.0 (2024-07-23).

**`reino`:** nenhum valor de `historical_item_prices.region` fica fora de `reino` (3209, 32512) e dos ids de commodities.

## 4. Estudo com dados reais

**Ambiente:** `.venv` com Python 3.13.14 (o 3.12 não está instalado). Com o controle inteligente de aplicativos desligado, rodam as versões atuais: numpy 2.5.3, pandas 3.0.6, pyarrow 25.0.1, SQLAlchemy 2.0.54, TensorFlow 2.21.0 e Keras 3.15.1.

### 4.1 `saida/real02`: preparação final (US, `--max-itens 500`, regras novas)

| Medida | Valor |
|---|---|
| RN15 | 20.557 de 22.865 itens aptos |
| RN02 | 6.562 de 20.557 séries com quantidade média > 50 nos últimos 7 dias |
| Sorteadas | 500 séries, 617.959 linhas |
| Cortes | início 2022-09-04 · validação 2025-07-16 · teste 2026-05-11 · fim 2026-10-06 |
| Linhas aptas | 580.993 |
| Descartadas pela RN03 | 33.933 (5,49%) |
| Preenchidas | 35.241 |
| Amostras | treino 289.673 · validação 110.782 · teste 60.129 |
| Atributos | cobertura de 100% nas 500 séries |
| Commodities | 499 itens |

`--verificar`: **OK**, com maior erro relativo de 4,18e-07 (float32).

Referências na validação: 498 itens, 744.443 alvos avaliados, 31.031 não observados.

| Horizonte | h1 | h2 | h3 | h4 | h5 | h6 | h7 |
|---|---|---|---|---|---|---|---|
| MAPE ingênuo | 27,65% | 42,27% | 54,02% | 64,67% | 74,44% | 82,44% | 91,22% |
| MAPE regressão linear | 30,72% | 42,60% | 50,52% | 56,64% | 61,76% | 65,88% | 70,02% |
| Mediana do erro, ingênuo | 5,47% | 15,79% | 22,66% | 26,69% | 30,08% | 32,53% | 33,39% |

| Modelo | MAPE médio por item | MAPE geral | Itens que superam o ingênuo | Liberados (RN10, MAPE < 15%) |
|---|---|---|---|---|
| Ingênuo | 75,80% | 62,32% | — | 0 |
| Regressão linear | 67,02% | 53,98% | **328 de 498** | 5 |

O MAPE médio é puxado por uma cauda de poucos itens com erros enormes, mas a mediana do erro é baixa. O `real02` sorteou itens diferentes do `real01`, porque a aptidão mudou; não compare os dois diretamente. A comparação justa é a da seção 4.2.

**Base completa:** 6.562 séries aptas e líquidas, **≈ 8,07 milhões de linhas, ≈ 6,5 GB**, para 34,7 GB livres de 63,8 GB. Cabe; dá para rodar a etapa 2 sem `--max-itens`.

### 4.2 RN03: decisão e comparação

O problema: com a EMA calculada sobre todos os preços brutos, um anúncio-placeholder (99.999 ou 1 milhão de ouro) inflava a própria EMA, e o filtro descartava os preços reais por semanas. No item 238485, foram 106 de 223 dias.

Regra adotada (`rn03_por_serie`; parâmetros em `config.py`, todos marcados "A CONFIRMAR"):

1. a EMA de 14 dias usa só os preços anteriores **já aceitos**;
2. preço acima de 4× ou abaixo de 0,1× a EMA é descartado;
3. **7 preços seguidos** fora da faixa, do mesmo lado, confirmam uma mudança real de patamar. O novo patamar é a mediana da sequência: os preços próximos dela são aceitos e a EMA recomeça neles. Sem isso, a série travaria depois de uma mudança real;
4. um salto de **1.000× ou mais** sobre um patamar confirmado exige **28 preços seguidos**. O anúncio de 1 milhão de ouro que ficou sozinho por duas semanas no item 38518 não vira patamar;
5. o primeiro patamar da série só vale depois de 7 preços aceitos. Se outro patamar for confirmado antes, o primeiro é descartado (o placeholder de um item novo).

Na comparação, as variantes rodaram nas mesmas séries e com os mesmos cortes, na validação, com a regressão linear. O erro foi medido contra o **preço bruto**, nos dias "reais" por uma referência neutra (entre 0,1× e 4× a mediana centrada de 15 dias), e nas amostras que existem em todas as variantes.

| RN03 (500 séries do `real01`) | Dias descartados | Mediana do MAPE por item | Erros > 100% | Itens que superam o ingênuo | h1 | h7 |
|---|---|---|---|---|---|---|
| EMA de todos os preços (anterior) | 7,24% | 47,43% | 8,71% | 269 | 30,8% | 65,5% |
| Aceitos, confirmação 5 | 4,40% | 45,02% | 7,74% | 274 | 28,2% | 62,5% |
| **Aceitos, confirmação 7 (adotada)** | 5,51% | 44,07% | 7,31% | 296 | 28,0% | **61,0%** |
| Aceitos, confirmação 10 | 6,66% | 43,39% | 7,20% | 304 | 28,1% | 61,1% |

| RN03 (500 séries do `real02`) | MAPE médio por item | Mediana do MAPE por item | Erros > 100% | Itens que superam o ingênuo | h7 |
|---|---|---|---|---|---|
| EMA de todos os preços (anterior) | 59,49% | 48,95% | 9,41% | 279 | 66,2% |
| **Regra adotada** | **53,50%** | **45,53%** | **8,00%** | **317** | **61,2%** |

A confirmação de 10 dias ganha um pouco nas medianas, mas descarta picos reais de 7 a 9 dias, piora a média por item e tira amostras do treino. Por isso ficaram 7 dias.

Na amostra do `real01`, a média por item da regra nova (163,9%) fica acima da anterior (154,1%) por causa de **um único item** (42779, com erro de ~50.000% em qualquer regra). Na comparação item a item, **449 itens melhoram e 33 pioram**.

**Descartes perto de PATCH/EXPANSAO** (`real02`, treino + validação, 28 marcos, janela de ±7 dias):

| Regra | Perto de marcos | Demais dias | Razão |
|---|---|---|---|
| Anterior | 7,87% | 7,31% | 1,08 |
| **Adotada** | **5,80%** | **5,56%** | **1,04** |

Os dias perto de marcos concentram 29,1% dos descartes, em 28,3% dos dias. O efeito é pequeno.

### 4.3 Eventos e commodity

- **Pré-patch:** o primeiro patch de cada versão maior (10.0.0, 11.0.0, 12.0.0; historicamente 4.0.1 … 9.0.1) passa a marcar o `f_expansao`. Antes só o 12.0.0 era reconhecido, porque era o único com "pre-patch" no nome.
- **Versões repetidas:** a mesma versão de patch conta só na primeira data. As datas seguintes (9.2.5 e 10.2.6) são inícios de temporada, que a variável 13 já cobre.
- **`f_commodity`:** vem do `source_region` do item: 32512 = arquivo de commodities da região, em 10.881 itens. Antes ficava 0 em tudo, porque o histórico das commodities é gravado sob 3209. Hoje 499 das 500 séries do `real02` são commodities.

### 4.4 Ambiente de treino

`treinar.py --nome teste_ambiente --epocas 2 --amostras-por-epoca 20000` no `real02`: **5,3 s por época** (10,6 s no total), na CPU, com TensorFlow 2.21.0; `val_loss` (huber) 0,296 e `prever_teste: false`.

## 5. Decisões tomadas

Pendências da primeira versão:

1. **RN03:** EMA dos preços aceitos, com confirmação de patamar em 7 dias e salto absurdo de 1.000× exigindo 28 (seção 4.2). Delegado pelo autor: "o que for melhor para o treinamento".
2. **`f_commodity`:** vem do `source_region` (aprovado pelo autor).
3. **Eventos:** pré-patch pela versão maior e versão repetida contada uma vez, tratados no estudo; o banco não foi alterado. Delegado pelo autor.
4. **`aptidao_treinamento`:** revalidada pelo CU10-C3 (aprovado pelo autor).
5. **Atributos em `metadata_info` (JSON, com ids da API), sem colunas próprias:** para o treino não faz diferença, e assim não é preciso migração. Fica a sugestão de texto para o TC (seção 6). Delegado pelo autor.
6. **Dependências:** versões atuais (pandas 3, pyarrow 25, TensorFlow 2.21), testadas e registradas no `requirements.txt`; o aviso do NumPy 2.5 foi corrigido. Delegado pelo autor.

Decisões da parte de código:

- **Ordem da mescla no sync:** o que já existe vence; o `source` original é preservado.
- **`ChunkWriter` do CU10-C1:** passou a mesclar só o ETag e a origem.
- **Item 404:** nunca é reconsultado. Para reconsultar, basta remover `atributos_indisponiveis`.
- **Ícone:** só é pedido para quem não tem. A concorrência (10) e a pausa (0,1 s) ficaram como estavam.

## 6. Pendências e textos sugeridos para o TC

**Para decidir no Cowork:**

- **RN02 e itens do reino.** Das 6.562 séries aptas e líquidas da base completa, **6.547 são commodities**. O limite de quantidade média > 50 em 7 dias praticamente exclui os itens do reino (equipamentos têm poucas unidades à venda), embora os aptos se dividam meio a meio (10.162 do reino e 10.395 commodities). Se o modelo deve prever também itens do reino, a RN02 precisa de outro critério para eles.
- **Máscara dos alvos no treino.** O `treinar.py` não usa `obs_1..obs_7`: dias descartados ou preenchidos entram na perda com o último preço válido repetido. Recomendo mascarar a perda nesses alvos antes da etapa 2. A avaliação já ignora esses dias.
- **CU11-C3 (previsão diária).** Com a confirmação de 7 dias, uma mudança de patamar ainda não confirmada deixa o item sem amostra por até ~4 dias, depois dos 3 dias de preenchimento.
- **Item 42779:** erro de ~50.000% em qualquer regra. A RN10 o bloqueia, mas vale olhar a série.

**Texto sugerido para a RN03:**

> O pipeline de dados (Python) deve descartar registros cujo preço diário seja 300% superior ou 90% inferior à Média Móvel Exponencial (EMA) de 14 dias do item, calculada somente com os registros anteriores já aceitos. Quando o preço permanecer fora dessa faixa, do mesmo lado, por 7 registros seguidos, considera-se uma mudança real de patamar: os registros próximos da mediana dessa sequência são aceitos e a EMA recomeça a partir deles. Se a mudança for de 1.000 vezes ou mais em relação ao patamar anterior, são exigidos 28 registros seguidos. No início da série, o primeiro patamar só é considerado confirmado depois de 7 registros aceitos.

**Variáveis do CU11:**

- **12:** "pré-patch é o primeiro patch de cada nova versão maior do jogo".
- **18:** "commodity é o item cujo histórico vem do arquivo de commodities da região".

**Modelo relacional (7.2):** em vez de `classe VARCHAR(20)`, `subclasse VARCHAR(45)` e `raridade VARCHAR(10)`, os atributos do item ficam em `metadata_info` (JSONB), com os identificadores da API da Blizzard (`item_class_id`, `item_subclass_id`, `quality`, `level`, `sell_price`). O modelo precisa dos ids, e os nomes podem ser obtidos da API quando a tela precisar.
