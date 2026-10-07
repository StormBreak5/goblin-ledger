# Pedido ao Claude Code: etapa 2d, o modelo sabe se o item é da expansão vigente?

Esta é a **etapa 2d de `estudos/lstm/ROTEIRO.md`**. As etapas 1, 2, 2b e 2c já foram feitas (`docs/relatorio-etapa*.md`).

## Contexto

As variáveis 10 a 13 dizem ao modelo **quando** vem um patch ou uma expansão. Nenhuma diz **a que expansão o item pertence**.

Na troca para Midnight (02/03/2026, dentro da validação), o modelo da etapa 2c perdeu a vantagem sobre o ingênuo justamente nos itens da expansão que estava saindo:
- a razão entre o erro dele e o do ingênuo ficou em 0,98, contra 0,86 a 0,94 nos demais grupos;
- a 7 dias, ele previu preços 8% acima do real.

A etapa 2d testa duas variáveis novas, já implementadas e testadas no estudo, desligadas por padrão:

| Nº | Variável | Chave do `preparar_dados.py` |
|---|---|---|
| 19 | Item da expansão vigente no dia (0/1) | `--variavel-expansao-item` |
| 20 | Idade do item (dias desde o primeiro registro, até 180, divididos por 180) | `--variavel-idade-item` |

**Leia antes** a seção "Ciclo de vida do item (etapa 2d)" do `estudos/lstm/README.md`.

**Regras:**
- **Não altere o código nem as regras do estudo.** Se algo falhar, pare e me traga o erro.
- **Tudo é avaliado só na validação.** Não preveja nem avalie o teste (RN25).
- Siga o `CLAUDE.md`: não leia nem altere arquivos `.env`. Não versione `saida/`.

A referência (sem as variáveis novas) são os três treinos escolhidos na etapa 2b: `saida/treino01_agr/modelos/treino01_agr_semmascara_s{42,7,2026}`. Eles **não** são retreinados.

## Regra de decisão (definida antes do experimento)

- **Medida principal:** a mediana do MdAPE por item (a medida da RN10), em média nas 3 sementes.
- **Medida da troca:** a razão entre o MdAPE do modelo e o do ingênuo a 7 dias, nos itens da **expansão que sai**, na janela da troca, em média nas 3 sementes.
- **A variável 19 entra** (configuração `exp` contra a referência) se:
  - melhorar a medida principal mais que o maior desvio entre sementes das duas configurações; **ou**
  - melhorar a medida da troca mais que esse desvio, sem piorar a principal mais que ele.
- **A variável 20 entra** (configuração `expidade` contra `exp`) se:
  - melhorar a medida principal pelo mesmo critério; **ou**
  - melhorar a razão a 7 dias nos itens da **expansão que entra**, fora da janela da troca (os itens novos de Midnight), sem piorar a principal.
- **Empate:** fica a configuração mais simples.

## Passo 0: salvar o estado atual

1. Em `estudos/lstm`, com o `.venv` ativo, rode `pytest`. Os **36 testes** devem passar.
2. Faça o commit:

   ```bash
   git add estudos/lstm
   git commit -m "feat(estudo): variáveis do ciclo do item e análise da troca de expansão (etapa 2d)"
   ```

## Passo 1: duas bases novas

Rode a partir de `estudos/lstm`, com `DB_HOST=localhost` e `DB_PORT=5435`:

```bash
python preparar_dados.py --banco --env-arquivo ../../backend/.env --regiao US --saida saida/treino2d_exp \
    --variavel-expansao-item
python preparar_dados.py --banco --env-arquivo ../../backend/.env --regiao US --saida saida/treino2d_expidade \
    --variavel-expansao-item --variavel-idade-item
python avaliar.py --pasta saida/treino2d_exp --periodo validacao --verificar        # tem que dar OK
python avaliar.py --pasta saida/treino2d_expidade --periodo validacao --verificar   # tem que dar OK
```

**Confira contra `saida/treino01_agr/normalizacao.json`.** Nas duas bases novas, estes valores precisam ser iguais aos de lá:
- as datas de corte;
- as linhas (8.073.939);
- as amostras: treino 3.792.068, validação 1.420.443 e teste 786.081.

**Se algo não bater, pare e me avise:** a comparação com a referência deixaria de valer.

Anote `ciclo_do_item.itens_por_expansao` de qualquer uma das duas bases.

## Passo 2: reavaliar a referência

Reavalie a referência com o `avaliar.py` atual, para que a RN10 seja pelo MdAPE:

```bash
for s in 42 7 2026; do
  python avaliar.py --pasta saida/treino01_agr --periodo validacao \
      --previsoes saida/treino01_agr/modelos/treino01_agr_semmascara_s$s/previsoes_validacao.parquet --rotulo ref_s$s
done
```

## Passo 3: seis treinos, um por vez

Use os parâmetros padrão do `treinar.py` (sem máscara):

```bash
for s in 42 7 2026; do
  python treinar.py --pasta saida/treino2d_exp --nome exp_s$s --semente $s
  python avaliar.py --pasta saida/treino2d_exp --periodo validacao \
      --previsoes saida/treino2d_exp/modelos/exp_s$s/previsoes_validacao.parquet --rotulo exp_s$s
done
for s in 42 7 2026; do
  python treinar.py --pasta saida/treino2d_expidade --nome expidade_s$s --semente $s
  python avaliar.py --pasta saida/treino2d_expidade --periodo validacao \
      --previsoes saida/treino2d_expidade/modelos/expidade_s$s/previsoes_validacao.parquet --rotulo expidade_s$s
done
```

No `treino.json` de cada um, confira `variaveis_sequencia`: deve ser 17 nos `exp` e 18 nos `expidade`.

## Passo 4: erro na troca de expansão

A referência usa o `itens.parquet` da `treino2d_exp`, porque os itens são os mesmos.

```bash
for s in 42 7 2026; do
  python transicao.py --base saida/treino2d_exp \
      --detalhe saida/treino01_agr/avaliacao_validacao_ref_s${s}_detalhe.parquet --rotulo ref_s$s
  python transicao.py --base saida/treino2d_exp \
      --detalhe saida/treino2d_exp/avaliacao_validacao_exp_s${s}_detalhe.parquet --rotulo exp_s$s
  python transicao.py --base saida/treino2d_expidade \
      --detalhe saida/treino2d_expidade/avaliacao_validacao_expidade_s${s}_detalhe.parquet --rotulo expidade_s$s
done
```

O lançamento avaliado deve sair como 2026-03-02.

## Passo 5: comparação item a item com a referência

```bash
for s in 42 7 2026; do
  python comparar.py --a saida/treino2d_exp/avaliacao_validacao_exp_s${s}_itens.csv \
      --b saida/treino01_agr/avaliacao_validacao_ref_s${s}_itens.csv \
      --rotulos "com a 19" "referência" --saida saida/treino2d_exp/comparacao_ref_s$s.json
  python comparar.py --a saida/treino2d_expidade/avaliacao_validacao_expidade_s${s}_itens.csv \
      --b saida/treino01_agr/avaliacao_validacao_ref_s${s}_itens.csv \
      --rotulos "com a 19 e a 20" "referência" --saida saida/treino2d_expidade/comparacao_ref_s$s.json
done
```

## Passo 6: relatório

Escreva `docs/relatorio-etapa2d.md`, no estilo dos relatórios anteriores. Traga os números e aplique a regra de decisão acima, dizendo o que ela indica. **A decisão final é do autor.**

1. **O que foi rodado.**
   - A conferência das contagens do passo 1.
   - Os itens por expansão.
   - O tempo de cada treino: épocas, melhor época, segundos por época e total.
2. **Tabela principal.** Média ± desvio nas 3 sementes, para referência, `exp` e `expidade`:
   - mediana do MdAPE por item;
   - mediana do MAPE por item;
   - MAPE h1 e h7 (dos `_horizontes.csv`);
   - mediana do erro relativo ao ingênuo;
   - itens com erro relativo menor que 1;
   - itens liberados pela RN10.

   Depois, uma tabela com a mediana do MdAPE por item em cada semente.
3. **Troca de expansão**, dos `transicao_*.csv`. Média ± desvio nas 3 sementes, para cada configuração, da razão e do viés mediano a 7 dias (`horizonte = h7`) em:
   - expansão que sai, na troca;
   - anteriores ou desconhecida, na troca;
   - todos, na troca;
   - todos, no resto;
   - expansão que entra, no resto.
4. **Comparação item a item**, dos `comparacao_ref_s*.json`, para cada semente:
   - a mediana da diferença no MdAPE e o intervalo p25 a p75;
   - os itens em que a configuração nova é melhor;
   - a concordância da RN10.
5. **Regra de decisão** aplicada às variáveis 19 e 20, com os números usados.
6. **Problemas encontrados**, se houver.

## Entrega

- Commit `docs: relatório da etapa 2d (ciclo de vida do item)`, só com o relatório.
- Me traga o resumo das seções 2 a 5.
