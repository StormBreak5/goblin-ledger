# Relatório da etapa 2i: subclasse dentro da classe

Etapa 2i do estudo, depois da 2h. Foi executada entre 29 e 30/10/2026, das 23:14 de 29/10 às 00:49 de 30/10 de Brasília (de 02:14 a 03:49 de 30/10 em UTC), conforme o plano aprovado no chat com a regra A. Corrige um defeito encontrado ao responder às perguntas do orientador sobre a variável 15:

| Candidato | O que é | Treino novo? |
|---|---|---|
| `sub` | a subclasse identificada pelo par (classe, subclasse), e não pelo código da subclasse sozinho, nas variáveis 6 e 15 | 3 treinos |

**O defeito.** Na API da Blizzard, o código da subclasse só é único dentro da classe. A subclasse 5, por exemplo, é "Comida e bebida" nos consumíveis e "Tecido" nos materiais de profissão. O estudo e o sistema usavam o código sozinho em dois lugares:
- **Variável 6 (índice da subclasse):** a média dos log-retornos "dos demais itens da subclasse" misturava itens de classes diferentes que têm o mesmo código.
- **Variável 15 (classe e subclasse):** o vetor aprendido da subclasse 5 era um só para a comida e para o tecido. Só o vetor da classe separava os dois.

**A correção.** A chave da subclasse passa a ser `classe × 1000 + subclasse`, nas duas variáveis.
- No estudo, ela fica atrás da opção `subclasse_por_classe`, desligada por padrão. Desligada, a base é a mesma de antes, o que é conferido pelo teste `test_subclasse_por_classe_desligada_mantem_a_base`.
- O vocabulário continua com o nome `subclasse_id`, então o `treinar.py` e a rede não mudam. Um par que não aparece no treino vira o índice 0 (desconhecida), como já acontecia com o código.

**Condições da etapa:**
- **Base:** uma cópia da `saida/treino01_agr`, em `saida/treino2i_sub`, com só a variável 6 e o índice da subclasse refeitos pelo `refazer_subclasse.py`. Todo o resto (linhas originais, janelas, cortes, demais variáveis e constantes) é o mesmo arquivo da base de 06/10. Não foi preparada base nova a partir do banco, porque o banco mudou desde 06/10 e isso misturaria duas mudanças.
- **Referência:** os treinos `gelu_s42`, `gelu_s7` e `gelu_s2026` da etapa 2g, que não foram retreinados nem reavaliados. Os `sub_s*` usam a mesma GELU, as mesmas sementes e os mesmos parâmetros; só a base muda.
- **Regra A (não inferioridade),** escolhida antes dos treinos: o `sub` é adotado se a mediana do MdAPE por item não piorar mais que o maior desvio entre sementes **e** os liberados pela RN10 não caírem mais que o maior desvio dessa medida. É diferente da regra da 2g e da 2h, que exigia melhorar mais que o desvio: aqui a mudança é uma correção, e basta que ela não piore.
- **Tudo foi avaliado só na validação** (2025-07-16 a 2026-05-10). Nenhum treino previu o teste (`previu_teste: false` nos três `treino.json` novos).
- **Passo 0:** salvo nos commits `2c78a75` (a correção) e `33f08e9` (a falha da seção 7). O `pytest` do estudo tem 56 testes passando: os 51 de antes e os 5 novos.
- Depois do passo 0, nenhum código nem regra do estudo foi alterado. As análises das seções 3 e 4 usaram scripts descartáveis fora do estudo, que só leem os arquivos de `saida/`.

Este relatório traz os números e aplica a regra A. **A decisão final é do autor.**

## 1. O que foi rodado

**Comandos**, a partir de `estudos/lstm`, com o `.venv` do estudo e um treino por vez. Os passos 2 e 4 foram gravados em `saida/etapa2i_sequencia.log`, e o passo 1, em `saida/etapa2i_passo1.log`.

```bash
B=saida/treino2i_sub
R=saida/treino01_agr
# passo 1: a base corrigida, com a conferência
python refazer_subclasse.py --banco --pasta $R --saida $B
# conferência: o ingênuo na base corrigida
python avaliar.py --pasta $B --periodo validacao --ingenuo --rotulo ing2i
# passo 2: os treinos
for s in 42 7 2026; do
  python treinar.py --pasta $B --nome sub_s$s --semente $s --ativacao gelu
  python avaliar.py --pasta $B --periodo validacao --previsoes $B/modelos/sub_s$s/previsoes_validacao.parquet \
      --rotulo sub_s$s
done
# passo 4: apoio
for s in 42 7 2026; do
  python comparar.py --a $B/avaliacao_validacao_sub_s${s}_itens.csv --b $R/avaliacao_validacao_gelu_s${s}_itens.csv \
      --rotulos "sub" "referência" --saida $B/comparacao_sub_gelu_s$s.json
  python transicao.py --base saida/treino2d_exp --detalhe $B/avaliacao_validacao_sub_s${s}_detalhe.parquet \
      --rotulo sub_s$s
done
```

**Tempo:**
- passo 1: concluído às 02:14 UTC de 30/10, logo antes dos treinos;
- passo 2: 1 h 34 min, de 02:15 a 03:49 UTC;
- passo 4: 28 s.

**Conferência da base (passo 1).** Antes de gravar, o `refazer_subclasse.py` recalcula a variável 6 com a chave **antiga**, a partir das linhas originais da base e da classe e subclasse de cada item lidas do banco hoje, e compara com a base de 06/10.
- **Bateu em todas as 8.073.939 linhas,** sem nenhuma diferença. A constante (0,5756), o vocabulário e os índices também bateram.
- Isso confirma duas coisas: o cálculo novo é o mesmo da preparação, e a classe e a subclasse dos itens no banco não mudaram desde 06/10.
- Só depois disso a chave nova é aplicada.

**O que a chave nova mudou na base:**

| Medida | Chave antiga (código) | Chave nova (par) |
|---|---|---|
| Subclasses no vocabulário | 18 códigos | 70 pares |
| Constante da variável 6 (percentil 99 do treino) | 0,5756 | 0,5627 (−2,24%) |
| Linhas sem nenhum outro item da subclasse no dia | 93.145 | 105.002 |
| Linhas aptas com a variável 6 igual a 0 | 57.626 | 67.199 |
| Linhas aptas da validação com a subclasse desconhecida (índice 0) | 0 | 886, de 21 itens |

- **Itens:** 6.562 na base. 5.951 (91%) têm um código de subclasse que existe em mais de uma classe; só 611 têm um código que aparece numa classe só. O código 0 aparece em 11 classes, e o 1, em 7.
- **Pares:** a base tem 78 pares (classe, subclasse). Desses, 8 só aparecem fora do período de treino e ficam fora do vocabulário. Outros 8 têm um item só, e neles a variável 6 passou a valer sempre 0, porque não há outro item no par.

**Conferências do `treino.json`** (todas bateram):
- Fora o nome, a pasta e o horário, nenhum parâmetro difere dos `gelu_*` da mesma semente.
- Os três `sub_*` têm 24.179 parâmetros, contra 23.763 da GELU. A diferença, 416, são as 52 subclasses a mais no vocabulário, cada uma com um vetor de 8 dimensões.
- Em todos, `previu_teste` é `false`.
- **O ingênuo na base corrigida é igual ao da referência** em todos os 6.484 itens (MdAPE, MAPE e MAE do ingênuo), com as mesmas 1.420.443 amostras e os mesmos 9.561.970 alvos. Os modelos são comparados exatamente nos mesmos alvos.
- O lançamento avaliado pelo `transicao.py` foi 2026-03-02 nas três análises.

**Treinos** (o `val_loss` é a MAE nas 200.000 amostras da parada antecipada e é comparável entre os seis):

| Treino | Épocas | Melhor época | Melhor `val_loss` | Tempo por época | Tempo total do `fit` |
|---|---|---|---|---|---|
| `sub_s42` | 63 | 53 | 0,5112 | 27,5 s | 28 min 50 s |
| `sub_s7` | 52 | 42 | 0,5094 | 27,2 s | 23 min 33 s |
| `sub_s2026` | 88 | 78 | 0,5090 | 26,8 s | 39 min 19 s |
| *Referência `gelu` s42 · s7 · s2026 (etapa 2g)* | *63 · 48 · 71* | *53 · 38 · 61* | *0,5110 · 0,5098 · 0,5094* | *27,7 · 27,5 · 27,1 s* | *29 min 04 s · 22 min 02 s · 32 min 06 s* |

Os três treinos somaram 1 h 32 min de `fit`. Nenhuma das 203 épocas passou de 31 s: o computador não dormiu.

## 2. Tabela principal

**Validação inteira** (6.484 itens e 1.420.443 amostras): média ± desvio-padrão amostral nas 3 sementes (42, 7 e 2026).
- O desvio dos percentuais está em pontos percentuais.
- A RN10 é a do `avaliar.py`: MdAPE ≤ 15%, menor que o do ingênuo e pelo menos 30 dias avaliados.
- A coluna da referência é a da `gelu` na seção 2 de `docs/relatorio-etapa2g.md`.

| Medida | Ingênuo | Referência (`gelu`) | `sub` |
|---|---|---|---|
| **Mediana do MdAPE por item** | 24,17% | **20,40% ± 0,10** | **20,31% ± 0,11** |
| Mediana do MAPE por item | 47,19% | 37,61% ± 0,18 | 37,46% ± 0,23 |
| MAPE h1 | 26,64% | 24,77% ± 0,07 | 24,74% ± 0,07 |
| MAPE h7 | 88,98% | 63,37% ± 0,15 | 62,68% ± 0,57 |
| Mediana do erro relativo ao ingênuo | 1,0000 | 0,8361 ± 0,0020 | 0,8335 ± 0,0029 |
| Itens com erro relativo < 1 | 0 | 5.831 ± 14 | 5.826 ± 27 |
| **Itens liberados (RN10)** | 0 | **916 ± 19** | **918 ± 12** |
| Itens liberados sem o mínimo de 30 dias | 0 | 1.155 ± 32 | 1.161 ± 23 |

Mediana do MdAPE por item e itens liberados (RN10) em cada semente:

| Configuração | s42 | s7 | s2026 |
|---|---|---|---|
| Referência (`gelu`) | 20,42% (917) | 20,49% (897) | 20,30% (935) |
| `sub` | 20,44% (911) | 20,24% (912) | 20,25% (932) |
| Diferença (`sub` − `gelu`) | +0,03 ponto (−6) | −0,25 ponto (+15) | −0,05 ponto (−3) |

**O que a tabela mostra:**
- **MdAPE:** o `sub` fica 0,09 ponto melhor na média, com o mesmo desvio entre sementes (0,11 contra 0,10). A melhora vem quase toda da semente 7; nas outras duas, a diferença é de poucos centésimos.
- **Liberados:** ficam iguais na média (918 contra 916), com desvio menor (12 contra 19).
- **Demais medidas:** todas melhoram um pouco ou empatam. O MAPE h7 é a única em que a diferença (−0,69 ponto) passa do maior desvio (0,57), mas o desvio do `sub` nessa medida é quase quatro vezes o da referência.
- **`val_loss`:** fica no mesmo intervalo da GELU (0,5090 a 0,5112, contra 0,5094 a 0,5110).
- **Coincidência na semente 42:** o `sub_s42` parou na mesma época que o `gelu_s42` (63, com a melhor na 53). O `val_loss` (0,5112 contra 0,5110) e as previsões são diferentes, então não é o mesmo treino.

## 3. Quanto a variável 6 mudou

Comparação do índice **bruto** da variável 6 (antes da constante) nas 7.587.388 linhas aptas, entre a chave antiga e a nova. O índice bruto tira o efeito da constante nova: se só a constante tivesse mudado, nenhuma linha contaria como mudada.

| Itens | Linhas aptas | Índice mudou | Correlação antigo × novo | Mediana da diferença absoluta | Mediana do índice antigo, em módulo |
|---|---|---|---|---|---|
| Com o código da subclasse em mais de uma classe (5.951) | 6.997.172 | 98,9% | **0,41** | 0,047 | 0,069 |
| Com o código numa classe só (611) | 590.216 | 0,0% (220 linhas) | 1,00 | 0 | 0,064 |
| Todos | 7.587.388 | 91,2% | 0,46 | 0,037 | 0,069 |

- **Para quase todos os itens, o índice antigo media outra coisa.** Com correlação de 0,41, ele refletia, em boa parte, o movimento de itens de outras classes. A diferença típica entre os dois (0,047) é dois terços do tamanho típico do próprio índice (0,069).
- **Os itens de código único funcionam como controle:** o índice deles não mudou. As 220 linhas que contam como mudadas estavam perto do limite e, com a constante menor, passaram a ser cortadas em ±1. Nos resultados, o que muda para esses itens é só o ruído do treino.

## 4. Item a item, recortes e troca de expansão

### Item a item

Mesma semente nos dois modelos (6.484 itens).
- A diferença é `sub` − referência, em pontos percentuais; valor negativo significa que o `sub` erra menos.
- A RN10 está como "liberados nos dois / só no `sub` / só na referência".

| Semente | Mediana da diferença no MdAPE | p25 a p75 | `sub` melhor | Iguais | `sub` pior | RN10 |
|---|---|---|---|---|---|---|
| 42 | +0,01 | −0,31 a +0,33 | 3.122 | 66 | 3.296 | 855 / 56 / 62 |
| 7 | −0,07 | −0,60 a +0,37 | 3.535 | 57 | 2.892 | 824 / 88 / 73 |
| 2026 | −0,00 | −0,48 a +0,50 | 3.249 | 55 | 3.180 | 862 / 70 / 73 |

**Consistência entre as sementes:**
- 1.002 itens erram menos com o `sub` nas três sementes, e 904 erram mais nas três. Os outros 4.578 não têm o mesmo resultado nas três.
- Com a média das três sementes por item, a mediana da diferença é −0,02 ponto.
- Liberados nas três sementes: 793 na referência e 783 no `sub`, 734 deles nos dois.

**Leitura:** item a item, a correção é quase um empate, com uma leve inclinação a favor do `sub` (1.002 contra 904 nas três sementes; a semente 7 com 3.535 melhores contra 2.892 piores). A faixa p25–p75 é estreita, de cerca de ±0,4 ponto. Pela seção 3, a variável 6 mudou bastante para quase todos os itens, mas a rede quase não mudou de comportamento: ela dependia pouco dessa variável, na forma antiga e na nova.

### Recortes

Mediana da diferença `sub` − referência no MdAPE por item, média ± desvio nas 3 sementes, e itens liberados na média das sementes.

| Recorte | Itens | O que mudou para eles | Diferença | Por semente (42 · 7 · 2026) | Liberados: referência → `sub` |
|---|---|---|---|---|---|
| Código compartilhado | 5.905 | a variável 6 (98,9% das linhas) e o vetor da subclasse | −0,02 ± 0,03 | +0,01 · −0,06 · −0,01 | 848,7 → 851,0 |
| Código único | 579 | nada (controle) | −0,04 ± 0,13 | +0,05 · −0,19 · +0,04 | 67,7 → 67,3 |
| Par de um item só | 8 | a variável 6 passou a valer sempre 0 | **+0,79 ± 0,30** | +0,81 · +0,48 · +1,08 | 1,0 → 1,0 |
| Par fora do vocabulário do treino | 21 | a subclasse virou desconhecida (0) | +0,34 | −0,00 · −0,01 · +1,03 | 0 → 0 |

Por classe, nas classes com pelo menos 50 itens na validação (nomes da API da Blizzard):

| Classe | Itens | Diferença | Por semente (42 · 7 · 2026) | Liberados: referência → `sub` |
|---|---|---|---|---|
| 0 Consumíveis | 2.403 | +0,00 ± 0,06 | +0,03 · −0,07 · +0,05 | 271,7 → 278,7 |
| 3 Gemas | 384 | −0,09 ± 0,06 | −0,08 · −0,04 · −0,15 | 39,0 → 41,7 |
| 7 Materiais de profissão | 2.342 | −0,04 ± 0,05 | +0,01 · −0,09 · −0,04 | 403,0 → 400,0 |
| 8 Aprimoramentos de item | 654 | −0,04 ± 0,09 | −0,02 · −0,14 · +0,04 | 100,3 → 100,3 |
| 12 Itens de missão | 89 | −0,01 ± 0,09 | +0,08 · −0,10 · −0,01 | 22,0 → 21,7 |
| 15 Diversos | 480 | −0,02 ± 0,04 | +0,01 · +0,00 · −0,06 | 51,7 → 50,7 |
| 16 Glifos | 111 | +0,07 ± 0,05 | +0,01 · +0,10 · +0,10 | 26,7 → 23,3 |

As outras nove classes somam 24 itens e nenhum liberado nos dois modelos. Com tão poucos itens, as diferenças delas (de −0,15 a +2,4 pontos) são só ruído.

**Leitura dos recortes:**
- **Nos itens em que a correção mexe (código compartilhado),** a diferença é −0,02 ± 0,03 ponto: um empate, com um desvio pequeno entre sementes.
- **No controle (código único),** a diferença varia mais entre sementes (±0,13) do que nos itens corrigidos. Isso mostra o tamanho do ruído de treino para um grupo de cerca de 580 itens e confirma que a correção não deixou nada pior.
- **O único custo claro são os 8 itens de pares de um item só:** perdem 0,79 ponto nas três sementes. Para eles, a variável 6 antiga trazia o movimento de outros itens com o mesmo código, e a nova não traz nada. São 0,1% dos itens, com um liberado nos dois modelos.
- **Gemas melhoram nas três sementes** (−0,09 ponto e +2,7 liberados), e **glifos pioram nas três** (+0,07 ponto e −3,3 liberados). As duas diferenças ficam perto do desvio entre sementes.

### Troca de expansão (lançamento de Midnight, 2026-03-02)

Razão entre o MdAPE do modelo e o do ingênuo a 7 dias (`horizonte = h7`), média ± desvio nas 3 sementes, dos `transicao_*.csv`. Abaixo de 1, o modelo erra menos que o ingênuo. A linha da referência é a da `gelu` na seção 4 de `docs/relatorio-etapa2g.md`.

| Configuração | Expansão que sai · troca | Todos · troca | Todos · resto | Expansão que entra · resto |
|---|---|---|---|---|
| Referência (`gelu`) | 0,923 ± 0,013 | 0,863 ± 0,001 | 0,822 ± 0,002 | 0,790 ± 0,051 |
| `sub` | **0,909 ± 0,019** | **0,854 ± 0,013** | **0,820 ± 0,002** | **0,771 ± 0,047** |

**Leitura da tabela:**
- As quatro razões melhoram um pouco: −0,014, −0,009, −0,002 e −0,019.
- Todas ficam dentro do maior desvio da coluna.
- Diferente da 2h, a melhora não troca o resto por ganho na troca: o `sub` também empata ou melhora fora dela ("todos · resto").

## 5. Regra A

O critério é o escolhido no plano, de não inferioridade:
- a mediana do MdAPE por item não pode piorar mais que o maior desvio entre sementes das duas configurações;
- **e** os itens liberados pela RN10 não podem cair mais que o maior desvio dessa medida.

| Candidato | Comparado com | MdAPE: referência → `sub` | Piora | Limite (maior desvio) | Liberados: referência → `sub` | Queda | Limite (maior desvio) | Adotado? |
|---|---|---|---|---|---|---|---|---|
| `sub` | `gelu_s*`, validação | 20,40% → 20,31% | −0,093 ponto (melhorou) | 0,113 ponto (o do `sub`) | 916 → 918 | −2 (subiu) | 19 (o da referência) | **Sim** |

Passo a passo:

1. **Medida principal:** o MdAPE vai de 20,404% para 20,310%. Em vez de piorar, o `sub` melhora 0,093 ponto, e o limite era piorar até 0,113. **Passa.**
2. **Proteção:** os liberados vão de 916,3 para 918,3. Em vez de cair, sobem 2,0, e o limite era cair até 19,0. **Passa.**
3. **Pela regra A, o `sub` é adotado.** A configuração indicada pelo estudo passa a ser:
   - eventos agregados (variáveis 1 a 18), sem máscara, perda MAE;
   - **a subclasse identificada pelo par (classe, subclasse) nas variáveis 6 e 15** (`--subclasse-por-classe` na preparação);
   - LSTM de 64 unidades, taxa fixa de 0,001;
   - Dense(32, GELU);
   - sem o calendário dos dias previstos;
   - os demais parâmetros padrão do `treinar.py`.

**O que a regra A não diz,** registrado para a decisão do autor:

- **O `sub` não é melhor de forma demonstrável.** Pela regra da 2g e da 2h, que exige melhorar mais que o desvio, ele não seria aprovado (0,093 é menor que 0,113). O motivo para adotar é outro: a variável passa a medir o que o TC diz que ela mede, sem perda de qualidade.
- **A favor:**
  - todas as medidas da seção 2 empatam ou melhoram, e o desvio dos liberados entre sementes cai de 19 para 12;
  - item a item, há mais itens melhores nas três sementes do que piores nas três (1.002 contra 904);
  - a troca de expansão melhora um pouco nas quatro razões, dentro do desvio.
- **Contra:**
  - os 8 itens de pares de um item só perdem 0,79 ponto (seção 4);
  - 21 itens da validação ficam com a subclasse desconhecida, porque o par deles não aparece no treino (antes, todo código aparecia). Doze deles são do par (8, 0), de aprimoramentos de item;
  - o desvio do MAPE h7 entre sementes vai de 0,15 para 0,57 ponto;
  - +416 parâmetros (24.179 contra 23.763). O `modelo.keras` vai de 340.778 para 345.770 bytes.
- **Para a discussão dos resultados no TC:** uma variável que mudou em 91% das linhas, com correlação de 0,41 entre a forma antiga e a nova, quase não mudou o resultado. Isso indica que a rede se apoia pouco na variável 6. A etapa não mede quanto a variável contribui sozinha; para isso, seria preciso treinar sem ela.

## 6. O que muda no sistema e no TC se o `sub` for adotado

**Nada foi alterado no sistema (`backend/src/ml/`)** nesta etapa. A mudança fica para depois da decisão do autor, junto com a GELU da 2g, se ela também for aprovada, para que haja um retreinamento só.

### No sistema

O sistema tem o mesmo defeito do estudo, nos mesmos lugares de `backend/src/ml/preparacao.py`:
- linhas 321 a 329: a variável 6 agrupa por `regiao`, `subclasse_id` e `data`;
- linha 393 (`ajustar`): o vocabulário da subclasse é montado com o código sozinho;
- linha 426 (`aplicar`): o índice da subclasse é mapeado pelo código sozinho.

A correção seria o porte do que o estudo já faz (`chave_da_subclasse`, `retorno_da_subclasse` e `CATEGORICAS` em `estudos/lstm/preparar_dados.py`):

1. **`configuracao.py`:** um campo `subclasse_por_classe` em `ConfigModelo`, ligado para as versões novas.
   - O `normalizacao.json` de uma versão já treinada não tem o campo, e ele precisa ser lido como desligado. Assim, a versão vigente continua recebendo a variável 6 e o índice da subclasse do jeito com que foi treinada.
   - O campo entra em `PARAMETROS_DAS_BRUTAS`. Com isso, o C2 recalcula as variáveis brutas com a configuração do vigente para avaliá-lo (`_base_do_vigente` já faz isso quando a configuração muda). O C3 também já prepara as brutas com a configuração da versão vigente (`prever_dia`, em `previsao.py`).
2. **`preparacao.py`:** a chave `classe × 1000 + subclasse`, quando o campo está ligado, no agrupamento da variável 6, no vocabulário e no índice.
3. **`dataset.py`:** `assinatura_normalizacao` e `assinatura_das_constantes` incluem o campo só quando ele está ligado, como no estudo, para que as versões já treinadas mantenham a assinatura.
4. **`rede.py`, linha 77:** `activation="gelu"`, se a GELU também for aprovada.
5. **Testes, um por fluxo afetado:** o campo desligado mantém a base; ligado, separa classes com o mesmo código; a versão vigente com a chave antiga é avaliada no C2 e prevista no C3 com a própria chave.
6. **Implantação:** reconstruir só o serviço `modelo` (não há migração) e retreinar pelo caminho do C2:

   ```bash
   docker-compose up --build -d modelo
   docker-compose exec modelo python -m src.modelo_worker --retreinar US --aguardar
   ```

   O C2 compara a versão nova com a vigente no período de teste novo (RN26) e só a substitui se ela for melhor. A decisão final no sistema continua sendo a dessa comparação.

### No TC (CU11, seção 5.12.2 e Observações para a implementação)

- **Variável 6:** "Média dos log-retornos dos demais itens **da mesma classe e subclasse** no dia, ponderada pela quantidade ofertada, dividida por uma constante global e limitada ao intervalo. A subclasse é identificada junto com a classe, porque o código da subclasse só é único dentro da classe."
- **Variável 15:** a faixa "—" e a descrição atual não dizem como a variável entra na rede, e foi isso que levou à pergunta do orientador. Sugestão:
  - Faixa: "índice (0 = desconhecida)".
  - Cálculo: "A classe e o par classe e subclasse são convertidos em índices do vocabulário do período de treinamento (0 para os que não aparecem nele). Cada índice é convertido em um vetor aprendido pelo modelo (*embedding*), de 4 dimensões para a classe e 8 para a subclasse. Por ser categórica, a variável não é normalizada numericamente."
- **Observações do CU11:** a da variável 6 passa a citar o par, e a da arquitetura passa a dizer GELU no lugar de ReLU, se ela for aprovada.

**Sugestões ligadas às outras perguntas do orientador**, independentes da regra A:
- **A variável de saída não aparece no quadro.** Ela só é descrita no parágrafo antes dele. Sugestão: uma linha ou um quadro à parte, "Variável de saída: log-retorno do preço em D+h em relação ao preço de D, para h de 1 a 7, padronizado pela média e pelo desvio de cada h no treinamento (RN24) e convertido para Cobre na exibição (RN01)."
- **A coluna "Tipo" chama de "futuro conhecido" variáveis que descrevem o próprio dia da janela.**
  - As variáveis 10 (dias desde o último patch), 13 (temporada ativa e dias desde o início) e 14 (evento sazonal ativo) dizem respeito ao dia t, ao passado ou ao presente.
  - Só as variáveis 11 (dias até o próximo patch) e 12 (expansão ou pré-patch nos próximos 14 dias) usam o futuro já conhecido.
  - Sugestão: "Evento (até o dia)" para 10, 13 e 14, e manter "Evento (futuro conhecido)" para 11 e 12.

## 7. Problemas encontrados

A execução dos passos 2 e 4 não teve erros (`saiu com 0` no log, nenhum `Traceback`), e nenhuma conferência pedida falhou. Pontos a registrar:

- **Falha no passo 1, corrigida antes dos treinos.** A primeira execução do `refazer_subclasse.py` parou com `KeyError: 'assinatura'`.
  - O `normalizacao.json` da `treino01_agr`, de 06/10, é de antes de esse campo ser gravado nas bases, e o script esperava encontrá-lo.
  - A falha foi na hora de gravar, depois da conferência, que já tinha passado. Nada foi gravado.
  - Correção no commit `33f08e9`: sem o campo, a assinatura é calculada a partir da própria normalização, com um teste que cobre esse caso. A segunda execução rodou do começo e passou na conferência com as mesmas zero diferenças.
- **Pares sem dados no treino.** Com a chave antiga, todo código de subclasse da validação aparecia no treino. Com o par, 8 dos 78 pares só aparecem depois do corte, e 21 itens da validação (886 linhas aptas) ficam com a subclasse desconhecida. Isso é o comportamento previsto para uma categoria nova (RN24/RN25), e não um defeito, mas não acontecia antes.
- **Pares de um item só.** Em 8 pares, a variável 6 vale sempre 0, porque não há outro item no par. O sistema calcula a variável 6 com todos os itens elegíveis do dia, e não só com os da base do estudo, então lá um par pode ter mais itens e esse caso pode ser menor.
- **Commits do passo 0 (`2c78a75` e `33f08e9`):**
  - Entraram só os arquivos do passo: `config.py`, `dataset.py`, `io_dados.py`, `preparar_dados.py`, `refazer_subclasse.py` (novo), `tests/test_estudo.py` e `README.md`.
  - Ficaram de fora, como nas etapas anteriores, as suas alterações locais em `ROTEIRO.md` e os pedidos não versionados.
- **Avisos no `pytest`:** os 56 testes passam com 34 avisos. Todos são o mesmo `DeprecationWarning` de dentro do Keras com o NumPy 2, como na 2h.
- **Voltar como estava:** a opção fica desligada por padrão no estudo, então nada precisa ser desfeito se o autor não adotar a correção. Os resultados desta etapa ficam em `saida/`, fora do Git.

Os arquivos ficam em `estudos/lstm/saida/`, fora do Git:
- **Em `treino2i_sub/`:**
  - a base corrigida: `linhas_normalizadas.parquet` e `normalizacao.json` novos, com a assinatura `92da6bd526ab450b`, a conferência e as contagens da seção 1 no bloco `subclasse_refeita`. Os demais arquivos são cópias dos da `treino01_agr`.
  - `subclasses.csv`: a classe e a subclasse de cada item, e se o código é compartilhado;
  - os modelos novos (`modelos/sub_s*`);
  - as avaliações (`avaliacao_validacao_sub_s*` e `avaliacao_validacao_ing2i_*`);
  - as comparações (`comparacao_sub_gelu_s*.json`);
  - as análises da troca (`transicao_sub_s*.csv`).
- **Logs:**
  - `etapa2i_passo1.log`;
  - `etapa2i_sequencia.log` (a conferência do ingênuo e os passos 2 e 4);
  - `etapa2i_resumo.txt`: as tabelas acima, em bruto, com os recortes e a seção 3.
