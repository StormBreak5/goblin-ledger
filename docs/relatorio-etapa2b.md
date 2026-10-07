# Relatório da etapa 2b: sementes e dados para a RN10

Continuação de `docs/relatorio-etapa2.md`, executada em 2026-10-07. Mesma base completa (`saida/treino01` e `saida/treino01_agr`) e parâmetros padrão do `treinar.py`. **Tudo foi avaliado só no período de validação.** Nenhum treino previu o teste (`previu_teste: false` nos 12 `treino.json`), que fica para o CU11 (RN25).

O `avaliar.py` novo traz MdAPE, erro relativo ao ingênuo e a curva `liberacao_por_limiar`. O `pytest` do estudo tinha 23 testes passando antes da execução.

## 1. O que foi rodado

1. **Reavaliação** com o `avaliar.py` novo: ingênuo, regressão linear e os três treinos da semente 42 da etapa 2. Os números antigos se repetem; por exemplo, `lstm01` continua com 62,70% de MAPE médio por item e 5.100 itens que superam o ingênuo.
2. **9 treinos novos**, um por vez, completando 4 configurações × 3 sementes (42, 7 e 2026). Os nomes seguem `<base>_<mascara|semmascara>_s<semente>`.
   - Os três treinos da semente 42 da etapa 2 foram reaproveitados sem retreino: `lstm01` = `treino01_mascara_s42`, `lstm01_sem_mascara` = `treino01_semmascara_s42` e `lstm01_agr` = `treino01_agr_mascara_s42`.

As 12 avaliações usam as mesmas 1.420.443 amostras de validação, os mesmos 6.484 itens e os mesmos 9.561.970 alvos observados.

## 2. As 4 configurações nas 3 sementes

Média ± desvio-padrão amostral nas 3 sementes. O desvio dos percentuais está em pontos percentuais. As referências não dependem de semente.

| Configuração | Mediana do MAPE por item | MAPE médio por item | MAPE h1 | MAPE h7 | Itens que superam o ingênuo | Mediana do erro relativo ao ingênuo |
|---|---|---|---|---|---|---|
| Eventos detalhados, com máscara | 39,89% ± 0,32 | 61,84% ± 0,82 | 26,03% ± 0,24 | 65,25% ± 1,14 | 5.234 ± 123 | 0,855 ± 0,004 |
| Eventos detalhados, sem máscara | 39,83% ± 0,25 | 61,78% ± 0,57 | 25,92% ± 0,16 | 64,76% ± 0,92 | 5.276 ± 90 | 0,854 ± 0,002 |
| Eventos agregados, com máscara | 39,27% ± 0,41 | 61,27% ± 1,40 | 25,89% ± 0,21 | 64,62% ± 1,88 | 5.292 ± 130 | 0,851 ± 0,003 |
| **Eventos agregados, sem máscara** | **38,66% ± 0,19** | **59,69% ± 0,33** | **25,36% ± 0,03** | **62,32% ± 0,57** | **5.476 ± 65** | **0,846 ± 0,001** |
| *Referência: regressão linear* | *44,51%* | *68,69%* | *29,64%* | *69,43%* | *3.949* | *0,906* |
| *Referência: ingênuo* | *47,19%* | *76,31%* | *26,64%* | *88,98%* | — | *1 (por definição)* |

Mediana do MAPE por item em cada semente:

| Configuração | s42 | s7 | s2026 |
|---|---|---|---|
| Eventos detalhados, com máscara | 40,26% | 39,66% | 39,75% |
| Eventos detalhados, sem máscara | 40,00% | 39,96% | 39,55% |
| Eventos agregados, com máscara | 38,80% | 39,51% | 39,51% |
| Eventos agregados, sem máscara | 38,55% | 38,88% | 38,56% |

## 3. Configuração escolhida

A regra é: menor média da mediana do MAPE por item. Se a diferença para a segunda for menor que o desvio entre sementes, fica a mais simples (eventos agregados, com máscara).

| Posição | Configuração | Média |
|---|---|---|
| 1ª | Eventos agregados, sem máscara | 38,66% |
| 2ª | Eventos agregados, com máscara | 39,27% |
| 3ª | Eventos detalhados, sem máscara | 39,83% |
| 4ª | Eventos detalhados, com máscara | 39,89% |

A diferença entre a 1ª e a 2ª é de **0,61 ponto**. Ela é maior que o desvio entre sementes das duas (0,19 da 1ª e 0,41 da 2ª), então o desempate pela mais simples não se aplica.

**Escolhida: eventos agregados, sem máscara** (`--eventos-agregados` na preparação e `--sem-mascara` no treino). Ela também é a melhor nas outras cinco medidas e a de menor dispersão entre sementes.

Observações:

- **Agregados contra detalhados:** os eventos agregados ficaram à frente dos detalhados com e sem máscara. O resultado da etapa 2, que tinha uma semente só, se confirma com três.
- **Máscara:** sem a máscara foi melhor nas duas bases. Nos eventos agregados a diferença (0,61 ponto) supera o desvio. Nos detalhados (0,05 ponto), fica dentro do ruído.
  - Uma hipótese, não testada: os alvos preenchidos ("sem mudança") puxam a rede para perto do ingênuo, que é forte nos primeiros dias.
  - O `val_loss` com e sem máscara não é comparável, porque sem máscara ele inclui os dias preenchidos. A comparação vale pelo `avaliar.py`, que só conta os dias observados.
- **Viés otimista:** a validação serve tanto para a parada antecipada quanto para esta escolha, então os números da configuração escolhida são levemente otimistas. O teste continua intocado.

## 4. Dados para a RN10 (configuração escolhida, melhor semente)

A melhor semente é a 42 (`treino01_agr_semmascara_s42`), com 38,55% de mediana do MAPE por item. Na prática empata com a semente 2026 (38,56%).

| Medida | Valor |
|---|---|
| Itens avaliados | 6.484 |
| Mediana do MdAPE por item | **22,83%** (regressão linear 28,02%; ingênuo 24,17%) |
| Mediana do MAPE por item | 38,55% |
| Itens com erro relativo ao ingênuo menor que 1 | **5.334** (82,3%; regressão linear 4.257) |
| Itens que superam o ingênuo no MAPE | 5.470 |
| Itens liberados pela RN10 atual (MAPE ≤ 15% e menor que o do ingênuo) | 391 (6,0%) |

**Curva de liberação.** Para cada limiar, quantos itens têm a medida menor ou igual a ele **e** menor que a do ingênuo na mesma medida. O ingênuo não libera nenhum item, já que não pode superar a si mesmo.

| Limiar | Pelo MAPE | Pelo MdAPE | Regressão linear pelo MAPE | Regressão linear pelo MdAPE |
|---|---|---|---|---|
| 10% | 154 (2,4%) | 216 (3,3%) | 23 | 35 |
| 15% | 391 (6,0%) | 592 (9,1%) | 80 | 172 |
| 20% | 713 (11,0%) | 1.167 (18,0%) | 221 | 447 |
| 25% | 1.155 (17,8%) | 1.861 (28,7%) | 464 | 868 |
| 30% | 1.698 (26,2%) | 2.487 (38,4%) | 803 | 1.313 |

Os percentuais são sobre os 6.484 itens. O MdAPE é menos sensível aos poucos dias com erro enorme (os patamares de preço alternados da etapa 2) e libera de 1,4 a 1,6 vez mais itens que o MAPE no mesmo limiar.

## 5. Treinos

Todos os treinos usaram:

- perda Huber, LSTM de 64 unidades, dropout 0,2, Adam com taxa 0,001 e lote de 512;
- 400.000 amostras de treino por época;
- parada antecipada com 200.000 amostras da validação (paciência de 10 épocas, máximo de 100).

| Treino | Pasta do modelo (em `estudos/lstm/saida/`) | Épocas | Melhor época | Tempo por época | Tempo total |
|---|---|---|---|---|---|
| `treino01_mascara_s42` * | `treino01/modelos/lstm01` | 28 | 18 | 28,7 s | 13 min 22 s |
| `treino01_mascara_s7` | `treino01/modelos/treino01_mascara_s7` | 36 | 26 | 27,6 s | 16 min 35 s |
| `treino01_mascara_s2026` | `treino01/modelos/treino01_mascara_s2026` | 30 | 20 | 27,6 s | 13 min 49 s |
| `treino01_semmascara_s42` * | `treino01/modelos/lstm01_sem_mascara` | 19 | 9 | 30,0 s | 9 min 30 s |
| `treino01_semmascara_s7` | `treino01/modelos/treino01_semmascara_s7` | 18 | 8 | 28,0 s | 8 min 23 s |
| `treino01_semmascara_s2026` | `treino01/modelos/treino01_semmascara_s2026` | 30 | 20 | 27,7 s | 13 min 51 s |
| `treino01_agr_mascara_s42` * | `treino01_agr/modelos/lstm01_agr` | 52 | 42 | 30,6 s | 26 min 32 s |
| `treino01_agr_mascara_s7` | `treino01_agr/modelos/treino01_agr_mascara_s7` | 21 | 11 | 26,8 s | 9 min 23 s |
| `treino01_agr_mascara_s2026` | `treino01_agr/modelos/treino01_agr_mascara_s2026` | 30 | 20 | 27,1 s | 13 min 32 s |
| `treino01_agr_semmascara_s42` | `treino01_agr/modelos/treino01_agr_semmascara_s42` | 45 | 35 | 28,2 s | 21 min 10 s |
| `treino01_agr_semmascara_s7` | `treino01_agr/modelos/treino01_agr_semmascara_s7` | 50 | 40 | 26,8 s | 22 min 22 s |
| `treino01_agr_semmascara_s2026` | `treino01_agr/modelos/treino01_agr_semmascara_s2026` | 34 | 24 | 27,0 s | 15 min 19 s |

\* Treino da etapa 2, reaproveitado.

- O tempo total é o do `fit`, como registrado no `treino.json`.
- Os 9 treinos novos somaram 2 h 14 min de `fit`; a sequência inteira, com as avaliações, levou 2 h 22 min, na CPU.
- As avaliações ficam em `saida/<base>/avaliacao_validacao_<nome>_*` e os logs, em `saida/etapa2b_sequencia.log` e `saida/<base>/treino_<nome>.log`.
- O acompanhamento visual dos treinos (curvas de perda por época) está em `saida/painel/index.html`.

Nenhum código nem regra do estudo foi alterado nesta etapa, e nenhum erro foi encontrado na execução.
