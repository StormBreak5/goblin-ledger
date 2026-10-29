# Pedido ao Claude Code: etapa 2g, melhorias baratas da previsão

Esta é a **etapa 2g**, depois da 2f de `estudos/lstm/ROTEIRO.md`. As etapas 1 a 2f já foram feitas (`docs/relatorio-etapa*.md`), e a configuração final da 2e está no sistema (CU11, versão 1).

## Contexto

A pesquisa de 28/10/2026 levantou dez formas de melhorar a previsão. Esta etapa testa as três mais baratas. Duas não precisam de nenhum treino novo.

| Candidato | O que é | Treino novo? | Por que pode ajudar |
|---|---|---|---|
| `ens` | **Média das sementes:** a previsão é a média dos log-retornos previstos por 2 ou 3 modelos iguais, treinados com sementes diferentes. | Não: usa os `mae_s*` | A combinação de previsões é uma das ideias mais sólidas das competições M (Comb, N-BEATS). As três sementes da configuração final diferem em até 0,18 ponto. |
| `enc` | **Encolhimento em direção ao ingênuo:** log-retorno final = αₕ × log-retorno previsto, com um α entre 0 e 1 por horizonte. Com α = 0, a previsão vira o ingênuo. | Não: usa os `mae_s*` | O preço está perto de um passeio aleatório. Um pouco de encolhimento costuma cortar o erro dos itens voláteis, que são os que ficam acima do limiar de 15% da RN10. |
| `lrelu` e `gelu` | **Ativação da camada densa de 32:** troca da ReLU pela LeakyReLU (inclinação negativa de 0,1) ou pela GELU. | Sim: 6 treinos | No sistema, em 12% das janelas de 19/10, as 32 unidades da ReLU ficaram em zero, e a rede devolveu só o viés: na prática, o ingênuo. |

Ficam para depois (seção "Depois da 2g"):
- o calendário dos dias previstos;
- a janela maior;
- o LightGBM e o Chronos-2 como comparações;
- o peso para dados recentes;
- as fontes novas;
- a busca de hiperparâmetros.

**Referência:** os três treinos da configuração final da etapa 2e, `mae_s{42,7,2026}` em `saida/treino01_agr/modelos/`. Eles **não** são retreinados.

Os resumos que existem são de 07/10. São anteriores ao mínimo de 30 dias da RN10, que entrou na 2f. Por isso, o passo 1 **reavalia** a referência com o `avaliar.py` atual (rótulos `ref2g_s*`), e é ela que entra na regra. Os números da 2e, sem o mínimo, são:

| Referência (validação, avaliação de 07/10) | s42 | s7 | s2026 | Média |
|---|---|---|---|---|
| Mediana do MdAPE por item | 20,53% | 20,71% | 20,64% | 20,62% |
| Itens liberados pela RN10 (sem o mínimo de dias) | 1.089 | 1.096 | 1.084 | 1.090 |

**Regras:**
- **Base:** a de sempre, `saida/treino01_agr`. A validação vai de 16/07/2025 a 10/05/2026. Não prepare base nova.
- **Tudo é avaliado só na validação.** Não preveja nem avalie o teste (RN25).
- **O αₕ do `enc` é escolhido só na 1ª metade da validação e medido só na 2ª.** Escolher e medir no mesmo período daria um ganho otimista. A referência e o ingênuo também são medidos na 2ª metade, para comparar igual com igual.
- Siga o `CLAUDE.md`: não leia nem altere arquivos `.env`. Não versione `saida/`.
- Fora do passo 0, **não altere o código nem as regras do estudo.** Se algo falhar, pare e me traga o erro.

## Regra de decisão (definida antes do experimento)

- **Medida principal:** a mediana do MdAPE por item, em média nas sementes.
- **Proteção:** o número de itens liberados pela RN10, com o mínimo de 30 dias, em média nas sementes.
- **Ruído:** o maior desvio entre sementes das duas configurações comparadas. O `ens` tem um valor só, então usa o desvio da referência.
- **Um candidato é aprovado** se:
  - melhorar a medida principal mais que o ruído;
  - **e** não reduzir os itens liberados mais que o ruído dessa medida.
- **O `ens` é avaliado com 3 modelos (`ens3`).** O `ens2`, a média das 3 duplas, só serve para mostrar quanto cada modelo a mais acrescenta, porque o custo cresce com o número de modelos.
- **Nenhum aprovado:** fica a referência, e a etapa termina.
- **Um aprovado:** ele passa a ser a configuração.
- **Mais de um aprovado:** monte a combinação (`comb`, passo 3) e compare pelo mesmo critério. Ela fica se superar o melhor candidato aprovado; senão, fica o melhor aprovado.
- **Empate:** fica a mais simples. A ordem é: referência, `enc`, ativação, `ens`, combinação. O `ens` vem antes só da combinação porque multiplica o tempo de treino do C1 e do C2 e o da previsão do C3.
- **Depois disso, a configuração congela.**

## Passo 0: implementar e salvar

1. **`treinar.py`:** nova opção `--ativacao {relu,leaky_relu,gelu}`, com padrão `relu`.
   - O padrão não pode mudar em nada os treinos atuais.
   - A LeakyReLU usa inclinação negativa de 0,1. Sem outras variações.
   - Grave `parametros.ativacao` no `treino.json`.
2. **`combinar.py` (novo)**, com dois subcomandos:
   - **`media`:** recebe vários `previsoes_validacao.parquet` da mesma base e grava a média, na escala normalizada. Na mesma base, a média normalizada é igual à média dos log-retornos.
   - **`encolher`:** recebe um arquivo de previsões e divide a validação ao meio pela data de origem da amostra.
     - Na 1ª metade, escolhe αₕ na grade 0, 0,05, …, 1 para cada horizonte. O critério é a menor mediana, entre os itens, do MdAPE do item naquele horizonte.
     - Na 1ª metade, ficam de fora as amostras cujos 7 dias previstos passam do meio, como na RN25.
     - Grava três arquivos da 2ª metade: as previsões encolhidas, as mesmas sem encolher (`ref2`) e o ingênuo (`ing2`). Grava também um `.json` com os αₕ e o MdAPE da 1ª metade para cada α.
3. **`ativacoes.py` (novo):** diagnóstico da camada densa de um modelo na validação.
   - A fração de amostras em que nenhuma unidade tem pré-ativação positiva (para a ReLU, é a saída igual ao viés).
   - As unidades que nunca ficam positivas.
4. **Testes novos**, todos com dados sintéticos:
   - `test_ativacao_padrao_mantem_a_rede` (ReLU; mesma contagem de parâmetros);
   - `test_ativacao_leaky_e_gelu_constroem`;
   - `test_media_de_previsoes_iguais_e_a_propria`;
   - `test_encolher_alfa_1_e_o_modelo_e_alfa_0_e_o_ingenuo` (α = 0 bate com o `avaliar.py --ingenuo`);
   - `test_encolher_escolhe_alfa_so_na_primeira_metade` (alterar a 2ª metade não muda os αₕ);
   - `test_ativacoes_conta_amostras_sem_unidade_ativa`.
5. **README:** seção "Melhorias baratas (etapa 2g)", com os comandos.
6. Em `estudos/lstm`, com o `.venv` ativo, rode `pytest`. Os 40 testes atuais e os novos devem passar.
7. Na raiz, faça o commit:

   ```bash
   git add estudos/lstm
   git commit -m "feat(estudo): média de sementes, encolhimento e ativação da camada densa (etapa 2g)"
   ```

## Passo 1: sem treino (`ens` e `enc`)

- Rode a partir de `estudos/lstm` e grave o log em `saida/etapa2g_sequencia.log`.
- As previsões combinadas vão para `saida/treino01_agr/combinadas/`.

```bash
M=saida/treino01_agr/modelos
C=saida/treino01_agr/combinadas
for s in 42 7 2026; do   # a referência, com o avaliar.py atual (mínimo de 30 dias da RN10)
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
```

## Passo 2: os treinos da ativação (`lrelu` e `gelu`)

- São 6 treinos, de 20 a 35 minutos cada, um por vez.
- A ordem é por semente: se a noite acabar antes, os dois candidatos já terão a semente 42.

```bash
for s in 42 7 2026; do
  python treinar.py --pasta saida/treino01_agr --nome lrelu_s$s --semente $s --ativacao leaky_relu
  python treinar.py --pasta saida/treino01_agr --nome gelu_s$s --semente $s --ativacao gelu
  for n in lrelu gelu; do
    python avaliar.py --pasta saida/treino01_agr --periodo validacao \
        --previsoes saida/treino01_agr/modelos/${n}_s$s/previsoes_validacao.parquet --rotulo ${n}_s$s
  done
done
for n in mae lrelu gelu; do for s in 42 7 2026; do
  python ativacoes.py --modelo saida/treino01_agr/modelos/${n}_s$s --pasta saida/treino01_agr --periodo validacao
done; done
```

No `treino.json` de cada treino, confira que `parametros.ativacao` é `leaky_relu` só nos `lrelu_*`, `gelu` só nos `gelu_*`, e que o resto é igual ao dos `mae_*`.

## Passo 3: aplicar a regra e, se for o caso, a combinação

1. Aplique a regra:
   - **`ens3`:** contra os `ref2g_s*`, na validação inteira;
   - **`enc_s*`:** contra os `ref2_s*`, na 2ª metade;
   - **`lrelu_s*` e `gelu_s*`:** contra os `ref2g_s*`, na validação inteira.
2. **Mais de um aprovado:** monte a `comb` só com os aprovados, nesta ordem:
   1. as sementes da ativação aprovada (ou os `mae_s*`, se nenhuma for aprovada);
   2. a média das 3, se o `ens` for aprovado;
   3. o encolhimento, se o `enc` for aprovado, com o α escolhido de novo na 1ª metade.

   Se houver encolhimento, compare tudo na 2ª metade. Senão, na validação inteira.

## Passo 4: comparações de apoio

Elas **não** entram na regra; servem para a decisão do autor.

- **Item a item:** `comparar.py` de cada candidato contra a referência, por semente (para o `ens3`, contra cada `ref2g_s*`).
- **Troca de expansão:** `transicao.py` com a base `saida/treino2d_exp`, como na etapa 2e, para todos os candidatos.

## Passo 5: relatório

Escreva `docs/relatorio-etapa2g.md`, no estilo dos anteriores. Traga os números e aplique a regra, dizendo o que ela indica. **A decisão final é do autor.**

1. **O que foi rodado:**
   - os comandos exatos;
   - por treino: épocas, melhor época, segundos por época e tempo total;
   - por semente: os αₕ escolhidos e o MdAPE da 1ª metade em cada α.
2. **Tabela principal**, com média ± desvio nas sementes:
   - **colunas:** referência, `ens2`, `ens3`, `lrelu`, `gelu` e, se houver, `comb`. Numa tabela à parte, para a 2ª metade: ingênuo, referência e `enc`;
   - **linhas:** a mediana do MdAPE por item, a mediana do MAPE por item, o MAPE h1 e h7, a mediana do erro relativo ao ingênuo, os itens com erro relativo menor que 1 e os itens liberados pela RN10.
3. **Diagnóstico da camada densa (`ativacoes.py`):** a fração de amostras sem unidade ativa e as unidades nunca ativas, para os `mae`, `lrelu` e `gelu`.
4. **Comparação item a item** e **troca de expansão**, como na etapa 2e.
5. **Regra de decisão** aplicada passo a passo, com os números usados e a configuração que ela indica.
6. **Custo no sistema** da configuração indicada:
   - o tempo de treino do C1 e do C2;
   - o tempo da previsão diária do C3;
   - o espaço dos artefatos.
7. **Problemas encontrados**, se houver.

## Entrega

- Commit `docs: relatório da etapa 2g (melhorias baratas da previsão)`, só com o relatório.
- Me traga o resumo das seções 2, 3, 5 e 6.

## Se algo for aprovado: o que muda no sistema e no TC

Isto vira um pedido próprio para o `backend/src/ml/`, depois da sua decisão.

| Aprovado | Sistema | TC |
|---|---|---|
| `enc` | Os αₕ são escolhidos na validação no C1 e no C2, gravados no `normalizacao.json` (entram na assinatura) e aplicados no C2 e no C3. | Seção 5.12.2 (saída do modelo). A RN24 ganha o encolhimento. |
| Ativação | Uma linha no `construir_modelo` (`rede.py`). As versões antigas continuam carregando. | Seção 5.12.2 (arquitetura). |
| `ens` | O C1 e o C2 treinam k modelos (de cerca de 33 para 100 min com 3). A versão guarda k arquivos `.keras`. O C2 compara a média nova com a média vigente. O C3 prevê com os k. | Seção 5.12.2 e o tempo de treino. A RN26 não muda. |

## Depois da 2g (não faz parte deste pedido)

1. **Etapa 2h, calendário dos dias previstos.** A ideia vem do TFT e do TiDE: juntar à camada densa o dia da semana, o patch conhecido (regra dos 14 dias da RN25) e os eventos de D+1 a D+7. Hoje as variáveis 9 a 14 só entram com os 30 dias passados. Exige base nova (`preparar_dados.py`) e treinos.
2. **Comparações mais fortes, só medida**, para a discussão dos resultados no TC:
   - um LightGBM global com as mesmas 18 variáveis, como os vencedores da M5;
   - o Chronos-2 sem treino, numa amostra de itens, porque a previsão em CPU é pesada.
3. **Para mais tarde:**
   - **Janela de 60 ou 90 dias:** mexe na RN27 e na RN24 e tira itens novos da projeção.
   - **Peso maior para os dados recentes:** para as trocas de expansão.
   - **Fontes novas:** dados horários da Blizzard e região EU. Exigem dados e RNs novas.
   - **Busca de hiperparâmetros (Optuna):** cara em CPU; só depois das mudanças maiores.

Fontes da pesquisa: Montero-Manso e Hyndman (2021); Smyl (2020, ES-RNN); Oreshkin et al. (2020, N-BEATS); Lim et al. (2021, TFT); Das et al. (2023, TiDE); Ansari et al. (2025, Chronos-2); Makridakis et al. (M4 e M5); Lu et al. (2020, ReLU morta); Moosa e Vaz (2015, passeio aleatório). Os links estão na conversa de 28/10/2026.
