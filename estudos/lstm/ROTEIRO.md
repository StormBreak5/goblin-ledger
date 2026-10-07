# Roteiro: do estado atual até o treino da rede neural

| Etapa | Quem faz | O que sai dela |
|---|---|---|
| 0. Arrumar o terreno | você | banco no ar, arquivos no projeto |
| 1. Preparação | Claude Code (pedido 1) | atributos no banco, dados conferidos, primeiras referências |
| 2. **Primeiro treino da rede neural** | você ou o Claude Code (comandos abaixo) | LSTM treinada e comparada com o ingênuo e a regressão linear |
| 2c. **Itens fora do treino** | Claude Code (`pedido-etapa2c.md`) | erro do modelo em itens que ele nunca viu e em itens fora da seleção |
| 3. Levar para o sistema (CU11) | Claude Code (pedidos 2, 3 e 4) | treinamento pela tela do Admin, retreino semanal, previsões diárias |
| 4. Escrever no TC | você (com o Claude no Cowork) | texto do CU11 com o comportamento e os números reais |

Ao fim de cada etapa, traga o resultado para o Claude no Cowork antes de seguir.

---

## Etapa 0: arrumar o terreno

1. **Confira que estes arquivos estão no projeto:**
   - `docs/casos-de-uso/CU11-treinar-modelo.md` (provisório);
   - em `estudos/lstm/`: `ROTEIRO.md`, `pedido-preparacao-treino.md`, `pedido-cu11-c1.md`, `treinar.py`, `README.md` e `requirements.txt`.
2. **Suba o banco e o worker:**

   ```powershell
   cd D:\workspace\goblin-ledger\backend
   docker-compose up --build -d
   docker ps        # precisa aparecer o postgres (porta 5435) e o worker
   ```

3. **Salve o estado atual no Git** (recomendado):

   ```powershell
   cd D:\workspace\goblin-ledger
   git add docs/casos-de-uso/CU11-treinar-modelo.md estudos/lstm
   git commit -m "docs: CU11 provisório e estudo da LSTM"
   ```

   O vídeo `.mp4` fica de fora: o `.gitignore` do estudo já o ignora.
4. **Abra o Claude Code** na pasta `D:\workspace\goblin-ledger`.

---

## Etapa 1: preparação (pedido 1)

1. **Cole no Claude Code:**

   ```
   Leia estudos/lstm/pedido-preparacao-treino.md e siga, começando pelo plano. Não implemente o CU11 nesta etapa.
   ```

2. **Revise o plano** que ele apresentar e aprove.
3. **No fim, confira:**
   - classe e subclasse gravadas na grande maioria dos itens;
   - `aptidao_treinamento` preenchida;
   - patches e expansões cadastrados desde 2022;
   - `--verificar` dando **OK**;
   - o MAPE do ingênuo e o da regressão linear.
4. **Traga o resumo dele para o Claude no Cowork.**

---

## Etapa 2: primeiro treino da rede neural (no estudo)

> **Concluída.** Resultados em `docs/relatorio-etapa2.md` e `docs/relatorio-etapa2b.md`. A configuração escolhida (eventos agregados, sem máscara) e a RN10 por MdAPE ≤ 15% já são o padrão dos scripts.

Você pode rodar os comandos no PowerShell ou pedir ao Claude Code: *"Rode a etapa 2 de `estudos/lstm/ROTEIRO.md` (passos 1 a 4) e me traga a tabela de resultados."*

```powershell
cd D:\workspace\goblin-ledger\estudos\lstm
.\.venv\Scripts\Activate.ps1
$env:DB_HOST="localhost"; $env:DB_PORT="5435"

# 1. Preparar a base do treino com todos os itens. Se faltar memória, acrescente --max-itens 3000.
python preparar_dados.py --banco --env-arquivo ..\..\backend\.env --regiao US --saida saida\treino01

# 2. Conferir o mecanismo e medir as referências (só na validação)
python avaliar.py --pasta saida\treino01 --periodo validacao --verificar
python avaliar.py --pasta saida\treino01 --periodo validacao --ingenuo
python regressao_linear.py --pasta saida\treino01
python avaliar.py --pasta saida\treino01 --periodo validacao --previsoes saida\treino01\previsoes_validacao_linear.parquet

# 3. TREINAR A REDE NEURAL
python treinar.py --pasta saida\treino01 --nome lstm01

# 4. Avaliar a rede na validação
python avaliar.py --pasta saida\treino01 --periodo validacao --previsoes saida\treino01\modelos\lstm01\previsoes_validacao.parquet --rotulo lstm01
```

**Leitura dos resultados.** Os números ficam em `saida\treino01\avaliacao_validacao_<rotulo>_resumo.json`. Monte esta tabela:

| Modelo | MAPE médio por item | Itens que superam o ingênuo | Itens liberados (RN10) |
|---|---|---|---|
| Ingênuo | | — | — |
| Regressão linear | | | |
| LSTM (`lstm01`) | | | |

**Tempo de treino.** O tempo por época fica em `saida\treino01\modelos\lstm01\treino.json`. Se cada época demorar demais, diminua `--amostras-por-epoca` (o padrão é 400000).

**Ajustes, comparando sempre na validação.** Mude uma coisa por vez, sempre com um `--nome` novo:
- `--unidades 128`
- `--perda mse`
- `--taxa 0.0005`
- janela de 60 dias: prepare uma base nova com `--janela 60 --saida saida\treino01_j60` e treine nela.
- eventos detalhados (um indicador por festival e pela Feira de Negrilua): prepare uma base nova com `--eventos-detalhados --saida saida\treino01_det` e treine nela com os mesmos parâmetros.
- `--mascara`: ignora, no erro do treino, os dias sem preço real.

Anote cada resultado na tabela. Fica a configuração que errar menos.

**Não avalie o teste no estudo.** O teste oficial (10% finais) é o do treinamento inicial no sistema, na etapa 3. Usá-lo duas vezes tiraria o valor dele (RN25).

Traga a tabela para o Claude no Cowork. Com ela, decidimos a configuração da rede e confirmamos se a LSTM vale a pena contra a regressão linear.

---

## Etapa 2c: o modelo prevê itens que não viu no treino?

A rede foi pensada para prever **qualquer item** com histórico, não só os do treino. Antes de levar o CU11 para o sistema, a etapa 2c mede isso no estudo:

- **Parte A:** 20% dos itens ficam fora do treino. O erro neles é comparado, item a item, com o de um modelo que os viu.
- **Parte B:** o modelo já treinado prevê 3.000 itens que a seleção do treino deixa de fora (equipamentos de reino, commodities pouco negociadas, itens com histórico curto).

1. Cole no Claude Code:

   ```
   Leia estudos/lstm/pedido-etapa2c.md e siga.
   ```

2. São 4 treinos de 10 a 25 minutos cada, mais as preparações: umas 2 horas no total.
3. Traga o `docs/relatorio-etapa2c.md` para o Claude no Cowork.
4. Com o resultado, o CU11 e as regras (RN02, RN10, RN15 e uma nova regra de histórico mínimo) são ajustados para separar quem **treina** o modelo de quem **recebe** projeção. Só depois disso siga para a etapa 3.

---

## Etapa 3: levar para o sistema (CU11)

> **Aguarde a etapa 2c** e a atualização do `docs/casos-de-uso/CU11-treinar-modelo.md`. O fluxo de seleção e liberação dos itens vai mudar.

1. **Pedido 2: Cenário 01, treinamento inicial.** Os resultados das etapas 1 e 2 já estão em `docs/relatorio-etapa1.md`, `docs/relatorio-etapa2.md` e `docs/relatorio-etapa2b.md`. Cole no Claude Code:

   ```
   Leia estudos/lstm/pedido-cu11-c1.md e siga, começando pelo plano.
   ```

   - No plano, ele vai perguntar as decisões pendentes. As recomendações estão no próprio CU11: serviço `modelo` separado, a configuração da etapa 2b (perda Huber, sem máscara, eventos agregados) e a RN07 desligada até você definir o nível.
   - Depois de pronto, **dispare o treinamento inicial pela tela do Admin**. Esse é o treino oficial da rede, com o teste de verdade.
2. **Pedido 3: Cenário 02, retreinamento semanal.** Cole:

   ```
   Implemente o CU11 Cenário 02 (retreinar o modelo periodicamente) conforme docs/casos-de-uso/CU11-treinar-modelo.md, nas mesmas regras do pedido do C1: plano primeiro, um teste por fluxo, mensagens exatas, valores configuráveis. Commit: feat(CU11): retreinamento semanal (C2).
   ```

3. **Pedido 4: Cenário 03, consolidação diária.** Cole:

   ```
   Implemente o CU11 Cenário 03 (consolidar predições diárias) conforme docs/casos-de-uso/CU11-treinar-modelo.md, nas mesmas regras do pedido do C1. No plano, proponha como agendar a importação incremental diária da Undermine (decisão pendente do CU11) antes de implementar. Commit: feat(CU11): consolidação diária das predições (C3).
   ```

---

## Etapa 4: escrever no TC

1. Traga para o Claude no Cowork os resumos finais dos três cenários, com as decisões tomadas e as pendências.
2. Atualizamos o documento de alterações (v2) com o que mudou na implementação e os números reais. Depois você cola no TC.
3. Por fim, reexportamos o `docs/` a partir do TC. Aí o CU11 deixa de ser provisório.
