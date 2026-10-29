# Pedido ao Claude Code: etapa 2h, calendário dos dias previstos

Esta é a **etapa 2h**, depois da 2g (`docs/relatorio-etapa2g.md`). A 2g indicou a GELU na camada densa de 32 e congelou a configuração. Esta etapa testa uma mudança só: dar à rede o calendário dos 7 dias que ela prevê.

## Contexto

Hoje as variáveis de calendário e eventos (9 a 14) só entram com os 30 dias passados, na sequência da LSTM. A rede prevê D+1 a D+7 sem ver diretamente o que vai acontecer nesses dias. É a ideia do TFT (Lim et al., 2021) e do TiDE (Das et al., 2023): entradas conhecidas do futuro, juntadas à parte densa da rede.

O que a rede **já sabe** em D, pelo último passo da sequência:
- o dia da semana de D, e daí o dos dias seguintes;
- os dias até o próximo patch, se ele estiver a até 14 dias (variável 11);
- se há expansão ou pré-patch nos próximos 14 dias (variável 12), mas sem o dia.

O que ela **não sabe** em D:
- se um festival começa ou termina entre D+1 e D+7;
- se uma temporada começa nesse intervalo;
- em que dia, exatamente, cai o marco de expansão.

**Expectativa: ganho incerto, provavelmente pequeno.** Parte da informação já entra pela variável 11. Na etapa 2b, os eventos detalhados, que incluíam a fração dos próximos 7 dias com cada festival, ficaram atrás dos agregados (`docs/relatorio-etapa2b.md`). A diferença agora: são poucas colunas, que entram uma vez por dia previsto, direto na camada densa, em vez de muitas colunas nos 30 passos da LSTM.

| Candidato | O que é | Treino novo? |
|---|---|---|
| `cal` | GELU + entrada nova `X_fut` [7 × 6]: o calendário de D+1 a D+7, como conhecido em D | Sim: 3 treinos |

**Referência:** os três treinos `gelu_s{42,7,2026}` da etapa 2g, já avaliados com o mínimo de 30 dias da RN10 (rótulos `gelu_s*`). Eles **não** são retreinados.

**Voltar atrás é simples:**
- tudo fica no estudo, atrás de uma opção desligada por padrão;
- o sistema (`backend/`) não muda nesta etapa;
- se o `cal` não for aprovado, fica a GELU, e o commit do passo 0 pode ser revertido sem afetar nada.

## As colunas de `X_fut`

Para cada amostra com dia de origem D e cada h de 1 a 7, há 6 colunas. Todas vêm só da data e de `evento_jogo`, sem preço:

| Coluna | Valor | Mesma definição da variável |
|---|---|---|
| `fut_dia_sin`, `fut_dia_cos` | dia da semana de D+h | 9 |
| `fut_patch` | 1 se algum patch cai entre D+1 e D+h | 10 e 11 (lista de patches de `datas_de_patch_e_marcos`) |
| `fut_expansao` | 1 se algum marco de expansão (pré-patch ou lançamento) cai entre D+1 e D+h | 12 |
| `fut_temporada` | 1 se alguma temporada começa entre D+1 e D+h | 13 |
| `fut_evento` | 1 se algum evento sazonal está ativo em D+h | 14 (agregada) |

**RN25 (só o que se sabe em D):**
- Um patch só é conhecido 14 dias antes. Como D+h fica a no máximo 7 dias, todo patch do horizonte já é conhecido em D.
- Festivais e temporadas seguem a premissa que o estudo já usa: o calendário deles é conhecido antecipadamente.
- Nenhuma coluna olha além de D+7.
- Os valores já ficam entre −1 e 1, e nenhuma constante é ajustada; com isso, o período de teste não influencia nada.

## Regras

- **Base:** a de sempre, `saida/treino01_agr`, sem alteração. O calendário vai para uma pasta à parte, `saida/calendario2h/`, e é ligado pelo dia de origem de cada amostra. As amostras, os alvos e a normalização ficam idênticos aos da referência.
- **Eventos:** são lidos do banco atual (`evento_jogo`). Antes de usar, confira que as variáveis 9 a 14 recalculadas com eles, em todas as datas da base, batem com as de `linhas_normalizadas.parquet`, preparadas em 07/10. Se não baterem, pare e me traga a diferença: os eventos mudaram desde então.
- **Tudo é avaliado só na validação.** Não preveja nem avalie o teste (RN25).
- Siga o `CLAUDE.md`: não leia nem altere arquivos `.env`. Não versione `saida/`.
- Fora do passo 0, **não altere o código nem as regras do estudo.** Se algo falhar, pare e me traga o erro.

## Regra de decisão (a mesma da 2g)

- **Medida principal:** a mediana do MdAPE por item, em média nas sementes.
- **Proteção:** os itens liberados pela RN10, com o mínimo de 30 dias, em média nas sementes.
- **Ruído:** o maior desvio entre sementes das duas configurações.
- **O `cal` é aprovado** se melhorar a medida principal mais que o ruído **e** não reduzir os liberados mais que o ruído dessa medida.
- **Aprovado:** ele passa a ser a configuração. **Não aprovado:** fica a GELU. Nos dois casos, a configuração congela.

## Passo 0: implementar e salvar

1. **`calendario_futuro.py` (novo):**
   - Lê os eventos do banco (`--banco`) ou de um `eventos.csv` (`--csv`, para os sintéticos), e as datas da base (`--pasta`).
   - Faz a conferência das variáveis 9 a 14 descrita nas regras.
   - Grava `calendario_futuro.parquet`, com uma linha por dia de origem D e as 42 colunas (`fut_<coluna>_h<h>`). Grava também um `.json` com as colunas, as contagens de valores diferentes de zero por período e uma assinatura do arquivo.
   - Usa as funções de `preparar_dados.py` (`datas_de_patch_e_marcos` e a mesma leitura dos eventos sazonais e das temporadas), sem duplicar regra.
2. **`treinar.py`:** nova opção `--calendario-futuro ARQUIVO`.
   - Sem ela, nada muda.
   - Com ela, entra o `X_fut` [7, 6], achatado e juntado ao `Concatenate`, antes da camada densa de 32.
   - O `prever` passa a mandar o `X_fut` também.
   - Grave em `treino.json` o caminho, as colunas e a assinatura do calendário.
3. **`eventos_no_horizonte.py` (novo):** separa as amostras da validação em "com evento no horizonte" e "sem evento".
   - "Com evento" é ter, entre D+1 e D+7, um patch, um marco de expansão, um início de temporada ou um início ou fim de evento sazonal.
   - Para cada grupo, calcula a mediana do MdAPE por item, o MAPE e a razão contra o ingênuo, a partir do `_detalhe.parquet` do `avaliar.py`.
   - É onde o ganho deveria aparecer, se houver.
4. **Testes novos**, com dados sintéticos:
   - `test_calendario_futuro_desligado_mantem_a_rede` (mesma contagem de parâmetros, 23.763 com a GELU);
   - `test_calendario_futuro_so_usa_o_que_se_sabe_em_d`:
     - um patch em D+3 marca `fut_patch` só de h3 a h7;
     - um patch em D+8 não marca nada;
     - mudar um evento depois de D+7 não muda a linha de D;
   - `test_calendario_futuro_confere_as_variaveis_da_base` (um evento alterado faz a conferência falhar);
   - `test_calendario_futuro_treina_e_preve` (1 época com a opção, `treino.json` com o calendário, recarga e previsão);
   - `test_eventos_no_horizonte_separa_as_amostras`.
5. **README:** seção "Calendário dos dias previstos (etapa 2h)", com os comandos.
6. Em `estudos/lstm`, com o `.venv` ativo, rode `pytest`. Os 46 testes atuais e os novos devem passar.
7. Na raiz, faça o commit só com os arquivos do passo:

   ```bash
   git commit -m "feat(estudo): calendário dos dias previstos como entrada da rede (etapa 2h)"
   ```

## Passo 1: o calendário

```bash
python calendario_futuro.py --banco --pasta saida/treino01_agr --saida saida/calendario2h
```

Traga a conferência das variáveis 9 a 14 e quantas amostras da validação têm cada coluna diferente de zero.

## Passo 2: os treinos

São 3 treinos, de 20 a 35 minutos cada, um por vez. O log vai para `saida/etapa2h_sequencia.log`.

```bash
for s in 42 7 2026; do
  python treinar.py --pasta saida/treino01_agr --nome cal_s$s --semente $s --ativacao gelu \
      --calendario-futuro saida/calendario2h/calendario_futuro.parquet
  python avaliar.py --pasta saida/treino01_agr --periodo validacao \
      --previsoes saida/treino01_agr/modelos/cal_s$s/previsoes_validacao.parquet --rotulo cal_s$s
done
```

No `treino.json`, confira que o único parâmetro diferente dos `gelu_*` é o `calendario_futuro`, e que `previu_teste` é `false`.

## Passo 3: regra

Aplique a regra: `cal_s*` contra `gelu_s*`, na validação inteira.

## Passo 4: comparações de apoio

Elas **não** entram na regra.

- **Item a item:** `comparar.py` de `cal_s*` contra `gelu_s*`, por semente.
- **Troca de expansão:** `transicao.py` com a base `saida/treino2d_exp`, para `cal_s*`.
- **Eventos no horizonte:** `eventos_no_horizonte.py` para `gelu_s*` e `cal_s*`.

## Passo 5: relatório

Escreva `docs/relatorio-etapa2h.md`, no estilo do da 2g. **A decisão final é do autor.**

1. **O que foi rodado:** os comandos, a conferência dos eventos e, por treino, as épocas, a melhor época, o tempo por época e o tempo total.
2. **Tabela principal:** referência (`gelu`) e `cal`, com as mesmas linhas da 2g.
3. **Eventos no horizonte:** os dois grupos, para os dois modelos.
4. **Item a item** e **troca de expansão**.
5. **Regra de decisão**, passo a passo.
6. **Custo no sistema**, se aprovado.
7. **Problemas encontrados.**

## Entrega

- Commit `docs: relatório da etapa 2h (calendário dos dias previstos)`, só com o relatório.
- Me traga o resumo das seções 2, 3 e 5.

## Se for aprovado: o que muda no sistema e no TC

Isto vira um pedido próprio para o `backend/src/ml/`, depois da sua decisão.

- **Sistema:**
  - `rede.py` ganha a entrada `X_fut`, e `preparacao.py` monta o calendário.
  - O C3 lê os eventos de D+1 a D+7 em `evento_jogo`.
    - Hoje, o banco já tem os festivais e os eventos recorrentes até 2027, mas **nenhum patch nem temporada futuros**: o último patch é de 2026-08-11, e a última temporada, de 2026-08-18.
    - Para o C3 aproveitar o `fut_patch` e o `fut_temporada`, eles precisam ser cadastrados assim que forem anunciados. Isso já vale hoje para as variáveis 11 e 13.
  - As versões antigas continuam carregando, porque o modelo sem `X_fut` segue a entrada antiga.
- **TC:**
  - Seção 5.12.1 (variáveis): uma variável nova, o calendário dos dias previstos.
  - Seção 5.12.2 (arquitetura).
  - A RN25 ganha a frase sobre o que se sabe em D para os dias previstos.

## Depois da 2h (não faz parte deste pedido)

As comparações mais fortes, só medida, continuam para a discussão dos resultados no TC:
- o LightGBM global com as mesmas variáveis;
- o Chronos-2 numa amostra de itens.
