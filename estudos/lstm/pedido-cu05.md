# Pedido ao Claude Code: implementar o CU05 (Consultar Previsão Preditiva)

> Revisado em 11/11/2026. A versão de 20/10 previa o CU05 como provisório e usava a RN07 antiga (nível de item). Esta versão substitui aquela.

O CU11 está completo (C1, C2 e C3, commits `83bebfb` e `c5e3d88`). O C3 grava todo dia as previsões dos próximos 7 dias dos itens com projeção liberada. O CU05 é a tela que mostra essas previsões ao usuário, no gráfico do histórico do item (CU04). O texto do CU05 está no TC (seção 6.4.5) e é igual ao de `docs/casos-de-uso/CU05-consultar-previsao-preditiva.md`.

**Pré-requisito:** o `estudos/lstm/pedido-correcoes-orientacao.md` já executado. Com ele:

- a RN07 do nível de item saiu do código;
- o `CLAUDE.md` passou a incluir o CU05 a CU08 na regra 1.

Se não estiver assim, pare e me avise.

## O que fazer

1. **Leia antes de planejar:**
   - `docs/casos-de-uso/CU05-consultar-previsao-preditiva.md`, inteiro, principalmente as "Observações para a implementação";
   - os diagramas `docs/diagramas-atualizados/cu05c01.png`, `cu05c02.png` e `cu05c03.png`;
   - o protótipo do TC, `docs/prototipos/rf04-projecao.png` (Figura 14), e o código dele, `docs/prototipos/codigo/rf04-projecao.html`, só como referência visual;
   - o código do CU04:
     - no frontend, `frontend/app/item/[id]/page.tsx`, `components/PriceChart.tsx`, `components/TooltipDoPonto.tsx`, `lib/historicoDoItem.ts`, `lib/useHistoricoDoItem.ts` e `lib/moeda.ts`;
     - no backend, o controller e o serviço do histórico;
   - as tabelas do CU11 em `backend/src/models/modelo.py` (`ProjecaoItem` e `PredicaoDiaria`) e os critérios de elegibilidade em `backend/src/ml/selecao.py`.
2. **Implemente os três cenários.** O CU é pequeno e os três dividem a mesma tela.
3. **Comece em modo de planejamento.** Proponha os arquivos a criar e a alterar, o endpoint e a lista de testes, um por fluxo, com os nomes do CU05.
4. **Espere a minha aprovação antes de implementar.**

## Já decidido, não pergunte

- **API:** `GET /items/{item_id}/projection`, sem autenticação, e na mesma região do histórico (hoje, US). A resposta traz:
  - a situação e a mensagem;
  - a data de referência da projeção;
  - o preço diário do dia de referência;
  - o erro típico;
  - as predições a exibir (data prevista, preço em Cobre e variação);
  - o indicador de desatualizada.

  As mensagens vêm do backend, com o texto exato dos fluxos, como nos avisos do CU04. Uma falha de banco responde 503 com a mensagem do FE1.
- **Situação e fluxo:** siga a tabela das observações do CU05.
- **FA2:** a elegibilidade é **RN02 e RN27**. A RN07 não é mais critério.
  - Para um item fora de `projecao_item`, ou com o motivo "deixou de ser elegível", a API recalcula na hora os critérios só desse item, em SQL e com as mesmas definições do `selecao.py`:
    - RN02: a média da quantidade nos últimos 7 dias encerrados da série diária da Undermine;
    - RN27: os dias desde o primeiro registro diário.
  - Se os dois critérios falharem, vale a mensagem da RN02.
  - Crie um teste no container do `modelo` que confira, com os mesmos dados sintéticos, que o critério da API e o do `selecao.py` dão o mesmo resultado.
  - O teste do fluxo se chama `test_cu05_c1_fa2_item_nao_elegivel_rn02_rn27`.
- **Série:** é a da região. Para as commodities, é a série de commodities. Para itens de reino com mais de uma série, vale a com projeção liberada. Havendo mais de uma, vale a de maior quantidade média ofertada.
- **Predições exibidas:**
  - as de `data_previsao` mais recente da versão vigente, só com `data_prevista` a partir de hoje (UTC);
  - a projeção está desatualizada (FA7) quando a data de referência fica mais de `PROJECAO_DESATUALIZADA_DIAS` (2) dias atrás do último dia encerrado;
  - sem nenhum dia a exibir, vale o FA6.
- **Ponto de partida e variação:** a linha começa no preço diário do dia de referência, o mesmo que o C3 usou como base da previsão. A variação é calculada sobre esse preço.
- **Erro típico:** o `mdape` de `projecao_item`, arredondado para inteiro.
- **Tela, seguindo o protótipo:**
  - **Linha da projeção:**
    - tracejada, numa cor própria (no protótipo, `#A78BFA`; crie um token em `globals.css`), com a legenda "Projeção (menor preço diário)";
    - o eixo do tempo se estende pelos dias previstos, e a escala inclui a projeção;
    - ao trocar a janela de tempo (CU04-C2), a projeção continua presa ao fim do histórico.
  - **Abaixo do gráfico:**
    - a linha "Projeção gerada em ..., a partir do menor preço diário de ...";
    - "Erro mediano de X% nas previsões deste item";
    - o aviso "A projeção é uma estimativa estatística e não garante o preço futuro";
    - o alerta "Projeção desatualizada" (FA7);
    - a tabela da projeção.
  - **Projeção indisponível (FA1 a FA6):** a mensagem fica no lugar da projeção, e o histórico continua normal.
  - **Tooltip (C2):**
    - mostra "PROJEÇÃO", a data com "dia inteiro", o preço em Ouro, Prata e Cobre (com `moeda.ts`) e a variação;
    - o ponto do gráfico e a linha da tabela se destacam juntos, apontando por qualquer um dos dois;
    - no ponto de partida, vale o tooltip do histórico (C2-FA1);
    - uma falha na conversão omite o tooltip e registra no console (C2-FE1, como o CU04-C3).
  - **Controle "Projeção" (C3):**
    - fica na barra das janelas de tempo e só aparece quando a projeção está disponível;
    - ocultar esconde a linha e a tabela e recalcula a escala;
    - a escolha fica no `sessionStorage`, com leitura e gravação protegidas por try/catch.
- **CU04:** não mude o comportamento do CU04 além de acrescentar a projeção. Os testes dele têm que continuar passando.
- **Valor configurável:** `PROJECAO_DESATUALIZADA_DIAS` = 2, em `backend/.env.example`.
- **Testes de tela:** em `frontend/tests/`, com o prefixo `cu05-`, como os do CU04.

## Regras

- Siga o `CLAUDE.md`:
  - type hints;
  - Pydantic nas bordas da API;
  - TypeScript sem `any`;
  - regra de negócio só no backend;
  - RN01 em Cobre;
  - datas em UTC;
  - docstrings citando o CU e a RN.
- Um teste por fluxo, com os nomes da lista do CU05, no backend e no frontend conforme o fluxo.
- Não altere as funções de teste dos outros casos de uso.
- **Não leia nem altere arquivos `.env`.**

## Depois de implementar

1. Rode as três suítes:
   - a do backend no host;
   - a do container do `modelo`;
   - a do frontend, com `npm test`, `npm run lint` e `npx tsc --noEmit`.
2. Abra no navegador, com os dados reais, três itens:
   - um com projeção liberada pela versão vigente (pegue um em `projecao_item` com a situação `LIBERADA`);
   - um bloqueado;
   - um não elegível.

   Teste também ocultar e mostrar a projeção e o tooltip de um dia previsto. Salve as capturas em `docs/capturas/`, em PNG com escala 2. A do item liberado pode substituir o protótipo no TC.
3. Atualize a documentação, que entra no commit:
   - a "Situação no código" do CU05;
   - `docs/plano-de-testes-por-fluxo.md`;
   - `docs/casos-de-uso/README.md`.
4. Faça o commit `feat(CU05): consultar previsão preditiva (C1 a C3)`.

## O que devolver

1. O que ficou pendente e as decisões que você tomou, para eu atualizar o texto do TC.
2. A quantidade de funções de teste por cenário (C1, C2 e C3), separando backend, container do `modelo` e frontend. Esses números vão para o Quadro 82 do TC.
3. Para cada cenário, se o resultado esperado do Quadro 75 do TC foi obtido na conferência pelo navegador:
   - C1: a projeção dos próximos 7 dias em continuação ao histórico, com a tabela e o erro típico, ou o motivo da indisponibilidade;
   - C2: a data, o preço previsto e a variação do dia selecionado, identificados como projeção;
   - C3: ocultar e voltar a exibir a linha e a tabela, com a escala recalculada e a escolha mantida na sessão.
