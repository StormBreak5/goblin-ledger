# Relatório do CU08: manter notificações

Pedido: `estudos/lstm/pedido-cu08.md`. Commit: `feat(CU08): manter notificações (C1 a C3, RN07)`.

O CU08 fecha o ciclo dos alertas de preço do CU07. A cada ciclo de ingestão, o sistema confere os alertas ativos e registra as notificações dos alertas atingidos (C1). Em seguida, envia por e-mail as que têm esse canal (C2). O usuário consulta as notificações pelo sino do cabeçalho (C3).

## 1. Banco de dados

A migração `0012_notificacoes` cria a tabela `notificacao`, como no MR:

- **Colunas:**
  - `id_notificacao`, a chave;
  - `id_alerta`, que fica nulo quando o alerta é excluído;
  - `id_usuario`;
  - `item_id` e `tipo`;
  - `preco_alvo` e `valor_mercado`, em Cobre;
  - `canal`;
  - `disparada_em` e `lida_em`;
  - `envio_email`, `tentativas_email` e `enviada_em`.
- **Exclusões:**
  - `id_alerta` usa `ON DELETE SET NULL`: a notificação continua no histórico quando o alerta é excluído (CU07-C3) ou quando o favorito é removido com os alertas (CU06-C2);
  - `id_usuario` usa `ON DELETE CASCADE`, então a exclusão da conta remove as notificações (RN20).
- **Verificações (CHECK):**
  - o tipo é `COMPRA` ou `VENDA`;
  - o canal é `WEB`, `EMAIL` ou `AMBOS`;
  - `envio_email` é `PENDENTE`, `ENVIADO` ou `FALHOU`, e fica nulo se, e só se, o canal for só a tela.
- **Índices:**
  - (usuário, data do disparo), para a lista do sino;
  - um índice parcial com as pendentes de envio, para o C2;
  - (situação, item) em `alerta_preco`, para o passo 2 do C1.

No banco local, a `0012` foi aplicada em 11/11/2026, com o `worker` e o `modelo` reconstruídos juntos.

## 2. O que foi implementado

### Backend

| Arquivo | O que faz |
|---|---|
| `src/models/notificacao.py`, `src/migrations/versions/0012_notificacoes.py` | O modelo e a migração da seção 1 |
| `src/services/notificacao_service.py` | O C1 (`verificar_alertas`, com a função `gatilho_atingido` da RN07), o C2 (`enviar_pendentes`) e o C3 (`nao_lidas`, `listar` e `marcar_como_lidas`). Também `processar_ciclo` (o C1 seguido do C2, sem nunca levantar exceção) e `processar_coleta_da_ficha` |
| `src/repositories/notificacao_repository.py` | Os alertas ativos dos itens do ciclo e o disparo condicional (`UPDATE … WHERE situacao = 'ATIVO'`); as pendentes de envio, com a trava de cada uma (`FOR UPDATE SKIP LOCKED`); a contagem, a lista e a marcação do C3 |
| `src/services/ingestao_service.py` | Depois do commit da consolidação de um ciclo concluído (CU09-C3), chama o CU08 com o valor de mercado e a marca de anomalia de cada ponto gravado. Uma falha no CU08 vai para o log e não muda o resultado do ciclo |
| `src/controllers/mercado_controller.py` | A ingestão manual do Admin (CU09-C4) passa o serviço de e-mail ao `IngestaoService`, para os testes usarem o e-mail falso |
| `src/worker.py` | Na rotina de 15 minutos da Ficha do WoW, a cada preço novo gravado, chama `processar_coleta_da_ficha` |
| `src/services/email_de_alerta.py`, `src/services/moeda.py` | O e-mail da Figura 18, em texto e HTML. Os valores ficam no formato `12g 49s 30c` (o mesmo do `lib/moeda.ts`) e a data no horário de Brasília |
| `src/services/email_service.py` | O método novo `enviar_notificacao_de_alerta`. O envio por SMTP passou para um `_enviar` comum, sem mudar o e-mail de recuperação do CU02-C2 |
| `src/controllers/notificacao_controller.py`, `src/main.py` | As três rotas do C3 |
| `src/models/api_models.py`, `src/services/mensagens.py` | Os modelos das respostas e as duas mensagens do CU08 |
| `src/repositories/alerta_repository.py` | A trava do CU07 passou de `FOR UPDATE` para `FOR NO KEY UPDATE` (ver a decisão 4) |
| `requirements.txt` | `tzdata`: a imagem alpine do worker não traz a base de fusos que o `zoneinfo` usa |
| `docker-compose.yml`, `.env.example` | O worker passa a enviar para o `mailpit` (`SMTP_HOST_DOCKER`). Também `NOTIFICACAO_EMAIL_TENTATIVAS=3` |

**Respostas da API (C3):**

| Rota | Situação | Resposta |
|---|---|---|
| todas | sem sessão válida | 401 |
| `GET /api/notifications/unread-count` | passo 1 | 200 `{nao_lidas}`, só com as notificações dos canais `WEB` e `AMBOS` |
| `GET /api/notifications` | passos 3 e 4 | 200 `{notificacoes, nao_lidas, mensagem: null}`, da mais recente para a mais antiga. Cada notificação traz o item (nome e ícone), o tipo, o preço-alvo, o valor de mercado, a data e a hora e `lida`. Não marca nada como lido |
| | FA1 | 200 `{notificacoes: [], nao_lidas: 0, mensagem: "Você não tem notificações"}` |
| `POST /api/notifications/read` | passo 5 | 200 `{nao_lidas}`. Marca só as notificações do próprio usuário que ainda não estavam lidas |
| GET e POST | FE1 | 503 "Não foi possível carregar as notificações no momento. Tente novamente mais tarde" |

### Frontend

| Arquivo | O que faz |
|---|---|
| `components/SinoDeNotificacoes.tsx` | O sino (Figura 17), só para o usuário autenticado. O contador é consultado ao carregar e a cada 5 minutos. O painel tem "Notificações", "N não lidas" e, em cada linha, o ícone, "**{item}** atingiu o preço do seu alerta de compra/venda", "Alvo: … · Valor de mercado: …" e a data e a hora no fuso local. As não lidas aparecem com fundo destacado e um ponto. Depois de exibir, o sino marca as não lidas e zera o contador. Selecionar uma notificação abre a tela do item. O painel também mostra as mensagens do FA1 e do FE1, e fecha com Esc ou com um clique fora |
| `lib/notificacoesApi.ts` | As três chamadas e a mensagem do FE1 para quando a rede cai |
| `components/AuthNav.tsx` | O sino entre "Favoritos" e "Meu perfil" |
| `lib/instante.ts`, `components/AlertasDoItem.tsx` | `dataEHora`, o formato `dd/mm/aaaa às hh:mm`, agora usado pelo sino e pela situação "Disparado" do CU07, que continua exibida como antes |

## 3. Testes

| Suíte | Executados | Aprovados | Com falha |
|---|---|---|---|
| Backend no host (`pytest`) | 387 (+ 5 módulos ignorados, os de `tests/modelo`) | 387 | 0 |
| Container do `modelo` (`modelo-testes`) | 50 | 50 | 0 |
| Frontend (`npm test`) | 76 | 76 | 0 |

`npm run lint` terminou com 0 erros e os mesmos 3 avisos de `<img>` de antes; `npx tsc --noEmit` passou sem erros.

**Funções de teste por cenário (Quadro 82):**

| Cenário | Backend | Frontend | Total |
|---|---|---|---|
| C1 | 5 | 0 | 5 |
| C2 | 3 | 0 | 3 |
| C3 | 3 | 5 | 8 |
| Regras gerais (RN07; RN20; a notificação permanece quando o alerta é excluído; só as notificações do próprio usuário) | 4 | 0 | 4 |
| **CU08** | **15** | **5** | **20** |

- **Sem tela:** o C1 e o C2 são do sistema, por isso só têm testes de backend. Os testes do C1 rodam dentro de um ciclo real do CU09 (fluxo principal, FA2 e FE1), com a API da Blizzard falsa.
- **O que os testes do C1 e do C2 substituem:** o relógio e o envio de e-mail (`EmailFalso`).
- **Teste da decisão da Ficha:** o quinto teste do C1 é `test_cu08_c1_ficha_do_wow_dispara_alerta_sem_rn12`.
- **Frontend:** o C3 tem cinco testes:
  - o fluxo principal;
  - o passo 1 (o contador a cada 5 minutos, e nenhum sino para o anônimo);
  - o FA1;
  - o FE1 ao carregar;
  - o FE1 ao marcar como lidas.
- **Testes de outros casos de uso:** nenhuma função de teste deles mudou. A limpeza do `db_session`, o `EmailFalso` e o teste das migrações (que agora espera a `0012`) são apoio.

## 4. Conferência de ponta a ponta (Quadro 78)

A conferência foi feita em 11/11/2026, com o banco local, os dados reais e o worker reconstruído. Usei o usuário de teste (a credencial está em `.claude/usuario-de-teste.local.json`, fora do versionamento). Os alertas foram criados pela API local:

- **Compra no Ironclaw Ore (favoritado na hora),** com o canal "Tela e e-mail" e o alvo de 2g 70s. O valor de mercado era 2g 51s.
- **Venda no Mycobloom,** só "Tela", com o alvo de 4g 40s. O valor era 4g 50s.
- **Compra na Ficha do WoW,** só "Tela", com o alvo de 310.000g. O valor era 305.052g.
- **Venda no Mycobloom que já existia** (CU07), com o alvo de 6g 20s e "E-mail". Esta não deveria ser atingida.

Rodou o ciclo agendado do worker, respeitando a RN05; a ingestão manual do Admin não foi usada.

| Cenário | Resultado esperado | Obtido |
|---|---|---|
| C1 | Os alertas atingidos ficam com a situação "Disparado" e as notificações ficam registradas | **Sim.** Ver o detalhe abaixo da tabela |
| C1-FA1 | Nenhum alerta atingido; o log da conclusão | **Sim.** O ciclo do reino 3209 (21:18) teve 7.191 itens verificados e nenhum alerta atingido, e o log saiu com `CU08-C1-FA1`. Os itens da conferência são commodities |
| C2 | O e-mail é enviado e a notificação registra a data e a hora do envio | **Sim.** O Mailpit recebeu "Alerta de preço atingido – Ironclaw Ore" no e-mail cadastrado do usuário, como na Figura 18. A notificação ficou `ENVIADO`, com `enviada_em`. Capturas: `cu08-c2-email-no-mailpit.png` e `cu08-c2-email-html.png` |
| C3 | O usuário visualiza as suas notificações, e as exibidas ficam marcadas como lidas | **Sim.** Ver o detalhe abaixo da tabela |
| C3-FA1 | A mensagem "Você não tem notificações" | **Sim.** Antes dos disparos, o painel mostrou a mensagem (`cu08-c3-fa1-nenhuma-notificacao.png`) |
| RN07, disparo único | Um alerta disparado não gera outra notificação | **Sim.** Ver o detalhe abaixo da tabela |

**C1, em detalhe:**
- **A Ficha (às 20:35):** a cotação nova de 304.375g atingiu o alerta de compra. O alerta ficou `DISPARADO` e a notificação foi para a tela, sem e-mail.
- **O ciclo das commodities (às 21:20):** o log saiu com `CU08-C1: … 9767 itens verificados, 0 ignorados por anomalia de volume (RN12), 2 alertas atingidos, 1 notificações encaminhadas para e-mail`.
  - A compra do Ironclaw Ore foi atingida (2g 51s ≤ 2g 70s) e a venda do Mycobloom também (4g 50s ≥ 4g 40s). Os dois alertas ficaram `DISPARADO`, com `disparado_em`.
  - As notificações gravaram o item, o tipo, o alvo, o valor que atingiu, o canal e a data e a hora.
  - A venda de 6g 20s continuou `ATIVO`.
- **Na tela do item:** "Disparado em 11/11/2026 às 18:20", com "Editar e reativar" (`cu08-c1-alerta-disparado.png`).

**C3, em detalhe:**
- O sino mostrou 3 (`cu08-c3-sino-com-contador.png`).
- O painel mostrou "3 não lidas" e as três notificações, da mais recente para a mais antiga, com o ícone, o texto, o alvo, o valor de mercado e a data e a hora no fuso local. As não lidas apareceram destacadas (`cu08-c3-painel-de-notificacoes.png`).
- A tela enviou `POST /notifications/read` e o contador sumiu (`cu08-c3-contador-zerado.png`).
- Reaberto, o painel mostrou as três já lidas.
- Selecionar a primeira abriu `/item/210796` (passo 6).
- Não houve erros no console.

**RN07, disparo único:**
- **A Ficha:** as cotações novas das 20:50, 21:05, 21:50 e 22:05 continuaram abaixo do alvo. O log saiu com "nenhum alerta atingido" e não houve segunda notificação.
- **O ciclo seguinte (22:18 no reino e 22:20 nas commodities):** com os alertas já `DISPARADO`, o log saiu com `CU08-C1-FA1 … nenhum alerta atingido`. O banco continuou com as mesmas 3 notificações.

**Fluxos não exercitados de ponta a ponta:**
- o C1-FA2 (precisaria de uma injeção real de volume);
- o C1-FE1 e o C2-FE1 (precisariam derrubar o banco);
- o C2-FA1 (precisaria do SMTP fora do ar);
- o C3-FE1.

Todos estão cobertos pelos testes da seção 3.

## 5. Decisões tomadas, para o texto do TC

1. **Ficha do WoW.**
   - A cotação dela vem da rotina de 15 minutos do worker, fora do ciclo do CU09.
   - A cada preço novo gravado, a rotina faz a mesma verificação (RN07) e o mesmo envio. A Blizzard atualiza a Ficha a cada 20 minutos, e uma leitura repetida não verifica de novo.
   - A RN12 não se aplica, porque a Ficha não tem volume.
   - O texto do C1 ("a cada ciclo de ingestão") e a RN07 ("de 60 em 60 minutos") não falam da Ficha. Vale acrescentar uma frase.
2. **Tentativas de e-mail.**
   - O C2 roda logo depois de cada C1 (o ciclo do CU09 ou uma cotação nova da Ficha) e processa todas as pendentes, com uma tentativa por notificação em cada execução.
   - Como a Ficha também aciona o C2, uma nova tentativa pode acontecer em menos de 60 minutos.
   - A tentativa que dá certo também é contada em `tentativas_email`, que registra quantas vezes se tentou.
3. **Consulta separada da marcação.**
   - O `GET /notifications` não marca nada; a tela grava a leitura pelo `POST /notifications/read`, com os ids exibidos.
   - O resultado é o mesmo do passo 5. A sugestão das observações era marcar no próprio GET.
   - O destaque das não lidas continua até o painel fechar.
4. **Trava do CU07.**
   - O `travar_usuario` da RN08 passou a `FOR NO KEY UPDATE`.
   - Com o `FOR UPDATE`, um usuário salvando um alerta no mesmo instante em que o ciclo o dispara podia travar os dois lados, porque a gravação da notificação confere a chave do usuário.
   - O teste de pedidos simultâneos do CU07 continua passando sem mudança.
5. **Disparo concorrente com a edição.**
   - O `UPDATE` do disparo também confere o tipo e o preço-alvo lidos.
   - Se o usuário alterar o alerta durante a verificação, ele não dispara com os valores antigos e é verificado no próximo ciclo.
6. **Região.** A verificação roda em cada ciclo dos mercados monitorados (hoje, reino 3209 e commodities US) e não filtra os alertas pela região do usuário.
7. **SMTP do worker no Docker.** Dentro da rede do Docker, o worker envia para o serviço `mailpit`. Para um SMTP real, basta definir `SMTP_HOST_DOCKER`.
8. **Item sem cadastro.** No e-mail e no sino, o nome do item é "Item {id}", como no CU06.

## 6. Pendências

- **Quadro 78:** o texto dele não está no repositório. A conferência usou a pós-condição de cada cenário; vale comparar com o Quadro.
- **Fluxos fora da conferência no navegador:**
  - o C1-FA2 (anomalia de volume), o C1-FE1, o C2-FA1 e o C2-FE1 dependem de um bot, de uma queda do banco ou do SMTP fora do ar;
  - estão cobertos pelos testes.
- **A Undermine continua com HTTP 403** desde 11/11 (a importação diária do CU10), sem relação com o CU08.
