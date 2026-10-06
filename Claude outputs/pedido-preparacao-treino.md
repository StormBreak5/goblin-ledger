# Pedido ao Claude Code: preparação para o treinamento (antes do CU11)

## Contexto

- O CU11 (Treinar Modelo) **ainda não está em `docs/`**, então **não implemente o CU11**. Esta tarefa prepara os dados e o ambiente que ele vai usar.
- As decisões do modelo estão em dois lugares:
  - `docs/Alterações do TC - modelo global (para colar) v2.docx`, que ainda vai entrar no TC;
  - no estudo em `estudos/lstm/`: leia o `README.md` de lá antes de começar.
- Não há regra de negócio nova nem tela nova.
- Siga o `CLAUDE.md`:
  - comece em **modo de planejamento**, proponha os arquivos e os testes, e espere a minha aprovação;
  - não leia nem altere arquivos `.env`;
  - não altere `docs/`.

## Parte 1: gravar os atributos fixos dos itens

**Problema.** `src/scraper/populate_item_details.py` já consulta `/data/wow/item/{id}` na API da Blizzard, mas só grava o nome e o ícone. O modelo precisa de classe, subclasse, qualidade, nível e preço de venda ao vendedor. Eles alimentam as variáveis 6, 7 e 15 a 17 do quadro de variáveis e o filtro da RN07.

1. **Gravar os atributos.** A partir da resposta que a rotina já obtém, grave em `items.metadata_info` as chaves abaixo. Use exatamente estes nomes, que são os que `estudos/lstm/io_dados.py` lê:

   | Chave | Valor |
   |---|---|
   | `item_class_id` | `item_class.id` |
   | `item_subclass_id` | `item_subclass.id` |
   | `quality` | `quality.type` (por exemplo, `"EPIC"`) |
   | `level` | `level` |
   | `sell_price` | `sell_price`, em Cobre (RN01) |
   | `atributos_atualizados_em` | data e hora UTC da gravação |

2. **Selecionar os itens.** Além dos itens com nome provisório ou sem ícone, a rotina deve pegar também os que ainda não têm `item_class_id`.
   - Se a API não tiver o item (404), marque `"atributos_indisponiveis": true`, registre em log e siga.
   - Itens marcados assim não devem ser consultados de novo a cada execução.
3. **Mesclar, nunca substituir, o `metadata_info`.** O backfill do CU10 guarda `last_etag` e `source_region` nele.
4. **Corrigir o bug do `sync_items_from_blizzard`.** O upsert diário em `src/scraper/sync_items.py` faz `metadata_info = excluded.metadata_info`. Isso troca o JSON inteiro por `{"source": "ah_dump"}` todos os dias e apaga, além dos atributos, o `last_etag` e o `source_region` do CU10.
   - Corrija para mesclar, por exemplo `items.metadata_info || excluded.metadata_info` no PostgreSQL.
   - Leia `src/services/importacao_historico.py` e me diga qual era o efeito disso na importação incremental.
5. **Respeitar o limite da API**, mantendo a concorrência atual. Crie um comando, ou reaproveite o job, para preencher uma vez todos os itens existentes, com o progresso no log.
6. **Não criar migração.** `metadata_info` já é JSONB, e o próprio modelo usa `item_class` como exemplo. Se você achar que colunas próprias são melhores, pergunte antes.

**Testes** (unitários, com a API simulada; ajuste os nomes ao padrão do projeto se preferir):

- `test_atributos_populate_grava_atributos_do_item`
- `test_atributos_populate_mescla_metadata_sem_apagar_etag`
- `test_atributos_populate_seleciona_itens_sem_atributos`
- `test_atributos_item_inexistente_na_api_nao_interrompe`
- `test_atributos_sync_items_preserva_metadata_existente`

Depois de implementar, rode o preenchimento no banco local e me informe a cobertura de cada chave: a porcentagem de itens que a têm.

## Parte 2: verificar os dados que o treino usa

Esta parte é somente leitura, com consultas SQL. Monte um relatório com:

1. **`historical_item_prices`**, filtrando `origem = 'UNDERMINE'`, `granularidade = 'DIARIA'` e `NOT anomalia`:
   - data mínima e data máxima;
   - número de itens e de linhas;
   - itens por região (ligando `region` a `reino.regiao`; os ids de commodities estão em `ingestao_config`);
   - quantos itens têm pelo menos 120 dias de histórico.
2. **`aptidao_treinamento`:** total, aptos, não aptos e data da última validação. Se estiver vazia, rode a validação de cobertura do CU10-C3 pelo caminho já implementado e informe o resultado.
3. **`evento_jogo`:**
   - contagem por tipo e por ano desde set/2022;
   - lista de `PATCH` e `EXPANSAO` com as datas;
   - temporadas com início e fim;
   - lacunas aparentes, como um ano sem patch.

   **Não cadastre eventos.** Se faltar algo, liste o que falta e diga se a extração do CU10-C2 cobriria.
4. **`reino`:** valores de `historical_item_prices.region` que não aparecem na tabela `reino` nem nos ids de commodities.

## Parte 3: primeira execução do estudo com dados reais (`estudos/lstm/`)

1. **Ambiente.**
   - Crie um ambiente virtual em `estudos/lstm/.venv`, com Python 3.12 se estiver instalado. O backend usa 3.14, e o TensorFlow pode ainda não suportar essa versão.
   - Acrescente `.venv/` ao `.gitignore` do estudo.
   - Rode `pip install -r requirements.txt` e depois `pytest`. Os 11 testes devem passar.
2. **Preparação**, com os dados até hoje:

   ```bash
   DB_HOST=localhost DB_PORT=5435 python preparar_dados.py --banco --env-arquivo ../../backend/.env \
       --regiao US --saida saida/real01 --max-itens 500
   ```

   As variáveis da linha de comando têm prioridade sobre o `.env`, e o script não mostra o conteúdo dele. Se `aptidao_treinamento` estiver vazia, use `--ignorar-aptidao` e avise.

   Depois, informe quantas linhas a base completa teria. O script usa cerca de 0,8 KB por linha, então só rode sem `--max-itens` se couber na memória.
3. **Verificações e referências de comparação, somente no período de validação:**

   ```bash
   python avaliar.py --pasta saida/real01 --periodo validacao --verificar     # tem que dar OK
   python avaliar.py --pasta saida/real01 --periodo validacao --ingenuo
   python regressao_linear.py --pasta saida/real01
   python avaliar.py --pasta saida/real01 --periodo validacao --previsoes saida/real01/previsoes_validacao_linear.parquet
   ```

4. **Não avalie nada no período de teste.** Ele está reservado para a avaliação final (RN25).
5. **Análise extra:** quantos descartes da RN03 caem a até 7 dias de um `PATCH` ou `EXPANSAO`, comparado com os demais dias. Use `linhas_originais.parquet` e `evento_jogo`.
6. **Não versione `saida/`**, que já está no `.gitignore`.

## Parte 4 (opcional): ambiente de treino

1. Instale `tensorflow` no mesmo `.venv`.
2. Rode `python exemplo_keras.py --pasta saida/real01 --max-amostras 20000 --epocas 2`, só para confirmar que o ambiente funciona.
3. Informe o tempo por época. No Windows, o TensorFlow roda no processador.

## Entrega

- **Commits:**
  - `fix(itens): sync preserva metadata_info`
  - `feat(itens): grava atributos do item para o modelo preditivo`
  - `chore(estudo): ambiente local`, se mudar o `.gitignore`
- **Resumo final:**
  - o que mudou no código;
  - os números das Partes 2 e 3: datas de corte, contagens do `normalizacao.json`, cobertura dos atributos, MAPE do ingênuo e da regressão linear por horizonte, quantos itens superam o ingênuo, descartes da RN03 perto de patches;
  - as decisões que você tomou;
  - o que ficou pendente.
