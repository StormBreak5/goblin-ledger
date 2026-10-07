# Relatório da etapa 2d: ciclo de vida do item

Etapa 2d de `estudos/lstm/ROTEIRO.md`, executada em 2026-10-07 conforme `estudos/lstm/pedido-etapa2d.md`. Testa duas variáveis novas:

- **19:** item da expansão vigente no dia (`--variavel-expansao-item`);
- **20:** idade do item (`--variavel-idade-item`).

Todos os modelos usaram a configuração escolhida na etapa 2b: eventos agregados, sem máscara e parâmetros padrão do `treinar.py`.

- **Tudo foi avaliado só no período de validação.** Nenhum treino previu o teste (`previu_teste: false` nos seis `treino.json`).
- Antes de começar, o `pytest` do estudo tinha 36 testes passando, e o estado foi salvo no commit `3e23462`.
- Nenhum código nem regra do estudo foi alterado.

Este relatório traz os números e aplica a regra de decisão definida no pedido. **A decisão final é do autor.**

## 1. O que foi rodado

**Bases novas e conferência com a referência** (`saida/treino01_agr/normalizacao.json`):

| Base | Variáveis de sequência | Datas de corte | Linhas | Amostras (treino · validação · teste) | Verificação |
|---|---|---|---|---|---|
| `treino01_agr` (referência) | 16 | 2022-09-04 · 2025-07-16 · 2026-05-11 · 2026-10-06 | 8.073.939 | 3.792.068 · 1.420.443 · 786.081 | — |
| `treino2d_exp` | 17 (+ `f_item_expansao_vigente`) | iguais | 8.073.939 | iguais | OK (7,11e-07) |
| `treino2d_expidade` | 18 (+ `f_idade_item`) | iguais | 8.073.939 | iguais | OK (7,11e-07) |

As contagens das duas bases novas são **iguais** às da referência, então a comparação vale. A referência (`treino01_agr_semmascara_s42`, `s7` e `s2026`) não foi retreinada: só foi reavaliada como `ref_s*`, com o `avaliar.py` atual, em que a RN10 é por MdAPE ≤ 15%.

**Itens por expansão** (`ciclo_do_item.itens_por_expansao`, igual nas duas bases):

| Expansão do item | Itens |
|---|---|
| Anterior aos dados ou desconhecida | 4.064 |
| The War Within | 927 |
| Dragonflight | 821 |
| Midnight | 714 |
| Shadowlands | 36 |
| **Total** | **6.562** |

**Treinos** (parâmetros padrão; perda Huber, 64 unidades, 400.000 amostras por época, paciência de 10 épocas, sem máscara):

| Treino | Variáveis de sequência | Épocas | Melhor época | Tempo por época | Tempo total |
|---|---|---|---|---|---|
| `exp_s42` | 17 | 23 | 13 | 28,7 s | 11 min 00 s |
| `exp_s7` | 17 | 36 | 26 | 29,3 s | 17 min 34 s |
| `exp_s2026` | 17 | 30 | 20 | 28,1 s | 14 min 03 s |
| `expidade_s42` | 18 | 61 | 51 | 28,2 s | 28 min 37 s |
| `expidade_s7` | 18 | 36 | 26 | 29,0 s | 17 min 24 s |
| `expidade_s2026` | 18 | 30 | 20 | 28,6 s | 14 min 18 s |
| *Referência s42, s7, s2026 (etapa 2b)* | *16* | *45 · 50 · 34* | *35 · 40 · 24* | — | — |

`variaveis_sequencia` foi conferido nos seis treinos: 17 nos `exp` e 18 nos `expidade`. Os seis treinos somaram 1 h 43 min de `fit`; a sequência inteira levou 1 h 55 min.

## 2. Tabela principal (validação, 6.484 itens)

Média ± desvio-padrão amostral nas 3 sementes (42, 7 e 2026). O desvio dos percentuais está em pontos percentuais.

| Medida | Referência | `exp` (com a 19) | `expidade` (com a 19 e a 20) |
|---|---|---|---|
| **Mediana do MdAPE por item** | **22,67% ± 0,15** | **22,35% ± 0,36** | **22,53% ± 0,31** |
| Mediana do MAPE por item | 38,66% ± 0,19 | 38,69% ± 0,42 | 38,96% ± 0,43 |
| MAPE h1 | 25,36% ± 0,03 | 25,43% ± 0,33 | 25,40% ± 0,26 |
| MAPE h7 | 62,32% ± 0,57 | 63,46% ± 0,33 | 63,94% ± 0,59 |
| Mediana do erro relativo ao ingênuo | 0,8459 ± 0,0008 | 0,8439 ± 0,0003 | 0,8445 ± 0,0013 |
| Itens com erro relativo < 1 | 5.345 ± 11 | 5.399 ± 73 | 5.409 ± 55 |
| Itens liberados (RN10: MdAPE ≤ 15% e menor que o do ingênuo) | 603 ± 21 | 653 ± 20 | 627 ± 37 |

Mediana do MdAPE por item em cada semente:

| Configuração | s42 | s7 | s2026 |
|---|---|---|---|
| Referência | 22,83% | 22,66% | 22,53% |
| `exp` | 22,19% | 22,09% | 22,76% |
| `expidade` | 22,59% | 22,19% | 22,80% |

## 3. Troca de expansão (lançamento de Midnight, 2026-03-02)

O `transicao.py` foi rodado nas 9 avaliações, e o lançamento avaliado foi 2026-03-02 em todas. A janela da troca vai de 21 dias antes a 30 dias depois do lançamento; o resto é o restante da validação. Os grupos da referência usam o `itens.parquet` da `treino2d_exp`, que tem os mesmos itens.

Previsões a 7 dias (`horizonte = h7`), média ± desvio nas 3 sementes. A razão é o MdAPE do modelo dividido pelo do ingênuo: abaixo de 1, o modelo erra menos. O viés mediano positivo significa que o modelo previu acima do preço real.

| Grupo · janela | Medida | Referência | `exp` | `expidade` |
|---|---|---|---|---|
| Expansão que sai (The War Within) · troca | razão | **0,959 ± 0,004** | **1,017 ± 0,052** | **1,015 ± 0,046** |
| | viés mediano | +8,35% ± 0,65 | +12,81% ± 3,64 | +12,19% ± 4,14 |
| Anteriores ou desconhecida · troca | razão | 0,887 ± 0,008 | 0,890 ± 0,008 | 0,893 ± 0,007 |
| | viés mediano | +2,47% ± 1,21 | +3,14% ± 1,28 | +3,57% ± 0,56 |
| Todos · troca | razão | 0,897 ± 0,006 | 0,910 ± 0,014 | 0,912 ± 0,001 |
| | viés mediano | +3,30% ± 1,16 | +4,38% ± 1,49 | +4,58% ± 0,53 |
| Todos · resto | razão | 0,873 ± 0,001 | 0,868 ± 0,004 | 0,872 ± 0,007 |
| | viés mediano | +0,66% ± 0,59 | +0,65% ± 0,43 | +1,07% ± 1,11 |
| Expansão que entra (Midnight) · resto | razão | **0,942 ± 0,012** | **0,761 ± 0,048** | **0,779 ± 0,044** |
| | viés mediano | +13,85% ± 0,69 | +5,75% ± 2,77 | +4,14% ± 2,76 |

Por semente, nas duas razões usadas pela regra:

| Razão a 7 dias | Configuração | s42 | s7 | s2026 |
|---|---|---|---|---|
| Expansão que sai · troca | Referência | 0,963 | 0,955 | 0,961 |
| | `exp` | 1,004 | 1,074 | 0,972 |
| | `expidade` | 0,978 | 1,000 | 1,066 |
| Expansão que entra · resto | Referência | 0,954 | 0,930 | 0,942 |
| | `exp` | 0,805 | 0,769 | 0,710 |
| | `expidade` | 0,824 | 0,776 | 0,736 |

Tamanho dos grupos (alvos a 7 dias, referência s42):

| Grupo · janela | Alvos | Itens | Variação real mediana |
|---|---|---|---|
| Expansão que sai · troca | 38.676 | 855 | −2,82% |
| Anteriores ou desconhecida · troca | 199.749 | 4.746 | −2,00% |
| Todos · troca | 238.425 | 5.601 | −2,11% |
| Todos · resto | 1.117.255 | 6.477 | −1,10% |
| Expansão que entra · resto | 4.741 | 672 | −11,46% |

## 4. Comparação item a item com a referência

São os 6.484 itens, com a mesma semente nos dois modelos. A diferença é nova − referência, em pontos percentuais; valor negativo significa que a configuração nova erra menos. A concordância da RN10 está como "liberados nos dois / só na nova / só na referência".

| Configuração | Semente | Mediana da diferença no MdAPE | p25 a p75 | Nova melhor | Iguais | Nova pior | RN10 |
|---|---|---|---|---|---|---|---|
| `exp` | 42 | −0,25 | −1,23 a +0,50 | 3.800 | 19 | 2.665 | 501 / 154 / 91 |
| `exp` | 7 | −0,23 | −1,06 a +0,53 | 3.774 | 27 | 2.683 | 518 / 154 / 73 |
| `exp` | 2026 | +0,28 | −0,44 a +1,10 | 2.565 | 25 | 3.894 | 495 / 137 / 132 |
| `expidade` | 42 | −0,05 | −0,99 a +0,79 | 3.346 | 22 | 3.116 | 474 / 125 / 118 |
| `expidade` | 7 | −0,17 | −1,06 a +0,57 | 3.671 | 26 | 2.787 | 520 / 149 / 71 |
| `expidade` | 2026 | +0,26 | −0,48 a +1,13 | 2.619 | 25 | 3.840 | 490 / 122 / 137 |

## 5. Regra de decisão

Aplicação literal da regra do pedido:
- **Desvio da medida principal:** o maior desvio entre sementes das duas configurações comparadas.
- **Desvio da medida da troca:** o maior desvio da própria medida.
- **"Melhorar":** reduzir a mediana do MdAPE ou a razão.

**Variável 19** (`exp` contra a referência):

| Critério | Referência | `exp` | Ganho da `exp` | Desvio considerado | Atende? |
|---|---|---|---|---|---|
| Medida principal: mediana do MdAPE por item | 22,67% | 22,35% | 0,33 ponto | 0,36 ponto (o da `exp`) | **Não** (0,33 < 0,36) |
| Medida da troca: razão a 7 dias, expansão que sai, na troca | 0,959 | 1,017 | −0,057 (piorou) | 0,052 (o da `exp`) | **Não** (piorou) |

**Variável 20** (`expidade` contra `exp`):

| Critério | `exp` | `expidade` | Ganho da `expidade` | Desvio considerado | Atende? |
|---|---|---|---|---|---|
| Medida principal: mediana do MdAPE por item | 22,35% | 22,53% | −0,18 ponto (piorou) | 0,36 ponto | **Não** |
| Razão a 7 dias, expansão que entra, fora da troca | 0,761 | 0,779 | −0,017 (piorou) | 0,048 | **Não** |

**O que a regra indica:** nenhuma das duas variáveis entra. Fica a **referência**, sem as variáveis 19 e 20, que é a configuração mais simples.

Como define o pedido, a 20 foi comparada com a `exp` (as duas com a 19). Contra a referência, a `expidade` melhora a razão da expansão que entra (0,779 contra 0,942), mas esse ganho é o mesmo que já aparece na `exp`, que só tem a 19.

Números que a regra não usa, registrados para a decisão do autor:

- **Medida principal da 19:** o ganho de 0,33 ponto fica a 0,03 ponto do limiar. A `exp` foi melhor em duas sementes (s42 e s7) e pior na s2026.
- **Itens liberados pela RN10:** a `exp` liberou 653 ± 20, contra 603 ± 21 da referência.
- **Expansão que sai, na troca:** as duas variáveis pioraram a razão nas três sementes, com viés mediano de +12% a +13%, contra +8% da referência.
- **Expansão que entra (itens novos de Midnight), fora da troca:** as duas variáveis melhoraram a razão em todas as sementes (de 0,942 para 0,761 e 0,779), e o viés mediano caiu de +13,85% para +5,75% e +4,14%. Este grupo tem 672 itens e 4.741 alvos a 7 dias.
- **MAPE h7:** piorou com as duas variáveis (de 62,32% para 63,46% e 63,94%).

## 6. Problemas encontrados

A execução não teve erros, e nenhuma conferência pedida falhou: as contagens das bases, as duas verificações de ida e volta, o número de variáveis de sequência dos treinos e o lançamento avaliado (2026-03-02) bateram.

Pontos a registrar:

- **Razão na expansão que sai:** o pedido cita 0,98 para o modelo da etapa 2c; a referência desta etapa (outro modelo, a `treino01_agr`) tem 0,959 ± 0,004 no mesmo grupo e janela.
- **Grupos da referência:** vêm do `itens.parquet` da `treino2d_exp`, porque a `treino01_agr` foi preparada antes da etapa 2d.

Os arquivos ficam em `estudos/lstm/saida/` (fora do Git):

- `treino2d_exp/` e `treino2d_expidade/`, com bases, modelos, avaliações, `transicao_*.csv` e `comparacao_ref_s*.json`;
- `treino01_agr/avaliacao_validacao_ref_s*` e `treino01_agr/transicao_ref_s*.csv`;
- os logs `etapa2d_sequencia.log` e `transicao_*.log`;
- o painel dos treinos em `painel/index.html` (o da etapa 2c ficou em `painel/etapa2c.html`).
