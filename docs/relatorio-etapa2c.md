# Relatório da etapa 2c: generalização para itens fora do treino

Etapa 2c de `estudos/lstm/ROTEIRO.md`, executada em 2026-10-07 conforme `estudos/lstm/pedido-etapa2c.md`.

- Configuração: a escolhida na etapa 2b (eventos agregados, sem máscara), com os parâmetros padrão do `treinar.py`.
- **Tudo foi avaliado só no período de validação.** Nenhum treino previu o teste (`previu_teste: false` nos quatro `treino.json`), e o `prever.py` só prevê a validação.
- Antes de começar, o `pytest` do estudo tinha 33 testes passando, e o estado foi salvo no commit `c42a371`.
- Nenhum código nem regra do estudo foi alterado.

Este relatório traz os números; a interpretação será feita com o autor.

## 1. O que foi rodado

### Base `treino2c`

Mesma seleção da etapa 2: 6.562 séries e 8.073.939 linhas. Dos itens, 20% (**1.312 de 6.562**) foram reservados por sorteio estratificado pela classe, com semente 42. A verificação de ida e volta deu **OK** (maior erro relativo de 5,73e-07).

| Período | Amostras: total | Reservadas | Não reservadas | Itens: total | Reservados | Não reservados |
|---|---|---|---|---|---|---|
| treino | 3.792.068 | 774.755 | 3.017.313 | 5.734 | 1.165 | 4.569 |
| validação | 1.420.443 | 289.655 | 1.130.788 | 6.484 | 1.296 | 5.188 |
| teste | 786.081 | 156.067 | 630.014 | 6.536 | 1.306 | 5.230 |

Os itens contam como "do período" quando têm ao menos uma amostra nele. Dos 1.312 reservados, 1.298 têm amostras no treino ou na validação (é o número do bloco `reserva` dos `treino.json`), e 1.296 têm alvos avaliados na validação.

### Base `fora2c`

Amostra de **3.000 séries** entre os 16.303 itens que não estão na `treino2c`, preparada com `--ignorar-aptidao` e `--sem-filtro-liquidez` e normalizada como a versão do modelo (`--normalizacao-de saida/treino2c`).

| Medida | Valor |
|---|---|
| Linhas | 3.940.075 (2.951.595 aptas) |
| Amostras de validação | 409.950 |
| Itens com alvos avaliados na validação | **2.596** |
| Commodities | 686 (1.910 não commodities) |
| Aptos pela RN15 | 2.419 (177 não aptos) |
| Líquidos pela RN02 | 0 (todos os 2.596 são "não líquidos") |
| Cobertura dos atributos fixos | 99,27% das séries |

A base também tem amostras de treino (1.343.862) e de teste (186.729), mas elas não são usadas: só a validação foi prevista.

### Treinos

Parâmetros padrão:

- perda Huber, LSTM de 64 unidades, dropout 0,2, Adam com taxa 0,001 e lote de 512;
- 400.000 amostras de treino por época;
- parada antecipada com 200.000 amostras da validação (paciência de 10 épocas);
- sem máscara.

| Treino | Épocas | Melhor época | Tempo por época | Tempo total | `itens_reservados` | `incluidos_no_treino` | `amostras_reservadas_treino` | `amostras_reservadas_validacao` |
|---|---|---|---|---|---|---|---|---|
| `c_sem_s42` | 47 | 37 | 30,0 s | 23 min 29 s | 1.298 | false | 774.755 | 289.655 |
| `c_todos_s42` | 45 | 35 | 31,6 s | 23 min 42 s | 1.298 | true | 774.755 | 289.655 |
| `c_sem_s7` | 30 | 20 | 29,4 s | 14 min 43 s | 1.298 | false | 774.755 | 289.655 |
| `c_todos_s7` | 50 | 40 | 32,7 s | 27 min 13 s | 1.298 | true | 774.755 | 289.655 |

Os blocos `reserva` foram conferidos: `incluidos_no_treino` é `false` nos `c_sem` e `true` nos `c_todos`. A sequência inteira (preparações, quatro treinos, avaliações, comparações e previsões) levou 1 h 39 min.

## 2. Conferência com a etapa 2b

Mediana do MAPE por item em todos os 6.484 itens da validação:

| Modelo | Mediana do MAPE por item | MAPE médio por item | Mediana do MdAPE por item | Liberados (RN10) |
|---|---|---|---|---|
| `c_todos_s42` | 38,61% | 59,67% | 22,82% | 591 |
| `c_todos_s7` | 38,96% | 60,55% | 22,60% | 608 |
| *Etapa 2b, configuração escolhida (3 sementes)* | *38,66% ± 0,19* | *59,69% ± 0,33* | — | — |
| `c_sem_s42` (sem os reservados no treino) | 39,28% | 60,80% | 22,52% | 563 |
| `c_sem_s7` (sem os reservados no treino) | 39,29% | 60,52% | 22,86% | 540 |

A RN10 desta etapa é a do `avaliar.py`: MdAPE ≤ 15% e menor que o do ingênuo.

## 3. Parte A: itens não vistos (`treino2c`)

Por treino e por grupo (`por_grupo.reservado`). O MdAPE do ingênuo é o mesmo nos quatro treinos, porque os dias avaliados são os mesmos.

| Treino · grupo | Itens | Mediana do MdAPE por item | MdAPE do ingênuo | Mediana do MAPE por item | Mediana do erro relativo ao ingênuo | Erro relativo < 1 | Liberados (RN10) |
|---|---|---|---|---|---|---|---|
| `c_sem_s42` · reservados | 1.296 | 22,27% | 23,53% | 39,81% | 0,848 | 83,4% | 128 (9,9%) |
| `c_sem_s42` · não reservados | 5.188 | 22,59% | 24,23% | 39,13% | 0,846 | 82,4% | 435 (8,4%) |
| `c_todos_s42` · reservados | 1.296 | 22,59% | 23,53% | 38,96% | 0,851 | 82,6% | 135 (10,4%) |
| `c_todos_s42` · não reservados | 5.188 | 22,87% | 24,23% | 38,45% | 0,845 | 82,0% | 456 (8,8%) |
| `c_sem_s7` · reservados | 1.296 | 22,86% | 23,53% | 39,85% | 0,854 | 82,8% | 123 (9,5%) |
| `c_sem_s7` · não reservados | 5.188 | 22,86% | 24,23% | 39,13% | 0,852 | 81,3% | 417 (8,0%) |
| `c_todos_s7` · reservados | 1.296 | 22,47% | 23,53% | 39,86% | 0,846 | 84,0% | 136 (10,5%) |
| `c_todos_s7` · não reservados | 5.188 | 22,63% | 24,23% | 38,74% | 0,842 | 83,2% | 472 (9,1%) |

## 4. Comparação pareada nos reservados

São os 1.296 reservados, item a item, com os mesmos itens e os mesmos dias nos dois modelos. A diferença é A − B. Para MdAPE e MAPE ela está em pontos percentuais; para o erro relativo, na própria escala (razão). Valor positivo significa que A erra mais.

**Semente 42: não vistos (A, `c_sem_s42`) × vistos (B, `c_todos_s42`)**

| Medida | Mediana A | Mediana B | Mediana de A − B | p25 a p75 de A − B | Itens em que A é pior |
|---|---|---|---|---|---|
| MdAPE | 22,27% | 22,59% | −0,11 | −1,14 a +0,63 | 596 |
| MAPE | 39,81% | 38,96% | +0,41 | −0,45 a +1,41 | 834 |
| Erro relativo ao ingênuo | 0,848 | 0,851 | −0,0003 | −0,0132 a +0,0114 | 639 |

- Itens com diferença de até 1 ponto no MdAPE: **730** (56,3%).
- RN10: 128 liberados em A e 135 em B; **109 nos dois**, 19 só em A e 26 só em B.

**Semente 7: não vistos (A, `c_sem_s7`) × vistos (B, `c_todos_s7`)**

| Medida | Mediana A | Mediana B | Mediana de A − B | p25 a p75 de A − B | Itens em que A é pior |
|---|---|---|---|---|---|
| MdAPE | 22,86% | 22,47% | +0,23 | −0,45 a +1,01 | 777 |
| MAPE | 39,85% | 39,86% | +0,07 | −0,76 a +0,86 | 689 |
| Erro relativo ao ingênuo | 0,854 | 0,846 | +0,0049 | −0,0056 a +0,0176 | 816 |

- Itens com diferença de até 1 ponto no MdAPE: **794** (61,3%).
- RN10: 123 liberados em A e 136 em B; **112 nos dois**, 11 só em A e 24 só em B.

**Ruído: controle s42 (A, `c_todos_s42`) × controle s7 (B, `c_todos_s7`)**, os mesmos itens vistos pelos dois

| Medida | Mediana A | Mediana B | Mediana de A − B | p25 a p75 de A − B | Itens em que A é pior |
|---|---|---|---|---|---|
| MdAPE | 22,59% | 22,47% | +0,21 | −0,49 a +0,99 | 740 |
| MAPE | 38,96% | 39,86% | −0,24 | −1,06 a +0,49 | 539 |
| Erro relativo ao ingênuo | 0,851 | 0,846 | +0,0021 | −0,0080 a +0,0157 | 721 |

- Itens com diferença de até 1 ponto no MdAPE: **817** (63,0%).
- RN10: 135 liberados em A e 136 em B; **119 nos dois**, 16 só em A e 17 só em B.

**Lado a lado:**

| | Mediana de A − B no MdAPE | Mediana de A − B no MAPE | Mediana de A − B no erro relativo |
|---|---|---|---|
| Não vistos × vistos, s42 | −0,11 | +0,41 | −0,0003 |
| Não vistos × vistos, s7 | +0,23 | +0,07 | +0,0049 |
| Ruído entre sementes | +0,21 | −0,24 | +0,0021 |

## 5. Parte B: itens fora da seleção (`fora2c`)

Mesmas medidas da seção 3, com os modelos treinados com todos os itens da `treino2c`. Na `fora2c`, todos os itens são "não líquidos" pela RN02, então o grupo "líquido: sim" não existe e a linha "líquido: não" repete "todos".

**`c_todos_s42`**

| Grupo | Itens | Mediana do MdAPE por item | MdAPE do ingênuo | Mediana do MAPE por item | Mediana do erro relativo ao ingênuo | Erro relativo < 1 | Liberados (RN10) |
|---|---|---|---|---|---|---|---|
| todos | 2.596 | 16,85% | 8,52% | 38,21% | 1,081 | 28,0% | 46 (1,8%) |
| commodity: sim | 686 | 19,97% | 12,34% | 45,87% | 1,018 | 47,5% | 13 (1,9%) |
| commodity: não | 1.910 | 15,81% | 7,35% | 35,54% | 1,100 | 21,1% | 33 (1,7%) |
| apto pela RN15: sim | 2.419 | 17,15% | 8,83% | 38,63% | 1,077 | 29,1% | 43 (1,8%) |
| apto pela RN15: não | 177 | 14,20% | 3,88% | 26,38% | 1,166 | 13,6% | 3 (1,7%) |
| líquido pela RN02: não | 2.596 | 16,85% | 8,52% | 38,21% | 1,081 | 28,0% | 46 (1,8%) |

**`c_todos_s7`**

| Grupo | Itens | Mediana do MdAPE por item | MdAPE do ingênuo | Mediana do MAPE por item | Mediana do erro relativo ao ingênuo | Erro relativo < 1 | Liberados (RN10) |
|---|---|---|---|---|---|---|---|
| todos | 2.596 | 15,96% | 8,52% | 38,76% | 1,054 | 30,5% | 53 (2,0%) |
| commodity: sim | 686 | 19,58% | 12,34% | 45,91% | 1,014 | 46,5% | 15 (2,2%) |
| commodity: não | 1.910 | 14,80% | 7,35% | 36,61% | 1,070 | 24,7% | 38 (2,0%) |
| apto pela RN15: sim | 2.419 | 16,23% | 8,83% | 39,46% | 1,051 | 31,5% | 44 (1,8%) |
| apto pela RN15: não | 177 | 11,73% | 3,88% | 27,45% | 1,164 | 16,4% | 9 (5,1%) |
| líquido pela RN02: não | 2.596 | 15,96% | 8,52% | 38,76% | 1,054 | 30,5% | 53 (2,0%) |

Na `fora2c`, a mediana do erro relativo ao ingênuo fica **acima de 1** nos dois modelos e em todos os grupos. Já o MdAPE do ingênuo (8,52%) é bem menor que na `treino2c` (23,5% a 24,2%).

## 6. Erro pela idade do item

Idade do item no dia da previsão (`por_idade`). A razão é o MdAPE do modelo dividido pelo do ingênuo: abaixo de 1, o modelo erra menos.

**`fora2c`, modelo `c_todos_s42`**

| Idade do item no dia da previsão | Alvos | Itens | MdAPE | MdAPE do ingênuo | Razão (modelo ÷ ingênuo) |
|---|---|---|---|---|---|
| até 89 dias | 21.314 | 152 | 16,52% | 13,76% | 1,200 |
| 90 a 119 dias | 15.976 | 96 | 13,71% | 8,01% | 1,711 |
| 120 a 179 dias | 27.937 | 106 | 18,62% | 12,18% | 1,529 |
| 180 a 364 dias | 66.586 | 195 | 20,40% | 14,55% | 1,402 |
| 365 dias ou mais | 2.319.814 | 2.439 | 14,64% | 6,05% | 2,417 |

**`treino2c`, modelo `c_sem_s42`**

| Idade do item no dia da previsão | Alvos | Itens | MdAPE | MdAPE do ingênuo | Razão (modelo ÷ ingênuo) |
|---|---|---|---|---|---|
| até 89 dias | 43.896 | 736 | 13,68% | 14,88% | 0,920 |
| 90 a 119 dias | 9.275 | 81 | 12,56% | 13,64% | 0,921 |
| 120 a 179 dias | 18.802 | 55 | 18,12% | 20,00% | 0,906 |
| 180 a 364 dias | 249.931 | 844 | 15,32% | 16,77% | 0,914 |
| 365 dias ou mais | 9.240.066 | 5.729 | 20,11% | 21,62% | 0,930 |

Um item entra em mais de uma faixa quando a idade dele muda ao longo da validação, por isso a soma da coluna "Itens" passa do total de itens.

## 7. Problemas encontrados

A execução não teve erros; nenhuma conferência pedida falhou. Pontos a registrar:

- **Contagem de reservados:** 1.312 itens foram reservados na preparação; 1.298 têm amostras no treino ou na validação, 1.296 têm alvos avaliados na validação e 1.165 têm amostras de treino. Os demais são itens com histórico curto demais para formar amostras naquele período.
- **`fora2c`:**
  - das 3.000 séries sorteadas, 2.596 têm alvos avaliáveis na validação;
  - 0,73% das séries estão sem atributos fixos;
  - nenhum item é "líquido" pela RN02, então o grupo `liquido_rn02` tem só "não";
  - a variação do índice da subclasse (variável 6) é calculada só com os itens da `fora2c`, e não com o mercado inteiro, como registra o README do estudo.
- O servidor local do painel de acompanhamento (`.claude/launch.json`) foi reiniciado uma vez pelo app, sem efeito nos treinos.

Os arquivos ficam em `estudos/lstm/saida/` (fora do Git):

- `treino2c/`, com as avaliações, os modelos, `comparacao_s42.json`, `comparacao_s7.json` e `ruido_sementes.json`;
- `fora2c/`, com as previsões e avaliações dos dois modelos;
- os logs `etapa2c_sequencia.log`, `treino2c_preparar.log` e `fora2c_preparar.log`;
- o painel dos treinos em `painel/index.html`.
