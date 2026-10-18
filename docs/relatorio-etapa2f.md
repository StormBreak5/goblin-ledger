# Relatório da etapa 2f: generalização com a configuração final

Etapa 2f de `estudos/lstm/ROTEIRO.md`, executada em 2026-10-18 conforme `estudos/lstm/pedido-etapa2f.md`. Repete as medidas de generalização da etapa 2c (Parte A, itens não vistos; Parte B, itens fora da seleção) com a configuração final da etapa 2e: eventos agregados, sem máscara e **perda MAE**.

**Esta etapa só mede; não decide nada nem muda nenhuma configuração.** Este relatório traz os números, sem propor mudanças.

- **Bases:** foram usadas as que já existiam, `saida/treino2c` (20% dos itens reservados) e `saida/fora2c` (3.000 itens fora da seleção). Nenhuma base nova foi preparada.
- **Tudo foi avaliado só no período de validação.** Nenhum treino previu o teste (`previu_teste: false` nos quatro `treino.json`).
- Antes de começar, o `pytest` do estudo tinha 40 testes passando, e o estado foi salvo no commit `0dcf690`.
- Nenhum código nem regra do estudo foi alterado.

Os números entre parênteses, quando marcados como "2c", são os da etapa 2c (perda Huber), tirados de `docs/relatorio-etapa2c.md`. Nas comparações de liberados com a 2c, uso o número **sem** o mínimo de dias, porque a 2c não tinha o mínimo.

## 1. O que foi rodado

**Comandos**, a partir de `estudos/lstm`, um treino por vez, com o log em `saida/etapa2f_sequencia.log` e a saída de cada comando num log próprio:

```bash
for s in 42 7; do
  python treinar.py --pasta saida/treino2c --nome m_sem_s$s --semente $s --perda mae
  python treinar.py --pasta saida/treino2c --nome m_todos_s$s --semente $s --perda mae --incluir-reservados
  for n in m_sem m_todos; do
    python avaliar.py --pasta saida/treino2c --periodo validacao \
        --previsoes saida/treino2c/modelos/${n}_s$s/previsoes_validacao.parquet --rotulo ${n}_s$s
  done
done
for s in 42 7; do
  python comparar.py --a saida/treino2c/avaliacao_validacao_m_sem_s${s}_itens.csv \
      --b saida/treino2c/avaliacao_validacao_m_todos_s${s}_itens.csv \
      --rotulos "não vistos" "vistos" --filtro reservado --saida saida/treino2c/comparacao_mae_s$s.json
done
python comparar.py --a saida/treino2c/avaliacao_validacao_m_todos_s42_itens.csv \
    --b saida/treino2c/avaliacao_validacao_m_todos_s7_itens.csv \
    --rotulos "controle s42" "controle s7" --filtro reservado --saida saida/treino2c/ruido_sementes_mae.json
for s in 42 7; do
  python prever.py --modelo saida/treino2c/modelos/m_todos_s$s --pasta saida/fora2c
  python avaliar.py --pasta saida/fora2c --periodo validacao \
      --previsoes saida/fora2c/previsoes_validacao_m_todos_s$s.parquet --rotulo m_todos_s$s
done
for s in 42 7; do
  python generalizacao.py liquidez \
      --avaliacao saida/treino2c/avaliacao_validacao_m_todos_s${s}_itens.csv \
      --avaliacao saida/fora2c/avaliacao_validacao_m_todos_s${s}_itens.csv --saida saida/liquidez_mae_s$s.csv
  python generalizacao.py novos --avaliacao saida/treino2c/avaliacao_validacao_m_sem_s${s}_itens.csv \
      --saida saida/novos_mae_s$s.csv
done
```

Para as colunas "2c" das seções 5 e 6, o mesmo `generalizacao.py` foi rodado também sobre as avaliações da etapa 2c (`c_todos_s*` e `c_sem_s*`). As saídas ficaram fora do estudo, numa pasta temporária. Na 2c a RN10 não tinha o mínimo de dias, então os liberados dela correspondem ao "sem mínimo" da 2f.

**Treinos** (parâmetros padrão; perda `mae` conferida nos quatro):

| Treino | Épocas | Melhor época | Tempo por época | Tempo total | `itens_reservados` | `incluidos_no_treino` | `amostras_reservadas_treino` | `amostras_reservadas_validacao` |
|---|---|---|---|---|---|---|---|---|
| `m_sem_s42` | 59 | 49 | 29,0 s | 28 min 30 s | 1.298 | false | 774.755 | 289.655 |
| `m_todos_s42` | 47 | 37 | 30,5 s | 23 min 51 s | 1.298 | true | 774.755 | 289.655 |
| `m_sem_s7` | 50 | 40 | 29,9 s | 24 min 54 s | 1.298 | false | 774.755 | 289.655 |
| `m_todos_s7` | 52 | 42 | 29,8 s | 25 min 52 s | 1.298 | true | 774.755 | 289.655 |

Os blocos `reserva` foram conferidos: `incluidos_no_treino` é `false` nos `m_sem` e `true` nos `m_todos`. A sequência inteira levou 1 h 47 min.

**Em todos os 6.484 itens da `treino2c`:**

| Modelo | Mediana do MdAPE por item | Mediana do MAPE por item | Liberados (com mínimo) | Liberados (sem mínimo) |
|---|---|---|---|---|
| `m_todos_s42` | 20,85% (2c: 22,82%) | 37,53% (2c: 38,61%) | 795 | 1.018 (2c: 591) |
| `m_todos_s7` | 20,81% (2c: 22,60%) | 38,08% (2c: 38,96%) | 847 | 1.071 (2c: 608) |
| `m_sem_s42` | 20,65% (2c: 22,52%) | 37,96% (2c: 39,28%) | 852 | 1.091 (2c: 563) |
| `m_sem_s7` | 20,70% (2c: 22,86%) | 37,36% (2c: 39,29%) | 811 | 1.043 (2c: 540) |

A RN10 desta etapa é MdAPE ≤ 15% e menor que o do ingênuo, com pelo menos 30 dias de previsões avaliadas (`minimo_dias_rn10`).

## 2. Parte A: itens não vistos (`treino2c`)

Por treino e por grupo (`por_grupo.reservado`). O MdAPE do ingênuo é o mesmo nos quatro treinos: 23,53% nos reservados e 24,23% nos não reservados.

| Treino · grupo | Itens | Mediana do MdAPE por item (2c) | Mediana do MAPE por item | Mediana do erro relativo (2c) | Erro relativo < 1 (2c) | Liberados com o mínimo | Liberados sem o mínimo (2c) |
|---|---|---|---|---|---|---|---|
| `m_sem_s42` · reservados | 1.296 | 20,67% (22,27%) | 38,51% | 0,837 (0,848) | 90,7% (83,4%) | 189 (14,6%) | 244 (18,8%) (128, 9,9%) |
| `m_sem_s42` · não reservados | 5.188 | 20,64% (22,59%) | 37,83% | 0,833 (0,846) | 89,2% (82,4%) | 663 (12,8%) | 847 (16,3%) (435, 8,4%) |
| `m_todos_s42` · reservados | 1.296 | 20,83% (22,59%) | 37,96% | 0,837 (0,851) | 90,1% (82,6%) | 174 (13,4%) | 224 (17,3%) (135, 10,4%) |
| `m_todos_s42` · não reservados | 5.188 | 20,85% (22,87%) | 37,46% | 0,832 (0,845) | 88,8% (82,0%) | 621 (12,0%) | 794 (15,3%) (456, 8,8%) |
| `m_sem_s7` · reservados | 1.296 | 20,70% (22,86%) | 37,61% | 0,841 (0,854) | 91,5% (82,8%) | 175 (13,5%) | 230 (17,7%) (123, 9,5%) |
| `m_sem_s7` · não reservados | 5.188 | 20,71% (22,86%) | 37,33% | 0,834 (0,852) | 89,7% (81,3%) | 636 (12,3%) | 813 (15,7%) (417, 8,0%) |
| `m_todos_s7` · reservados | 1.296 | 20,71% (22,47%) | 38,70% | 0,844 (0,846) | 91,5% (84,0%) | 179 (13,8%) | 230 (17,7%) (136, 10,5%) |
| `m_todos_s7` · não reservados | 5.188 | 20,84% (22,63%) | 38,02% | 0,840 (0,842) | 89,4% (83,2%) | 668 (12,9%) | 841 (16,2%) (472, 9,1%) |

## 3. Comparação pareada nos reservados

São os 1.296 reservados, item a item, com os mesmos itens e os mesmos dias nos dois modelos. A diferença é A − B. Para MdAPE e MAPE ela está em pontos percentuais; para o erro relativo, na própria escala. Valor positivo significa que A erra mais.

**Semente 42: não vistos (A, `m_sem_s42`) × vistos (B, `m_todos_s42`)**

| Medida | Mediana A | Mediana B | Mediana de A − B | p25 a p75 de A − B | Itens em que A é pior |
|---|---|---|---|---|---|
| MdAPE | 20,67% | 20,83% | +0,00 | −0,64 a +0,48 | 649 |
| MAPE | 38,51% | 37,96% | +0,11 | −0,42 a +1,11 | 742 |
| Erro relativo ao ingênuo | 0,837 | 0,837 | +0,0003 | −0,0093 a +0,0101 | 660 |

- Itens com diferença de até 1 ponto no MdAPE: **922** (71,1%).
- RN10 (com o mínimo): 189 liberados em A e 174 em B; **166 nos dois**, 23 só em A e 8 só em B.

**Semente 7: não vistos (A, `m_sem_s7`) × vistos (B, `m_todos_s7`)**

| Medida | Mediana A | Mediana B | Mediana de A − B | p25 a p75 de A − B | Itens em que A é pior |
|---|---|---|---|---|---|
| MdAPE | 20,70% | 20,71% | −0,02 | −0,59 a +0,54 | 630 |
| MAPE | 37,61% | 38,70% | −0,39 | −1,21 a +0,20 | 407 |
| Erro relativo ao ingênuo | 0,841 | 0,844 | −0,0025 | −0,0138 a +0,0077 | 563 |

- Itens com diferença de até 1 ponto no MdAPE: **916** (70,7%).
- RN10 (com o mínimo): 175 liberados em A e 179 em B; **159 nos dois**, 16 só em A e 20 só em B.

**Ruído: controle s42 (A, `m_todos_s42`) × controle s7 (B, `m_todos_s7`)**

| Medida | Mediana A | Mediana B | Mediana de A − B | p25 a p75 de A − B | Itens em que A é pior |
|---|---|---|---|---|---|
| MdAPE | 20,83% | 20,71% | +0,03 | −0,50 a +0,65 | 673 |
| MAPE | 37,96% | 38,70% | −0,27 | −1,21 a +0,23 | 487 |
| Erro relativo ao ingênuo | 0,837 | 0,844 | −0,0028 | −0,0141 a +0,0076 | 555 |

- Itens com diferença de até 1 ponto no MdAPE: **878** (67,7%).
- RN10 (com o mínimo): 174 liberados em A e 179 em B; **161 nos dois**, 13 só em A e 18 só em B.

**Lado a lado com a etapa 2c** (mediana de A − B):

| Comparação | MdAPE, Huber (2c) | MdAPE, MAE (2f) | MAPE, Huber (2c) | MAPE, MAE (2f) | Erro relativo, Huber (2c) | Erro relativo, MAE (2f) | Até 1 ponto no MdAPE, 2c → 2f |
|---|---|---|---|---|---|---|---|
| Não vistos × vistos, s42 | −0,11 | +0,00 | +0,41 | +0,11 | −0,0003 | +0,0003 | 730 → 922 |
| Não vistos × vistos, s7 | +0,23 | −0,02 | +0,07 | −0,39 | +0,0049 | −0,0025 | 794 → 916 |
| Ruído entre sementes | +0,21 | +0,03 | −0,24 | −0,27 | +0,0021 | −0,0028 | 817 → 878 |

Na 2c, a concordância da RN10 (sem o mínimo de dias) foi de 109 / 19 / 26 (s42), 112 / 11 / 24 (s7) e 119 / 16 / 17 (ruído), contados como "nos dois / só em A / só em B". Os números da 2f acima já usam o mínimo de 30 dias, então não são diretamente comparáveis.

## 4. Parte B: itens fora da seleção (`fora2c`)

Os modelos são os treinados com todos os itens da `treino2c`. Há 2.596 itens avaliados, todos "não líquidos" pela RN02, por isso a linha "líquido: não" repete "todos". O MdAPE do ingênuo é o mesmo nos dois modelos.

**`m_todos_s42`** (2c: `c_todos_s42`):

| Grupo | Itens | Mediana do MdAPE por item (2c) | MdAPE do ingênuo | Mediana do MAPE por item | Mediana do erro relativo (2c) | Erro relativo < 1 (2c) | Liberados com o mínimo | Liberados sem o mínimo (2c) |
|---|---|---|---|---|---|---|---|---|
| todos | 2.596 | 12,64% (16,85%) | 8,52% | 36,66% | 1,011 (1,081) | 43,7% (28,0%) | 83 (3,2%) | 111 (4,3%) (46, 1,8%) |
| commodity: sim | 686 | 15,11% (19,97%) | 12,34% | 44,72% | 0,970 (1,018) | 60,3% (47,5%) | 38 (5,5%) | 44 (6,4%) (13, 1,9%) |
| commodity: não | 1.910 | 12,00% (15,81%) | 7,35% | 34,66% | 1,021 (1,100) | 37,7% (21,1%) | 45 (2,4%) | 67 (3,5%) (33, 1,7%) |
| apto pela RN15: sim | 2.419 | 12,87% (17,15%) | 8,83% | 37,26% | 1,008 (1,077) | 45,0% (29,1%) | 80 (3,3%) | 102 (4,2%) (43, 1,8%) |
| apto pela RN15: não | 177 | 8,39% (14,20%) | 3,88% | 23,12% | 1,046 (1,166) | 26,6% (13,6%) | 3 (1,7%) | 9 (5,1%) (3, 1,7%) |
| líquido pela RN02: não | 2.596 | 12,64% (16,85%) | 8,52% | 36,66% | 1,011 (1,081) | 43,7% (28,0%) | 83 (3,2%) | 111 (4,3%) (46, 1,8%) |

**`m_todos_s7`** (2c: `c_todos_s7`):

| Grupo | Itens | Mediana do MdAPE por item (2c) | MdAPE do ingênuo | Mediana do MAPE por item | Mediana do erro relativo (2c) | Erro relativo < 1 (2c) | Liberados com o mínimo | Liberados sem o mínimo (2c) |
|---|---|---|---|---|---|---|---|---|
| todos | 2.596 | 11,72% (15,96%) | 8,52% | 36,87% | 1,002 (1,054) | 48,3% (30,5%) | 137 (5,3%) | 176 (6,8%) (53, 2,0%) |
| commodity: sim | 686 | 14,01% (19,58%) | 12,34% | 45,44% | 0,970 (1,014) | 62,7% (46,5%) | 60 (8,7%) | 67 (9,8%) (15, 2,2%) |
| commodity: não | 1.910 | 10,93% (14,80%) | 7,35% | 34,92% | 1,009 (1,070) | 43,1% (24,7%) | 77 (4,0%) | 109 (5,7%) (38, 2,0%) |
| apto pela RN15: sim | 2.419 | 12,04% (16,23%) | 8,83% | 37,46% | 1,000 (1,051) | 49,6% (31,5%) | 131 (5,4%) | 158 (6,5%) (44, 1,8%) |
| apto pela RN15: não | 177 | 7,85% (11,73%) | 3,88% | 22,38% | 1,025 (1,164) | 30,5% (16,4%) | 6 (3,4%) | 18 (10,2%) (9, 5,1%) |
| líquido pela RN02: não | 2.596 | 11,72% (15,96%) | 8,52% | 36,87% | 1,002 (1,054) | 48,3% (30,5%) | 137 (5,3%) | 176 (6,8%) (53, 2,0%) |

Itens com avaliação insuficiente (menos de 30 dias) na `fora2c`: 282 nos dois modelos.

## 5. Liquidez

Faixas de quantidade média ofertada no período avaliado (`liquidez_mae_s*.csv`), com os modelos `m_todos_s*` nas duas bases. Em cada célula, o número entre parênteses é o da etapa 2c (`c_todos_s*`, perda Huber) na mesma faixa. Os liberados aparecem como "com o mínimo · sem o mínimo (2c, sem mínimo)".

**Semente 42**

| Quantidade média ofertada | `treino2c`: itens | MdAPE (ingênuo) | Erro relativo (2c) | Erro relativo < 1 (2c) | Liberados (2c) | `fora2c`: itens | MdAPE (ingênuo) | Erro relativo (2c) | Erro relativo < 1 (2c) | Liberados (2c) |
|---|---|---|---|---|---|---|---|---|---|---|
| menos de 5 | 1 | 1,59% (0,00%) | 1,079 (1,133) | 0,0% (0,0%) | 0,0% · 0,0% (0,0%) | 1.790 | 11,37% (6,92%) | 1,025 (1,110) | 35,1% (18,0%) | 2,2% · 3,3% (1,3%) |
| 5 a 20 | 47 | 21,16% (15,38%) | 0,996 (1,030) | 57,5% (42,5%) | 2,1% · 2,1% (2,1%) | 415 | 15,98% (11,51%) | 0,987 (1,038) | 54,7% (41,4%) | 4,1% · 4,6% (1,9%) |
| 20 a 50 | 392 | 14,94% (12,75%) | 0,940 (0,964) | 69,1% (57,1%) | 9,9% · 9,9% (1,5%) | 225 | 15,95% (13,54%) | 0,940 (0,984) | 68,9% (55,1%) | 4,4% · 6,2% (2,7%) |
| 50 a 200 | 1.391 | 19,67% (20,00%) | 0,879 (0,898) | 82,2% (72,4%) | 7,8% · 9,0% (2,4%) | 125 | 16,94% (16,67%) | 0,893 (0,944) | 75,2% (60,8%) | 8,0% · 10,4% (0,8%) |
| 200 a 1.000 | 1.884 | 22,26% (25,21%) | 0,835 (0,855) | 91,0% (82,4%) | 10,8% · 14,6% (6,4%) | 29 | 22,16% (25,00%) | 0,856 (0,874) | 79,3% (75,9%) | 3,4% · 3,4% (3,4%) |
| 1.000 a 10.000 | 1.740 | 22,19% (27,00%) | 0,808 (0,817) | 93,2% (89,1%) | 13,7% · 18,1% (12,1%) | 12 | 11,63% (12,00%) | 0,981 (0,967) | 58,3% (91,7%) | 41,7% · 41,7% (50,0%) |
| 10.000 ou mais | 1.029 | 20,10% (24,47%) | 0,808 (0,814) | 97,0% (94,3%) | 19,8% · 25,5% (21,2%) | — | — | — | — | — |

**Semente 7**

| Quantidade média ofertada | `treino2c`: itens | MdAPE (ingênuo) | Erro relativo (2c) | Erro relativo < 1 (2c) | Liberados (2c) | `fora2c`: itens | MdAPE (ingênuo) | Erro relativo (2c) | Erro relativo < 1 (2c) | Liberados (2c) |
|---|---|---|---|---|---|---|---|---|---|---|
| menos de 5 | 1 | 0,74% (0,00%) | 0,934 (1,123) | 100,0% (0,0%) | 0,0% · 0,0% (0,0%) | 1.790 | 10,36% (6,92%) | 1,013 (1,078) | 39,6% (21,2%) | 4,0% · 5,6% (1,8%) |
| 5 a 20 | 47 | 21,89% (15,38%) | 0,998 (1,039) | 55,3% (36,2%) | 4,3% · 6,4% (2,1%) | 415 | 14,50% (11,51%) | 0,983 (1,029) | 60,2% (41,9%) | 5,5% · 6,5% (1,7%) |
| 20 a 50 | 392 | 14,11% (12,75%) | 0,934 (0,966) | 71,7% (58,7%) | 13,3% · 13,3% (1,5%) | 225 | 15,65% (13,54%) | 0,940 (0,980) | 74,2% (56,9%) | 8,4% · 9,8% (1,8%) |
| 50 a 200 | 1.391 | 19,27% (20,00%) | 0,881 (0,899) | 85,1% (72,5%) | 9,1% · 10,4% (2,4%) | 125 | 17,07% (16,67%) | 0,888 (0,931) | 78,4% (62,4%) | 12,0% · 15,2% (1,6%) |
| 200 a 1.000 | 1.884 | 22,42% (25,21%) | 0,843 (0,850) | 91,3% (84,8%) | 11,8% · 15,6% (6,5%) | 29 | 22,73% (25,00%) | 0,873 (0,868) | 82,8% (75,9%) | 10,3% · 10,3% (3,4%) |
| 1.000 a 10.000 | 1.740 | 22,23% (27,00%) | 0,814 (0,815) | 93,2% (90,8%) | 14,1% · 18,2% (12,9%) | 12 | 11,41% (12,00%) | 0,987 (0,966) | 50,0% (83,3%) | 41,7% · 41,7% (50,0%) |
| 10.000 ou mais | 1.029 | 20,24% (24,47%) | 0,813 (0,814) | 96,3% (94,5%) | 19,4% · 25,3% (21,5%) | — | — | — | — | — |

Nas duas bases e nas duas sementes, a mediana do erro relativo fica abaixo de 1 a partir da faixa "5 a 20". Na `treino2c`, a diferença é mínima nessa faixa (0,996 e 0,998). Ela cai à medida que a liquidez sobe, com uma exceção na faixa "1.000 a 10.000" da `fora2c`, que tem só 12 itens.

## 6. Itens novos (sem nenhuma amostra de treino)

São os itens avaliados na validação da `treino2c` que não têm nenhuma amostra de treino na base (`novos_mae_s*.csv`), com o modelo `m_sem_s*`. Entre parênteses estão os números da 2c (`c_sem_s*`, perda Huber), calculados com o mesmo `generalizacao.py`.

**Semente 42**

| Itens | Reservado | Itens | MdAPE (ingênuo) | Erro relativo (2c) | Erro relativo < 1 (2c) | Liberados com o mínimo | Liberados sem o mínimo (2c) | Mediana de dias avaliados |
|---|---|---|---|---|---|---|---|---|
| **sem amostra de treino** | não | 622 | 15,44% (18,09%) | 0,823 (0,874) | 76,2% (66,6%) | 9 (1,4%) | 191 (30,7%) (144, 23,2%) | 8 |
| **sem amostra de treino** | sim | 133 | 14,83% (16,84%) | 0,823 (0,910) | 79,0% (61,7%) | 0 (0,0%) | 55 (41,4%) (35, 26,3%) | 8 |
| com amostra de treino | não | 4.566 | 21,25% (25,00%) | 0,834 (0,845) | 91,0% (84,5%) | 654 (14,3%) | 656 (14,4%) (291, 6,4%) | 259 |
| com amostra de treino | sim | 1.163 | 21,07% (24,47%) | 0,839 (0,847) | 92,0% (85,9%) | 189 (16,3%) | 189 (16,3%) (93, 8,0%) | 257 |
| todos | — | 6.484 | 20,65% (24,17%) | 0,834 (0,847) | 89,5% (82,6%) | 852 (13,1%) | 1.091 (16,8%) (563, 8,7%) | 253 |

**Semente 7**

| Itens | Reservado | Itens | MdAPE (ingênuo) | Erro relativo (2c) | Erro relativo < 1 (2c) | Liberados com o mínimo | Liberados sem o mínimo (2c) | Mediana de dias avaliados |
|---|---|---|---|---|---|---|---|---|
| **sem amostra de treino** | não | 622 | 15,15% (18,09%) | 0,843 (0,892) | 77,5% (67,5%) | 8 (1,3%) | 184 (29,6%) (130, 20,9%) | 8 |
| **sem amostra de treino** | sim | 133 | 14,97% (16,84%) | 0,851 (0,910) | 80,5% (66,2%) | 1 (0,8%) | 56 (42,1%) (33, 24,8%) | 8 |
| com amostra de treino | não | 4.566 | 21,35% (25,00%) | 0,834 (0,848) | 91,4% (83,2%) | 628 (13,8%) | 629 (13,8%) (287, 6,3%) | 259 |
| com amostra de treino | sim | 1.163 | 21,07% (24,47%) | 0,840 (0,851) | 92,8% (84,7%) | 174 (15,0%) | 174 (15,0%) (90, 7,7%) | 257 |
| todos | — | 6.484 | 20,70% (24,17%) | 0,835 (0,852) | 90,1% (81,6%) | 811 (12,5%) | 1.043 (16,1%) (540, 8,3%) | 253 |

A coluna "MdAPE (ingênuo)" traz o MdAPE do modelo e, entre parênteses, o do ingênuo. Os 755 itens sem amostra de treino (622 + 133) têm mediana de **8 dias** de previsões avaliadas na validação.

## 7. Erro pela idade do item

Idade do item no dia da previsão (`por_idade`). A razão é o MdAPE do modelo dividido pelo do ingênuo: abaixo de 1, o modelo erra menos.

**`fora2c`, modelo `m_todos_s42`** (2c: `c_todos_s42`):

| Idade do item no dia da previsão | Alvos | Itens | MdAPE | MdAPE do ingênuo | Razão (2c) |
|---|---|---|---|---|---|
| até 89 dias | 21.314 | 152 | 15,68% | 13,76% | 1,139 (1,200) |
| 90 a 119 dias | 15.976 | 96 | 12,00% | 8,01% | 1,498 (1,711) |
| 120 a 179 dias | 27.937 | 106 | 16,57% | 12,18% | 1,361 (1,529) |
| 180 a 364 dias | 66.586 | 195 | 17,69% | 14,55% | 1,215 (1,402) |
| 365 dias ou mais | 2.319.814 | 2.439 | 10,32% | 6,05% | 1,705 (2,417) |

**`treino2c`, modelo `m_sem_s42`** (2c: `c_sem_s42`):

| Idade do item no dia da previsão | Alvos | Itens | MdAPE | MdAPE do ingênuo | Razão (2c) |
|---|---|---|---|---|---|
| até 89 dias | 43.896 | 736 | 12,06% | 14,88% | 0,811 (0,920) |
| 90 a 119 dias | 9.275 | 81 | 12,14% | 13,64% | 0,890 (0,921) |
| 120 a 179 dias | 18.802 | 55 | 17,22% | 20,00% | 0,861 (0,906) |
| 180 a 364 dias | 249.931 | 844 | 14,91% | 16,77% | 0,889 (0,914) |
| 365 dias ou mais | 9.240.066 | 5.729 | 18,40% | 21,62% | 0,851 (0,930) |

Um item entra em mais de uma faixa quando a idade dele muda ao longo da validação.

## 8. Efeito do mínimo de 30 dias na RN10 (`treino2c`, modelo `m_todos_s42`)

| Medida | Valor |
|---|---|
| Itens avaliados | 6.484 |
| Liberados **sem** o mínimo de dias | 1.018 |
| Liberados **com** o mínimo de 30 dias | 795 |
| Liberações retiradas pelo mínimo | 223, das quais 222 são de itens sem amostra de treino |
| Itens com avaliação insuficiente (menos de 30 dias) | 730 |
| … dos quais são itens sem amostra de treino (itens novos) | **705** (de 755 itens novos avaliados) |
| … dos quais são reservados | 132 |
| Dias de previsões avaliadas desses 730 | mediana de 8 (de 1 a 29) |

## 9. Problemas encontrados

A execução não teve erros, e nenhuma conferência pedida falhou: perda e reserva nos `treino.json`, e nenhuma previsão do teste. Pontos a registrar:

- **Avisos no `pytest`:** os 40 testes passam com 14 avisos, todos de dentro do Keras com o NumPy 2 (`__array__` sem o argumento `copy`), não do código do estudo.
- **Liberados nas saídas do `generalizacao.py`:** a coluna `liberados_rn10` dos CSVs vem da `situacao` do `avaliar.py`. Na 2f ela já inclui o mínimo de 30 dias; nas avaliações da 2c, não. Por isso as tabelas das seções 5 e 6 trazem os dois números, e os "sem o mínimo" da 2f foram recalculados das colunas `mdape` e `mdape_ingenuo`.
- **Concordância da RN10:** na seção 3, a concordância usa a `situacao`, que na 2f já tem o mínimo. Ela não é diretamente comparável à da 2c.
- **Colunas "2c" das seções 5 e 6:** não constavam do `docs/relatorio-etapa2c.md`. Foram calculadas agora com o `generalizacao.py` sobre as avaliações da 2c, sem gravar nada em `saida/`.

Os arquivos ficam em `estudos/lstm/saida/` (fora do Git):

- em `treino2c/`, os modelos `m_*`, as avaliações `avaliacao_validacao_m_*`, `comparacao_mae_s*.json`, `ruido_sementes_mae.json` e os logs;
- em `fora2c/`, as previsões e avaliações `m_todos_s*`;
- `liquidez_mae_s*.csv`, `novos_mae_s*.csv` e `etapa2f_sequencia.log`;
- o painel dos treinos, em `painel/index.html` (o da etapa 2e ficou em `painel/etapa2e.html`).
