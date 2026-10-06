# Pedido ao Claude Code: implementar o CU11, Cenário 01 (treinamento inicial)

Esta é a **etapa 3 de `estudos/lstm/ROTEIRO.md`**. As etapas 1 (preparação) e 2 (primeiro treino no estudo) já foram feitas.

## Autorização do autor

O CU11 ainda não está no documento do TC. **Decidi implementá-lo e testá-lo antes de escrevê-lo.** A especificação provisória está em `docs/casos-de-uso/CU11-treinar-modelo.md`.

Antes do plano, faça estes três ajustes:

1. No `CLAUDE.md`, inclua o CU11 na regra 1 com a observação "provisório: especificado em `docs/casos-de-uso/CU11-treinar-modelo.md`, ainda fora do TC; as RNs desse arquivo prevalecem sobre `docs/regras-de-negocio.md`".
2. Ainda no `CLAUDE.md`, acrescente "→ CU11 (C1 → C2 → C3)" na "Ordem sugerida".
3. Em `docs/casos-de-uso/README.md`, na seção "Escopo da implementação atual", registre o CU11 como provisório.

## O que fazer

1. **Leia antes de planejar:**
   - `docs/casos-de-uso/CU11-treinar-modelo.md`, inteiro, principalmente as "Observações para a implementação";
   - `estudos/lstm/README.md` e o código do estudo, que é a implementação de referência do pipeline;
   - o resumo da etapa 1 (números do banco real) e os resultados da etapa 2 (configuração escolhida para a rede). Vou colar os dois abaixo.
2. **Implemente somente o Cenário 01.** O C2 e o C3 vêm em pedidos separados, mas o desenho das tabelas já deve atender aos três.
3. **Comece em modo de planejamento.** Proponha:
   - os arquivos a criar e a alterar;
   - a migração do Alembic;
   - o novo serviço do `docker-compose`;
   - o endpoint e a tela do Admin;
   - a lista de testes, um por fluxo, com os nomes do CU11.
4. **No plano, pergunte as decisões pendentes,** cada uma com a sua recomendação:
   - onde o TensorFlow roda (sugestão: serviço `modelo` com `python:3.11-slim`);
   - a função de perda;
   - o nível mínimo da RN07 (sugestão: desligado e configurável);
   - os nomes e campos das tabelas.
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
- **Porte, não reescreva do zero.** Traga as fórmulas de `estudos/lstm/` (variáveis, normalização, divisão 70/20/10, janelas, desnormalização, métricas) e os testes de regra listados no CU11. O estudo pode continuar existindo como está.
- **Use dados sintéticos e um modelo mínimo nos testes** (`gerar_sinteticos.py`; LSTM de 4 unidades, 1 época), para a suíte continuar rápida.
- **Mensagens:** exatamente as do cenário.
- **Valores a confirmar:** configuráveis por variável de ambiente (a tabela do CU11). Atualize `backend/.env.example`.
- **Não leia nem altere arquivos `.env`.**

## Depois de implementar

1. Rode o `pytest` do backend e, se mexer no frontend, `npm run lint` e `npx tsc --noEmit`.
2. Suba os containers e **dispare o treinamento inicial pela tela do Admin**, com os dados reais e a região US.
3. Traga o resumo:
   - itens liberados, bloqueados e ignorados;
   - MAPE médio do modelo e do ingênuo no teste;
   - tempo total e tempo por época;
   - versão gravada.
4. Faça o commit `feat(CU11): treinamento inicial do modelo global (C1)`.
5. Liste o que ficou pendente e as decisões tomadas, para eu atualizar o texto do TC.

## Resultados das etapas anteriores

(cole aqui o resumo da etapa 1 e a tabela da etapa 2)
