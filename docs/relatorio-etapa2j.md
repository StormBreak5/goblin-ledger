# Relatório da etapa 2j: qualidade do item em one-hot

Etapa 2j do estudo, depois da 2i. Foi executada em 11/11/2026, das 20:18 às 21:34 de Brasília (de 23:18 de 11/11 a 00:34 de 12/11 em UTC), conforme o plano aprovado no chat, com a regra A da 2i. Responde a um ponto da orientação de 30/10: as variáveis categóricas não devem entrar como número contínuo.

| Candidato | O que é | Treino novo? |
|---|---|---|
| `qual` | a qualidade do item (variável 16) em seis colunas de 0 ou 1, no lugar da qualidade dividida por 5 | 3 treinos |

**O ponto da orientação.** A classe e a subclasse já atendiam ao pedido, porque entram como vetores aprendidos (variável 15). A qualidade, não: ela entrava como `qualidade ÷ 5` (pobre = 0; comum = 0,2; … lendária ou acima = 1,0). Isso tem três problemas em tese:
- cria uma distância entre as qualidades que o jogo não define. A ordem existe (pobre < comum < … < lendária), mas épica não "vale o dobro" de incomum;
- junta lendária, artefato e herança no mesmo 1,0;
- confunde o item sem qualidade com o pobre, porque os dois viram 0.

**A troca.** Seis colunas de 0 ou 1:
- `f_qualidade_pobre`, `_comum`, `_incomum`, `_rara`, `_epica` e `_lendaria`;
- a última também vale para artefato e herança;
- um item sem qualidade fica com as seis em 0.

As variáveis fixas passam de 4 para 9, e a rede ganha 160 parâmetros.

**Condições da etapa:**
- **Base:** uma cópia da `saida/treino2i_sub`, em `saida/treino2j_qual`, com só a qualidade refeita pelo `refazer_qualidade.py`. Todo o resto (linhas originais, janelas, cortes, demais variáveis e constantes) é o mesmo arquivo da 2i. Não foi preparada base nova a partir do banco, porque o banco mudou desde a preparação.
- **Referência:** os treinos `sub_s42`, `sub_s7` e `sub_s2026` da 2i, que não foram retreinados. Os `qual_s*` usam a mesma GELU, as mesmas sementes e os mesmos parâmetros; só a base muda.
- **Regra A (não inferioridade),** fixada antes dos treinos: o `qual` é adotado se a mediana do MdAPE por item não piorar mais que o maior desvio entre sementes **e** os liberados pela RN10 não caírem mais que o maior desvio dessa medida.
- **Tudo foi avaliado só na validação** (2025-07-16 a 2026-05-10). Nenhum treino previu o teste (`previu_teste: false` nos três `treino.json`).
- **Passo 0:** salvo no commit `8787b52` (a opção `qualidade_one_hot`, o `refazer_qualidade.py` e 4 testes novos; o `pytest` do estudo tem 60 testes passando). Depois dele, nenhum código nem regra do estudo foi alterado. As análises das seções 3 e 4 usaram scripts descartáveis fora do estudo, que só leem os arquivos de `saida/`.

Este relatório traz os números e aplica a regra A. **A decisão final é do autor.**

## 1. O que foi rodado

**Comandos**, a partir de `estudos/lstm`, com o `.venv` do estudo e um treino por vez. O log está em `saida/etapa2j_sequencia.log`. Durante a sequência, o painel de `saida/painel/index.html` mostrou o andamento e a perda de validação por época contra a referência; a versão final fica em `saida/painel/etapa2j.html`.

```bash
B=saida/treino2j_qual
R=saida/treino2i_sub
# passo 1: a base com a qualidade em one-hot, com a conferência
python refazer_qualidade.py --banco --pasta $R --saida $B
# conferência: o ingênuo na base nova
python avaliar.py --pasta $B --periodo validacao --ingenuo --rotulo ing2j
# passo 2: os treinos
for s in 42 7 2026; do
  python treinar.py --pasta $B --nome qual_s$s --semente $s --ativacao gelu
  python avaliar.py --pasta $B --periodo validacao --previsoes $B/modelos/qual_s$s/previsoes_validacao.parquet \
      --rotulo qual_s$s
done
# passo 3: apoio
for s in 42 7 2026; do
  python comparar.py --a $B/avaliacao_validacao_qual_s${s}_itens.csv --b $R/avaliacao_validacao_sub_s${s}_itens.csv \
      --rotulos "qual" "referência" --saida $B/comparacao_qual_sub_s$s.json
  python transicao.py --base saida/treino2d_exp --detalhe $B/avaliacao_validacao_qual_s${s}_detalhe.parquet \
      --rotulo qual_s$s
done
```

**Tempo:** o passo 1 terminou às 23:18 UTC; os treinos e as avaliações levaram 1 h 15 min (23:19 a 00:34 UTC); o apoio, 31 s.

**Conferência da base (passo 1).** Antes de gravar, o `refazer_qualidade.py` recalcula a `f_qualidade` antiga (qualidade ÷ 5, sem qualidade = 0) com a qualidade de cada item lida do banco hoje e compara com a base.
- **Bateu em todas as 8.073.939 linhas,** sem nenhuma diferença. A qualidade dos itens no banco não mudou desde a preparação.
- A assinatura da base passou de `92da6bd526ab450b` para `5e278c3feeab270a`, porque as variáveis mudaram.

**A qualidade na base:**

| Qualidade | Itens | Linhas aptas |
|---|---|---|
| Pobre | 367 | 409.454 |
| Comum | 3.685 | 4.622.977 |
| Incomum | 1.073 | 1.137.949 |
| Rara | 1.197 | 1.133.726 |
| Épica | 237 | 278.917 |
| Lendária ou acima | 3 | 4.365 |
| Sem qualidade | 0 | 0 |

Nenhum item é artefato ou herança. Dois dos três problemas da forma antiga não aparecem nesta base: nenhum item fica sem qualidade, e a coluna "lendária ou acima" tem só 3 itens lendários.

**Conferências do `treino.json`** (todas bateram):
- Fora o nome, a pasta e o horário, nenhum parâmetro difere dos `sub_*` da mesma semente.
- Os três `qual_*` têm 24.339 parâmetros, contra 24.179 do `sub`. A diferença, 160, são as 5 entradas fixas a mais vezes os 32 neurônios da camada densa. A entrada `X_est` passou de 4 para 9 colunas.
- Em todos, `previu_teste` é `false`.
- **O ingênuo na base nova é igual ao da 2i** (24,17%, com as mesmas 1.420.443 amostras, os mesmos 9.561.970 alvos e os mesmos 6.484 itens). Os modelos são comparados exatamente nos mesmos alvos.
- O lançamento avaliado pelo `transicao.py` foi 2026-03-02 nas três análises.

**Treinos** (o `val_loss` é a MAE nas 200.000 amostras da parada antecipada e é comparável entre os seis):

| Treino | Épocas | Melhor época | Melhor `val_loss` | Tempo por época | Tempo total do `fit` |
|---|---|---|---|---|---|
| `qual_s42` | 52 | 42 | 0,5114 | 29,7 s | 25 min 47 s |
| `qual_s7` | 48 | 38 | 0,5106 | 28,9 s | 23 min 05 s |
| `qual_s2026` | 50 | 40 | 0,5103 | 29,1 s | 24 min 13 s |
| *Referência `sub` s42 · s7 · s2026 (etapa 2i)* | *63 · 52 · 88* | *53 · 42 · 78* | *0,5112 · 0,5094 · 0,5090* | *27,5 · 27,2 · 26,8 s* | *28 min 50 s · 23 min 33 s · 39 min 19 s* |

Os três `qual` pararam antes da referência da mesma semente. Isso não explica a diferença: com o mesmo número de épocas que o `qual` rodou, a melhor `val_loss` da referência já era 0,5116 (s42), 0,5094 (s7) e 0,5095 (s2026), igual ou melhor que a do `qual` (0,5114, 0,5106 e 0,5103).

## 2. Tabela principal

**Validação inteira** (6.484 itens e 1.420.443 amostras): média ± desvio-padrão amostral nas 3 sementes (42, 7 e 2026).
- O desvio dos percentuais está em pontos percentuais.
- A RN10 é a do `avaliar.py`: MdAPE ≤ 15%, menor que o do ingênuo e pelo menos 30 dias avaliados.

| Medida | Ingênuo | Referência (`sub`) | `qual` |
|---|---|---|---|
| **Mediana do MdAPE por item** | 24,17% | **20,31% ± 0,11** | **20,50% ± 0,10** |
| Mediana do MAPE por item | 47,19% | 37,46% ± 0,23 | 37,63% ± 0,22 |
| MAPE h1 | 26,64% | 24,74% ± 0,07 | 24,83% ± 0,13 |
| MAPE h7 | 88,98% | 62,68% ± 0,57 | 63,08% ± 0,62 |
| Mediana do erro relativo ao ingênuo | 1,0000 | 0,8335 ± 0,0029 | 0,8352 ± 0,0014 |
| Itens com erro relativo < 1 | 0 | 5.826 ± 27 | 5.807 ± 46 |
| **Itens liberados (RN10)** | 0 | **918 ± 12** | **854 ± 27** |
| Itens liberados sem o mínimo de 30 dias | 0 | 1.161 ± 23 | 1.088 ± 34 |

Mediana do MdAPE por item e itens liberados (RN10) em cada semente:

| Configuração | s42 | s7 | s2026 |
|---|---|---|---|
| Referência (`sub`) | 20,44% (911) | 20,24% (912) | 20,25% (932) |
| `qual` | 20,58% (826) | 20,54% (856) | 20,39% (880) |
| Diferença (`qual` − `sub`) | +0,14 ponto (−85) | +0,30 ponto (−56) | +0,14 ponto (−52) |

**O que a tabela mostra:**
- **As três sementes pioram** nas duas medidas da regra A. Não há uma semente que puxe a média.
- **MdAPE:** +0,19 ponto na média, com desvios parecidos (0,10 contra 0,11).
- **Liberados:** −64 na média (−7%), e o desvio entre sementes dobra (27 contra 12).
- **Demais medidas:** todas pioram um pouco. Os liberados sem o mínimo de 30 dias caem 74, mais que o maior desvio (34), como os liberados. As outras diferenças ficam dentro do maior desvio da coluna.

## 3. Item a item e por qualidade

### Item a item

Mesma semente nos dois modelos (6.484 itens).
- A diferença é `qual` − referência, em pontos percentuais; valor negativo significa que o `qual` erra menos.
- A RN10 está como "liberados nos dois / só no `qual` / só na referência".

| Semente | Mediana da diferença no MdAPE | p25 a p75 | `qual` melhor | Iguais | `qual` pior | RN10 |
|---|---|---|---|---|---|---|
| 42 | +0,06 | −0,45 a +0,68 | 2.975 | 45 | 3.464 | 784 / 42 / 127 |
| 7 | +0,06 | −0,48 a +0,66 | 2.938 | 54 | 3.492 | 797 / 59 / 115 |
| 2026 | +0,12 | −0,50 a +0,76 | 2.794 | 39 | 3.651 | 802 / 78 / 130 |

**Consistência entre as sementes:**
- 677 itens erram menos com o `qual` nas três sementes, e 1.140 erram mais nas três. Os outros 4.667 não têm o mesmo resultado nas três.
- Com a média das três sementes por item, a mediana da diferença é +0,09 ponto.
- Liberados nas três sementes: 783 na referência e 728 no `qual`, 693 deles nos dois.

**Leitura:** a piora é pequena por item, mas espalhada e consistente. Em cada semente há mais itens piores que melhores, e nas três sementes os itens sempre piores são 1,7 vez os sempre melhores. Na RN10, cada semente perde de 115 a 130 liberados da referência e ganha só de 42 a 78.

### Por qualidade

Mediana da diferença `qual` − referência no MdAPE por item, média ± desvio nas 3 sementes, e liberados na média das sementes.

| Qualidade | Itens | Diferença | Por semente (42 · 7 · 2026) | Liberados: referência → `qual` |
|---|---|---|---|---|
| Pobre | 365 | +0,02 ± 0,02 | +0,02 · +0,00 · +0,05 | 29,7 → 26,0 |
| Comum | 3.655 | +0,10 ± 0,04 | +0,10 · +0,06 · +0,15 | 487,3 → 441,3 |
| Incomum | 1.069 | +0,08 ± 0,09 | −0,02 · +0,14 · +0,11 | 179,0 → 171,0 |
| Rara | 1.157 | +0,09 ± 0,05 | +0,05 · +0,06 · +0,15 | 195,3 → 186,3 |
| Épica | 235 | +0,01 ± 0,10 | +0,08 · −0,10 · +0,05 | 25,0 → 27,3 |
| Lendária ou acima | 3 | +0,09 ± 0,34 | +0,35 · −0,30 · +0,22 | 2,0 → 2,0 |

**Leitura:**
- **A piora não fica numa qualidade só.** Comum, incomum e rara pioram de 0,08 a 0,10 ponto. Pobre e épica quase empatam.
- **Os itens comuns respondem por 46 dos 64 liberados perdidos** (72%), sendo 56% dos itens.
- **A épica é a única qualidade que ganha liberados** (+2,3), dentro do ruído de um grupo de 235 itens.
- **Os 3 itens lendários** não dão para concluir nada (desvio de 0,34 ponto).

### Troca de expansão (lançamento de Midnight, 2026-03-02)

Razão entre o MdAPE do modelo e o do ingênuo a 7 dias (`horizonte = h7`), média ± desvio nas 3 sementes, dos `transicao_*.csv`. Abaixo de 1, o modelo erra menos que o ingênuo.

| Configuração | Expansão que sai · troca | Todos · troca | Todos · resto | Expansão que entra · resto |
|---|---|---|---|---|
| Referência (`sub`) | 0,909 ± 0,019 | 0,854 ± 0,013 | 0,820 ± 0,002 | 0,771 ± 0,047 |
| `qual` | 0,904 ± 0,006 | 0,857 ± 0,003 | 0,824 ± 0,001 | 0,803 ± 0,020 |

**Leitura:** na troca de expansão, as duas configurações empatam, com diferenças dentro do desvio. Fora dela ("todos · resto"), o `qual` fica 0,004 pior, e o maior desvio é 0,002. Nos itens da expansão que entra, fica 0,032 pior, mas dentro do desvio da referência (0,047).

## 4. Regra A

O critério é o escolhido no plano, de não inferioridade:
- a mediana do MdAPE por item não pode piorar mais que o maior desvio entre sementes das duas configurações;
- **e** os itens liberados pela RN10 não podem cair mais que o maior desvio dessa medida.

| Candidato | Comparado com | MdAPE: referência → `qual` | Piora | Limite (maior desvio) | Liberados: referência → `qual` | Queda | Limite (maior desvio) | Adotado? |
|---|---|---|---|---|---|---|---|---|
| `qual` | `sub_s*`, validação | 20,31% → 20,50% | +0,192 ponto | 0,113 ponto (o da referência) | 918,3 → 854,0 | 64,3 | 27,1 (o do `qual`) | **Não** |

Passo a passo:

1. **Medida principal:** o MdAPE vai de 20,310% para 20,502%. Piora 0,192 ponto, e o limite era 0,113. **Não passa.**
2. **Proteção:** os liberados vão de 918,3 para 854,0. Caem 64,3, e o limite era 27,1. **Não passa.**
3. **Pela regra A, o `qual` não é adotado.** A configuração indicada pelo estudo continua a da 2i: a qualidade dividida por 5.

**O que a regra A não diz,** registrado para a decisão do autor:

- **A piora é pequena em valor absoluto,** mas passa do ruído entre sementes nas duas medidas, e as três sementes pioram. Não é um empate.
- **A etapa não mede por que o one-hot piora.** Ela só mostra que, nesta base e com esta rede, tratar as qualidades como categorias sem ordem foi um pouco pior que a escala de 0 a 1. Uma leitura possível, não testada: a escala carrega a ordem real das qualidades, e o one-hot obriga a rede a aprender cada qualidade separadamente.
- **Para responder à orientação no TC:**
  - a qualidade da API da Blizzard é uma escala ordinal (pobre < comum < incomum < rara < épica < lendária), e não uma categoria sem ordem como a classe;
  - nesta base, nenhum item fica sem qualidade e nenhum é artefato ou herança. Dois dos três problemas da forma antiga não ocorrem na prática;
  - a forma em one-hot foi testada e piorou o resultado, além do ruído entre sementes (este relatório).
- **Outra forma possível, não testada:** a qualidade como vetor aprendido (embedding), como a classe e a subclasse. Seria uma etapa nova, com uma mudança na rede e cerca de 1 h 20 min de treinos.

## 5. O que muda no sistema e no TC

**Nada mudou no sistema.** O plano previa o porte para o CU11 e uma versão nova pelo treinamento inicial (C1) só se a regra A aprovasse o `qual`.
- O porte (`backend/src/ml/configuracao.py`, `preparacao.py`, `dataset.py`, `rede.py` e 2 testes em `tests/modelo/test_cu11_regras_do_modelo.py`) chegou a ser escrito, mas não foi testado nem commitado.
- Com a reprovação, os arquivos do backend voltaram ao estado do commit. O porte ficou guardado em `estudos/lstm/saida/porte_qualidade_one_hot.patch`, fora do git, porque a pasta `saida/` é ignorada. Ele se reaplica com `git apply` sobre o commit atual.
- **A versão vigente da região US continua a v1,** e o C1 não foi executado.

**No TC:** se o autor seguir a regra A, a variável 16 continua "Qualidade dividida por 5". A seção do modelo pode citar a etapa 2j como a resposta à orientação (seção 4, "Para responder à orientação no TC").

**Se o autor preferir o one-hot mesmo assim,** pela orientação e não pelo resultado, o caminho é:
1. reaplicar o patch;
2. rodar os testes do host e do `modelo-testes`;
3. commitar `feat(CU11): qualidade do item em one-hot (variável 16, etapa 2j)`;
4. reconstruir o serviço `modelo`;
5. rodar o C1 da região US pela tela do Admin, com a conta Admin de teste (cerca de 40 min).

O custo esperado, pelo estudo, é de cerca de 0,2 ponto no MdAPE e 7% dos liberados.
