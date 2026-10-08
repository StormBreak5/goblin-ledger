# Relatório da etapa 2e: ajuste da rede

Etapa 2e de `estudos/lstm/ROTEIRO.md`, executada de 2026-10-07 a 2026-10-08 conforme `estudos/lstm/pedido-etapa2e.md`. Testa três ajustes da rede, cada um sozinho contra a configuração da etapa 2b (eventos agregados, sem máscara):

| Candidato | Ajuste |
|---|---|
| `mae` | perda pelo erro absoluto (`--perda mae`) |
| `taxa` | redução da taxa de aprendizado na estagnação (`--reduzir-taxa`) |
| `u128` | LSTM de 128 unidades (`--unidades 128`) |

- **Base e referência:** a base é a `saida/treino01_agr`, sem base nova. A referência são os três treinos da etapa 2b, já avaliados na etapa 2d como `ref_s42`, `ref_s7` e `ref_s2026`; eles não foram retreinados.
- **Tudo foi avaliado só no período de validação.** Nenhum treino previu o teste (`previu_teste: false` nos nove `treino.json`).
- Antes de começar, o `pytest` do estudo tinha 38 testes passando, e o estado foi salvo no commit `c32332c`.
- Nenhum código nem regra do estudo foi alterado.

Este relatório traz os números e aplica a regra de decisão definida no pedido. **A decisão final é do autor.**

## 1. O que foi rodado

**Comandos**, a partir de `estudos/lstm`, um treino por vez, com o log em `saida/etapa2e_sequencia.log`:

```bash
for s in 42 7 2026; do
  python treinar.py --pasta saida/treino01_agr --nome mae_s$s --semente $s --perda mae
  python treinar.py --pasta saida/treino01_agr --nome taxa_s$s --semente $s --reduzir-taxa
  python treinar.py --pasta saida/treino01_agr --nome u128_s$s --semente $s --unidades 128
  for n in mae taxa u128; do
    python avaliar.py --pasta saida/treino01_agr --periodo validacao \
        --previsoes saida/treino01_agr/modelos/${n}_s$s/previsoes_validacao.parquet --rotulo ${n}_s$s
  done
done
# apoio (passo 4)
for n in mae taxa u128; do for s in 42 7 2026; do
  python comparar.py --a saida/treino01_agr/avaliacao_validacao_${n}_s${s}_itens.csv \
      --b saida/treino01_agr/avaliacao_validacao_ref_s${s}_itens.csv \
      --rotulos "$n" "referência" --saida saida/treino01_agr/comparacao_${n}_ref_s$s.json
  python transicao.py --base saida/treino2d_exp \
      --detalhe saida/treino01_agr/avaliacao_validacao_${n}_s${s}_detalhe.parquet --rotulo ${n}_s$s
done; done
```

A saída de cada comando foi gravada num log próprio em `saida/treino01_agr/`.

**Conferências:** depois de cada treino, o `treino.json` foi conferido, e tudo bateu:

| Treinos | `parametros.perda` | `parametros.reduzir_taxa` | `parametros.unidades` |
|---|---|---|---|
| `mae_*` | `mae` | `false` | 64 |
| `taxa_*` | `huber` | `true` | 64 |
| `u128_*` | `huber` | `false` | 128 |

Nos nove, `mascara` é `false` e `previu_teste` é `false`. O lançamento avaliado pelo `transicao.py` foi 2026-03-02 nas nove análises.

**Treinos:**

| Treino | Perda | Redução da taxa | Unidades | Épocas | Melhor época | Tempo por época | Tempo total |
|---|---|---|---|---|---|---|---|
| `mae_s42` | mae | não | 64 | 68 | 58 | 30,3 s | 34 min 22 s |
| `mae_s7` | mae | não | 64 | 52 | 42 | 31,3 s | 27 min 06 s |
| `mae_s2026` | mae | não | 64 | 44 | 34 | 28,8 s | 21 min 09 s |
| `taxa_s42` | huber | sim | 64 | 35 | 25 | 30,9 s | 18 min 02 s |
| `taxa_s7` | huber | sim | 64 | 37 | 27 | 31,9 s | 19 min 38 s |
| `taxa_s2026` | huber | sim | 64 | 34 | 24 | 27,9 s | 15 min 50 s |
| `u128_s42` | huber | não | 128 | 50 | 40 | 46,6 s | 38 min 51 s |
| `u128_s7` | huber | não | 128 | 33 | 23 | 49,0 s | 26 min 58 s |
| `u128_s2026` | huber | não | 128 | 30 | 20 | 41,0 s | 20 min 30 s |
| *Referência s42 · s7 · s2026 (etapa 2b)* | *huber* | *não* | *64* | *45 · 50 · 34* | *35 · 40 · 24* | *28,2 · 26,8 · 27,0 s* | *21 min 10 s · 22 min 22 s · 15 min 19 s* |

Os nove treinos somaram 3 h 42 min de `fit`; a sequência inteira, com as avaliações e as comparações de apoio, levou 3 h 52 min.

**Taxa de aprendizado nos `taxa_*`.** A taxa começa em 0,001 e cai pela metade a cada 3 épocas sem melhora na validação, até o mínimo de 0,00001. O `historico.csv` registra a taxa usada em cada época; "a partir da época N" é a primeira época com a taxa nova.

| Treino | Taxa final | Reduções (a partir da época) |
|---|---|---|
| `taxa_s42` | 0,00003125 | 19 (0,0005), 25 (0,00025), 29 (0,000125), 32 (0,0000625), 35 (0,00003125) |
| `taxa_s7` | 0,00001 (mínimo) | 10, 15, 23, 27, 31, 34 e 37 (de 0,0005 até 0,00001) |
| `taxa_s2026` | 0,00001 (mínimo) | 11, 17, 20, 23, 28, 31 e 34 (de 0,0005 até 0,00001) |

## 2. Tabela principal (validação, 6.484 itens)

Média ± desvio-padrão amostral nas 3 sementes (42, 7 e 2026). O desvio dos percentuais está em pontos percentuais. A RN10 é a do `avaliar.py`: MdAPE ≤ 15% e menor que o do ingênuo.

| Medida | Referência | `mae` | `taxa` | `u128` |
|---|---|---|---|---|
| **Mediana do MdAPE por item** | **22,67% ± 0,15** | **20,62% ± 0,09** | **22,92% ± 0,16** | **22,74% ± 0,19** |
| Mediana do MAPE por item | 38,66% ± 0,19 | 37,92% ± 0,01 | 39,12% ± 0,34 | 38,92% ± 0,07 |
| MAPE h1 | 25,36% ± 0,03 | 24,82% ± 0,12 | 25,52% ± 0,21 | 25,47% ± 0,09 |
| MAPE h7 | 62,32% ± 0,57 | 63,72% ± 0,42 | 63,41% ± 0,54 | 63,25% ± 0,81 |
| Mediana do erro relativo ao ingênuo | 0,8459 ± 0,0008 | 0,8380 ± 0,0041 | 0,8483 ± 0,0012 | 0,8451 ± 0,0010 |
| Itens com erro relativo < 1 | 5.345 ± 11 | 5.849 ± 18 | 5.308 ± 18 | 5.362 ± 38 |
| **Itens liberados (RN10)** | **603 ± 21** | **1.090 ± 6** | **591 ± 29** | **611 ± 16** |

Mediana do MdAPE por item em cada semente:

| Configuração | s42 | s7 | s2026 |
|---|---|---|---|
| Referência | 22,83% | 22,66% | 22,53% |
| `mae` | 20,53% | 20,71% | 20,64% |
| `taxa` | 22,79% | 23,10% | 22,89% |
| `u128` | 22,89% | 22,52% | 22,81% |

## 3. Comparação item a item com a referência

São os 6.484 itens, com a mesma semente nos dois modelos. A diferença é candidato − referência, em pontos percentuais; valor negativo significa que o candidato erra menos. A concordância da RN10 está como "liberados nos dois / só no candidato / só na referência".

| Candidato | Semente | Mediana da diferença no MdAPE | p25 a p75 | Candidato melhor | Iguais | Candidato pior | RN10 |
|---|---|---|---|---|---|---|---|
| `mae` | 42 | −1,25 | −3,92 a −0,03 | 4.905 | 4 | 1.575 | 543 / 546 / 49 |
| `mae` | 7 | −1,26 | −3,58 a −0,05 | 4.920 | 2 | 1.562 | 554 / 542 / 37 |
| `mae` | 2026 | −1,02 | −3,44 a +0,11 | 4.675 | 8 | 1.801 | 590 / 494 / 37 |
| `taxa` | 42 | −0,05 | −0,58 a +0,46 | 3.404 | 35 | 3.045 | 525 / 59 / 67 |
| `taxa` | 7 | +0,28 | −0,25 a +1,06 | 2.350 | 20 | 4.114 | 509 / 57 / 82 |
| `taxa` | 2026 | +0,21 | −0,22 a +0,77 | 2.386 | 38 | 4.060 | 570 / 53 / 57 |
| `u128` | 42 | +0,10 | −0,72 a +0,90 | 2.989 | 24 | 3.471 | 508 / 96 / 84 |
| `u128` | 7 | +0,10 | −0,68 a +0,89 | 2.986 | 24 | 3.474 | 500 / 129 / 91 |
| `u128` | 2026 | +0,20 | −0,44 a +0,96 | 2.654 | 36 | 3.794 | 518 / 81 / 109 |

## 4. Troca de expansão (lançamento de Midnight, 2026-03-02)

Razão entre o MdAPE do modelo e o do ingênuo a 7 dias (`horizonte = h7`), média ± desvio nas 3 sementes, dos `transicao_*.csv`. Abaixo de 1, o modelo erra menos que o ingênuo. A linha da referência é a mesma da seção 3 de `docs/relatorio-etapa2d.md`.

| Configuração | Expansão que sai · troca | Todos · troca | Todos · resto | Expansão que entra · resto |
|---|---|---|---|---|
| Referência | 0,959 ± 0,004 | 0,897 ± 0,006 | 0,873 ± 0,001 | 0,942 ± 0,012 |
| `mae` | **0,934 ± 0,010** | **0,867 ± 0,006** | **0,826 ± 0,003** | **0,822 ± 0,029** |
| `taxa` | 0,956 ± 0,008 | 0,904 ± 0,001 | 0,876 ± 0,003 | 0,979 ± 0,037 |
| `u128` | 0,998 ± 0,008 | 0,926 ± 0,012 | 0,876 ± 0,006 | 0,847 ± 0,016 |

## 5. Regra de decisão

O critério de cada candidato é:
- melhorar a mediana do MdAPE por item mais que o maior desvio entre sementes do candidato e da referência;
- **e** não reduzir os itens liberados pela RN10 mais que o maior desvio dessa medida.

| Candidato | MdAPE: referência → candidato | Ganho | Maior desvio | Liberados: referência → candidato | Queda | Maior desvio | Aprovado? |
|---|---|---|---|---|---|---|---|
| `mae` | 22,67% → 20,62% | **2,05 pontos** | 0,15 ponto | 603 → 1.090 | nenhuma (+487) | 21 | **Sim** |
| `taxa` | 22,67% → 22,92% | −0,25 ponto (piorou) | 0,16 ponto | 603 → 591 | 12 | 29 | Não |
| `u128` | 22,67% → 22,74% | −0,06 ponto (piorou) | 0,19 ponto | 603 → 611 | nenhuma (+7) | 21 | Não |

Passo a passo:

1. **Aprovados:** só a `mae`. O ganho dela (2,05 pontos) é cerca de 13 vezes o maior desvio, e ela melhora nas três sementes (20,53%, 20,71% e 20,64%, contra 22,53% a 22,83% da referência). A `taxa` e a `u128` pioram a medida principal.
2. **Com um aprovado,** ele passa a ser a configuração e não há treino extra. A combinação (passo 3 do pedido) não foi treinada.
3. **A regra indica a configuração final** e, a partir dela, a configuração congela:
   - eventos agregados (variáveis 1 a 18, sem as 19 e 20);
   - sem máscara;
   - **perda MAE**;
   - LSTM de 64 unidades e taxa de aprendizado fixa de 0,001;
   - os demais parâmetros padrão do `treinar.py`.

Números que a regra não usa, registrados para a decisão do autor:

- **Medidas a favor:** além do MdAPE, a `mae` melhora a mediana do MAPE por item (37,92%), o MAPE h1 (24,82%), o erro relativo ao ingênuo e as quatro razões da troca de expansão.
- **MAPE h7:** a `mae` **piora** a média do erro a 7 dias, de 62,32% para 63,72%. O MAPE é uma média e é puxado pelos erros grandes; a perda MAE mira a mediana.
- **Comparação item a item:** a `mae` erra menos que a referência em 4.675 a 4.920 dos 6.484 itens.
- **RN10:** a `mae` libera de 494 a 546 itens que a referência não libera, e a referência libera de 37 a 49 que a `mae` não libera.

## 6. Problemas encontrados

A execução não teve erros, e nenhuma conferência pedida falhou. Pontos a registrar:

- **Avisos no `pytest`:** os 38 testes passam com 14 avisos, todos de dentro do Keras com o NumPy 2 (`__array__` sem o argumento `copy`), não do código do estudo.
- **Tempo da `u128`:** fica entre 41 e 49 s por época, contra 27 a 32 s das demais.
- **`val_loss`:** o da perda MAE não é comparável ao da Huber. A comparação vale pelo `avaliar.py`.

Os arquivos ficam em `estudos/lstm/saida/` (fora do Git):

- em `treino01_agr/`, os modelos (`modelos/{mae,taxa,u128}_s*`), as avaliações (`avaliacao_validacao_*`), as comparações (`comparacao_*_ref_s*.json`), as análises da troca (`transicao_*.csv`) e os logs de cada treino;
- a sequência, em `etapa2e_sequencia.log`;
- o painel dos treinos, em `painel/index.html` (o da etapa 2d ficou em `painel/etapa2d.html`).
