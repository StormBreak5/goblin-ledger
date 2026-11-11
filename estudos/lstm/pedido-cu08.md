# Pedido ao Claude Code: implementar o CU08 (Manter Notificações)

O CU08 fecha o ciclo dos alertas de preço:

- **C1:** a cada ciclo de ingestão, o sistema confere os alertas ativos e registra as notificações dos alertas atingidos;
- **C2:** envia por e-mail as que têm esse canal;
- **C3:** o usuário consulta as notificações pelo sino do cabeçalho.

O texto está no TC (seção 6.4.8) e é igual ao de `docs/casos-de-uso/CU08-manter-notificacoes.md`. A regra do gatilho é a **RN07 – Gatilho e Disparo Único do Alerta** (a antiga RN28).

**Pré-requisitos:**

- o `pedido-correcoes-orientacao.md` já executado;
- o CU06 e o CU07 já implementados (`pedido-cu06-cu07.md`), com as tabelas `favorito` e `alerta_preco`.

Se não estiver assim, pare e me avise.

## O que fazer

1. **Leia antes de planejar:**
   - `docs/casos-de-uso/CU08-manter-notificacoes.md`, inteiro, principalmente as "Observações para a implementação";
   - a RN07 em `docs/regras-de-negocio.md`;
   - os diagramas `docs/diagramas-atualizados/cu08c01.png` a `cu08c03.png`;
   - os protótipos do TC em `docs/prototipos/`:
     - `rf06-notificacoes.png` (Figura 17, sino e painel);
     - `rf06-email.png` (Figura 18, e-mail);
   - o código desses protótipos em `docs/prototipos/codigo/` (`rf06-SinoDeNotificacoes.tsx`, `rf06-email.page.tsx` e `AuthNav.com-favoritos-e-sino.tsx`). Leia o `README.md` de lá. É referência visual, com dados fixos, e não código para copiar;
   - o ciclo de ingestão do CU09:
     - `services/ingestao_service.py`, principalmente o `executar` e o `_consolidar` (CU09-C3);
     - `services/rodada_de_ingestao.py`;
     - a ingestão manual do Admin em `controllers/mercado_controller.py` (CU09-C4);
   - o envio de e-mail do CU02-C2, em `services/email_service.py`, com o Mailpit do docker-compose;
   - o código do CU06 e do CU07, e o `components/AuthNav.tsx` no frontend.
2. **Implemente os três cenários.**
3. **Comece em modo de planejamento.** Proponha:
   - a migração;
   - o ponto exato do ciclo de ingestão onde a verificação entra;
   - os arquivos a criar e a alterar;
   - os endpoints;
   - a lista de testes, um por fluxo, com os nomes do CU08.
4. **Espere a minha aprovação antes de implementar.**

## Já decidido, não pergunte

### Banco de dados

- Migração Alembic, a próxima da sequência (`0012_notificacoes`).
- **`notificacao`**, como no MR:
  - `id_notificacao` INTEGER (PK);
  - `id_alerta` INTEGER, FK para `alerta_preco` com `ON DELETE SET NULL`. A notificação guarda os dados do disparo e continua no histórico do usuário se o alerta for excluído (CU07-C3) ou o favorito removido (CU06-C2);
  - `id_usuario` INTEGER, FK para `usuario` com `ON DELETE CASCADE` (RN20);
  - `item_id` INTEGER;
  - `tipo` VARCHAR(10);
  - `preco_alvo` e `valor_mercado` BIGINT, em Cobre;
  - `canal` VARCHAR(20);
  - `disparada_em` TIMESTAMPTZ;
  - `lida_em` TIMESTAMPTZ, que pode ser nulo;
  - `envio_email` VARCHAR(8): `PENDENTE`, `ENVIADO` ou `FALHOU`, nulo quando o canal é só `WEB`;
  - `tentativas_email` SMALLINT;
  - `enviada_em` TIMESTAMPTZ, que pode ser nulo.
- Crie o teste `test_cu08_exclusao_da_conta_remove_notificacoes_rn20`.

### C1 – Verificar alertas e disparar notificações

- **Onde entra:** logo depois de cada ciclo do CU09-C3 concluído com sucesso, no próprio `IngestaoService`. Assim vale para o ciclo agendado e para a ingestão manual do Admin (CU09-C4).
  - Roda numa transação própria, depois do commit da consolidação. Uma falha no CU08 não muda o resultado do ciclo do CU09.
- **Itens do ciclo:** os que tiveram ponto gravado no ciclo (`pontos` do `_consolidar`).
- **Valor de mercado atual (RN06):** o valor do ponto do item nesse ciclo.
- **Volume anômalo (FA2):** a marca de anomalia desse mesmo ponto (RN12). Os alertas desse item não são verificados no ciclo.
- **Gatilho (RN07):**
  - `COMPRA` dispara quando o valor de mercado ≤ preço-alvo;
  - `VENDA` dispara quando o valor de mercado ≥ preço-alvo.
- **Disparo único:** a troca de `ATIVO` para `DISPARADO` é condicional (`UPDATE … WHERE situacao = 'ATIVO'`, ou equivalente). Dois ciclos simultâneos não geram duas notificações do mesmo alerta (`test_rn07_alerta_dispara_uma_unica_vez`).
  - O alerta guarda `disparado_em`.
  - A notificação guarda o item, o tipo, o preço-alvo, o valor que o atingiu, o canal e a data e a hora.
  - `envio_email` começa como `PENDENTE` quando o canal é `EMAIL` ou `AMBOS`.
- **Região:** a mesma do histórico do CU04 (hoje, US). Não filtre os alertas pela região do usuário.
- **FE1:** a verificação inteira fica numa transação. Se falhar, desfaz tudo e registra em log. Os alertas continuam `ATIVO` e são verificados de novo quando o item aparecer no próximo ciclo.
- **Passo 8:** um log com os itens verificados, os ignorados por anomalia, os alertas atingidos e as notificações de e-mail encaminhadas.
- **Ficha do WoW:** a cotação dela é coletada pela rotina de 15 minutos do `worker.py`, fora do ciclo do CU09. Proponha no plano como verificar os alertas dela. Sugestão: o mesmo serviço, ao fim de cada coleta da Ficha, sem a RN12, que não se aplica.

### C2 – Enviar notificação por e-mail

- **Quando:** logo depois do C1, na mesma rotina. Processa todas as notificações com `envio_email = PENDENTE`, inclusive as que ficaram de ciclos anteriores.
- **Tentativas:**
  - no máximo `NOTIFICACAO_EMAIL_TENTATIVAS` = 3, em `backend/.env.example`, uma por ciclo;
  - em cada falha, soma uma tentativa;
  - na terceira falha, marca como `FALHOU` e registra em log (FA1).
- **Envio:** com o mesmo `EmailService` do CU02-C2. Crie um método novo e reaproveite a configuração SMTP.
  - A falha de um e-mail não impede os outros.
  - O envio não segura a transação do C1.
- **Mensagem, seguindo o protótipo (Figura 18):**
  - **Assunto:** "Alerta de preço atingido – {nome do item}".
  - **Título:** "Seu alerta de preço foi atingido", e a frase "O valor de mercado do item {item} atingiu o preço do seu alerta de {compra|venda}."
  - **Quadro:**
    - Item;
    - Tipo do alerta: "Compra (preço cair até o alvo)" ou "Venda (preço subir até o alvo)";
    - Preço-alvo e Valor de mercado, em Ouro, Prata e Cobre, no mesmo formato do `lib/moeda.ts` (`12g 49s 30c`);
    - Data e hora, no horário de Brasília (`dd/mm/aaaa às hh:mm`).
  - **Botão:** "Ver o item no Goblin Ledger", com o link `{FRONTEND_URL}/item/{item_id}` (a variável `FRONTEND_URL` já existe no `.env.example`).
  - **Aviso:** "O alerta foi desativado após o disparo. Para voltar a acompanhar o preço, reative-o na seção "Alertas de preço" da tela do item."
  - **Rodapé:** "Você recebeu este e-mail porque configurou um alerta de preço no Goblin Ledger com notificação por e-mail."
  - Envie em HTML e em texto simples.
- **Destino:** o e-mail cadastrado do usuário (RN18).
- **FE1:** a falha de banco nos passos 1 ou 4 vai para o log, e as pendentes ficam para o próximo ciclo.

### C3 – Consultar notificações

- **API**, autenticada:
  - `GET /notifications/unread-count`: a quantidade de não lidas com canal `WEB` ou `AMBOS`;
  - `GET /notifications`: as notificações do usuário com canal `WEB` ou `AMBOS`, da mais recente para a mais antiga, com o nome e o ícone do item;
  - `POST /notifications/read`: recebe os ids exibidos e grava `lida_em` (passo 5).
  - Separei a leitura da marcação para o `GET` não ter efeito colateral. O resultado é o mesmo do passo 5.
- **Tela, seguindo o protótipo (Figura 17):**
  - sino no cabeçalho, só para o usuário autenticado, ao lado do link "Favoritos", com o contador de não lidas;
  - o contador é consultado ao carregar a página e a cada 5 minutos;
  - o sino abre um painel com o título "Notificações" e "N não lidas". Cada notificação mostra:
    - o ícone do item;
    - "**{item}** atingiu o preço do seu alerta de {compra|venda}";
    - "Alvo: … · Valor de mercado: …";
    - a data e a hora no fuso local, como o CU04;
    - as não lidas com fundo destacado e um ponto.
  - Depois de exibir, a tela marca as notificações como lidas e zera o contador.
  - Selecionar uma notificação abre a tela do item (passo 6).
- **Mensagens:** exatamente as do CU08:
  - "Você não tem notificações" (FA1);
  - "Não foi possível carregar as notificações no momento. Tente novamente mais tarde" (FE1).

### Testes

- Use os nomes da lista do CU08, com a RN07 no lugar da RN28:
  - `test_cu08_c1_fluxo_principal_dispara_alerta_de_compra_e_de_venda_rn07`;
  - `test_rn07_alerta_dispara_uma_unica_vez`.
- O C1 e o C2 são testados no backend, com o relógio e o envio de e-mail substituídos.
- O C3 é testado no backend (API) e no frontend, em `frontend/tests/`, com o prefixo `cu08-`.

## Regras

- Siga o `CLAUDE.md`:
  - type hints;
  - Pydantic nas bordas da API;
  - TypeScript sem `any`;
  - regra de negócio só no backend;
  - RN01 em Cobre;
  - datas em UTC;
  - docstrings citando o CU e a RN.
- Não altere as funções de teste dos outros casos de uso. Os testes do CU09 continuam passando sem mudança de comportamento.
- **Não leia nem altere arquivos `.env`.**

## Depois de implementar

1. Rode a suíte do backend no host e a do frontend, com `npm test`, `npm run lint` e `npx tsc --noEmit`.
2. Faça a conferência de ponta a ponta com os dados reais e um usuário de teste:
   1. Favorite um item e crie um alerta de compra com o preço-alvo um pouco acima do valor de mercado atual, com o canal "Ambos".
   2. Rode um ciclo de ingestão (o agendado ou a ingestão manual do Admin, respeitando a RN05).
   3. Confira:
      - o alerta como "Disparado";
      - a notificação no sino;
      - o contador zerando depois de abrir;
      - o e-mail no Mailpit (`http://localhost:8025`).
   4. Rode outro ciclo e confira que não houve segunda notificação.
   5. Salve as capturas do sino e do e-mail em `docs/capturas/`, em PNG com escala 2.
3. Atualize a documentação, que entra no commit:
   - a "Situação no código" do CU08;
   - `docs/plano-de-testes-por-fluxo.md`;
   - `docs/casos-de-uso/README.md`.
4. Faça o commit `feat(CU08): manter notificações (C1 a C3, RN07)`.

## O que devolver

1. O que ficou pendente e as decisões que você tomou (inclusive a da Ficha do WoW), para eu atualizar o texto do TC.
2. A quantidade de funções de teste por cenário, separando backend e frontend. Esses números vão para o Quadro 82 do TC.
3. Para cada cenário, se o resultado esperado do Quadro 78 do TC foi obtido na conferência de ponta a ponta.
