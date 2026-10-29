# Relatório da etapa 2g: melhorias baratas da previsão

Etapa 2g de `estudos/lstm/ROTEIRO.md`, depois da 2f. Foi executada de 2026-10-28 a 2026-10-29, conforme `estudos/lstm/pedido-etapa2g.md`. Testa três melhorias baratas, cada uma sozinha contra a configuração final da etapa 2e:

| Candidato | O que é | Treino novo? |
|---|---|---|
| `ens` | média dos log-retornos previstos pelos 3 modelos da referência (`ens3`); o `ens2`, das 3 duplas, só mostra quanto cada modelo acrescenta | não |
| `enc` | encolhimento em direção ao ingênuo: log-retorno final = αₕ × log-retorno previsto, com αₕ escolhido na 1ª metade da validação e medido na 2ª | não |
| `lrelu` | LeakyReLU (inclinação negativa de 0,1) na camada densa de 32 | 3 treinos |
| `gelu` | GELU na camada densa de 32 | 3 treinos |

- **Base:** a de sempre, `saida/treino01_agr`. A validação vai de 2025-07-16 a 2026-05-10; não foi preparada base nova.
- **Referência:** os treinos `mae_s42`, `mae_s7` e `mae_s2026` da etapa 2e, que não foram retreinados.
  - Eles foram reavaliados com o `avaliar.py` atual, que tem o mínimo de 30 dias da RN10 (rótulos `ref2g_s*`).
  - Na 2ª metade da validação, a referência e o ingênuo foram medidos à parte (`ref2_s*` e `ing2`).
- **Tudo foi avaliado só na validação.** Nenhum treino previu o teste (`previu_teste: false` nos seis `treino.json` novos).
- **Passo 0:** salvo no commit `426b9b7`. O `pytest` do estudo tem 46 testes passando: os 40 de antes e os 6 novos.
- Depois do passo 0, nenhum código nem regra do estudo foi alterado.
- Duas análises extras deste relatório usaram scripts descartáveis, fora do estudo, que só leem os modelos e os arquivos de `saida/`:
  - o tempo de previsão, na seção 6;
  - de onde vem a piora do `enc`, na seção 7.

Este relatório traz os números e aplica a regra de decisão definida no pedido. **A decisão final é do autor.**

## 1. O que foi rodado

**Comandos**, a partir de `estudos/lstm`, com o `.venv` do estudo e um treino por vez. Os passos 1 e 2 foram gravados em `saida/etapa2g_sequencia.log`; o passo 4, em `saida/etapa2g_apoio.log`.

```bash
M=saida/treino01_agr/modelos
C=saida/treino01_agr/combinadas
A=saida/treino01_agr/avaliacao_validacao
# passo 1: sem treino
for s in 42 7 2026; do
  python avaliar.py --pasta saida/treino01_agr --periodo validacao \
      --previsoes $M/mae_s$s/previsoes_validacao.parquet --rotulo ref2g_s$s
done
python combinar.py media --nome ens3 --saida $C \
    --previsoes $M/mae_s42/previsoes_validacao.parquet $M/mae_s7/previsoes_validacao.parquet \
                $M/mae_s2026/previsoes_validacao.parquet
for par in "42 7" "42 2026" "7 2026"; do set -- $par
  python combinar.py media --nome ens2_s$1_s$2 --saida $C \
      --previsoes $M/mae_s$1/previsoes_validacao.parquet $M/mae_s$2/previsoes_validacao.parquet
done
for s in 42 7 2026; do
  python combinar.py encolher --pasta saida/treino01_agr --nome enc_s$s --saida $C \
      --previsoes $M/mae_s$s/previsoes_validacao.parquet
done
for n in ens3 ens2_s42_s7 ens2_s42_s2026 ens2_s7_s2026 enc_s42 enc_s7 enc_s2026 ref2_s42 ref2_s7 ref2_s2026 ing2; do
  python avaliar.py --pasta saida/treino01_agr --periodo validacao --previsoes $C/$n.parquet --rotulo $n
done
# passo 2: treinos da ativação
for s in 42 7 2026; do
  python treinar.py --pasta saida/treino01_agr --nome lrelu_s$s --semente $s --ativacao leaky_relu
  python treinar.py --pasta saida/treino01_agr --nome gelu_s$s --semente $s --ativacao gelu
  for n in lrelu gelu; do
    python avaliar.py --pasta saida/treino01_agr --periodo validacao \
        --previsoes $M/${n}_s$s/previsoes_validacao.parquet --rotulo ${n}_s$s
  done
done
for n in mae lrelu gelu; do for s in 42 7 2026; do
  python ativacoes.py --modelo $M/${n}_s$s --pasta saida/treino01_agr --periodo validacao
done; done
# passo 4: apoio
for s in 42 7 2026; do
  for n in lrelu gelu; do
    python comparar.py --a ${A}_${n}_s${s}_itens.csv --b ${A}_ref2g_s${s}_itens.csv \
        --rotulos "$n" "referência" --saida saida/treino01_agr/comparacao_${n}_ref2g_s$s.json
  done
  python comparar.py --a ${A}_ens3_itens.csv --b ${A}_ref2g_s${s}_itens.csv \
      --rotulos "ens3" "referência" --saida saida/treino01_agr/comparacao_ens3_ref2g_s$s.json
  python comparar.py --a ${A}_enc_s${s}_itens.csv --b ${A}_ref2_s${s}_itens.csv \
      --rotulos "enc" "referência (2ª metade)" --saida saida/treino01_agr/comparacao_enc_ref2_s$s.json
done
for n in ref2g_s42 ref2g_s7 ref2g_s2026 lrelu_s42 lrelu_s7 lrelu_s2026 gelu_s42 gelu_s7 gelu_s2026 ens3 \
         ref2_s42 ref2_s7 ref2_s2026 enc_s42 enc_s7 enc_s2026; do
  python transicao.py --base saida/treino2d_exp --detalhe ${A}_${n}_detalhe.parquet --rotulo $n
done
```

**Tempo:**
- passo 1: 5 min, de 00:47 a 00:52 UTC de 29/10;
- passo 2: 3 h 55 min, até 04:47 UTC;
- passo 4: 2 min.

**Conferências do `treino.json`** (todas bateram):
- `parametros.ativacao` é `leaky_relu` só nos `lrelu_*` e `gelu` só nos `gelu_*`.
- Fora o nome e a semente, os demais parâmetros são iguais aos dos `mae_*`: perda `mae`, 64 unidades, dropout de 0,2, taxa fixa de 0,001, lote de 512, 400.000 amostras por época, 200.000 na parada antecipada, paciência de 10, sem redução da taxa e sem máscara.
- Os `treino.json` dos `mae_*` são de 07/10, de antes da opção, e não têm o campo `ativacao`. O padrão da opção (`relu`) é a rede deles; o teste `test_ativacao_padrao_mantem_a_rede` confere isso.
- Em todos, `previu_teste` é `false`.
- O lançamento avaliado pelo `transicao.py` foi 2026-03-02 nas 16 análises.

**Treinos** (o `val_loss` é a MAE nas 200.000 amostras da parada antecipada e é comparável entre os nove):

| Treino | Ativação | Épocas | Melhor época | Melhor `val_loss` | Tempo por época | Tempo total do `fit` |
|---|---|---|---|---|---|---|
| `lrelu_s42` | LeakyReLU (0,1) | 78 | 68 | 0,5101 | 71,0 s (mediana de 28 s) | 92 min 19 s (cerca de 41 min sem a pausa; seção 7) |
| `lrelu_s7` | LeakyReLU (0,1) | 64 | 54 | 0,5097 | 27,3 s | 29 min 08 s |
| `lrelu_s2026` | LeakyReLU (0,1) | 50 | 40 | 0,5106 | 27,4 s | 22 min 52 s |
| `gelu_s42` | GELU | 63 | 53 | 0,5110 | 27,7 s | 29 min 04 s |
| `gelu_s7` | GELU | 48 | 38 | 0,5098 | 27,5 s | 22 min 02 s |
| `gelu_s2026` | GELU | 71 | 61 | 0,5094 | 27,1 s | 32 min 06 s |
| *Referência `mae` s42 · s7 · s2026 (etapa 2e)* | *ReLU* | *68 · 52 · 44* | *58 · 42 · 34* | *0,5096 · 0,5105 · 0,5107* | *30,3 · 31,3 · 28,8 s* | *34 min 22 s · 27 min 06 s · 21 min 09 s* |

Os seis treinos somaram 3 h 48 min de `fit`, ou cerca de 2 h 56 min sem a pausa do `lrelu_s42`.

**Encolhimento:**
- O meio da validação é 2025-12-12.
- **1ª metade:** 693.923 amostras. Ficam de fora as 27.561 cujos 7 dias previstos passam do meio, como na RN25.
- **2ª metade:** 698.959 amostras, de 6.478 itens.

Os αₕ escolhidos na 1ª metade, com a mediana entre os itens do MdAPE do item em cada horizonte:

| Semente | h1 | h2 | h3 | h4 | h5 | h6 | h7 |
|---|---|---|---|---|---|---|---|
| 42 | 0,00 | 0,50 | 0,85 | 1,00 | 0,95 | 1,00 | 1,00 |
| 7 | 0,05 | 0,65 | 0,85 | 0,85 | 1,00 | 1,00 | 1,00 |
| 2026 | 0,05 | 0,55 | 0,90 | 1,00 | 1,00 | 0,95 | 0,95 |

MdAPE da 1ª metade nos extremos e no α escolhido (sementes 42 · 7 · 2026). A grade inteira, de 0 a 1 em passos de 0,05, está no anexo.

| h | α = 0 (ingênuo) | α = 1 (modelo) | α escolhido |
|---|---|---|---|
| 1 | 2,61% | 3,75% · 3,73% · 3,89% | 2,61% · 2,60% · 2,59% |
| 2 | 12,92% | 12,15% · 11,91% · 11,97% | 11,81% · 11,58% · 11,73% |
| 3 | 21,72% | 18,16% · 18,21% · 18,27% | 18,07% · 18,06% · 18,27% |
| 4 | 27,18% | 22,64% · 22,52% · 22,59% | 22,64% · 22,42% · 22,59% |
| 5 | 31,41% | 25,77% · 25,41% · 25,43% | 25,75% · 25,41% · 25,43% |
| 6 | 33,40% | 28,00% · 27,76% · 27,87% | 28,00% · 27,76% · 27,85% |
| 7 | 35,60% | 29,63% · 29,80% · 29,69% | 29,63% · 29,80% · 29,67% |

O encolhimento só mexe de verdade no h1, que vai para o ingênuo, e no h2, pela metade. Do h3 ao h7, o α fica entre 0,85 e 1.

## 2. Tabela principal

**Validação inteira** (6.484 itens e 1.420.443 amostras): média ± desvio-padrão amostral nas 3 sementes (42, 7 e 2026).
- O desvio dos percentuais está em pontos percentuais.
- O `ens2` é a média das 3 duplas; o `ens3` tem um valor só.
- A RN10 é a do `avaliar.py`: MdAPE ≤ 15%, menor que o do ingênuo e pelo menos 30 dias avaliados.

| Medida | Referência | `ens2` | `ens3` | `lrelu` | `gelu` |
|---|---|---|---|---|---|
| **Mediana do MdAPE por item** | **20,62% ± 0,09** | 20,55% ± 0,06 | 20,54% | 20,50% ± 0,07 | **20,40% ± 0,10** |
| Mediana do MAPE por item | 37,92% ± 0,01 | 37,81% ± 0,03 | 37,76% | 37,77% ± 0,22 | 37,61% ± 0,18 |
| MAPE h1 | 24,82% ± 0,12 | 24,77% ± 0,06 | 24,76% | 24,88% ± 0,08 | 24,77% ± 0,07 |
| MAPE h7 | 63,72% ± 0,42 | 63,43% ± 0,21 | 63,33% | 63,55% ± 0,38 | 63,37% ± 0,15 |
| Mediana do erro relativo ao ingênuo | 0,8380 ± 0,0041 | 0,8353 ± 0,0023 | 0,8346 | 0,8364 ± 0,0023 | 0,8361 ± 0,0020 |
| Itens com erro relativo < 1 | 5.849 ± 18 | 5.880 ± 5 | 5.879 | 5.820 ± 4 | 5.831 ± 14 |
| **Itens liberados (RN10)** | **862 ± 6** | 892 ± 1 | 902 | 881 ± 36 | **916 ± 19** |
| Itens liberados sem o mínimo de 30 dias | 1.090 ± 6 | 1.126 ± 4 | 1.135 | 1.119 ± 43 | 1.155 ± 32 |

**2ª metade da validação**, de 2025-12-12 a 2026-05-10 (6.478 itens e 698.959 amostras):

| Medida | Ingênuo | Referência | `enc` |
|---|---|---|---|
| **Mediana do MdAPE por item** | 25,15% | **21,95% ± 0,08** | 22,24% ± 0,10 |
| Mediana do MAPE por item | 48,37% | 38,77% ± 0,18 | 39,52% ± 0,19 |
| MAPE h1 | 28,68% | 26,70% ± 0,14 | 28,57% ± 0,10 |
| MAPE h7 | 102,10% | 72,80% ± 0,82 | 72,96% ± 0,88 |
| Mediana do erro relativo ao ingênuo | 1,0000 | 0,8318 ± 0,0040 | 0,8422 ± 0,0024 |
| Itens com erro relativo < 1 | 0 | 5.775 ± 25 | 5.802 ± 24 |
| **Itens liberados (RN10)** | 0 | **831 ± 30** | 813 ± 34 |
| Itens liberados sem o mínimo de 30 dias | 0 | 1.073 ± 36 | 1.049 ± 41 |

Mediana do MdAPE por item e itens liberados (RN10) em cada semente:

| Configuração | s42 | s7 | s2026 |
|---|---|---|---|
| Referência | 20,53% (856) | 20,71% (868) | 20,64% (862) |
| `lrelu` | 20,45% (920) | 20,47% (871) | 20,58% (851) |
| `gelu` | 20,42% (917) | 20,49% (897) | 20,30% (935) |
| Referência, 2ª metade | 21,97% (847) | 21,86% (849) | 22,02% (796) |
| `enc`, 2ª metade | 22,21% (826) | 22,15% (838) | 22,36% (774) |

**O `ens` por número de modelos** (validação inteira):

| Média de | MdAPE | Liberados |
|---|---|---|
| 1 modelo (referência) | 20,62% | 862 |
| 2 modelos | 20,55% | 892 |
| 3 modelos (`ens3`) | 20,54% | 902 |

Os valores das 3 duplas do `ens2`:

| Dupla | MdAPE | Liberados |
|---|---|---|
| s42 + s7 | 20,55% | 892 |
| s42 + s2026 | 20,50% | 891 |
| s7 + s2026 | 20,61% | 892 |

O 2º modelo tira 0,07 ponto do MdAPE, e o 3º, 0,01.

## 3. Diagnóstico da camada densa (`ativacoes.py`)

São as pré-ativações z = x·W + b das 32 unidades da camada densa, nas 1.420.443 amostras da validação.

| Modelo | Ativação | Amostras sem nenhuma unidade com z > 0 | Unidades que nunca ficam com z > 0 | Unidades com z > 0 por amostra (p10 · mediana · p90) |
|---|---|---|---|---|
| `mae_s42` | ReLU | 14,81% (210.427) | 1 | 0 · 4 · 9 |
| `mae_s7` | ReLU | 13,51% (191.969) | 4 | 0 · 4 · 9 |
| `mae_s2026` | ReLU | 19,59% (278.244) | 2 | 0 · 3 · 7 |
| `lrelu_s42` | LeakyReLU | 0,01% (155) | 0 | 4 · 6 · 10 |
| `lrelu_s7` | LeakyReLU | 0,00% (3) | 0 | 2 · 6 · 11 |
| `lrelu_s2026` | LeakyReLU | 1,56% (22.148) | 0 | 1 · 4 · 9 |
| `gelu_s42` | GELU | 9,70% (137.819) | 0 | 1 · 4 · 9 |
| `gelu_s7` | GELU | 6,89% (97.913) | 0 | 1 · 3 · 8 |
| `gelu_s2026` | GELU | 3,33% (47.361) | 0 | 1 · 4 · 9 |

O que isso quer dizer:

- **ReLU:** sem nenhuma unidade com z > 0, a saída da camada densa é zero, e a camada `y` devolve só o viés.
  - É o mesmo log-retorno normalizado para qualquer item; em preço, é o ingênuo com uma deriva fixa por horizonte.
  - Isso acontece em 13,5% a 19,6% das amostras da validação. No sistema, foram 12% das janelas de 19/10.
  - De 1 a 4 das 32 unidades nunca ficam positivas: estão mortas na validação.
- **LeakyReLU e GELU:** a parte negativa ainda passa sinal. A LeakyReLU devolve 0,1·z; a GELU, z·Φ(z), que vai até cerca de −0,17.
  - Mesmo sem unidade com z > 0, a saída depende da entrada, e o gradiente não zera.
  - A coluna "sem nenhuma unidade com z > 0" não é, para elas, a saída igual ao viés; ela só mede quantas amostras ficam inteiramente no lado negativo.
  - Com a LeakyReLU, quase nenhuma amostra fica assim (de 0,00% a 1,56%), e há mais unidades positivas por amostra (mediana de 4 a 6).
  - Com a GELU, ficam de 3,3% a 9,7%.
  - Nenhuma unidade fica morta nos seis modelos.

## 4. Comparação item a item e troca de expansão

### Item a item

Mesma semente nos dois modelos; o `ens3` foi comparado com cada `ref2g_s*`.
- A diferença é candidato − referência, em pontos percentuais; valor negativo significa que o candidato erra menos.
- A RN10 está como "liberados nos dois / só no candidato / só na referência".
- O `enc` é comparado na 2ª metade (6.478 itens); os demais, na validação inteira (6.484 itens).

| Candidato | Semente | Mediana da diferença no MdAPE | p25 a p75 | Candidato melhor | Iguais | Candidato pior | RN10 |
|---|---|---|---|---|---|---|---|
| `ens3` | 42 | −0,05 | −0,44 a +0,25 | 3.626 | 85 | 2.773 | 821 / 81 / 35 |
| `ens3` | 7 | −0,04 | −0,43 a +0,29 | 3.540 | 112 | 2.832 | 821 / 81 / 47 |
| `ens3` | 2026 | −0,09 | −0,49 a +0,21 | 3.851 | 127 | 2.506 | 810 / 92 / 52 |
| `enc` | 42 | +0,14 | −0,05 a +0,70 | 2.055 | 478 | 3.945 | 802 / 24 / 45 |
| `enc` | 7 | +0,08 | −0,08 a +0,62 | 2.169 | 567 | 3.742 | 811 / 27 / 38 |
| `enc` | 2026 | +0,12 | −0,04 a +0,66 | 2.155 | 437 | 3.886 | 751 / 23 / 45 |
| `lrelu` | 42 | −0,04 | −0,69 a +0,47 | 3.385 | 46 | 3.053 | 793 / 127 / 63 |
| `lrelu` | 7 | +0,05 | −0,58 a +0,64 | 3.047 | 44 | 3.393 | 779 / 92 / 89 |
| `lrelu` | 2026 | +0,05 | −0,53 a +0,62 | 3.045 | 43 | 3.396 | 769 / 82 / 93 |
| `gelu` | 42 | −0,06 | −0,66 a +0,51 | 3.442 | 19 | 3.023 | 792 / 125 / 64 |
| `gelu` | 7 | 0,00 | −0,61 a +0,61 | 3.198 | 37 | 3.249 | 785 / 112 / 83 |
| `gelu` | 2026 | −0,20 | −0,89 a +0,42 | 3.822 | 32 | 2.630 | 791 / 144 / 71 |

**O que a tabela mostra:**
- **`ens3`:** é o único que erra menos na maioria dos itens nas três sementes, e com a faixa p25–p75 mais estreita. É um ganho pequeno e espalhado.
- **`lrelu`:** erra menos na maioria dos itens só na semente 42. Nas outras duas, a diferença mediana é +0,05; a mediana do MdAPE melhora mesmo assim, porque o ganho está nos itens perto do meio da distribuição.
- **`gelu`:** a vantagem se concentra na semente 2026. A semente 7 empata: 3.198 itens melhores e 3.249 piores.
- **Faixas:** nas ativações, a faixa p25–p75, de cerca de −0,6 a +0,6 ponto, é mais larga que a do `ens3`. Trocar a ativação muda bastante item a item, para os dois lados.
- **RN10:** a `gelu` libera de 112 a 144 itens que a referência não libera, e a referência libera de 64 a 83 que a `gelu` não libera.

### Troca de expansão (lançamento de Midnight, 2026-03-02)

Razão entre o MdAPE do modelo e o do ingênuo a 7 dias (`horizonte = h7`), média ± desvio nas 3 sementes, dos `transicao_*.csv`. Abaixo de 1, o modelo erra menos que o ingênuo. A linha da referência é a mesma da `mae` na seção 4 de `docs/relatorio-etapa2e.md`.

| Configuração | Expansão que sai · troca | Todos · troca | Todos · resto | Expansão que entra · resto |
|---|---|---|---|---|
| Referência | 0,934 ± 0,010 | 0,867 ± 0,006 | 0,826 ± 0,003 | 0,822 ± 0,029 |
| `ens3` | 0,927 | 0,861 | 0,822 | 0,814 |
| `lrelu` | **0,911 ± 0,013** | **0,859 ± 0,011** | 0,826 ± 0,001 | 0,799 ± 0,028 |
| `gelu` | 0,923 ± 0,013 | 0,863 ± 0,001 | **0,822 ± 0,002** | **0,790 ± 0,051** |
| *Referência, 2ª metade* | *0,934 ± 0,010* | *0,867 ± 0,006* | *0,815 ± 0,004* | *0,822 ± 0,029* |
| *`enc`, 2ª metade* | *0,933 ± 0,009* | *0,866 ± 0,006* | *0,815 ± 0,005* | *0,825 ± 0,032* |

**Leitura da tabela:**
- A janela da troca, de 21 dias antes a 30 dias depois do lançamento, cai inteira na 2ª metade. Por isso, as duas primeiras colunas da 2ª metade repetem as da validação inteira.
- Os três candidatos da validação inteira melhoram as quatro razões ou empatam.
- O `enc` fica igual à referência: a tabela é do h7, em que o α é 0,95 ou 1.

## 5. Regra de decisão

O critério de cada candidato é:
- melhorar a mediana do MdAPE por item mais que o maior desvio entre sementes das duas configurações comparadas (o `ens3`, que tem um valor só, usa o desvio da referência);
- **e** não reduzir os itens liberados pela RN10 mais que o maior desvio dessa medida.

| Candidato | Comparado com | MdAPE: referência → candidato | Ganho | Maior desvio | Liberados: referência → candidato | Queda | Maior desvio | Aprovado? |
|---|---|---|---|---|---|---|---|---|
| `ens3` | `ref2g_s*`, validação | 20,62% → 20,54% | 0,084 ponto | 0,089 ponto | 862 → 902 | nenhuma (+40) | 6 | Não |
| `enc` | `ref2_s*`, 2ª metade | 21,95% → 22,24% | −0,289 ponto (piorou) | 0,104 ponto | 831 → 813 | 18 | 34 | Não |
| `lrelu` | `ref2g_s*`, validação | 20,62% → 20,50% | 0,124 ponto | 0,089 ponto | 862 → 881 | nenhuma (+19) | 36 | **Sim** |
| `gelu` | `ref2g_s*`, validação | 20,62% → 20,40% | **0,221 ponto** | 0,096 ponto | 862 → 916 | nenhuma (+54) | 19 | **Sim** |

Os ganhos e os desvios estão com três casas porque o `ens3` fica a 0,005 ponto do limite.

Passo a passo:

1. **Aprovados:** a `lrelu` e a `gelu`.
   - O `ens3` não passa por pouco: ganha 0,084 ponto, contra um desvio de 0,089. Ele também aumenta os liberados em 40.
   - O `enc` piora a medida principal (seção 7).
2. **Com mais de um aprovado, o pedido manda montar a combinação (`comb`)** só com os aprovados, nesta ordem:
   1. as sementes da ativação aprovada;
   2. a média, só se o `ens` for aprovado, e ele não foi;
   3. o encolhimento, só se o `enc` for aprovado, e ele também não foi.

   **Sobra só o item 1,** e a `comb` seria uma das próprias ativações. Não havia nada novo a montar nem a treinar.
   - O pedido não prevê duas ativações aprovadas. Elas são alternativas para a mesma camada e não se combinam numa rede só.
   - Também não montei uma média de modelos `lrelu` com `gelu`: seria um `ens`, que não foi aprovado.
   - Pela regra, como a `comb` não supera o melhor aprovado, **fica o melhor aprovado.**
3. **O melhor aprovado é a `gelu`.** Ela tem o maior ganho na medida principal (0,221 contra 0,124 ponto) e mais itens liberados (916 contra 881).
   - **Comparação direta pelo mesmo critério:** o MdAPE vai de 20,50% para 20,40%. A diferença, 0,097 ponto, fica acima do maior desvio, 0,096 (o da `gelu`), por 0,001 ponto: está no limite do ruído.
   - Os liberados sobem de 881 para 916.
   - A ordem de desempate não é necessária: as duas estão no mesmo nível ("ativação"), e a `gelu` vence nas duas medidas.
4. **A regra indica a configuração da etapa 2e com a GELU na camada densa de 32.** A partir dela, a configuração congela:
   - eventos agregados (variáveis 1 a 18), sem máscara, perda MAE;
   - LSTM de 64 unidades, taxa fixa de 0,001;
   - **Dense(32, GELU)**;
   - os demais parâmetros padrão do `treinar.py`.

**Números que a regra não usa,** registrados para a decisão do autor:

- **A favor da `gelu`:**
  - melhora nas três sementes: −0,12, −0,21 e −0,33 ponto contra a referência da mesma semente;
  - melhora a mediana do MAPE por item (37,61% contra 37,92%), o MAPE h7 (63,37% contra 63,72%), o erro relativo ao ingênuo (0,8361 contra 0,8380) e as quatro razões da troca de expansão;
  - o MAPE h1 fica praticamente igual (24,77% contra 24,82%).
- **Com cautela:**
  - **Ganho pequeno:** 0,22 ponto, cerca de nove vezes menor que o da perda MAE na etapa 2e (2,05).
  - **Item a item:** fica perto de metade melhor, metade pior na semente 7. A diferença mediana vai de 0,00 a −0,20 ponto.
  - **Erro relativo < 1:** os itens caem um pouco (5.831 contra 5.849), dentro do desvio de 18.
  - **Rotatividade dos liberados:** de 189 a 215 itens trocam de lado da RN10 entre a `gelu` e a referência.
  - **`val_loss`:** o das 200.000 amostras da parada antecipada é praticamente o mesmo nos nove modelos (0,5094 a 0,5110). A diferença só aparece na mediana por item.
- **O `ens3` sozinho** fica logo abaixo do limite.
  - Ele tem a menor dispersão item a item. É o único dos três que aumenta os itens com erro relativo < 1 (5.879 contra 5.849).
  - Uma média de 3 modelos `gelu` não foi testada: o `ens` não foi aprovado, e a configuração congela.
  - Testá-la seria uma decisão nova, que multiplica o custo de C1, C2 e C3 (seção 6).

## 6. Custo no sistema da configuração indicada (GELU)

**Mudança no código:**
- É uma linha em `construir_modelo` (`backend/src/ml/rede.py:77`): `layers.Dense(32, activation="gelu")` no lugar de `"relu"`.
- O Keras grava a ativação na configuração de cada `modelo.keras`, então as versões antigas, com ReLU, continuam carregando como são.
- No TC, muda a seção 5.12.2 (arquitetura).
- **O primeiro C2 depois da mudança** compara um modelo GELU com o vigente ReLU no mesmo período de teste, pela RN26, como em qualquer retreinamento. Nenhuma regra muda.

| Item | ReLU (hoje) | GELU | Fonte |
|---|---|---|---|
| Parâmetros da rede | 23.763 | 23.763 | `count_params()`; a ativação não tem parâmetros |
| Tempo por época (estudo, `fit`) | 28,8 a 31,3 s (etapa 2e, 07/10) | 27,1 a 27,7 s (esta etapa) | `treino.json` |
| Épocas até a parada | 44 a 68 (média de 54,7) | 48 a 71 (média de 60,7) | `treino.json` |
| `fit` no estudo | 21 a 34 min | 22 a 32 min | `treino.json` |
| C1 no sistema | 36,1 min (versão 1, 19/10) | da mesma ordem | `execucao_treinamento` |
| C2 no sistema | 47,5 min (20/10) e 38,8 min (27/10) | da mesma ordem | `execucao_treinamento` |
| Previsão de 1.420.443 janelas da validação | 20,2 e 20,4 s | 21,0 e 21,1 s (+3,5%) | duas rodadas no mesmo computador, semente 42 |
| C3 no sistema (com o passo 7) | 0,5 min (19/10) e 0,9 min (20/10), 8.596 previsões | da mesma ordem | `consolidacao_diaria` |
| `modelo.keras` | 340.778 bytes | 340.778 bytes | arquivo; a LeakyReLU teria 343.308, com uma camada a mais |
| `normalizacao.json` | igual | igual | não muda |

Notas:

- **Tempo por época:** não há custo mensurável. A diferença para a etapa 2e vem da carga do computador nos dois dias, não da ativação: a `lrelu`, rodada junto com a `gelu`, também ficou em 27 s.
- **Tempo do C1 e do C2:** depende do número de épocas até a parada, que varia mais entre sementes que entre ativações.
  - Se a média de épocas subir uns 10%, como entre as médias acima, são uns 2 a 3 minutos a mais por treinamento.
  - O C2 de 20/10 às 03:25 (511 min, até as 11:57 UTC) foge do padrão e não entra na comparação.
- **C3:** a rede prevê umas 1.300 janelas por dia, o que, pela medida acima, leva bem menos de 1 segundo com qualquer ativação. O tempo do C3 é dominado pela leitura e pela preparação dos dados.
  - De 21/10 a 27/10, a consolidação não gravou previsões, porque a importação diária não rodou nesses dias. Esses tempos não entram na tabela.
- **Espaço:** nenhum artefato novo.

## 7. Problemas encontrados

A execução não teve erros (`saiu com 0` nos dois logs, nenhum `Traceback`), e nenhuma conferência pedida falhou. Pontos a registrar:

- **O computador dormiu durante o `lrelu_s42`.**
  - A época 3 levou 3.096 s, contra cerca de 28 s das demais: foram uns 51 minutos de pausa, de cerca de 22:00 a 22:46 de Brasília em 28/10.
  - O treino só ficou parado, e o resultado não muda. O tempo total dele (92 min 19 s) e a média por época (71,0 s) ficaram inflados; sem a pausa, foram cerca de 41 min.
  - As primeiras épocas também foram mais lentas, cerca de 42 s, porque análises do passo 1 rodavam em paralelo.
  - Depois disso, o computador foi mantido acordado até o fim, e nenhum outro treino teve pausa.
- **Referência reavaliada:**
  - Os resumos de 07/10 não tinham o mínimo de 30 dias da RN10.
  - Com o `avaliar.py` atual, os `ref2g_s*` dão o mesmo MdAPE da etapa 2e (20,53%, 20,71% e 20,64%).
  - Dão 862 ± 6 liberados, contra 1.090 ± 6 sem o mínimo. A regra usou os `ref2g_s*`.
  - Os resumos de 07/10 não foram sobrescritos: os rótulos são novos.
- **Commit do passo 0 (`426b9b7`):**
  - O pedido dizia `git add estudos/lstm`. Entraram só os seis arquivos do passo: `treinar.py`, `combinar.py`, `ativacoes.py`, `tests/test_estudo.py`, `README.md` e `pedido-etapa2g.md`.
  - Ficaram de fora as suas alterações locais em `ROTEIRO.md` e quatro pedidos não versionados: `pedido-cu05.md`, `pedido-cu11-c2.md`, `pedido-cu11-c3.md` e `pedido-testes-final.md`. Eles não são desta etapa e continuam fora do Git.
- **A regra não prevê duas ativações aprovadas.** A seção 5 traz a leitura feita: a `comb` se reduz à melhor ativação, e não se montou nenhuma combinação nova.
- **Por que o `enc` piorou.** Esta é uma análise feita depois, que não muda a regra.
  - **A escolha do α:** na 1ª metade, o critério do pedido escolheu α ≈ 0 no h1 e cerca de 0,5 no h2.
    - O critério é a mediana entre os itens do MdAPE do item em cada horizonte.
    - No h1, 30,2% dos alvos da 2ª metade são exatamente o preço de hoje: o ingênuo tem erro zero neles. Esse critério favorece o ingênuo; na 1ª metade, foram 2,61% contra 3,73% a 3,89% do modelo.
  - **A medida principal** é outra: a mediana do item com os 7 horizontes juntos.
    - Trocando, na 2ª metade, o modelo pelo encolhido em um horizonte por vez: só o h1 piora o MdAPE por item em 0,15 a 0,18 ponto, e só o h2, em 0,09 a 0,11. Do h3 ao h7, o efeito fica entre −0,02 e +0,02.
    - Cerca de 70% dos erros do modelo no h1 já ficam abaixo da mediana do item, porque são os menores; trocá-los por zero não baixa a mediana.
    - Com o ingênuo, a parte dos erros do h1 acima da mediana do item passa de 29,5% para 31,2% nas três sementes, e a mediana sobe.
  - **Conclusão:** o critério de escolha do α, definido no pedido, não é a medida principal.
    - Na mediana das amostras do h1, o encolhimento até funcionou: foi de 5,56% para 5,26% na semente 42.
    - Se o encolhimento voltar a ser testado, o α deveria ser escolhido pela própria medida principal.
- **Avisos no `pytest`:** os 46 testes passam com 24 avisos, de dentro do Keras com o NumPy 2, como na etapa 2e.

Os arquivos ficam em `estudos/lstm/saida/`, fora do Git:
- **Em `treino01_agr/`:**
  - os modelos novos (`modelos/{lrelu,gelu}_s*`);
  - o diagnóstico `ativacoes_validacao.json`, dentro da pasta de cada um dos nove modelos, inclusive dos `mae_*`;
  - as previsões combinadas (`combinadas/`, 445 MB, com os `enc_s*.json` dos α);
  - as avaliações (`avaliacao_validacao_{ref2g,ens2,ens3,enc,ref2,ing2,lrelu,gelu}*`);
  - as comparações (`comparacao_*_ref2*_s*.json`);
  - as análises da troca (`transicao_*.csv`).
- **Logs:** `etapa2g_sequencia.log` (passos 1 e 2), `etapa2g_apoio.log` (passo 4) e `etapa2g_resumo.txt` (as tabelas acima, em bruto).

## Anexo: MdAPE da 1ª metade em cada α

Mediana, entre os itens, do MdAPE do item em cada horizonte, na 1ª metade da validação (de 2025-07-16 até as amostras cujos 7 dias previstos terminam antes de 2025-12-12). O α escolhido está em negrito. Em empate, o critério fica com o maior α. Os valores estão arredondados: na semente 42, o h1 com α = 0 é menor que com α = 0,05 nas casas seguintes.

**Semente 42** (αₕ escolhidos em negrito)

| α | h1 | h2 | h3 | h4 | h5 | h6 | h7 |
|---|---|---|---|---|---|---|---|
| 0,00 | **2,61%** | 12,92% | 21,72% | 27,18% | 31,41% | 33,40% | 35,60% |
| 0,05 | 2,61% | 12,70% | 21,29% | 26,87% | 30,88% | 33,28% | 35,12% |
| 0,10 | 2,72% | 12,51% | 20,91% | 26,44% | 30,39% | 32,95% | 34,75% |
| 0,15 | 2,78% | 12,34% | 20,52% | 25,99% | 29,97% | 32,68% | 34,41% |
| 0,20 | 2,86% | 12,19% | 20,15% | 25,73% | 29,54% | 32,17% | 33,96% |
| 0,25 | 2,92% | 12,12% | 19,87% | 25,29% | 29,06% | 31,66% | 33,54% |
| 0,30 | 2,97% | 11,94% | 19,63% | 25,01% | 28,72% | 31,23% | 33,22% |
| 0,35 | 3,08% | 11,90% | 19,35% | 24,76% | 28,27% | 30,88% | 32,85% |
| 0,40 | 3,18% | 11,83% | 19,10% | 24,38% | 28,00% | 30,63% | 32,48% |
| 0,45 | 3,27% | 11,83% | 18,87% | 24,10% | 27,59% | 30,33% | 32,12% |
| 0,50 | 3,36% | **11,81%** | 18,68% | 23,98% | 27,24% | 29,96% | 31,82% |
| 0,55 | 3,39% | 11,84% | 18,52% | 23,79% | 26,90% | 29,74% | 31,58% |
| 0,60 | 3,44% | 11,83% | 18,41% | 23,57% | 26,66% | 29,46% | 31,29% |
| 0,65 | 3,46% | 11,86% | 18,33% | 23,33% | 26,49% | 29,07% | 31,04% |
| 0,70 | 3,51% | 11,85% | 18,29% | 23,20% | 26,31% | 28,88% | 30,60% |
| 0,75 | 3,59% | 11,90% | 18,12% | 23,00% | 26,15% | 28,75% | 30,35% |
| 0,80 | 3,62% | 11,94% | 18,14% | 22,82% | 26,07% | 28,47% | 30,16% |
| 0,85 | 3,68% | 11,96% | **18,07%** | 22,65% | 26,00% | 28,39% | 30,01% |
| 0,90 | 3,69% | 12,03% | 18,13% | 22,67% | 25,87% | 28,29% | 29,83% |
| 0,95 | 3,73% | 12,12% | 18,13% | 22,68% | **25,75%** | 28,20% | 29,76% |
| 1,00 | 3,75% | 12,15% | 18,16% | **22,64%** | 25,77% | **28,00%** | **29,63%** |

**Semente 7** (αₕ escolhidos em negrito)

| α | h1 | h2 | h3 | h4 | h5 | h6 | h7 |
|---|---|---|---|---|---|---|---|
| 0,00 | 2,61% | 12,92% | 21,72% | 27,18% | 31,41% | 33,40% | 35,60% |
| 0,05 | **2,60%** | 12,71% | 21,31% | 26,87% | 30,97% | 33,21% | 35,14% |
| 0,10 | 2,67% | 12,49% | 20,98% | 26,48% | 30,38% | 32,94% | 34,70% |
| 0,15 | 2,72% | 12,38% | 20,58% | 26,09% | 30,00% | 32,50% | 34,19% |
| 0,20 | 2,79% | 12,15% | 20,22% | 25,79% | 29,57% | 31,96% | 33,83% |
| 0,25 | 2,84% | 12,05% | 19,96% | 25,31% | 29,02% | 31,52% | 33,35% |
| 0,30 | 2,93% | 12,01% | 19,65% | 25,09% | 28,58% | 31,17% | 33,08% |
| 0,35 | 3,00% | 11,90% | 19,42% | 24,80% | 28,24% | 30,83% | 32,71% |
| 0,40 | 3,07% | 11,80% | 19,24% | 24,41% | 27,76% | 30,47% | 32,36% |
| 0,45 | 3,12% | 11,71% | 18,97% | 24,19% | 27,45% | 30,13% | 32,01% |
| 0,50 | 3,18% | 11,64% | 18,74% | 23,96% | 27,13% | 29,87% | 31,69% |
| 0,55 | 3,25% | 11,67% | 18,58% | 23,67% | 26,81% | 29,47% | 31,15% |
| 0,60 | 3,27% | 11,60% | 18,46% | 23,43% | 26,53% | 29,23% | 30,98% |
| 0,65 | 3,33% | **11,58%** | 18,44% | 23,13% | 26,32% | 28,94% | 30,74% |
| 0,70 | 3,40% | 11,64% | 18,20% | 22,91% | 26,14% | 28,79% | 30,38% |
| 0,75 | 3,45% | 11,68% | 18,15% | 22,75% | 26,10% | 28,50% | 30,25% |
| 0,80 | 3,54% | 11,72% | 18,12% | 22,57% | 25,88% | 28,38% | 30,05% |
| 0,85 | 3,61% | 11,75% | **18,06%** | **22,42%** | 25,70% | 28,21% | 29,95% |
| 0,90 | 3,67% | 11,75% | 18,12% | 22,47% | 25,50% | 27,99% | 29,92% |
| 0,95 | 3,73% | 11,84% | 18,16% | 22,45% | 25,54% | 27,90% | 29,84% |
| 1,00 | 3,73% | 11,91% | 18,21% | 22,52% | **25,41%** | **27,76%** | **29,80%** |

**Semente 2026** (αₕ escolhidos em negrito)

| α | h1 | h2 | h3 | h4 | h5 | h6 | h7 |
|---|---|---|---|---|---|---|---|
| 0,00 | 2,61% | 12,92% | 21,72% | 27,18% | 31,41% | 33,40% | 35,60% |
| 0,05 | **2,59%** | 12,71% | 21,27% | 26,88% | 30,92% | 33,27% | 35,15% |
| 0,10 | 2,69% | 12,57% | 20,94% | 26,47% | 30,35% | 33,00% | 34,77% |
| 0,15 | 2,75% | 12,47% | 20,63% | 26,08% | 29,99% | 32,58% | 34,31% |
| 0,20 | 2,87% | 12,28% | 20,26% | 25,76% | 29,48% | 32,06% | 33,88% |
| 0,25 | 2,93% | 12,11% | 19,98% | 25,44% | 29,03% | 31,66% | 33,48% |
| 0,30 | 3,03% | 12,00% | 19,75% | 25,04% | 28,62% | 31,26% | 33,18% |
| 0,35 | 3,10% | 12,00% | 19,53% | 24,85% | 28,21% | 31,03% | 32,91% |
| 0,40 | 3,17% | 11,88% | 19,23% | 24,57% | 27,96% | 30,73% | 32,48% |
| 0,45 | 3,23% | 11,80% | 19,02% | 24,37% | 27,73% | 30,37% | 32,09% |
| 0,50 | 3,34% | 11,78% | 18,85% | 24,16% | 27,37% | 30,07% | 31,76% |
| 0,55 | 3,40% | **11,73%** | 18,70% | 23,88% | 27,00% | 29,77% | 31,37% |
| 0,60 | 3,46% | 11,83% | 18,60% | 23,60% | 26,76% | 29,36% | 31,03% |
| 0,65 | 3,49% | 11,85% | 18,48% | 23,40% | 26,47% | 29,18% | 30,76% |
| 0,70 | 3,54% | 11,86% | 18,36% | 23,27% | 26,48% | 28,95% | 30,62% |
| 0,75 | 3,65% | 11,86% | 18,43% | 23,09% | 26,26% | 28,67% | 30,32% |
| 0,80 | 3,72% | 11,91% | 18,33% | 22,89% | 26,02% | 28,45% | 30,09% |
| 0,85 | 3,77% | 11,91% | 18,35% | 22,74% | 25,79% | 28,34% | 29,97% |
| 0,90 | 3,78% | 11,90% | **18,27%** | 22,72% | 25,67% | 28,15% | 29,73% |
| 0,95 | 3,84% | 11,95% | 18,32% | 22,62% | 25,59% | **27,85%** | **29,67%** |
| 1,00 | 3,89% | 11,97% | 18,27% | **22,59%** | **25,43%** | 27,87% | 29,69% |
