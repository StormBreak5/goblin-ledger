# Relatório da etapa 2h: calendário dos dias previstos

Etapa 2h de `estudos/lstm/ROTEIRO.md`, depois da 2g. Foi executada em 2026-10-29, das 20:31 às 22:16 de Brasília (de 23:31 de 29/10 a 01:16 de 30/10 em UTC), conforme `estudos/lstm/pedido-etapa2h.md`. Testa uma mudança só, sobre a configuração indicada pela 2g:

| Candidato | O que é | Treino novo? |
|---|---|---|
| `cal` | o calendário dos 7 dias previstos (`X_fut` [7, 6]), conhecido em D, achatado e juntado antes da camada densa de 32 (GELU) | 3 treinos |

As seis colunas do `X_fut`, para cada h de 1 a 7:

| Coluna | Conteúdo |
|---|---|
| `fut_dia_sin`, `fut_dia_cos` | dia da semana de D+h |
| `fut_patch` | houve patch entre D+1 e D+h |
| `fut_expansao` | houve marco de expansão (lançamento ou pré-patch) entre D+1 e D+h |
| `fut_temporada` | houve início de temporada entre D+1 e D+h |
| `fut_evento` | evento sazonal ativo em D+h |

- **Base:** a de sempre, `saida/treino01_agr`. A validação vai de 2025-07-16 a 2026-05-10; não foi preparada base nova.
- **Referência:** os treinos `gelu_s42`, `gelu_s7` e `gelu_s2026` da etapa 2g, que não foram retreinados nem reavaliados. Os `cal_s*` usam a mesma GELU, as mesmas sementes e os mesmos parâmetros; só o `X_fut` muda.
- **RN25:** o horizonte (7 dias) é menor que a antecedência com que um patch é conhecido (`antecedencia_anuncio_dias` = 14). O `calendario_futuro.py` recusa um horizonte maior. Os festivais e as temporadas são tratados como conhecidos com antecedência.
- **Tudo foi avaliado só na validação.** Nenhum treino previu o teste (`previu_teste: false` nos três `treino.json` novos).
- **Passo 0:** salvo no commit `37fcd2e`. O `pytest` do estudo tem 51 testes passando: os 46 de antes e os 5 novos.
- Depois do passo 0, nenhum código nem regra do estudo foi alterado.
- Uma análise extra da seção 3, das amostras em que o calendário traz algo que a janela de D ainda não traz, usou um script descartável fora do estudo, que só lê os arquivos de `saida/`.

Este relatório traz os números e aplica a regra de decisão definida no pedido. **A decisão final é do autor.**

## 1. O que foi rodado

**Comandos**, a partir de `estudos/lstm`, com o `.venv` do estudo e um treino por vez. Os passos 2 e 4 foram gravados em `saida/etapa2h_sequencia.log`.

```bash
A=saida/treino01_agr/avaliacao_validacao
C=saida/calendario2h/calendario_futuro.parquet
# passo 1: o calendário
python calendario_futuro.py --banco --pasta saida/treino01_agr --saida saida/calendario2h
# passo 2: os treinos
for s in 42 7 2026; do
  python treinar.py --pasta saida/treino01_agr --nome cal_s$s --semente $s --ativacao gelu --calendario-futuro $C
  python avaliar.py --pasta saida/treino01_agr --periodo validacao \
      --previsoes saida/treino01_agr/modelos/cal_s$s/previsoes_validacao.parquet --rotulo cal_s$s
done
# passo 4: apoio
for s in 42 7 2026; do
  python comparar.py --a ${A}_cal_s${s}_itens.csv --b ${A}_gelu_s${s}_itens.csv \
      --rotulos "cal" "referência" --saida saida/treino01_agr/comparacao_cal_gelu_s$s.json
  python transicao.py --base saida/treino2d_exp --detalhe ${A}_cal_s${s}_detalhe.parquet --rotulo cal_s$s
  for n in gelu cal; do
    python eventos_no_horizonte.py --pasta saida/treino01_agr --calendario $C \
        --detalhe ${A}_${n}_s${s}_detalhe.parquet --rotulo ${n}_s$s
  done
done
```

**Tempo:**
- passo 1: às 23:31 UTC de 29/10, logo antes dos treinos;
- passo 2: 1 h 42 min, de 23:33 a 01:15 UTC;
- passo 4: 1 min.

**Conferência dos eventos (passo 1):** as variáveis 9 a 14 (`f_dia_sin`, `f_dia_cos`, `f_dias_desde_patch`, `f_dias_ate_patch`, `f_expansao`, `f_temporada_ativa`, `f_dias_temporada` e `f_evento`) foram recalculadas com o `evento_jogo` de hoje.
- **Bateram em todas as 1.494 datas da base** (2022-09-04 a 2026-10-06, região US), sem nenhuma diferença.
- Ou seja, os eventos não mudaram desde a preparação da base, e o calendário futuro é coerente com o que a rede viu no passado.

**O calendário gravado:** uma linha por dia de origem, de 2022-11-01 a 2026-09-29, só da região US, com a assinatura `c693b8e6e4402850`. Amostras de cada período com a coluna diferente de zero em algum h:

| Coluna | Treino | Validação | Teste |
|---|---|---|---|
| Amostras | 3.792.068 | 1.420.443 | 786.081 |
| `fut_patch` | 510.106 | 238.216 | 76.896 |
| `fut_expansao` | 52.770 | 68.997 | 0 |
| `fut_temporada` | 196.392 | 102.918 | 77.570 |
| `fut_evento` | 1.768.408 | 701.576 | 214.883 |
| **Com evento no horizonte** | 1.637.791 | **665.257 (47%)** | 231.397 |

"Com evento no horizonte" é ter, entre D+1 e D+7, um patch, um marco de expansão, um início de temporada ou um festival que começa ou termina. Uma amostra pode ter mais de um evento. A coluna do teste só foi contada; nada foi previsto nele.

**Conferências do `treino.json`** (todas bateram):
- Fora o nome, o único parâmetro diferente dos `gelu_*` da mesma semente é o `calendario_futuro`: o arquivo, a assinatura (`c693b8e6e4402850`), o formato [7, 6] e as seis colunas.
- Os três `cal_*` têm 25.107 parâmetros, contra 23.763 da GELU. A diferença, 1.344, são os 42 valores do calendário ligados às 32 unidades da camada densa.
- Em todos, `previu_teste` é `false`.
- O lançamento avaliado pelo `transicao.py` foi 2026-03-02 nas três análises.

**Treinos** (o `val_loss` é a MAE nas 200.000 amostras da parada antecipada e é comparável entre os seis):

| Treino | Épocas | Melhor época | Melhor `val_loss` | Tempo por época | Tempo total do `fit` |
|---|---|---|---|---|---|
| `cal_s42` | 79 | 69 | 0,5107 | 32,4 s | 42 min 41 s |
| `cal_s7` | 63 | 53 | 0,5095 | 32,6 s | 34 min 12 s |
| `cal_s2026` | 48 | 38 | 0,5108 | 28,8 s | 23 min 04 s |
| *Referência `gelu` s42 · s7 · s2026 (etapa 2g)* | *63 · 48 · 71* | *53 · 38 · 61* | *0,5110 · 0,5098 · 0,5094* | *27,7 · 27,5 · 27,1 s* | *29 min 04 s · 22 min 02 s · 32 min 06 s* |

Os três treinos somaram 1 h 40 min de `fit`. Nenhuma época passou de 35 s: o computador não dormiu.

## 2. Tabela principal

**Validação inteira** (6.484 itens e 1.420.443 amostras): média ± desvio-padrão amostral nas 3 sementes (42, 7 e 2026).
- O desvio dos percentuais está em pontos percentuais.
- A RN10 é a do `avaliar.py`: MdAPE ≤ 15%, menor que o do ingênuo e pelo menos 30 dias avaliados.
- A coluna da referência é a da `gelu` na seção 2 de `docs/relatorio-etapa2g.md`.

| Medida | Referência (`gelu`) | `cal` |
|---|---|---|
| **Mediana do MdAPE por item** | **20,40% ± 0,10** | 20,45% ± 0,21 |
| Mediana do MAPE por item | 37,61% ± 0,18 | 37,69% ± 0,18 |
| MAPE h1 | 24,77% ± 0,07 | 24,85% ± 0,07 |
| MAPE h7 | 63,37% ± 0,15 | 63,51% ± 0,89 |
| Mediana do erro relativo ao ingênuo | 0,8361 ± 0,0020 | 0,8342 ± 0,0014 |
| Itens com erro relativo < 1 | 5.831 ± 14 | 5.814 ± 16 |
| **Itens liberados (RN10)** | **916 ± 19** | 886 ± 16 |
| Itens liberados sem o mínimo de 30 dias | 1.155 ± 32 | 1.136 ± 15 |

Mediana do MdAPE por item e itens liberados (RN10) em cada semente:

| Configuração | s42 | s7 | s2026 |
|---|---|---|---|
| Referência (`gelu`) | 20,42% (917) | 20,49% (897) | 20,30% (935) |
| `cal` | 20,22% (904) | 20,59% (883) | 20,55% (872) |
| Diferença (`cal` − `gelu`) | −0,20 ponto (−13) | +0,10 ponto (−14) | +0,24 ponto (−63) |

**O que a tabela mostra:**
- **MdAPE:** o `cal` melhora na semente 42 e piora nas outras duas. Na média, fica 0,05 ponto pior, e o desvio entre sementes dobra (0,21 contra 0,10).
- **Liberados:** caem nas três sementes, de 13 a 63 itens; na média, 30.
- **Demais medidas:** o MAPE h1, o MAPE h7 e a mediana do MAPE por item pioram um pouco. Só a mediana do erro relativo ao ingênuo melhora (0,8342 contra 0,8361), dentro do desvio de 0,0020.
- **`val_loss`:** fica no mesmo intervalo da GELU (0,5095 a 0,5108, contra 0,5094 a 0,5110). Nem no próprio critério de treino o calendário fez diferença.

## 3. Eventos no horizonte

Saída do `eventos_no_horizonte.py`: as amostras da validação divididas pelo `com_evento_no_horizonte` do calendário, para os dois modelos. Média ± desvio nas 3 sementes, nos mesmos alvos.
- **MdAPE por item:** a mediana entre os itens do MdAPE do item, só com os alvos do grupo.
- **MAPE:** a média de todos os alvos do grupo. Não é a "mediana do MAPE por item" da seção 2.
- **Razão:** o MdAPE por item do modelo dividido pelo do ingênuo, no mesmo grupo. Abaixo de 1, o modelo erra menos que o ingênuo.

| Grupo | Amostras | Itens | Modelo | MdAPE por item | Razão | MAPE |
|---|---|---|---|---|---|---|
| **Com evento** | 665.257 | 6.483 | Ingênuo | 24,18% | 1 | 62,25% |
| | | | Referência (`gelu`) | 20,58% ± 0,07 | 0,851 ± 0,003 | 49,04% ± 0,01 |
| | | | `cal` | 20,58% ± 0,18 | 0,851 ± 0,007 | 49,25% ± 0,40 |
| **Sem evento** | 755.186 | 5.792 | Ingênuo | 24,88% | 1 | 58,19% |
| | | | Referência (`gelu`) | 20,76% ± 0,08 | 0,834 ± 0,003 | 45,12% ± 0,04 |
| | | | `cal` | 20,79% ± 0,24 | 0,836 ± 0,010 | 45,36% ± 0,45 |
| **Todos** | 1.420.443 | 6.484 | Ingênuo | 24,17% | 1 | 60,10% |
| | | | Referência (`gelu`) | 20,40% ± 0,10 | 0,844 ± 0,004 | 46,96% ± 0,02 |
| | | | `cal` | 20,45% ± 0,21 | 0,846 ± 0,009 | 47,18% ± 0,41 |

Diferença `cal` − `gelu` no MdAPE por item, por semente (42 · 7 · 2026):

| Grupo | Diferença | Média |
|---|---|---|
| Com evento | −0,23 · +0,13 · +0,09 | −0,00 ± 0,19 |
| Sem evento | −0,33 · +0,16 · +0,28 | +0,04 ± 0,32 |
| Todos | −0,20 · +0,10 · +0,24 | +0,05 ± 0,23 |

**O ganho não aparece nem onde deveria.** Nas amostras com evento, o `cal` empata com a referência (−0,00 ± 0,19 ponto), e o MAPE piora 0,21 ponto.

**Parte do calendário já estava na janela de D.** Esta é uma análise feita depois, com um script fora do estudo; não muda a regra.
- **Já estava, por construção das variáveis 9 a 14 no último dia da janela:**
  - o dia da semana de D+h sai do dia da semana de D;
  - o patch: `f_dias_ate_patch` dá o número exato de dias até o próximo patch, quando ele cai nos próximos 14;
  - o marco de expansão: `f_expansao` liga 14 dias antes do marco, e o dia em que ela ligou está nos 30 dias da janela (salvo dois marcos próximos).
- **É novo:** o início de temporada (as duas variáveis 13 só dizem se há temporada em D e há quanto tempo ela começou) e o festival que começa ou termina entre D+1 e D+7 (a variável 14 só diz se há festival em D).

Separando as amostras da validação pelo que é novo:

| Evento entre D+1 e D+7 | Amostras | Parte da validação |
|---|---|---|
| Patch (já estava na janela) | 238.216 | 16,8% |
| Marco de expansão (já estava na janela) | 68.997 | 4,9% |
| Início de temporada (novo) | 102.918 | 7,2% |
| Festival que começa ou termina (novo) | 455.573 | 32,1% |
| **Com algo novo** (temporada ou festival) | **558.491** | **39,3%**, em 115 dos 293 dias de origem |

| Grupo | Itens | Modelo | MdAPE por item | MAPE |
|---|---|---|---|---|
| **Com algo novo** | 6.482 | Referência (`gelu`) | 20,66% ± 0,14 | 48,29% |
| | | `cal` | 20,69% ± 0,19 | 48,66% |
| **Sem nada novo** | 5.792 | Referência (`gelu`) | 20,78% ± 0,01 | 46,09% |
| | | `cal` | 20,82% ± 0,14 | 46,22% |

Nas amostras com algo novo, a diferença `cal` − `gelu` é −0,22 · +0,04 · +0,26 ponto (média +0,03 ± 0,24). Mesmo onde o calendário traz informação que a rede não tinha, não houve ganho.

**Leitura:**
- **O calendário não ajudou** em nenhum dos recortes. As diferenças médias ficam entre −0,00 e +0,05 ponto, dentro do desvio entre sementes, que é de 0,14 a 0,32.
- **Os eventos não deixam a previsão mais difícil:** a referência erra o mesmo, ou um pouco menos, nas amostras com evento (20,58% contra 20,76%). Os grupos não têm os mesmos itens (6.483 contra 5.792), então essa comparação é só indicativa. Mesmo assim, ela sugere que, para o item típico, os eventos do horizonte não são de onde vem o erro.
- **O MAPE piora em todos os recortes,** de 0,13 a 0,36 ponto. Nos três grupos do `eventos_no_horizonte.py`, o desvio dele entre sementes vai de 0,01–0,04 ponto para 0,40–0,45. Com o calendário, alguns erros grandes ficam maiores, e isso varia com a semente.

## 4. Comparação item a item e troca de expansão

### Item a item

Mesma semente nos dois modelos (6.484 itens).
- A diferença é `cal` − referência, em pontos percentuais; valor negativo significa que o `cal` erra menos.
- A RN10 está como "liberados nos dois / só no `cal` / só na referência".

| Semente | Mediana da diferença no MdAPE | p25 a p75 | `cal` melhor | Iguais | `cal` pior | RN10 |
|---|---|---|---|---|---|---|
| 42 | 0,00 | −0,64 a +0,54 | 3.245 | 49 | 3.190 | 821 / 83 / 96 |
| 7 | +0,04 | −0,47 a +0,66 | 3.065 | 59 | 3.360 | 809 / 74 / 88 |
| 2026 | +0,18 | −0,38 a +0,94 | 2.670 | 38 | 3.776 | 803 / 69 / 132 |

**O que a tabela mostra:**
- **Semente 42:** empata, com metade dos itens para cada lado.
- **Sementes 7 e 2026:** o `cal` erra mais na maioria dos itens. Na 2026, são 3.776 piores contra 2.670 melhores.
- **Faixas:** a faixa p25–p75, de cerca de −0,5 a +0,7 ponto, é tão larga quanto a da troca de ativação na 2g. O calendário mexe bastante item a item, para os dois lados, sem ganho no saldo.
- **RN10:** de 162 a 201 itens trocam de lado. A referência libera de 88 a 132 itens que o `cal` não libera, e o `cal` libera de 69 a 83 que a referência não libera.

### Troca de expansão (lançamento de Midnight, 2026-03-02)

Razão entre o MdAPE do modelo e o do ingênuo a 7 dias (`horizonte = h7`), média ± desvio nas 3 sementes, dos `transicao_*.csv`. Abaixo de 1, o modelo erra menos que o ingênuo. A linha da referência é a da `gelu` na seção 4 de `docs/relatorio-etapa2g.md`.

| Configuração | Expansão que sai · troca | Todos · troca | Todos · resto | Expansão que entra · resto |
|---|---|---|---|---|
| Referência (`gelu`) | 0,923 ± 0,013 | 0,863 ± 0,001 | **0,822 ± 0,002** | 0,790 ± 0,051 |
| `cal` | **0,911 ± 0,006** | **0,856 ± 0,011** | 0,827 ± 0,005 | **0,748 ± 0,017** |

**Leitura da tabela:**
- **Este é o único lugar em que o calendário parece ajudar:** as três razões ligadas à expansão melhoram (−0,012, −0,007 e −0,042).
- **Mas cada melhora fica dentro do maior desvio** da coluna (0,013, 0,011 e 0,051).
- A janela da troca é pequena: a "expansão que entra · resto" tem 4.741 alvos no h7, de 672 itens.
- **Fora da troca** ("todos · resto"), o `cal` fica um pouco pior (0,827 contra 0,822), no limite do desvio de 0,005.
- O marco de expansão já estava na janela de D (seção 3). No `X_fut`, ele chega pronto, por dia previsto, em vez de a rede ter de deduzi-lo da janela; o efeito disso, se houver, ficou dentro do ruído.

## 5. Regra de decisão

O critério é o da 2g:
- melhorar a mediana do MdAPE por item mais que o maior desvio entre sementes das duas configurações;
- **e** não reduzir os itens liberados pela RN10 mais que o maior desvio dessa medida.

| Candidato | Comparado com | MdAPE: referência → `cal` | Ganho | Maior desvio | Liberados: referência → `cal` | Queda | Maior desvio | Aprovado? |
|---|---|---|---|---|---|---|---|---|
| `cal` | `gelu_s*`, validação | 20,40% → 20,45% | −0,049 ponto (piorou) | 0,206 ponto (o do `cal`) | 916 → 886 | 30 | 19 (o da referência) | **Não** |

Passo a passo:

1. **Medida principal:** o MdAPE vai de 20,404% para 20,452%. O `cal` piora 0,049 ponto, em vez de melhorar mais que 0,206. **Não passa.**
2. **Proteção:** os liberados caem de 916,3 para 886,3. A queda de 30,0 passa do maior desvio, 19,0. **Também não passa.**
3. **O `cal` não é aprovado nos dois critérios.** Pelo pedido, **fica a GELU,** e a configuração congela:
   - eventos agregados (variáveis 1 a 18), sem máscara, perda MAE;
   - LSTM de 64 unidades, taxa fixa de 0,001;
   - Dense(32, GELU);
   - **sem o calendário dos dias previstos** (`--calendario-futuro` desligado, o padrão do `treinar.py`);
   - os demais parâmetros padrão do `treinar.py`.

**Números que a regra não usa,** registrados para a decisão do autor:

- **A favor do `cal`:**
  - **Semente 42:** 20,22%, o menor MdAPE entre os seis modelos comparados.
  - **Erro relativo ao ingênuo:** fica um pouco menor (0,8342 contra 0,8361), dentro do desvio.
  - **Troca de expansão:** as três razões ligadas à expansão melhoram, dentro do desvio (seção 4).
- **Contra o `cal`:**
  - piora a medida principal em duas das três sementes, e o desvio entre sementes dobra (0,21 contra 0,10 ponto);
  - reduz os liberados nas três sementes;
  - piora o MAPE em todos os recortes da seção 3;
  - não ganha nas amostras com evento no horizonte, nem nas que trazem algo novo para a rede (seção 3);
  - deixa o `val_loss` no mesmo intervalo.

## 6. Custo no sistema

**Não se aplica:** o `cal` não foi aprovado, e nada muda no sistema (`backend/src/ml/`).
- O modelo vigente continua sendo o de antes.
- No estudo, o código da 2h fica atrás de uma opção desligada por padrão (`--calendario-futuro`). Sem ela, a rede é a mesma de antes; isso é conferido pelo teste `test_calendario_futuro_desligado_mantem_a_rede`.

Registro, só para a discussão dos resultados no TC, do que o calendário custaria se fosse adotado:
- **Rede:** +1.344 parâmetros (25.107 contra 23.763). O `modelo.keras` iria de 340.778 para 362.057 bytes.
- **Treino:** o `cal_s2026` levou 28,8 s por época, contra 27,1 a 27,7 s da GELU. Os outros dois `cal` levaram cerca de 33 s, mas com a mesma rede; a diferença entre eles é da carga da máquina na hora, e não do calendário.
- **C3:** o sistema precisaria de patches e temporadas futuros em `evento_jogo`. O banco não tem nenhum hoje: o último patch é de 2026-08-11, e a última temporada, de 2026-08-18.

## 7. Problemas encontrados

A execução não teve erros (`saiu com 0` no log, nenhum `Traceback`), e nenhuma conferência pedida falhou. Pontos a registrar:

- **O "com evento" do pedido inclui eventos que a rede já via.**
  - O patch e o marco de expansão já estavam nas variáveis 11 e 12 do último dia da janela, e o dia da semana, na variável 9.
  - Por isso, a seção 3 traz também o recorte "com algo novo" (início de temporada ou festival que começa ou termina entre D+1 e D+7).
  - Esse recorte usou um script descartável fora do estudo, que só lê o calendário, a base e os `_detalhe.parquet` de `saida/`. Ele reaproveita a função `analisar` do `eventos_no_horizonte.py`.
- **O tempo por época variou entre os `cal`,** de 28,8 s a 32,6 s em média, com a mesma rede. Nenhuma época passou de 35 s, então não houve pausa. Os números da seção 6 usam o treino mais rápido como estimativa do custo.
- **Commit do passo 0 (`37fcd2e`):**
  - Entraram só os sete arquivos do passo: `calendario_futuro.py`, `eventos_no_horizonte.py`, `io_dados.py`, `treinar.py`, `tests/test_estudo.py`, `README.md` e `pedido-etapa2h.md`.
  - Ficaram de fora, como na 2g, as suas alterações locais em `ROTEIRO.md` e os pedidos não versionados que não são desta etapa.
- **Avisos no `pytest`:** os 51 testes passam com 34 avisos. Todos são o mesmo `DeprecationWarning` de dentro do Keras com o NumPy 2, como nas etapas anteriores (eram 24 na 2g).
- **Voltar como estava:** não é preciso desfazer nada para manter a GELU. Se o autor preferir tirar a opção do estudo, basta reverter o commit `37fcd2e`. Os resultados desta etapa ficam em `saida/`, fora do Git.

Os arquivos ficam em `estudos/lstm/saida/`, fora do Git:
- **Em `calendario2h/`:** `calendario_futuro.parquet` e `calendario_futuro.json`, com a conferência e as contagens da seção 1.
- **Em `treino01_agr/`:**
  - os modelos novos (`modelos/cal_s*`);
  - as avaliações (`avaliacao_validacao_cal_s*`);
  - as comparações (`comparacao_cal_gelu_s*.json`);
  - as análises da troca (`transicao_cal_s*.csv`);
  - os eventos no horizonte (`eventos_horizonte_{gelu,cal}_s*.csv`).
- **Logs:** `etapa2h_sequencia.log` (passos 2 e 4) e `etapa2h_resumo.txt` (as tabelas acima, em bruto, com o recorte "com algo novo").
