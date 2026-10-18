# Pedido ao Claude Code: implementar o CU11, Cenário 01 (treinamento inicial)

> **Antes de usar este pedido,** confira se a etapa 2f (`pedido-etapa2f.md`) já foi feita e se `docs/relatorio-etapa2f.md` existe. Se ela ainda não foi feita, faça-a primeiro: é a última medição do estudo.

Esta é a **etapa 3 de `estudos/lstm/ROTEIRO.md`**. As etapas 1 (preparação) e 2 a 2f (treino, escolha da configuração e generalização, no estudo) já foram feitas. A configuração da rede está congelada (seção "Configuração final" do `estudos/lstm/README.md`).

## Autorização do autor

O CU11 já está no documento do TC (seção 6.4.11), mas o TC ainda não tem as mudanças da v4 do documento de alterações (`docs/Alterações do TC - modelo global (para colar) v4.docx`). A v4 separa os itens que treinam o modelo dos itens que recebem projeção, cria a RN27 e põe o mínimo de 30 dias avaliados na RN10. **Decidi implementar o CU11 com o texto da v4 antes de reexportar o `docs/`.** A especificação está em `docs/casos-de-uso/CU11-treinar-modelo.md`, que já traz a v4.

Antes do plano, faça estes três ajustes:

1. No `CLAUDE.md`, inclua o CU11 na regra 1 com a observação "provisório: especificado em `docs/casos-de-uso/CU11-treinar-modelo.md`, com a v4 do documento de alterações; as RNs desse arquivo prevalecem sobre `docs/regras-de-negocio.md` e `docs/requisitos.md`". Tire o CU11 da lista dos não especificados.
2. Ainda no `CLAUDE.md`, acrescente "→ CU11 (C1 → C2 → C3)" na "Ordem sugerida".
3. Em `docs/casos-de-uso/README.md`, na seção "Escopo da implementação atual", registre o CU11 como provisório e tire-o da lista dos que não devem ser implementados.

## O que fazer

1. **Leia antes de planejar:**
   - `docs/casos-de-uso/CU11-treinar-modelo.md`, inteiro, principalmente as "Observações para a implementação" e a tabela "Itens que treinam o modelo e itens que recebem projeção";
   - os diagramas `docs/diagramas-atualizados/cu11c01.png`, `cu11c02.png` e `cu11c03.png`;
   - `estudos/lstm/README.md` e o código do estudo, que é a implementação de referência do pipeline, inclusive `prever.py` e a opção `--normalizacao-de` do `preparar_dados.py`, que mostram como prever itens fora do treino;
   - os relatórios `docs/relatorio-etapa1.md` a `docs/relatorio-etapa2f.md`: números do banco real, resultados e decisões.
2. **Implemente somente o Cenário 01.** O C2 e o C3 vêm em pedidos separados, mas o desenho das tabelas já deve atender aos três.
3. **Comece em modo de planejamento.** Proponha:
   - os arquivos a criar e a alterar;
   - a migração do Alembic;
   - o novo serviço do `docker-compose`;
   - o endpoint e a tela do Admin;
   - a lista de testes, um por fluxo, com os nomes do CU11 (inclusive o FA5 e os testes da RN10 e da RN27).
4. **No plano, pergunte as decisões pendentes,** cada uma com a sua recomendação:
   - onde o TensorFlow roda (sugestão: serviço `modelo` com `python:3.11-slim`);
   - o nível mínimo da RN07 (sugestão: desligado e configurável);
   - os nomes e campos das tabelas.

   **Já decidido, não pergunte:**
   - a configuração da rede é a final, congelada depois da etapa 2e:
     - variáveis 1 a 18, com a 14 agregada;
     - janela de 30 dias, sem máscara;
     - **perda MAE**;
     - os demais padrões do `treinar.py`;
   - os conjuntos:
     - itens elegíveis à projeção = RN02 ∩ RN07 ∩ RN27;
     - conjunto de treinamento = elegíveis ∩ RN15;
     - o C1 avalia no teste **todos** os elegíveis, inclusive os que não treinaram;
   - a RN10 libera o item com MdAPE ≤ 15%, menor que o do ingênuo e medido em pelo menos 30 dias avaliados. Abaixo disso, a projeção fica bloqueada com o motivo "avaliação insuficiente" (FA5);
   - a RN27 exige 60 dias de histórico diário;
   - a RN03 é a do estudo, com EMA dos preços aceitos e confirmação de patamar;
   - a divisão é 70/20/10 por data.
5. **Espere a minha aprovação antes de implementar.**

## Regras

- Siga o `CLAUDE.md`:
  - type hints;
  - Pydantic nas bordas da API;
  - TypeScript sem `any`;
  - regra de negócio só no backend;
  - RN01 em Cobre;
  - datas em UTC;
  - docstrings citando o CU e a RN.
- **Porte, não reescreva do zero.** Traga as fórmulas de `estudos/lstm/` (variáveis, normalização, divisão 70/20/10, janelas, desnormalização, métricas, RN10 com o mínimo de dias) e os testes de regra listados no CU11. O estudo pode continuar existindo como está.
- **Constantes de normalização:** calculadas só com o período de treinamento do conjunto de treinamento e aplicadas a todos os elegíveis (RN24 e RN25).
- **Use dados sintéticos e um modelo mínimo nos testes** (`gerar_sinteticos.py`; LSTM de 4 unidades, 1 época), para a suíte continuar rápida.
- **Mensagens:** exatamente as do cenário.
- **Valores configuráveis:** por variável de ambiente, como na tabela do CU11. Atualize `backend/.env.example`.
- **Não leia nem altere arquivos `.env`.**

## Depois de implementar

1. Rode o `pytest` do backend e, se mexer no frontend, `npm run lint` e `npx tsc --noEmit`.
2. Suba os containers e **dispare o treinamento inicial pela tela do Admin**, com os dados reais e a região US.
3. Traga o resumo, com os números do **período de teste**, que aqui é usado pela primeira vez (RN25):
   - itens elegíveis e itens do conjunto de treinamento;
   - itens liberados, bloqueados (separados por motivo: acima do limiar, não supera o ingênuo, avaliação insuficiente) e ignorados;
   - quantos liberados não integram o conjunto de treinamento;
   - mediana do MdAPE e do MAPE por item, do modelo e do ingênuo, e quantos itens superam o ingênuo;
   - tempo total e tempo por época;
   - versão gravada.
4. Faça o commit `feat(CU11): treinamento inicial do modelo global (C1)`.
5. Liste o que ficou pendente e as decisões tomadas, para eu atualizar o texto do TC.
