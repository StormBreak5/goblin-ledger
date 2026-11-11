# Pedido ao Claude Code: implementar o CU06 (Manter Favoritos) e o CU07 (Manter Alerta)

Os dois casos de uso vão juntos porque um depende do outro:

- o alerta só existe para um item favorito (CU07-C1-FA1);
- remover um favorito remove os alertas dele (CU06-C2-FA1);
- a lista de favoritos mostra os alertas ativos de cada item (CU06-C3).

O texto dos dois está no TC (seções 6.4.6 e 6.4.7) e é igual ao de `docs/casos-de-uso/CU06-manter-favoritos.md` e `CU07-manter-alerta.md`.

**Pré-requisitos:**

- o `estudos/lstm/pedido-correcoes-orientacao.md` já executado. Com ele, o `CLAUDE.md` inclui o CU05 a CU08 na regra 1;
- de preferência, o CU05 já implementado (`pedido-cu05.md`), porque os dois mexem na tela do item. Se o CU05 ainda não estiver feito, avise no plano.

## O que fazer

1. **Leia antes de planejar:**
   - os dois arquivos dos casos de uso, inteiros, principalmente as "Observações para a implementação";
   - os diagramas `docs/diagramas-atualizados/cu06c01.png` a `cu06c03.png` e `cu07c01.png` a `cu07c03.png`;
   - os protótipos do TC em `docs/prototipos/`:
     - `rf09-favoritos.png` (Figura 21, lista de favoritos);
     - `rf05-alertas.png` (Figura 15, tela do item com o controle "Favoritado" e a seção "Alertas de preço");
     - `rf05-criar-alerta.png` (Figura 16, formulário do alerta);
   - o código desses protótipos em `docs/prototipos/codigo/`. Leia o `README.md` de lá. É referência visual, com dados fixos, e não código para copiar;
   - o código do CU01 e do CU02:
     - autenticação pelo token (`controllers/deps.py`, `LoginService.usuario_da_sessao`);
     - exclusão da conta com `ON DELETE CASCADE` (`usuario_repository.excluir_com_dados_vinculados`, RN20);
     - no frontend, `lib/auth.ts`, `components/AuthNav.tsx` e `components/Toast.tsx`;
   - o código do CU04 (tela do item, valor de mercado do cabeçalho em `ItemService.get_current_auctions` e frescor em `ItemService._frescor`) e o `lib/moeda.ts`;
   - as migrações em `backend/src/migrations/versions/`.
2. **Implemente o CU06 e depois o CU07**, com um commit para cada um.
3. **Comece em modo de planejamento.** Proponha:
   - a migração;
   - os arquivos a criar e a alterar;
   - os endpoints;
   - a lista de testes, um por fluxo, com os nomes dos arquivos dos CUs.
4. **Espere a minha aprovação antes de implementar.**

## Já decidido, não pergunte

### Banco de dados

- Uma migração Alembic, a próxima da sequência (`0011_favoritos_e_alertas`), com as duas tabelas, no commit do CU06. O CU06-C2 e o C3 já usam a tabela de alertas.
- **`favorito`**, como no MR:
  - `id_usuario` INTEGER, PK e FK para `usuario`, com `ON DELETE CASCADE`;
  - `item_id` INTEGER, PK. É o ID externo do item, o mesmo de `historical_item_prices`;
  - `data_inclusao` TIMESTAMPTZ.
- **`alerta_preco`**, como no MR:
  - `id_alerta` INTEGER (PK), `id_usuario` INTEGER (FK para `usuario`, `ON DELETE CASCADE`) e `item_id` INTEGER;
  - `tipo` VARCHAR(10) (`COMPRA`/`VENDA`), `preco_alvo` BIGINT em Cobre, `canal` VARCHAR(5) (`WEB`/`EMAIL`/`AMBOS`) e `situacao` VARCHAR(9) (`ATIVO`/`DISPARADO`);
  - `criado_em` e `atualizado_em` TIMESTAMPTZ, e `disparado_em` TIMESTAMPTZ, que pode ser nulo;
  - FK composta (`id_usuario`, `item_id`) para `favorito`, com `ON DELETE CASCADE`.
- Com isso, a exclusão da conta (CU01-C3, RN20) remove favoritos e alertas sem mudar o CU01. Crie o teste `test_cu06_exclusao_da_conta_remove_favoritos_e_alertas_rn20`.

### CU06 – Manter Favoritos

- **API**, toda autenticada pelo token, com 401 sem sessão válida:
  - `POST /favorites/{item_id}` (C1). O item já favoritado não é erro: responde com o estado "Favoritado" (FA2);
  - `DELETE /favorites/{item_id}` (C2):
    - sem `?confirmar=true` e com alertas do item, responde 409 com a mensagem do FA1 e não remove nada;
    - com `?confirmar=true`, remove os alertas e o favorito numa única transação. Se algo falhar, desfaz tudo (FE1);
  - `GET /favorites` (C3).
  - `GET /items/{item_id}` passa a informar se o item é favorito, quando houver um token válido. Sem token, continua público, como hoje.
- **C1-FA1 (não autenticado):** o controle "Favoritar" leva à tela de login com a mensagem "Entre na sua conta para favoritar itens". Proponha no plano como a mensagem chega à tela de login e, se o CU02 já tiver um destino de retorno depois do login, use-o.
- **C3:**
  - **Valor de mercado atual:** o mesmo do cabeçalho da tela do item, o primeiro quartil da RN06 (`ItemService.get_current_auctions`), calculado de uma vez para a lista;
  - **Variação em relação ao dia anterior:** valor de mercado atual contra o valor de mercado do ponto horário da Blizzard em `historical_item_prices` mais próximo de 24 horas antes, em percentual com uma casa decimal. Sem esse ponto, a variação fica "—";
  - **Dados Desatualizados (FA2):** a mesma regra do CU04 (`ItemService._frescor`: RN09 com o limiar de 24 h e RN14). Torne a função reutilizável em vez de copiá-la;
  - **Ficha do WoW:** pode ser favoritada. O valor dela vem da última coleta, como no CU04;
  - **Ordem:** alfabética pelo nome do item.
- **Telas, seguindo os protótipos:**
  - controle "Favoritar"/"Favoritado" no cabeçalho da tela do item, abaixo do nome (Figura 15);
  - link "Favoritos" no cabeçalho, só para o usuário autenticado, e a página `/favoritos` (Figura 21), com as colunas:
    - Item: ícone, nome e o selo "Dados Desatualizados" quando for o caso;
    - Valor de mercado;
    - Variação (dia anterior), em verde quando sobe e em vermelho quando cai;
    - Alertas ativos;
    - Ações: "Remover".
  - Selecionar um item abre a tela dele (C3, passo 5). A remoção pela lista ou pelo controle "Favoritado" segue o C2, com a confirmação do FA1 num diálogo.
- **Mensagens:** exatamente as do CU06:
  - "Item adicionado aos favoritos";
  - "Item removido dos favoritos";
  - "Este item possui alertas de preço, que também serão excluídos. Deseja continuar?";
  - "Você ainda não tem itens favoritos. Use a busca para encontrar itens e favoritá-los";
  - "Não foi possível atualizar os favoritos no momento. Tente novamente mais tarde";
  - "Não foi possível carregar os seus favoritos no momento. Tente novamente mais tarde" (C3-FE1).

### CU07 – Manter Alerta

- **API**, toda autenticada e só sobre os alertas do próprio usuário. O alerta de outro usuário responde 404 (`test_cu07_so_o_dono_altera_e_exclui_o_alerta`).
  - `GET /items/{item_id}/alerts` lista os alertas do usuário para o item, com a quantidade de alertas ativos do usuário em todos os itens e o limite. É a linha "Você tem X de 20 alertas ativos em todos os seus itens" do protótipo.
  - `GET /items/{item_id}/alerts/new` faz os passos 2 a 4 do C1 antes de abrir o formulário:
    - item fora dos favoritos: 409 com a mensagem do FA1;
    - limite atingido: 409 com a mensagem do FA2;
    - senão, devolve o valor de mercado atual do item, como referência.
  - `POST /items/{item_id}/alerts` confere de novo o favorito e o limite e registra o alerta como `ATIVO`.
  - `GET /alerts/{id}/edit` faz os passos 1 e 2 do C2:
    - devolve os dados atuais e o valor de mercado atual;
    - se o alerta estiver `DISPARADO`, confere antes o limite (C2-FA1 e FA2), com a mensagem "… para reativar este".
  - `PUT /alerts/{id}` altera e, se for o caso, reativa:
    - o alerta fica `ATIVO`, com `disparado_em` nulo;
    - na reativação, o limite é conferido de novo.
  - `DELETE /alerts/{id}` remove o alerta (C3). A confirmação "Deseja excluir este alerta?" é um diálogo da tela.
- **RN08 (cota):**
  - conta só os alertas `ATIVO` do usuário, em todos os itens;
  - o limite é `ALERTAS_MAXIMO_ATIVOS` = 20, em `backend/.env.example`;
  - a contagem e a gravação ficam na mesma transação, com bloqueio da linha do usuário (`SELECT … FOR UPDATE`), para dois pedidos simultâneos não passarem do limite.
- **Preço-alvo (RN01):** o formulário tem três campos, Ouro, Prata e Cobre. A API recebe os três inteiros e converte para Cobre no backend.
- **Dados inválidos (FA3):** conta como inválido:
  - o tipo ou o canal ausente;
  - o preço-alvo total zero;
  - qualquer parte negativa;
  - Prata ou Cobre acima de 99.

  A validação é do serviço. A resposta traz a mensagem do FA3, e não o erro padrão de validação do Pydantic.
- **Tela, seguindo os protótipos (Figuras 15 e 16):**
  - a seção "Alertas de preço" na tela do item aparece só para o usuário autenticado, com o botão "Criar alerta" e uma tabela com as colunas:
    - Tipo de gatilho: "Compra (preço cair até o alvo)" ou "Venda (preço subir até o alvo)";
    - Preço-alvo, em Ouro, Prata e Cobre;
    - Canal: `WEB` = "Tela", `EMAIL` = "E-mail", `AMBOS` = "Tela e e-mail";
    - Situação: "Ativo", ou "Disparado em dd/mm/aaaa às hh:mm", no fuso local, como o CU04;
    - Ações: "Editar" (ou "Editar e reativar", quando disparado) e "Excluir".
  - O formulário é um diálogo com:
    - o item e o valor de mercado atual;
    - o tipo de gatilho em dois cartões (Compra/Venda, com as descrições do protótipo);
    - os três campos do preço-alvo;
    - o canal em três opções: Tela, E-mail e Ambos;
    - os botões "Cancelar" e "Salvar alerta".
  - **C1-FA1:** a mensagem "Para criar um alerta, adicione o item aos favoritos" aparece com a opção de favoritar. Favoritando (CU06-C1), o fluxo volta ao passo 3: confere o limite e abre o formulário.
- **Mensagens:** exatamente as do CU07, inclusive:
  - "Alerta criado com sucesso";
  - "Alerta atualizado com sucesso";
  - "Alerta excluído com sucesso";
  - as duas variações da mensagem de limite, no C1 e no C2;
  - as mensagens dos fluxos de exceção.
- **O que fica para o CU08:** disparar alertas e notificar. Neste pedido o alerta só passa a `DISPARADO` nos testes, por inserção direta.

## Regras

- Siga o `CLAUDE.md`:
  - type hints;
  - Pydantic nas bordas da API;
  - TypeScript sem `any`;
  - regra de negócio só no backend;
  - RN01 em Cobre;
  - datas em UTC;
  - docstrings citando o CU e a RN.
- Um teste por fluxo, com os nomes das listas dos dois CUs. Os testes de tela ficam em `frontend/tests/`, com os prefixos `cu06-` e `cu07-`.
- Não altere as funções de teste dos outros casos de uso. O CU04 e o CU05 continuam passando.
- **Não leia nem altere arquivos `.env`.**

## Depois de implementar (ao fim de cada CU)

1. Rode a suíte do backend no host e a do frontend, com `npm test`, `npm run lint` e `npx tsc --noEmit`.
2. Confira no navegador, com um usuário de teste. Salve as capturas em `docs/capturas/`, em PNG com escala 2:
   - **CU06:**
     - favoritar e desfavoritar pela tela do item;
     - a lista com pelo menos três itens;
     - a lista vazia;
     - a remoção de um item com alerta, com o diálogo de confirmação.
   - **CU07:**
     - criar um alerta de compra e um de venda;
     - os dados inválidos;
     - editar;
     - excluir;
     - a mensagem do item fora dos favoritos;
     - um alerta disparado (marcado direto no banco de teste) sendo reativado.
3. Atualize a documentação, que entra no commit de cada CU:
   - a "Situação no código" do CU;
   - `docs/plano-de-testes-por-fluxo.md`;
   - `docs/casos-de-uso/README.md`.
4. Faça os commits:
   - `feat(CU06): manter favoritos (C1 a C3)`;
   - `feat(CU07): manter alerta de preço (C1 a C3, RN08)`.

## O que devolver

1. O que ficou pendente e as decisões que você tomou, para eu atualizar o texto do TC.
2. A quantidade de funções de teste por cenário de cada CU, separando backend e frontend. Esses números vão para o Quadro 82 do TC.
3. Para cada cenário, se o resultado esperado dos Quadros 76 (CU06) e 77 (CU07) do TC foi obtido na conferência pelo navegador.
