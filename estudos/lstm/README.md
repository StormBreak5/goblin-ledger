# Estudo preliminar: preparação dos dados da LSTM global (CU11)

Script inicial pedido pelo orientador. Ele faz três coisas:

1. aplica a normalização;
2. depois separa os dados em treino, validação e teste;
3. mantém a ligação entre cada linha original e a sua linha normalizada. Assim, ao fazer a estimativa (principalmente na validação), a previsão volta para o preço em Cobre e é comparada com o valor real.

O estudo fica fora de `backend/src` de propósito. Ele não é a implementação do CU11, só a preparação e a verificação dos dados para o treinamento.

## Como rodar

```bash
cd estudos/lstm
pip install -r requirements.txt

# 1. Preparar: lê o banco (variáveis DB_* do backend; porta padrão 5435) e grava em saida/estudo01
python preparar_dados.py --banco --env-arquivo ../../backend/.env --regiao US --saida saida/estudo01 --max-itens 500

# 2. Conferir o mecanismo de identificação: o próprio y verdadeiro tem que voltar ao preço original com erro zero
python avaliar.py --pasta saida/estudo01 --periodo validacao --verificar

# 3. Referências de comparação (R02 do TC): modelo ingênuo e regressão linear
python avaliar.py --pasta saida/estudo01 --periodo validacao --ingenuo
python regressao_linear.py --pasta saida/estudo01
python avaliar.py --pasta saida/estudo01 --periodo validacao --previsoes saida/estudo01/previsoes_validacao_linear.parquet

# 4. Treino da LSTM (precisa de tensorflow) e avaliação das estimativas na validação
python treinar.py --pasta saida/estudo01 --nome lstm01
python avaliar.py --pasta saida/estudo01 --periodo validacao --previsoes saida/estudo01/modelos/lstm01/previsoes_validacao.parquet --rotulo lstm01
# (exemplo_keras.py é a versão mínima, com amostra fixa; treinar.py usa todas as amostras e grava a versão do modelo)

# Ver uma amostra inteira (30 dias de entrada, original ao lado da normalizada, e os 7 alvos)
python dataset.py amostra --pasta saida/estudo01 --id-amostra 123
# Ver um item num intervalo de datas
python dataset.py inspecionar --pasta saida/estudo01 --item 210796 --de 2026-03-01 --ate 2026-03-10
```

Sem o banco, dá para testar com dados sintéticos:

```bash
python gerar_sinteticos.py --pasta dados_sinteticos
python preparar_dados.py --csv dados_sinteticos --saida saida/sintetico
pytest
```

Opções úteis de `preparar_dados.py`:

| Opção | Para que serve |
|---|---|
| `--itens` | Restringe a lista de itens. |
| `--max-itens` | Sorteia N séries. |
| `--corte-validacao` e `--corte-teste` | Fixam as datas de corte, por exemplo para repetir o mesmo corte num retreinamento. |
| `--ignorar-aptidao` | Usa todos os itens enquanto a `aptidao_treinamento` estiver vazia. |
| `--ilvl-minimo` | Filtro de nível de item da RN07. |
| `--rn03-confirmacao` | Preços seguidos fora da faixa da RN03 que confirmam um novo patamar (padrão 7; salto absurdo: 28). |
| `--rn03-ema-bruta` | RN03 com a EMA de todos os preços do banco (comportamento anterior), para comparação. |
| `--reservar-itens` | Etapa 2c: sorteia uma fração dos itens (ex.: 0.2, pela `--semente`, estratificado pela classe) e os deixa fora de tudo o que o modelo aprende. |
| `--normalizacao-de` | Etapa 2c: aplica a normalização de outra base (a de uma versão do modelo), sem recalcular nada. |
| `--excluir-itens-de` | Etapa 2c: não seleciona os itens que já estão em outra base. |
| `--variavel-expansao-item` | Etapa 2d: variável 19, item da expansão vigente no dia. |
| `--variavel-idade-item` | Etapa 2d: variável 20, idade do item (dias desde o primeiro registro, até 180). |

## O que acontece, na ordem

| Etapa | O que faz | Regra |
|---|---|---|
| Seleção | Itens aptos, com quantidade média acima de 50 nos últimos 7 dias. Lê só a série diária da Undermine, sem pontos anômalos. | RN15, RN02, RN16, RN12 |
| Calendário | Uma linha por item e por dia, do primeiro ao último registro. | |
| Higienização | Descarta o preço maior que 4× ou menor que 0,1× a EMA de 14 dias. A EMA usa só os dias anteriores **já aceitos**. 7 preços seguidos fora da faixa, do mesmo lado, confirmam um novo patamar (28, num salto de 1.000× ou mais; ver abaixo). | RN03 |
| Preenchimento | Até 3 dias sem registro recebem o último valor e são marcados como não observados. | RN24 |
| Variáveis | Calculadas **item a item**: todo shift, rolling e EMA é feito por série. | |
| Datas de corte | 70/20/10 do calendário, **as mesmas para todos os itens**. | RN25 |
| Normalização | As constantes saem **só do treino** e são aplicadas a todas as linhas. | RN24, RN25 |
| Separação | Cada linha recebe o seu período. As amostras vão para `janelas_treino`, `janelas_validacao` ou `janelas_teste`. | RN25 |

A separação física acontece depois da normalização, como pedido. As **datas** de corte são definidas antes, porque as constantes (percentil 99, mínimo e máximo do nível de item, média e desvio do alvo) só podem enxergar o treino.

A amostra pertence ao período dos seus 7 alvos. Se os alvos ficam dos dois lados de uma data de corte, a amostra é descartada. Assim nenhum alvo de treino cai na validação, e nenhum da validação cai no teste.

O teste `test_sem_vazamento_do_futuro` altera todos os preços da validação e do teste e confere duas coisas: nenhuma constante muda, e nenhuma linha do treino muda.

## Arquivos gerados

| Arquivo | Conteúdo |
|---|---|
| `linhas_originais.parquet` | Uma linha por item e dia, com `id_linha`. Guarda o preço e a quantidade como vieram do banco, se o dia foi descartado pela RN03, se foi observado ou preenchido, o preço usado (Cobre) e o período. |
| `linhas_normalizadas.parquet` | O mesmo `id_linha`, na mesma ordem. Traz as 16 variáveis de sequência, as 4 fixas e os 2 índices de categoria, além de `apta`, que diz se a linha pode entrar numa janela. |
| `janelas_<periodo>.parquet` | Uma amostra por linha. Traz `id_amostra`, `id_linha_origem` (o "hoje" da amostra), item, data, `preco_base` (Cobre), os alvos `y_1..y_7` já normalizados e `obs_1..obs_7`, que dizem se cada alvo foi observado. |
| `normalizacao.json` | Datas de corte, parâmetros, constantes, vocabulário das categorias, média e desvio do alvo e contagens. Tudo o que é preciso para desfazer a normalização. A `assinatura` identifica essa normalização; com a reserva da etapa 2c, `reserva` lista os itens reservados. |
| `itens.parquet` | Um registro por item: classe, subclasse, commodity, primeiro e último registro, se é apto pela RN15, se é líquido pela RN02 e se foi reservado. |
| `avaliacao_<periodo>_<rotulo>_*` | Gerado pelo `avaliar.py`. O detalhe (por amostra e por dia), o resumo por item com a situação pela RN10, o resumo por horizonte e um resumo geral. |

## Mecanismo de identificação

```
linhas_originais[id_linha]  <──── mesmo id_linha, mesma posição ────>  linhas_normalizadas[id_linha]

amostra (id_amostra)
  entrada = linhas id_linha_origem−29 ... id_linha_origem          → X_seq [30, 16], X_est [4], X_cat [2]
  alvo h  = linha  id_linha_origem + h   (h = 1..7, mesma série)    → y_h

estimativa: id_amostra + yhat_1..yhat_7 (escala normalizada, saída da Dense(7))
  r_h  = yhat_h · desvio_h + media_h                                 (normalizacao.json → "alvo")
  p̂_h  = preco_base · exp(r_h), arredondado                          (Cobre, RN01)
  real = linhas_originais[id_linha_origem + h].preco_cobre            (só dias observados)
```

Toda previsão deve ser gravada com o seu `id_amostra`, usando `avaliar.salvar_previsoes`. É ele que leva a estimativa de volta até a linha original.

Os dias preenchidos e os descartados pela RN03 não entram no cálculo do erro, porque não são preços reais.

## Variáveis

| Nº no TC | Coluna | Normalização |
|---|---|---|
| 1 | `f_log_return` | ln(pₜ ÷ pₜ₋₁) ÷ p99 do treino, limitado a [−1, 1] |
| 2 | `f_nivel_preco` | z-score de ln p nos últimos 90 dias do item, limitado a ±3 e dividido por 3 |
| 3 | `f_quantidade` | Igual à 2, sobre ln(1 + quantidade) |
| 4 | `f_preco_ema14` | ln(p ÷ EMA14 da RN03) ÷ p99 |
| 5 | `f_volatilidade_7d` | Desvio dos log-retornos em 7 dias (mínimo de 5) ÷ p99, limitado a [0, 1] |
| 6 | `f_retorno_subclasse` | Média dos log-retornos da subclasse no dia, ponderada pela quantidade e sem o próprio item, ÷ p99 |
| 7 | `f_preco_npc` | ln(p ÷ preço de venda ao vendedor) ÷ p99; 0 sem esse preço |
| 8 | `f_observado` | 1 = observado; 0 = preenchido |
| 9 | `f_dia_sin`, `f_dia_cos` | sen e cos de 2π·dia/7 |
| 10 | `f_dias_desde_patch` | min(dias, 60) ÷ 60. A mesma versão de patch com duas datas conta só na primeira. |
| 11 | `f_dias_ate_patch` | dias ÷ 14 quando o patch está a até 14 dias; senão 1 (o patch ainda não foi anunciado) |
| 12 | `f_expansao` | Expansão ou pré-patch nos próximos 14 dias. Pré-patch = primeiro patch de cada versão maior (10.0.0, 11.0.0, 12.0.0) ou nome com "pre-patch". |
| 13 | `f_temporada_ativa`, `f_dias_temporada` | Indicador; min(dias, 60) ÷ 60 |
| 14 | `f_evento` | Algum evento sazonal (festival) ativo hoje |
| 14 (detalhada) | `f_festival_<nome>`, `f_festival_<nome>_prox` | Para cada festival do banco (Winter Veil, Love is in the Air, Noblegarden etc.): ativo hoje (0/1) e fração dos próximos 7 dias em que estará ativo. O calendário dos festivais é conhecido antes (RN25). Festivais sem nenhum dia ativo no treino ficam de fora. **Desligada por padrão**; liga com `--eventos-detalhados`. |
| 14 (detalhada) | `f_feira_negrilua`, `f_feira_negrilua_prox` | O mesmo para a Feira de Negrilua (evento recorrente: uma semana por mês). |
| 15 | `classe_idx`, `subclasse_idx` | Índice para embedding (0 = desconhecida) |
| 16 | `f_qualidade`, `f_nivel_item` | Qualidade ÷ 5; nível pelo mínimo e máximo do treino |
| 16 (one-hot) | `f_qualidade_pobre` … `f_qualidade_lendaria` | Uma coluna de 0 ou 1 por qualidade, no lugar da `f_qualidade` (lendária reúne artefato e herança; sem qualidade = todas em 0). **Desligada por padrão**; liga com `--qualidade-one-hot` (etapa 2j). |
| 17 | `f_tem_piso` | Tem preço de venda ao vendedor |
| 18 | `f_commodity` | Commodity: `source_region` do item é o id de commodities da região (32512 nos EUA) |
| 19 (etapa 2d) | `f_item_expansao_vigente` | 1 quando o item é da expansão vigente no dia. A expansão do item é a do último lançamento até o primeiro registro dele, com 7 dias de folga (acesso antecipado). **Desligada por padrão**; liga com `--variavel-expansao-item`. |
| 20 (etapa 2d) | `f_idade_item` | Dias desde o primeiro registro do item, limitados a 180 e divididos por 180. **Desligada por padrão**; liga com `--variavel-idade-item`. |

Saída: 7 log-retornos ln(pₜ₊ₕ ÷ pₜ), com média e desvio próprios por horizonte, calculados no treino.

No treino (`treinar.py`), a opção `--mascara` faz o erro de cada amostra contar só os dias previstos com preço observado (`obs_1..obs_7`). **O padrão é sem máscara.**

## Configuração final (congelada depois da etapa 2e)

É o padrão dos scripts. Cada escolha foi feita na validação, com 3 sementes e uma regra de decisão definida antes do
experimento; o período de teste continua intocado e fica para o CU11 (RN25).

| Parte | Configuração | Etapa |
|---|---|---|
| Entrada | Variáveis 1 a 18, com a 14 agregada ("algum festival ativo"); janela de 30 dias | 2b, 2d |
| Rede | LSTM(64) → Dropout(0,2) → junta atributos fixos e embeddings (classe 4, subclasse 8) → Dense(32, relu) → Dense(7) | 2 |
| Treino | **Perda MAE**, sem máscara; Adam com taxa fixa de 0,001; lote de 512; 400.000 amostras por época; parada antecipada com paciência de 10 épocas | 2b, 2e |
| Liberação | RN10: MdAPE do item ≤ 15% e menor que o do ingênuo | 2b |

Resultado na validação (6.484 itens, média de 3 sementes):

| Medida | Configuração da 2b (Huber) | **Final (MAE)** | Ingênuo |
|---|---|---|---|
| Mediana do MdAPE por item | 22,67% | **20,62%** | 24,17% |
| Mediana do MAPE por item | 38,66% | **37,92%** | 47,19% |
| Itens em que o modelo erra menos que o ingênuo (MAE) | 5.345 | **5.849** | — |
| Itens liberados pela RN10 | 603 | **1.090** | — |
| MAPE médio por item | 59,68% | 61,44% | 76,31% |

A MAE leva o modelo a prever a mediana (Hyndman e Athanasopoulos, 2018, seção 3.4; Gneiting, 2011), a mesma coisa que
a RN10 mede. O preço disso é previsível: as medidas que dão peso aos erros grandes (MAPE médio, MAPE a 7 dias, RMSE)
pioram um pouco.

**Testado e reprovado:** máscara nos alvos (2b), eventos detalhados por festival (2b), item da expansão vigente e idade
do item (2d), redução da taxa de aprendizado e LSTM de 128 unidades (2e). O código continua no estudo, desligado.

## Configuração escolhida (etapa 2b)

Foram comparadas 4 configurações, com 3 sementes cada, na validação (`docs/relatorio-etapa2b.md`). A escolhida é **eventos agregados, sem máscara**, que é o padrão dos scripts:

| Configuração | Mediana do MAPE por item (média ± desvio, 3 sementes) |
|---|---|
| **Eventos agregados, sem máscara** | **38,66% ± 0,19** |
| Eventos agregados, com máscara | 39,27% ± 0,41 |
| Eventos detalhados, sem máscara | 39,83% ± 0,25 |
| Eventos detalhados, com máscara | 39,89% ± 0,32 |
| Regressão linear (referência) | 44,51% |
| Ingênuo (referência) | 47,19% |

**RN10 (decisão do autor):** a projeção do item é liberada se o **MdAPE** (mediana do erro percentual absoluto dos dias observados) for de no máximo 15% e menor que o do ingênuo. O preço da Undermine é o menor anúncio do dia, e quedas isoladas explodem a média (MAPE). Na validação, isso libera 592 de 6.484 itens (9,1%). No `avaliar.py`, `--metrica mape` e `--limiar` permitem comparar com outras regras.

Ficam de fora (limitações): a rotação mensal do Posto de Troca (cosmética), o reinício semanal (coberto pelo dia da semana) e os eventos de bônus que se alternam, como Caminhadas Temporais e Provação do Estilo, que não estão no `evento_jogo`.

## Ajuste da rede (etapa 2e)

Até a etapa 2d, só a entrada do modelo foi testada (máscara, eventos, variáveis 19 e 20). A rede continuava com os
valores iniciais: perda Huber, LSTM de 64 unidades e taxa de aprendizado fixa de 0,001. A etapa 2e testa três ajustes,
cada um sozinho contra a configuração da etapa 2b, com 3 sementes:

| Ajuste | Opção do `treinar.py` | Por quê |
|---|---|---|
| Perda pelo erro absoluto | `--perda mae` | A RN10 mede a mediana do erro absoluto (MdAPE). O erro absoluto leva o modelo a prever a mediana; a Huber trata os erros pequenos como quadráticos e é puxada pelos picos de preço. |
| Redução da taxa de aprendizado | `--reduzir-taxa` (`--fator-taxa 0.5`, `--paciencia-taxa 3`, `--taxa-minima 1e-5`) | Os treinos param entre as épocas 20 e 40 com a taxa fixa. Reduzir a taxa quando a validação estaciona costuma refinar os pesos. A taxa de cada época fica no `historico.csv` e a final, no `treino.json`. |
| LSTM de 128 unidades | `--unidades 128` | Mais capacidade para 6.500 itens com comportamentos diferentes. |

**Resultado (`docs/relatorio-etapa2e.md`):** só a perda MAE foi aprovada (mediana do MdAPE por item de 22,67% para
20,62%, com desvio de 0,09 a 0,15 ponto entre sementes; itens liberados pela RN10 de 603 para 1.090). A redução da taxa e
as 128 unidades pioraram a medida principal. Com um só aprovado, não houve combinação, e a configuração congelou.

A janela de 60 dias ficou de fora de propósito: ela subiria o histórico mínimo de um item novo de uns 60 para uns 90
dias, o contrário do que se quer com a previsão de itens novos (etapa 2c). A regra de decisão e os comandos estão em
`pedido-etapa2e.md`. Depois dela, a configuração congela.

## Melhorias baratas (etapa 2g)

Testa três melhorias contra a configuração final (`mae_s{42,7,2026}`), na validação, com a regra de decisão de
`pedido-etapa2g.md`. Duas não precisam de treino novo, porque usam as previsões já gravadas.

| Candidato | Como | Ideia |
|---|---|---|
| Média de sementes (`ens`) | `combinar.py media` | A previsão é a média dos log-retornos previstos por modelos iguais com sementes diferentes. |
| Encolhimento (`enc`) | `combinar.py encolher` | log-retorno final = αₕ × log-retorno previsto (α = 0 é o ingênuo). αₕ é escolhido na 1ª metade da validação e medido na 2ª. |
| Ativação da camada densa (`lrelu` e `gelu`) | `treinar.py --ativacao leaky_relu` (inclinação de 0,1) ou `--ativacao gelu` | Com a ReLU, uma amostra cujas 32 pré-ativações são negativas sai igual ao viés da saída. |

`ativacoes.py` conta, num período, as amostras sem nenhuma unidade com pré-ativação positiva e as unidades que nunca
ficam positivas.

```bash
python combinar.py media --nome ens3 --saida saida/treino01_agr/combinadas \
    --previsoes saida/treino01_agr/modelos/mae_s{42,7,2026}/previsoes_validacao.parquet
python combinar.py encolher --pasta saida/treino01_agr --nome enc_s42 --saida saida/treino01_agr/combinadas \
    --previsoes saida/treino01_agr/modelos/mae_s42/previsoes_validacao.parquet   # grava enc_s42, ref2_s42 e ing2
python avaliar.py --pasta saida/treino01_agr --periodo validacao \
    --previsoes saida/treino01_agr/combinadas/enc_s42.parquet --rotulo enc_s42
python treinar.py --pasta saida/treino01_agr --nome lrelu_s42 --semente 42 --ativacao leaky_relu
python ativacoes.py --modelo saida/treino01_agr/modelos/lrelu_s42 --pasta saida/treino01_agr --periodo validacao
```

O resultado está em `docs/relatorio-etapa2g.md`.

## Subclasse dentro da classe (etapa 2i)

**O problema:** o código da subclasse da API da Blizzard só é único dentro da classe. A subclasse 5 é "Comida e bebida" nos consumíveis (classe 0) e "Tecido" nos materiais de profissão (classe 7). Até a etapa 2h, a preparação usava o código sozinho:
- **Variável 6:** o índice da subclasse de um tecido incluía os itens de comida e bebida.
- **Variável 15:** os dois dividiam o mesmo vetor de subclasse.

**A opção:** `--subclasse-por-classe` na `preparar_dados.py` (`Config.subclasse_por_classe`, desligada por padrão).
- As duas variáveis passam a usar o par, com a chave classe × 1000 + subclasse.
- Um par que o treino não viu vira subclasse desconhecida (0), mesmo que a classe e o código sejam conhecidos.
- A opção fica gravada na configuração da base e entra na assinatura da normalização. As bases sem ela mantêm a assinatura de antes.
- Sem a opção, nada muda.

**A comparação:** `refazer_subclasse.py` faz uma cópia de uma base pronta com só as duas variáveis refeitas. A base não é preparada de novo a partir do banco, que mudou desde então.
- **Ficam idênticos:** as janelas, os alvos e as demais colunas.
- **Conferência:** antes de gravar, o script confere que, com a chave antiga, o cálculo reproduz a variável 6, a constante, o vocabulário e os índices da base. Isso também confirma que os atributos dos itens no banco não mudaram. Se não bater, ele para e não grava nada.
- **`subclasses.csv`:** traz, por item, o par e se o código da subclasse aparece em mais de uma classe.

```bash
python refazer_subclasse.py --banco --pasta saida/treino01_agr --saida saida/treino2i_sub
python treinar.py --pasta saida/treino2i_sub --nome sub_s42 --semente 42 --ativacao gelu
python avaliar.py --pasta saida/treino2i_sub --periodo validacao \
    --previsoes saida/treino2i_sub/modelos/sub_s42/previsoes_validacao.parquet --rotulo sub_s42
```

**Regra de decisão (escolhida pelo autor):** como é a correção de uma diferença em relação ao TC, a correção é adotada se não piorar. Ou seja:
- a mediana do MdAPE por item não pode piorar mais que o maior desvio entre sementes;
- **e** os itens liberados pela RN10 não podem cair mais que o maior desvio dessa medida.

A comparação é contra os `gelu_s*` da base `treino01_agr`.

## Qualidade em one-hot (etapa 2j)

**O problema (orientação de 30/10):** a qualidade é uma categoria, mas entrava como número (qualidade ÷ 5). Isso cria uma ordem e uma distância que não existem (épico "vale o dobro" de incomum), junta lendária, artefato e herança no mesmo 1,0 e confunde o item sem qualidade com o "pobre" (os dois viram 0).

**A opção:** `--qualidade-one-hot` na `preparar_dados.py` (`Config.qualidade_one_hot`, desligada por padrão).
- A `f_qualidade` dá lugar a seis colunas de 0 ou 1 (`COLUNAS_DA_QUALIDADE`): pobre, comum, incomum, rara, épica e lendária ou acima.
- O item sem qualidade fica com as seis em 0. As variáveis fixas passam de 4 para 9.
- As variáveis da base mudam, e com elas a assinatura. Sem a opção, nada muda.

**A comparação:** `refazer_qualidade.py` faz uma cópia de uma base pronta com só a qualidade refeita, como o `refazer_subclasse.py` da 2i. Antes de gravar, confere que a `f_qualidade` recalculada com a qualidade de cada item (do banco) é a gravada em todas as linhas; se não for, para e não grava nada. O `qualidades.csv` traz a qualidade de cada item.

```bash
python refazer_qualidade.py --banco --pasta saida/treino2i_sub --saida saida/treino2j_qual
python treinar.py --pasta saida/treino2j_qual --nome qual_s42 --semente 42 --ativacao gelu
```

**Regra de decisão:** a mesma da 2i (não inferioridade), contra os `sub_s*` da base `treino2i_sub`.

**Resultado (`docs/relatorio-etapa2j.md`): não adotado.** Na validação, a mediana do MdAPE por item foi de 20,31% para 20,50%, uma piora de 0,19 ponto contra o limite de 0,11. Os liberados pela RN10 foram de 918 para 854, uma queda de 64 contra o limite de 27. As três sementes pioraram nas duas medidas. A opção continua desligada por padrão.

## Calendário dos dias previstos (etapa 2h)

**O que muda:** as variáveis 9 a 14 só entram com os 30 dias passados. Na etapa 2h, a rede ganha a entrada `X_fut` [7, 6], com o calendário de D+1 a D+7 como conhecido em D (RN25). Ela é achatada e juntada antes da camada densa de 32.

| Coluna | Valor em D+h |
|---|---|
| `fut_dia_sin`, `fut_dia_cos` | dia da semana de D+h |
| `fut_patch` | algum patch entre D+1 e D+h |
| `fut_expansao` | algum marco de expansão (pré-patch ou lançamento) entre D+1 e D+h |
| `fut_temporada` | alguma temporada começa entre D+1 e D+h |
| `fut_evento` | algum evento sazonal ativo em D+h |

**Como o calendário é montado:**
- `calendario_futuro.py` lê só `evento_jogo`, do banco ou de um `eventos.csv`, e não mexe na base.
- Antes de gravar, ele confere se as variáveis 9 a 14 recalculadas com esses eventos batem com as da base. Se não baterem, ele para.
- O calendário vai para uma pasta à parte e é ligado a cada amostra pela região da série e pelo dia de origem.
- **Rede inalterada sem a opção:** sem `--calendario-futuro`, a rede não muda.

`eventos_no_horizonte.py` separa o erro das amostras com e sem evento entre D+1 e D+7: patch, marco de expansão, início de temporada, ou início ou fim de evento sazonal.

```bash
python calendario_futuro.py --banco --pasta saida/treino01_agr --saida saida/calendario2h
python treinar.py --pasta saida/treino01_agr --nome cal_s42 --semente 42 --ativacao gelu \
    --calendario-futuro saida/calendario2h/calendario_futuro.parquet
python avaliar.py --pasta saida/treino01_agr --periodo validacao \
    --previsoes saida/treino01_agr/modelos/cal_s42/previsoes_validacao.parquet --rotulo cal_s42
python eventos_no_horizonte.py --pasta saida/treino01_agr --calendario saida/calendario2h/calendario_futuro.parquet \
    --detalhe saida/treino01_agr/avaliacao_validacao_cal_s42_detalhe.parquet --rotulo cal_s42
```

A regra de decisão e os comandos estão em `pedido-etapa2h.md`.

## Generalização para itens fora do treino (etapa 2c)

**Pergunta.** O modelo não recebe nenhum identificador do item: só a janela de 30 dias, já em escala relativa ao
próprio item, e os atributos (classe, subclasse, qualidade, nível). Então ele deveria prever bem um item que **nunca viu
no treino**, desde que o item tenha histórico. A etapa 2c mede isso, em duas partes.

**Parte A: itens não vistos.** Na mesma base, 20% dos itens são sorteados e reservados (estratificado pela classe). Os
reservados ficam fora das constantes, do vocabulário, da escala do alvo, do treino e da parada antecipada. Dois modelos
são treinados com a mesma configuração:

| Braço | Treino | Para quê |
|---|---|---|
| `c_sem` | sem os reservados (padrão do `treinar.py` numa base com reserva) | erro nos itens que o modelo nunca viu |
| `c_todos` | com todos (`--incluir-reservados`) | controle: os mesmos itens, agora vistos |

Os mesmos itens e os mesmos dias são avaliados pelos dois. O `comparar.py` faz a comparação **item a item** nos
reservados: a diferença entre `c_sem` e `c_todos` é o custo de o item ter ficado fora do treino. A diferença entre duas
sementes do controle mostra o tamanho do ruído.

**Parte B: itens fora da seleção.** Uma segunda base, com uma amostra dos itens que a seleção do treino deixa de fora
(RN15, RN02: equipamentos de reino, commodities pouco negociadas, itens com histórico curto), normalizada **como a
versão do modelo** (`--normalizacao-de`). O `prever.py` passa essas janelas pelo modelo já treinado, como o sistema
fará com um item qualquer. O `avaliar.py` separa o resultado por grupo (commodity, apto pela RN15, líquido pela RN02) e
pela idade do item no dia da previsão (`por_idade`), que serve para definir o histórico mínimo. Uma diferença em
relação ao sistema: na base `fora2c`, a variação do índice da subclasse (variável 6) é calculada só com os itens dessa
base, e não com o mercado inteiro.

Os comandos estão em `pedido-etapa2c.md`. Tudo na validação: o teste continua reservado ao CU11 (RN25).

**Resultado (`docs/relatorio-etapa2c.md`, perda Huber).** Nos itens reservados, o erro do modelo que nunca os viu ficou
do tamanho da diferença entre duas sementes. Os 755 itens sem nenhuma amostra de treino (quase todos da expansão nova)
foram previstos melhor que pelo ingênuo em 62% a 69% dos casos. Fora da seleção, o modelo perdeu para o ingênuo, mas
porque esses itens são ilíquidos: com a mesma liquidez, itens do treino e de fora dele se comportam igual. A fronteira de
uso do modelo é a liquidez (RN02), não o item ter entrado no treino.

**Análises de apoio** (`generalizacao.py`, a partir das avaliações gravadas):

- `liquidez`: erro por faixa de quantidade média ofertada, em uma ou mais bases;
- `novos`: itens sem nenhuma amostra de treino contra os demais.

**Resultado com a configuração final (`docs/relatorio-etapa2f.md`, perda MAE).** A 2f repetiu a 2c com a perda MAE. Os
números do TC vêm daqui.

- **Itens não vistos:** o erro de quem nunca foi visto ficou igual ao de quem foi. A diferença mediana no MdAPE foi de
  +0,00 e −0,02 ponto, contra 0,03 ponto de ruído entre sementes. Cerca de 71% dos reservados ficaram a até 1 ponto
  (na 2c, 56% a 61%).
- **Itens novos:** os 755 itens sem nenhuma amostra de treino superaram o ingênuo em 76% a 81% dos casos (na 2c, 62% a
  69%), com erro relativo mediano de 0,82 a 0,85.
- **Liquidez:** o modelo empata com o ingênuo na faixa de 5 a 20 unidades ofertadas em média e o supera a partir de
  20, nas duas bases. O limiar de 50 da RN02 é conservador.
- **Fora da seleção:** a mediana do erro relativo caiu de 1,05–1,08 para 1,00–1,01; o modelo empata com o ingênuo.
- **Mínimo de 30 dias na RN10:** retirou 223 das 1.018 liberações (`m_todos_s42`), 222 delas de itens novos. Esses
  itens têm só 8 dias avaliados na validação (mediana), porque o corte da validação cai poucas semanas depois da
  expansão Midnight. No teste do sistema (de maio a outubro de 2026), os mesmos itens têm meses de histórico.

**RN10 com mínimo de dias.** O `avaliar.py` só libera um item com pelo menos `minimo_dias_rn10` (30) dias de previsões
avaliadas; abaixo disso, a situação é "Bloqueada" com o motivo "avaliação insuficiente" (`--minimo-dias 0` desliga). Na
etapa 2d, itens novos eram liberados com uns 8 dias de avaliação.

## Ciclo de vida do item (etapa 2d)

**Problema.** As variáveis 10 a 13 dizem ao modelo **quando** vem um patch ou uma expansão, mas nenhuma diz **a que
expansão o item pertence**. Uma erva de Dragonflight e uma de The War Within chegam iguais ao modelo. Na troca para
Midnight (validação), o modelo perdeu a vantagem sobre o ingênuo justamente nos itens da expansão que estava saindo
(razão de 0,98 contra 0,86 a 0,94 nos demais) e previu, a 7 dias, preços 8% acima do real: ele não antecipa a
obsolescência que a RN17 quer separar das flutuações normais.

**Variáveis candidatas** (calculadas por item e por dia, só com o que se sabe no dia, RN25):

- **19, item da expansão vigente:** a expansão do item é a do último lançamento até o primeiro registro dele (7 dias de
  folga para o acesso antecipado; os itens de Midnight apareceram em 27/02/2026). A variável vale 1 enquanto essa
  expansão é a vigente. Junto com a variável 12 (expansão nos próximos 14 dias), o modelo pode aprender "item da
  expansão vigente + expansão nova chegando = queda".
- **20, idade do item:** dias desde o primeiro registro, até 180. Os itens novos costumam cair nas semanas seguintes ao
  lançamento, e o modelo subestimava essa queda.

**Limitações.** Os itens que já existiam quando os dados começam (09/2022) têm a expansão desconhecida (variável 19 = 0)
e a idade máxima (variável 20 = 1). Um item antigo que só aparece no leilão anos depois seria contado como da expansão
daquele momento; nas commodities, que são negociadas o tempo todo, isso é raro.

O `transicao.py` mede o erro por grupo (expansão que sai, que entra, anteriores) na janela da troca e fora dela. Os
comandos e a regra de decisão estão em `pedido-etapa2d.md`.

## RN03: EMA só com os preços aceitos

A RN03 existe para que preços absurdos não "inflacionem médias". Com a EMA calculada sobre todos os preços do banco,
um único anúncio-placeholder de 99.999 ouro inflava a própria EMA, e os preços reais dos dias seguintes passavam a ser
descartados por semanas. No item 238485, foram 106 de 223 dias. Por isso (`rn03_por_serie`):

1. a EMA de 14 dias usa só os preços anteriores **já aceitos**;
2. 7 preços seguidos (`rn03_confirmacao`) fora da faixa, do mesmo lado, são uma mudança real de patamar, e a série não
   trava. O novo patamar é a mediana da sequência: os preços próximos dela são aceitos e a EMA recomeça neles. Um pico
   no meio da mudança continua descartado;
3. um salto de 1.000× ou mais (`rn03_salto_absurdo`) sobre um patamar já confirmado só vira patamar depois de 28 preços
   seguidos (`rn03_confirmacao_absurdo`). É o caso do anúncio de 1 milhão de ouro que fica sozinho por duas semanas;
4. o primeiro preço da série é aceito (não há com o que comparar). Se outro patamar for confirmado antes de o primeiro ter
   7 preços aceitos, o primeiro é descartado (o placeholder do item novo).

A EMA usa só os dias anteriores. Os dias posteriores servem apenas para confirmar um patamar. No sistema, durante uma
mudança de patamar ainda não confirmada, o preço fica preenchido por até 3 dias, e depois o item fica sem amostra até
a confirmação.

**Comparação.** Mesmas séries e mesmos cortes, só validação, regressão linear. Os erros foram medidos contra o preço
bruto, nos dias "reais" por uma referência neutra (preço entre 0,1× e 4× a mediana centrada de 15 dias), e nas amostras
que existem em todas as variantes.

| RN03 (500 séries do `real01`) | Dias descartados | Mediana do MAPE por item | Erros > 100% | Itens que superam o ingênuo | h7 |
|---|---|---|---|---|---|
| EMA de todos os preços (anterior) | 7,24% | 47,43% | 8,71% | 269 | 65,5% |
| Aceitos, confirmação 5 | 4,40% | 45,02% | 7,74% | 274 | 62,5% |
| **Aceitos, confirmação 7** | 5,51% | 44,07% | 7,31% | 296 | **61,0%** |
| Aceitos, confirmação 10 | 6,66% | 43,39% | 7,20% | 304 | 61,1% |

Nas 500 séries do `real02`, a regra nova também ganha em todas as medidas:

- MAPE médio por item: de 59,5% para 53,5%;
- mediana do MAPE por item: de 48,95% para 45,53%;
- itens que superam o ingênuo: de 279 para 317.

Com a confirmação de 10 dias há um pequeno ganho nas medianas, mas a média por item piora, porque picos reais de 7 a 9
dias passam a ser descartados, e o treino perde amostras. Por isso ficou a de 7 dias.

## Diferenças em relação ao script do estudo

| Ponto | Script do estudo | Aqui | Por quê |
|---|---|---|---|
| Alvo | Cotação absoluta (log1p + RobustScaler), `Dense(1)` | 7 log-retornos, `Dense(7)`, convertidos de volta para a cotação | As entradas não carregam a escala do preço. Num modelo único, a cotação absoluta não é aprendível. |
| Divisão | Por índice de linha, 70/20/10 | Por data de calendário, 70/20/10, igual para todos os itens | Evita que o treino de um item se sobreponha ao teste de outro. Referência: Hyndman e Athanasopoulos (2018, seção 3.4). |
| Cálculos por item | Sem `groupby` na função consolidada | Todo shift, rolling e EMA é feito por série | Sem isso, o primeiro dia de um item usa o último preço do item anterior. |
| Dias até o patch | Data real do patch, limite 60 | Conhecido só 14 dias antes, limite 14 | A tabela `evento_jogo` não guarda a data do anúncio, então usar a data real seria olhar o futuro. |
| Variáveis 8 e 13 | Não havia | `f_observado`, `f_temporada_ativa` | Marcam os dias preenchidos e tiram a ambiguidade de "0 dias de temporada". |
| Volatilidade | `min_periods=2` | `min_periods=5` | Com 2 retornos, o desvio é muito instável. |
| EMA da RN03 | Inclui o próprio dia e os preços descartados | Só os dias anteriores já aceitos, com confirmação de patamar | A RN03 fala em registros anteriores ao dia avaliado e quer evitar que preços absurdos inflacionem a média. |
| Atributos fixos | Repetidos nos 30 passos | Uma vez por amostra, depois da LSTM | Mesma informação, com menos memória. |

## Limitações conhecidas

- **Atributos fixos do item.** O backend grava classe, subclasse, qualidade, nível e preço de venda ao vendedor em `items.metadata_info` (`populate_item_details`; 99,4% dos itens em 2026-10-06). Os itens que a API da Blizzard não tem ficam com `atributos_indisponiveis` e as variáveis 6, 7, 15, 16 e 17 como "desconhecidas". O log mostra a cobertura de cada atributo e quantos itens são commodities.
- **Memória.** A preparação usa cerca de 0,8 KB por linha (item × dia). Com 10 milhões de linhas, isso dá uns 8 GB. Para os primeiros testes, use `--max-itens`.
- **Valores a confirmar.** Estão em `config.py`: janela de 30 dias, horizonte de 7, padronização de 90 dias, antecedência de 14 dias e os parâmetros da RN03 (confirmação de 7 dias; salto absurdo de 1.000× com 28 dias).
- **Alvos não observados no treino.** Por padrão, dias descartados ou preenchidos entram na perda com o último preço válido repetido. A máscara (`--mascara`) foi testada e piorou levemente o resultado (etapa 2b).
- **Dados sintéticos.** Os resultados com eles só servem para testar o código. Não dizem nada sobre o mercado real.
