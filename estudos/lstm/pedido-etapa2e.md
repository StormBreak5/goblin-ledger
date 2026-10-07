# Pedido ao Claude Code: etapa 2e, ajuste da rede

Esta é a **etapa 2e de `estudos/lstm/ROTEIRO.md`**. As etapas 1, 2, 2b, 2c e 2d já foram feitas (`docs/relatorio-etapa*.md`).

## Contexto

A etapa 2d manteve a configuração escolhida na etapa 2b: eventos agregados, sem máscara e sem as variáveis 19 e 20. Até agora, só a **entrada** do modelo foi testada. A **rede** continua com os valores iniciais: perda Huber, LSTM de 64 unidades e taxa de aprendizado fixa de 0,001.

A etapa 2e testa três ajustes da rede, cada um sozinho contra a configuração da 2b:

| Candidato | Opção do `treinar.py` | Ideia |
|---|---|---|
| `mae` | `--perda mae` | Treinar pelo erro absoluto, que leva o modelo a prever a mediana, a mesma coisa que a RN10 mede (MdAPE). |
| `taxa` | `--reduzir-taxa` | Reduzir a taxa de aprendizado pela metade após 3 épocas sem melhora na validação. |
| `u128` | `--unidades 128` | LSTM com o dobro de unidades. |

- **Leia antes** a seção "Ajuste da rede (etapa 2e)" do `estudos/lstm/README.md`.
- **Base:** a de sempre, `saida/treino01_agr`. Não prepare base nova.
- **Referência:** os três treinos da etapa 2b (`treino01_agr_semmascara_s{42,7,2026}`), já avaliados na etapa 2d como `ref_s42`, `ref_s7` e `ref_s2026`. Eles **não** são retreinados.

**Regras:**
- **Não altere o código nem as regras do estudo.** Se algo falhar, pare e me traga o erro.
- **Tudo é avaliado só na validação.** Não preveja nem avalie o teste (RN25).
- Siga o `CLAUDE.md`: não leia nem altere arquivos `.env`. Não versione `saida/`.

## Regra de decisão (definida antes do experimento)

- **Medida principal:** a mediana do MdAPE por item, em média nas 3 sementes.
- **Proteção:** o número de itens liberados pela RN10, em média nas 3 sementes.
- **Um candidato é aprovado** se:
  - melhorar a medida principal mais que o maior desvio entre sementes das duas configurações comparadas (o candidato e a referência);
  - **e** não reduzir os itens liberados mais que o maior desvio entre sementes dessa medida.
- **Nenhum aprovado:** fica a referência, e a etapa termina.
- **Um aprovado:** ele passa a ser a configuração. Não há treino extra.
- **Dois ou três aprovados:** treine a combinação deles (`comb`, passo 3). Pelo mesmo critério, a combinação fica se superar o melhor candidato aprovado. Se não superar, fica o melhor candidato aprovado, que é o de menor medida principal.
- **Empate:** fica a mais simples. A ordem é referência, depois um ajuste só, depois a combinação.
- **Depois disso, a configuração congela.** Não teste mais nada na validação.

## Passo 0: salvar o estado atual

1. Em `estudos/lstm`, com o `.venv` ativo, rode `pytest`. Os **38 testes** devem passar.
2. Faça o commit:

   ```bash
   git add estudos/lstm
   git commit -m "feat(estudo): perda MAE e redução da taxa de aprendizado (etapa 2e)"
   ```

## Passo 1: nove treinos, um por vez

- Rode a partir de `estudos/lstm` e grave o log em `saida/etapa2e_sequencia.log`.
- A ordem é por semente: se a noite acabar antes, os três candidatos já terão a semente 42.

```bash
for s in 42 7 2026; do
  python treinar.py --pasta saida/treino01_agr --nome mae_s$s --semente $s --perda mae
  python treinar.py --pasta saida/treino01_agr --nome taxa_s$s --semente $s --reduzir-taxa
  python treinar.py --pasta saida/treino01_agr --nome u128_s$s --semente $s --unidades 128
  for n in mae taxa u128; do
    python avaliar.py --pasta saida/treino01_agr --periodo validacao \
        --previsoes saida/treino01_agr/modelos/${n}_s$s/previsoes_validacao.parquet --rotulo ${n}_s$s
  done
done
```

Confira no `treino.json` de cada treino:
- `parametros.perda` é `mae` só nos `mae_*`;
- `parametros.reduzir_taxa` é `true` só nos `taxa_*`;
- `parametros.unidades` é 128 só nos `u128_*`.

Nos `taxa_*`, anote a `taxa_final` e em que épocas a taxa caiu (coluna `learning_rate` do `historico.csv`).

## Passo 2: aplicar a regra

Aplique a regra acima aos três candidatos, com os resumos `avaliacao_validacao_<nome>_resumo.json` (os `ref_s*` são a referência).

## Passo 3: combinação (só se houver dois ou três aprovados)

Treine a combinação **só** com as opções dos candidatos aprovados. Por exemplo, se `mae` e `taxa` forem aprovados:

```bash
for s in 42 7 2026; do
  python treinar.py --pasta saida/treino01_agr --nome comb_s$s --semente $s --perda mae --reduzir-taxa
  python avaliar.py --pasta saida/treino01_agr --periodo validacao \
      --previsoes saida/treino01_agr/modelos/comb_s$s/previsoes_validacao.parquet --rotulo comb_s$s
done
```

## Passo 4: comparações de apoio

Rode estes comandos para os candidatos e, se houver, para a `comb`. Eles **não** entram na regra; servem para a decisão do autor.

```bash
for n in mae taxa u128; do for s in 42 7 2026; do
  python comparar.py --a saida/treino01_agr/avaliacao_validacao_${n}_s${s}_itens.csv \
      --b saida/treino01_agr/avaliacao_validacao_ref_s${s}_itens.csv \
      --rotulos "$n" "referência" --saida saida/treino01_agr/comparacao_${n}_ref_s$s.json
  python transicao.py --base saida/treino2d_exp \
      --detalhe saida/treino01_agr/avaliacao_validacao_${n}_s${s}_detalhe.parquet --rotulo ${n}_s$s
done; done
```

Os `transicao.py` usam o `itens.parquet` da `treino2d_exp`, que tem os mesmos itens.

## Passo 5: relatório

Escreva `docs/relatorio-etapa2e.md`, no estilo dos relatórios anteriores. Traga os números e aplique a regra, dizendo o que ela indica. **A decisão final é do autor.**

1. **O que foi rodado.**
   - Os comandos exatos.
   - Por treino: épocas, melhor época, segundos por época e tempo total.
   - Nos `taxa_*`: a taxa final e as épocas em que ela caiu.
2. **Tabela principal.** Média ± desvio nas 3 sementes, para referência, `mae`, `taxa`, `u128` e, se houver, `comb`:
   - mediana do MdAPE por item;
   - mediana do MAPE por item;
   - MAPE h1 e h7 (dos `_horizontes.csv`);
   - mediana do erro relativo ao ingênuo;
   - itens com erro relativo menor que 1;
   - itens liberados pela RN10.

   Depois, a mediana do MdAPE por item em cada semente.
3. **Comparação item a item com a referência**, de `comparacao_*_ref_s*.json`, por candidato e semente:
   - a mediana da diferença no MdAPE e o intervalo p25 a p75;
   - os itens em que o candidato é melhor e pior;
   - a concordância da RN10.
4. **Troca de expansão**, dos `transicao_*.csv`. Média nas 3 sementes da razão a 7 dias para:
   - a expansão que sai, na troca;
   - todos, na troca;
   - todos, no resto;
   - a expansão que entra, no resto.

   A referência dessa tabela está em `docs/relatorio-etapa2d.md`, seção 3.
5. **Regra de decisão** aplicada passo a passo, com os números usados e a configuração final que ela indica.
6. **Problemas encontrados**, se houver.

## Entrega

- Commit `docs: relatório da etapa 2e (ajuste da rede)`, só com o relatório.
- Me traga o resumo das seções 2 a 5.
