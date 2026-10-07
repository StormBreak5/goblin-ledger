# Pedido ao Claude Code: etapa 2c, o modelo prevê itens que não viu no treino?

Esta é a **etapa 2c de `estudos/lstm/ROTEIRO.md`**. As etapas 1, 2 e 2b já foram feitas (`docs/relatorio-etapa1.md`, `docs/relatorio-etapa2.md` e `docs/relatorio-etapa2b.md`).

## Contexto

A intenção do autor é que a rede neural seja treinada para prever **qualquer item** com histórico, e não só os itens usados no treino. O modelo não recebe nenhum identificador do item: só a janela de 30 dias, em escala relativa ao próprio item, e os atributos (classe, subclasse, qualidade e nível). A etapa 2c mede se isso funciona, antes de o CU11 ser ajustado.

- **Leia antes:** a seção "Generalização para itens fora do treino (etapa 2c)" do `estudos/lstm/README.md`.
- **O código do experimento já está pronto e testado:**
  - `preparar_dados.py`: `--reservar-itens`, `--normalizacao-de` e `--excluir-itens-de`;
  - `treinar.py`: `--incluir-reservados`;
  - `prever.py` e `comparar.py`, novos;
  - `avaliar.py`: `por_grupo` e `por_idade` no resumo.
- **Não altere o código nem as regras do estudo.** Se algo falhar, pare e me traga o erro.
- **Tudo é avaliado só na validação.** Não preveja nem avalie o teste (RN25).
- Siga o `CLAUDE.md`: não leia nem altere arquivos `.env`. Não versione `saida/`.

## Passo 0: salvar o estado atual

1. Em `estudos/lstm`, com o `.venv` ativo, rode `pytest`. Os **33 testes** devem passar.
2. Faça um commit só de `estudos/lstm` e `docs`:

   ```bash
   git add estudos/lstm docs
   git commit -m "feat(estudo): configuração escolhida, RN10 por MdAPE e experimento de generalização (etapa 2c)"
   ```

## Passo 1: base com 20% dos itens reservados

Rode a partir de `estudos/lstm`, com `DB_HOST=localhost` e `DB_PORT=5435`. A base é a mesma da configuração escolhida: eventos agregados, que é o padrão.

```bash
python preparar_dados.py --banco --env-arquivo ../../backend/.env --regiao US --saida saida/treino2c \
    --reservar-itens 0.2 --semente 42
python avaliar.py --pasta saida/treino2c --periodo validacao --verificar     # tem que dar OK
python avaliar.py --pasta saida/treino2c --periodo validacao --ingenuo
```

Anote do log: os itens reservados e as amostras reservadas por período (`normalizacao.json` → `contagens.amostras_reservadas`).

## Passo 2: quatro treinos, um por vez

São 2 braços × 2 sementes, com os parâmetros padrão do `treinar.py` (sem máscara):

| Treino | Comando |
|---|---|
| `c_sem_s42` | `python treinar.py --pasta saida/treino2c --nome c_sem_s42 --semente 42` |
| `c_todos_s42` | `python treinar.py --pasta saida/treino2c --nome c_todos_s42 --semente 42 --incluir-reservados` |
| `c_sem_s7` | `python treinar.py --pasta saida/treino2c --nome c_sem_s7 --semente 7` |
| `c_todos_s7` | `python treinar.py --pasta saida/treino2c --nome c_todos_s7 --semente 7 --incluir-reservados` |

- `c_sem` treina **sem** os itens reservados; eles não entram nem na parada antecipada.
- `c_todos` é o controle: os mesmos itens, agora no treino.
- Confira no `treino.json` de cada um o bloco `reserva`: `incluidos_no_treino` deve ser `false` nos `c_sem` e `true` nos `c_todos`.

Depois de cada treino, avalie:

```bash
python avaliar.py --pasta saida/treino2c --periodo validacao \
    --previsoes saida/treino2c/modelos/<nome>/previsoes_validacao.parquet --rotulo <nome>
```

## Passo 3: comparação item a item nos reservados

```bash
python comparar.py --a saida/treino2c/avaliacao_validacao_c_sem_s42_itens.csv \
    --b saida/treino2c/avaliacao_validacao_c_todos_s42_itens.csv \
    --rotulos "não vistos" "vistos" --filtro reservado --saida saida/treino2c/comparacao_s42.json
python comparar.py --a saida/treino2c/avaliacao_validacao_c_sem_s7_itens.csv \
    --b saida/treino2c/avaliacao_validacao_c_todos_s7_itens.csv \
    --rotulos "não vistos" "vistos" --filtro reservado --saida saida/treino2c/comparacao_s7.json
# ruído: o mesmo controle com sementes diferentes, nos mesmos itens
python comparar.py --a saida/treino2c/avaliacao_validacao_c_todos_s42_itens.csv \
    --b saida/treino2c/avaliacao_validacao_c_todos_s7_itens.csv \
    --rotulos "controle s42" "controle s7" --filtro reservado --saida saida/treino2c/ruido_sementes.json
```

## Passo 4: itens fora da seleção do treino

Uma amostra de 3.000 itens que **não estão** na base do treino: equipamentos de reino, commodities pouco negociadas e itens com histórico curto. A base é normalizada exatamente como a versão do modelo.

```bash
python preparar_dados.py --banco --env-arquivo ../../backend/.env --regiao US --saida saida/fora2c \
    --normalizacao-de saida/treino2c --excluir-itens-de saida/treino2c \
    --ignorar-aptidao --sem-filtro-liquidez --max-itens 3000 --semente 42
python prever.py --modelo saida/treino2c/modelos/c_todos_s42 --pasta saida/fora2c
python prever.py --modelo saida/treino2c/modelos/c_todos_s7 --pasta saida/fora2c
python avaliar.py --pasta saida/fora2c --periodo validacao \
    --previsoes saida/fora2c/previsoes_validacao_c_todos_s42.parquet --rotulo c_todos_s42
python avaliar.py --pasta saida/fora2c --periodo validacao \
    --previsoes saida/fora2c/previsoes_validacao_c_todos_s7.parquet --rotulo c_todos_s7
```

- Se faltar memória, use `--max-itens 1500` e avise.
- Se a base ficar sem amostras de validação, pare e me avise.

## Passo 5: relatório

Escreva `docs/relatorio-etapa2c.md`, no estilo dos relatórios anteriores. **Traga os números; não proponha mudanças nas regras.** A interpretação será feita com o autor.

1. **O que foi rodado.**
   - Itens e amostras da base `treino2c`: total, reservados e não reservados, por período.
   - Itens da base `fora2c`.
   - Tempo de cada treino (épocas, melhor época, segundos por época, total) e os blocos `reserva` dos `treino.json`.
2. **Conferência com a etapa 2b.** A mediana do MAPE por item dos `c_todos` em todos os itens, ao lado dos 38,66% ± 0,19 da configuração escolhida.
3. **Parte A, itens não vistos.** Monte uma tabela por treino (`c_sem_s42`, `c_todos_s42`, `c_sem_s7`, `c_todos_s7`) e por grupo (reservados e não reservados), a partir de `por_grupo.reservado` do resumo:
   - itens;
   - mediana do MdAPE por item, ao lado da do ingênuo;
   - mediana do MAPE por item;
   - mediana do erro relativo ao ingênuo;
   - % de itens com erro relativo menor que 1;
   - itens liberados pela RN10 (MdAPE ≤ 15% e menor que o do ingênuo), com o %.
4. **Comparação pareada nos reservados**, de `comparacao_s42.json`, `comparacao_s7.json` e `ruido_sementes.json`:
   - para MdAPE, MAPE e erro relativo ao ingênuo: as duas medianas, a mediana da diferença e o intervalo p25 a p75 (em pontos percentuais);
   - itens com diferença de até 1 ponto no MdAPE;
   - a concordância da RN10: liberados nos dois, só em A e só em B.
5. **Parte B, itens fora da seleção.** Para cada modelo (`c_todos_s42` e `c_todos_s7`), as mesmas medidas do item 3, para:
   - todos os itens da `fora2c`;
   - cada grupo de `por_grupo`: commodity sim/não, apto pela RN15 sim/não e líquido pela RN02 sim/não.
6. **Erro pela idade do item**, de `por_idade` (alvos, itens, MdAPE, MdAPE do ingênuo e a razão), em duas tabelas:
   - na `fora2c`, com o modelo `c_todos_s42`;
   - na `treino2c`, com o modelo `c_sem_s42`.
7. **Problemas encontrados**, se houver.

## Entrega

- Commit `docs: relatório da etapa 2c (generalização para itens fora do treino)`, só com o relatório.
- Me traga o resumo das seções 2 a 6.
