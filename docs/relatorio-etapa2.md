# Relatório da etapa 2: primeiro treino da LSTM (estudo)

Etapa 2 de `estudos/lstm/ROTEIRO.md`, executada em 2026-10-06 e 2026-10-07 com a base completa (sem `--max-itens`), região US e parâmetros padrão. **Tudo foi avaliado só no período de validação.** Nenhum treino usou `--prever-teste` ou `--apenas-prever-teste` (`previu_teste: false` nos três `treino.json`); o teste fica para o CU11 (RN25).

Ambiente:

- Python 3.13.14, TensorFlow 2.21.0 e Keras 3.15.1, na CPU;
- pandas 3.0.6, pyarrow 25.0.1 e numpy 2.5.3;
- `pytest` do estudo com 22 testes passando antes da execução;
- banco local (`DB_HOST=localhost`, `DB_PORT=5435`, `--env-arquivo ../../backend/.env`).

## 1. Preparação (`saida/treino01`)

| Medida | Valor |
|---|---|
| Itens aptos (RN15) | 20.557 de 22.865 |
| Séries com liquidez (RN02: quantidade média > 50 nos últimos 7 dias) | 6.562 de 20.557, das quais 6.547 são commodities |
| Séries | 6.562 |
| Linhas (série × dia) | 8.073.939 |
| Linhas aptas a entrar numa janela | 7.587.388 |
| Descartadas pela RN03 | 436.153 (5,40%) |
| Preenchidas (RN24) | 456.334 |
| Cortes (RN25) | início 2022-09-04 · validação 2025-07-16 · teste 2026-05-11 · fim 2026-10-06 |
| Amostras | **treino 3.792.068 · validação 1.420.443 · teste 786.081** |
| Amostras descartadas por cruzarem uma data de corte | 61.941 |
| Cobertura dos atributos fixos | 100% (classe, subclasse, qualidade, nível, preço de venda ao vendedor) |
| Tempo da preparação | ~2,5 min |

**Colunas de entrada:**

| Grupo | `treino01` (eventos detalhados) | `treino01_agr` (`--eventos-agregados`) |
|---|---|---|
| Sequência (30 passos) | **46**: as 16 de base, mais 2 da Feira de Negrilua e 28 dos festivais (14 festivais × "ativo hoje" e "fração ativa nos próximos 7 dias") | **16** (só `f_evento`, "algum festival ativo") |
| Estáticas | 4 (`f_qualidade`, `f_nivel_item`, `f_tem_piso`, `f_commodity`) | 4 |
| Categóricas (embeddings) | 2 (`classe_idx`, `subclasse_idx`) | 2 |

**Festivais que entraram** (todos tiveram dias ativos no treino): Brewfest, Bronze Celebration, Children's Week, Day of the Dead, Feast of Winter Veil, Hallow's End, Harvest Festival, Love is in the Air, Lunar Festival, Midsummer Fire Festival, New Year, Noblegarden, Pilgrim's Bounty e Pirates' Day, além da Feira de Negrilua (Darkmoon Faire).

**Ficaram de fora:** nenhum (`sem_ocorrencia_no_treino` vazio).

A `treino01_agr` tem as mesmas séries, linhas, amostras, cortes e constantes do alvo da `treino01`; só mudam as colunas de eventos. A verificação de ida e volta (`avaliar.py --verificar`) deu **OK**, com maior erro relativo de 7,11e-07, que vem do `y` gravado em float32.

## 2. Resultados na validação

São 6.484 itens avaliados e 9.561.970 alvos observados (381.131 alvos não observados ficam de fora, como manda o `avaliar.py`). Todos os modelos foram avaliados sobre exatamente as mesmas amostras e alvos.

| Modelo | MAPE médio por item | Mediana do MAPE por item | h1 | h2 | h3 | h4 | h5 | h6 | h7 | Itens que superam o ingênuo | Itens que superam a regressão linear | Itens liberados (RN10) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Ingênuo | 76,31% | 47,19% | 26,64% | 40,47% | 51,81% | 62,07% | 71,12% | 80,06% | 88,98% | — | 2.535 | 0 |
| Regressão linear | 68,69% | 44,51% | 29,64% | 40,99% | 48,77% | 54,94% | 60,22% | 65,04% | 69,43% | 3.949 | — | 80 |
| `lstm01` | 62,70% | 40,25% | 26,10% | 36,53% | 44,09% | 51,38% | 57,29% | 62,18% | 66,57% | 5.100 | 5.423 | 315 |
| `lstm01_sem_mascara` | 62,16% | 40,00% | 26,03% | 36,77% | 44,42% | 50,34% | 55,74% | 60,60% | 65,44% | 5.232 | 5.672 | 342 |
| `lstm01_agr` | **59,92%** | **38,80%** | **25,65%** | **35,67%** | **42,91%** | **49,03%** | **54,44%** | **58,56%** | **63,23%** | **5.389** | **5.785** | 338 |

- O MAPE geral, sobre todos os alvos juntos, foi: ingênuo 60,10%, regressão linear 52,68%, `lstm01` 49,12%, `lstm01_sem_mascara` 48,43% e `lstm01_agr` 47,03%.
- "Liberados (RN10)": MAPE ≤ 15% e menor que o do ingênuo, nos 6.484 itens.

**Leitura:**

- **As três LSTMs superam o ingênuo e a regressão linear** em todas as medidas e em todos os horizontes. Em h1, a LSTM fica perto do ingênuo (26,1% contra 26,6%), e a vantagem cresce com o horizonte (h7: 66,6% contra 89,0%). A regressão linear perde do ingênuo em h1.
- **Eventos agregados contra detalhados:** o `lstm01_agr`, com 16 colunas, foi melhor que o `lstm01`, com 46. Neste primeiro treino, detalhar os festivais e a Feira de Negrilua não ajudou.
  - Cuidado: há um único treino por configuração (semente 42), e o `lstm01_agr` treinou 52 épocas, contra 28 do `lstm01`. Parte da diferença pode vir da dinâmica do treino, não das variáveis.
  - Para separar os dois efeitos, seria preciso repetir com outras sementes.
- **Máscara:** o `lstm01_sem_mascara` ficou ligeiramente melhor que o `lstm01` (0,5 ponto no MAPE médio e 27 itens liberados a mais). A diferença é pequena e tem o mesmo cuidado de execução única. O `val_loss` dos dois não é comparável, porque o sem máscara inclui os dias preenchidos.
- A validação serve tanto para a parada antecipada quanto para esta comparação. O número das LSTMs é, portanto, levemente otimista. O teste continua intocado.

## 3. Treinos

Parâmetros comuns (padrão do `treinar.py`):

- perda Huber, LSTM de 64 unidades, dropout 0,2, Adam com taxa 0,001 e lote de 512;
- 400.000 amostras de treino sorteadas por época;
- parada antecipada com 200.000 amostras fixas da validação (paciência de 10 épocas, máximo de 100) e semente 42.

| Treino | Base | Máscara | Épocas executadas | Melhor época | `val_loss` na melhor | Tempo por época | Tempo total |
|---|---|---|---|---|---|---|---|
| `lstm01` | `treino01` | sim | 28 | 18 | 0,2725 | 28,7 s | 802 s (13 min 22 s) |
| `lstm01_sem_mascara` | `treino01` | não | 19 | 9 | 0,2647 | 30,0 s | 570 s (9 min 30 s) |
| `lstm01_agr` | `treino01_agr` | sim | 52 | 42 | 0,2696 | 30,6 s | 1.592 s (26 min 32 s) |

O tempo total é o do `fit`, como registrado no `treino.json`; a previsão da validação e a gravação do modelo levam alguns segundos a mais. O histórico de cada época está em `saida/<base>/modelos/<nome>/historico.csv`.

## 4. Os 10 itens com maior erro no `lstm01`

| Item | Nome | MAPE `lstm01` | MAPE ingênuo | MAPE regressão linear | Alvos avaliados | Preço observado na validação (mín · mediana · máx) |
|---|---|---|---|---|---|---|
| 2894 | Rhapsody Malt | 19.968,1% | 23.122,2% | 23.859,3% | 95 | 1 prata · 1,80 ouro · 1.746 ouro |
| 162582 | Jungle Heat P'terrorwings | 9.106,5% | 11.130,1% | 11.220,0% | 428 | 4,49 · 3.000,50 · 49.998 ouro |
| 159873 | Hatherford Brunost | 5.509,4% | 5.950,6% | 5.030,6% | 515 | 1,19 · 50,00 · 49.998 ouro |
| 264982 | Wine Not | 3.414,4% | 3.436,5% | 3.340,4% | 35 | 0,80 · 48,99 · 69,50 ouro |
| 264992 | Blood Knight Burger | 3.182,3% | 3.272,2% | 3.241,8% | 49 | 0,97 · 59,95 · 500,00 ouro |
| 264993 | Delicate Dart Legs | 3.025,2% | 3.071,0% | 2.919,7% | 35 | 0,97 · 55,51 · 62,60 ouro |
| 37101 | Ivory Ink | 2.878,9% | 2.449,0% | 2.968,3% | 720 | 1 prata · 3,46 · 2.000 ouro |
| 169118 | Hydro-Stasis Plant Matter | 2.544,3% | 2.929,4% | 2.728,4% | 834 | 10,00 · 563,25 · 99.998 ouro |
| 56234 | Smooth Scale | 2.405,4% | 2.754,8% | 2.787,1% | 255 | 1 prata · 1,01 · 273.759 ouro |
| 2686 | Thunder Ale | 2.369,2% | 1.377,3% | 1.736,0% | 352 | 0,77 · 2.009,03 · 121.929 ouro |

Pistas para a investigação:

- **Classe:** 8 dos 10 são comida e bebida (classe 0, subclasse 5) e 2 são da classe 15, subclasse 0 (Ivory Ink e Smooth Scale). Todos são commodities.
- **Erro geral, não da LSTM:** o ingênuo e a regressão linear erram na mesma ordem de grandeza.
- **Faixa de preços:** em todos, os preços **aceitos** na validação cobrem de 3 a 7 ordens de grandeza (de 1 prata a centenas de milhares de ouro). A série alterna patamares que duram o bastante para a RN03 confirmar (7 dias, ou 28 num salto de 1.000×). O erro percentual explode quando o preço real cai para perto do mínimo depois de um patamar alto.
- **Itens novos:** 264982, 264992 e 264993 têm menos de 75 dias na validação.
- **Hipótese a conferir:** itens também vendidos por NPC, com oferta esporádica na Casa de Leilões, em que o "preço mínimo do dia" não representa um mercado contínuo.

O MAPE médio por item é sensível a esses poucos itens; por isso a tabela traz também a mediana.

## 5. Arquivos

Em `estudos/lstm/saida/` (fora do Git):

- `treino01/` e `treino01_agr/`, com os arquivos da preparação e `avaliacao_validacao_<rotulo>_*`;
- `modelos/lstm01`, `modelos/lstm01_sem_mascara` e `modelos/lstm01_agr`, com `modelo.keras`, `normalizacao.json`, `treino.json`, `historico.csv` e `previsoes_validacao.parquet`;
- os logs: `treino01_preparar.log`, `treino01_passo2.log`, `etapa2_sequencia.log`, `treino01/treino_*.log` e `treino01_agr/treino_*.log`.

Nenhuma regra ou código do estudo foi alterado nesta etapa, e nenhum erro foi encontrado na execução.
