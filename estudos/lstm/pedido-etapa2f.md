# Pedido ao Claude Code: etapa 2f, generalização medida com a configuração final

Esta é a **etapa 2f de `estudos/lstm/ROTEIRO.md`**. As etapas 1 a 2e já foram feitas (`docs/relatorio-etapa*.md`).

## Contexto

A etapa 2e congelou a configuração final, que passa a ser o padrão do `treinar.py`:
- eventos agregados;
- sem máscara;
- **perda MAE**.

O experimento de generalização da etapa 2c (itens não vistos e itens fora da seleção) foi feito com a perda antiga, a Huber. A etapa 2f **mede de novo** a mesma coisa com a configuração final, para que todos os números do TC venham do mesmo modelo.

**Esta etapa só mede. Não decide nada nem muda nenhuma configuração.**

Três novidades do estudo, já testadas:

- **`avaliar.py`:** a RN10 passa a exigir **30 dias de previsões avaliadas** (`minimo_dias_rn10`, a confirmar).
  - O resultado por item ganha `dias_avaliados` e `motivo_bloqueio`.
  - O resumo traz os liberados com e sem esse mínimo, para comparar com as etapas anteriores.
- **`generalizacao.py`:** script novo com duas análises.
  - `liquidez`: erro por faixa de quantidade média ofertada.
  - `novos`: itens sem nenhuma amostra de treino contra os demais.
  - São as análises que o Claude fez à parte sobre a etapa 2c.
- **`treinar.py`:** a perda padrão agora é `mae`.

**Regras:**
- **Não altere o código nem as regras do estudo.** Se algo falhar, pare e me traga o erro.
- **Tudo é avaliado só na validação.** Não preveja nem avalie o teste (RN25).
- Siga o `CLAUDE.md`: não leia nem altere arquivos `.env`. Não versione `saida/`.
- **Use as bases que já existem:** `saida/treino2c` (20% dos itens reservados) e `saida/fora2c` (3.000 itens fora da seleção). Não prepare base nova.

## Passo 0: salvar o estado atual

1. Em `estudos/lstm`, com o `.venv` ativo, rode `pytest`. Os **40 testes** devem passar.
2. Na raiz do repositório, faça o commit:

   ```bash
   git add estudos/lstm
   git commit -m "feat(estudo): perda MAE como padrão, mínimo de dias na RN10 e análises da generalização (etapa 2f)"
   ```

3. Ainda na raiz, faça um segundo commit, só com a documentação do CU11:

   ```bash
   git add "docs/Alterações do TC - modelo global (para colar) v4.docx" docs/casos-de-uso/CU11-treinar-modelo.md docs/diagramas-atualizados/cu11c01.* docs/diagramas-atualizados/cu11c02.* docs/diagramas-atualizados/cu11c03.*
   git commit -m "docs: v4 das alterações do TC, CU11 com a separação dos itens e diagramas de atividades"
   ```

## Passo 1: Parte A, itens não vistos, com a perda MAE

Rode a partir de `estudos/lstm` e grave o log em `saida/etapa2f_sequencia.log`.

```bash
for s in 42 7; do
  python treinar.py --pasta saida/treino2c --nome m_sem_s$s --semente $s --perda mae
  python treinar.py --pasta saida/treino2c --nome m_todos_s$s --semente $s --perda mae --incluir-reservados
  for n in m_sem m_todos; do
    python avaliar.py --pasta saida/treino2c --periodo validacao \
        --previsoes saida/treino2c/modelos/${n}_s$s/previsoes_validacao.parquet --rotulo ${n}_s$s
  done
done
```

No `treino.json`, confira:
- `parametros.perda` é `mae` nos quatro;
- `reserva.incluidos_no_treino` é `false` nos `m_sem` e `true` nos `m_todos`.

Depois, a comparação item a item nos reservados:

```bash
for s in 42 7; do
  python comparar.py --a saida/treino2c/avaliacao_validacao_m_sem_s${s}_itens.csv \
      --b saida/treino2c/avaliacao_validacao_m_todos_s${s}_itens.csv \
      --rotulos "não vistos" "vistos" --filtro reservado --saida saida/treino2c/comparacao_mae_s$s.json
done
python comparar.py --a saida/treino2c/avaliacao_validacao_m_todos_s42_itens.csv \
    --b saida/treino2c/avaliacao_validacao_m_todos_s7_itens.csv \
    --rotulos "controle s42" "controle s7" --filtro reservado --saida saida/treino2c/ruido_sementes_mae.json
```

## Passo 2: Parte B, itens fora da seleção

```bash
for s in 42 7; do
  python prever.py --modelo saida/treino2c/modelos/m_todos_s$s --pasta saida/fora2c
  python avaliar.py --pasta saida/fora2c --periodo validacao \
      --previsoes saida/fora2c/previsoes_validacao_m_todos_s$s.parquet --rotulo m_todos_s$s
done
```

## Passo 3: liquidez e itens novos

```bash
for s in 42 7; do
  python generalizacao.py liquidez \
      --avaliacao saida/treino2c/avaliacao_validacao_m_todos_s${s}_itens.csv \
      --avaliacao saida/fora2c/avaliacao_validacao_m_todos_s${s}_itens.csv \
      --saida saida/liquidez_mae_s$s.csv
  python generalizacao.py novos --avaliacao saida/treino2c/avaliacao_validacao_m_sem_s${s}_itens.csv \
      --saida saida/novos_mae_s$s.csv
done
```

## Passo 4: relatório

Escreva `docs/relatorio-etapa2f.md`, no estilo dos relatórios anteriores.

- **Traga os números, sem propor mudanças.** A interpretação será feita com o autor.
- Sempre que der, ponha ao lado o número da etapa 2c (perda Huber), tirado de `docs/relatorio-etapa2c.md`.
- Nas comparações de liberados com a 2c, use o número **sem** o mínimo de dias (`itens_liberados_rn10_sem_minimo_de_dias`), porque a 2c não tinha o mínimo.

1. **O que foi rodado.** Os comandos, o tempo de cada treino (épocas, melhor época, segundos por época e total) e os blocos `reserva` dos `treino.json`.
2. **Parte A, itens não vistos.** Por treino (`m_sem_s42`, `m_todos_s42`, `m_sem_s7`, `m_todos_s7`) e por grupo (reservados e não reservados), de `por_grupo.reservado`:
   - itens;
   - mediana do MdAPE por item e a do ingênuo;
   - mediana do MAPE por item;
   - mediana do erro relativo ao ingênuo;
   - % com erro relativo menor que 1;
   - liberados pela RN10, com e sem o mínimo de dias.
3. **Comparação pareada nos reservados,** de `comparacao_mae_s42.json`, `comparacao_mae_s7.json` e `ruido_sementes_mae.json`:
   - para MdAPE, MAPE e erro relativo: as medianas, a mediana da diferença e o intervalo p25 a p75;
   - os itens com diferença de até 1 ponto no MdAPE;
   - a concordância da RN10.

   Inclua a tabela "lado a lado" da etapa 2c, com uma coluna para a Huber (2c) e outra para a MAE (2f).
4. **Parte B, itens fora da seleção.** Por modelo (`m_todos_s42` e `m_todos_s7`), as mesmas medidas do item 2 para:
   - todos os itens da `fora2c`;
   - cada grupo de `por_grupo`: commodity, apto pela RN15 e líquido pela RN02.
5. **Liquidez,** de `liquidez_mae_s42.csv` e `liquidez_mae_s7.csv`. Uma tabela por faixa de quantidade média ofertada, com uma coluna para a `treino2c` e outra para a `fora2c`, mostrando:
   - itens;
   - mediana do MdAPE e a do ingênuo;
   - mediana do erro relativo;
   - % com erro relativo menor que 1;
   - % de liberados.
6. **Itens novos,** de `novos_mae_s42.csv` e `novos_mae_s7.csv`. Itens sem nenhuma amostra de treino contra os demais, separados por reservado, com as mesmas medidas e a mediana de dias avaliados.
7. **Erro pela idade do item,** de `por_idade`, em duas tabelas:
   - na `fora2c`, com o `m_todos_s42`;
   - na `treino2c`, com o `m_sem_s42`.
8. **Efeito do mínimo de 30 dias na RN10.** Na `treino2c` com o `m_todos_s42`:
   - liberados com e sem o mínimo;
   - itens com avaliação insuficiente;
   - quantos deles são itens sem amostra de treino (os itens novos).
9. **Problemas encontrados**, se houver.

## Entrega

- Commit `docs: relatório da etapa 2f (generalização com a configuração final)`, só com o relatório.
- Me traga o resumo das seções 2 a 8.
