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
| `normalizacao.json` | Datas de corte, parâmetros, constantes, vocabulário das categorias, média e desvio do alvo e contagens. Tudo o que é preciso para desfazer a normalização. |
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
| 14 | `f_evento` | Evento sazonal ativo |
| 15 | `classe_idx`, `subclasse_idx` | Índice para embedding (0 = desconhecida) |
| 16 | `f_qualidade`, `f_nivel_item` | Qualidade ÷ 5; nível pelo mínimo e máximo do treino |
| 17 | `f_tem_piso` | Tem preço de venda ao vendedor |
| 18 | `f_commodity` | Commodity: `source_region` do item é o id de commodities da região (32512 nos EUA) |

Saída: 7 log-retornos ln(pₜ₊ₕ ÷ pₜ), com média e desvio próprios por horizonte, calculados no treino.

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
- **Valores a confirmar.** Estão em `config.py`: janela de 30 dias, horizonte de 7, padronização de 90 dias, MAPE de 15% da RN10, antecedência de 14 dias e os parâmetros da RN03 (confirmação de 7 dias; salto absurdo de 1.000× com 28 dias).
- **Alvos não observados no treino.** O `treinar.py` ainda não usa a máscara `obs_1..obs_7`: dias descartados ou preenchidos entram na perda com o último preço válido repetido.
- **Dados sintéticos.** Os resultados com eles só servem para testar o código. Não dizem nada sobre o mercado real.
