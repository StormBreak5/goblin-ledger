# Relatório do CU06: manter favoritos

Implementação do CU06 (seção 6.4.6 do TC), feita em 11/11/2026 conforme o `estudos/lstm/pedido-cu06-cu07.md` e o plano aprovado no chat. O CU06 e o CU07 vão juntos, mas em commits separados; este relatório é o do commit `feat(CU06): manter favoritos (C1 a C3)`. A tabela de alertas entra já aqui, porque o C2 (remover os alertas do item) e o C3 (contar os alertas ativos) dependem dela.

## 1. Banco de dados

**Migração `0011_favoritos_e_alertas`**, a próxima depois da `0010`, com as duas tabelas do MR:

- **`favorito`:** `id_usuario` (PK e FK para `usuario`, `ON DELETE CASCADE`), `item_id` (PK, o ID externo do item) e `data_inclusao`.
- **`alerta_preco`:**
  - `id_alerta` (PK), `id_usuario` (FK para `usuario`, `ON DELETE CASCADE`) e `item_id`;
  - `tipo` (`COMPRA`/`VENDA`), `preco_alvo` (em Cobre), `canal` (`WEB`/`EMAIL`/`AMBOS`) e `situacao` (`ATIVO`/`DISPARADO`), com CHECK;
  - `criado_em`, `atualizado_em` e `disparado_em` (pode ser nulo);
  - FK composta (`id_usuario`, `item_id`) para `favorito`, com `ON DELETE CASCADE`;
  - índice (`id_usuario`, `situacao`), para a contagem da RN08 no CU07.

**Exclusão da conta (CU01-C3, RN20):** remove os favoritos e os alertas pelas cascatas, sem nenhuma mudança no CU01. O teste é `test_cu06_exclusao_da_conta_remove_favoritos_e_alertas_rn20`.

**Teste de migração:** o `tests/integration/test_migracoes.py`, de apoio, confere a lista de tabelas e a última revisão. Ele passou a esperar as duas tabelas novas e a revisão `0011`, como em cada migração anterior.

**Ambiente:** o banco real foi migrado para a `0011`. O `worker` e o `modelo` foram reconstruídos juntos (`docker-compose up --build -d worker modelo`), para nenhum dos dois ficar com uma imagem que não conhece a revisão.

## 2. O que foi implementado

### Backend

| Arquivo | O que faz |
|---|---|
| `src/models/favorito.py` | Os modelos `Favorito` e `AlertaPreco`, com as constantes de tipo, canal e situação |
| `src/repositories/favorito_repository.py` | Incluir, existe e remover (os alertas do item e o favorito, na mesma transação); a lista do usuário; os alertas ativos por item |
| `src/services/favorito_service.py` | O C1, o C2 (com o FA1 e o FE1) e o C3 (valor de mercado, variação, alertas ativos, frescor e ordem) |
| `src/controllers/favorito_controller.py` | `POST /api/favorites/{item_id}`, `DELETE /api/favorites/{item_id}?confirmar=true` e `GET /api/favorites`, todos autenticados |
| `src/services/frescor.py` | O frescor da RN09 e da RN14, antes um método privado do CU04 (`ItemService._frescor`), agora compartilhado pela tela do item e pela lista |
| `src/repositories/mercado_repository.py` | `leiloes_do_ultimo_ciclo_de_varios`, os leilões de todos os itens da lista numa consulta, e `valor_mais_proximo`, o ponto do ciclo mais perto de um instante |
| `src/controllers/item_controller.py` e `src/services/item_service.py` | O `GET /api/items/{item_id}` informa `favorito` quando há uma sessão válida. Sem ela, a resposta é a mesma de antes, porque o campo fica de fora |

**Respostas da API:**

| Situação | Resposta |
|---|---|
| sem sessão válida | 401 (C1-FA1: a tela leva ao login) |
| C1 | 200 `{item_id, favorito: true, message: "Item adicionado aos favoritos"}` |
| C1-FA2 (já favoritado) | 200 `{favorito: true, message: null}`; o registro é mantido |
| C2, sem alertas | 200 `{favorito: false, message: "Item removido dos favoritos"}` |
| C2-FA1, com alertas e sem `confirmar` | 409 com o aviso do cenário; nada é removido (é também o FA2, cancelada) |
| C2-FA1, com `?confirmar=true` | os alertas do item e o favorito saem numa única transação |
| C1-FE1 e C2-FE1 | 503 com "Não foi possível atualizar os favoritos…", e a transação é desfeita |
| C3 | a lista em ordem alfabética, ou a mensagem do FA1 |
| C3-FE1 | 503 com "Não foi possível carregar os seus favoritos…" |

### Frontend

| Arquivo | O que faz |
|---|---|
| `components/ControleDeFavorito.tsx` | O controle "Favoritar"/"Favoritado" abaixo do nome do item (Figura 15) |
| `lib/useAcoesDeFavorito.ts` | Adicionar e remover pela tela do item e pela lista, com o diálogo do C2-FA1 e os avisos |
| `components/Dialogo.tsx` | O diálogo de confirmação, reaproveitado pelo CU07 |
| `app/favoritos/page.tsx` | A página "Meus favoritos" (Figura 21); clicar na linha abre a tela do item (C3, passo 5) |
| `components/AuthNav.tsx` | O link "Favoritos" no cabeçalho, só para o usuário autenticado |
| `app/login/page.tsx` | O aviso "Entre na sua conta para favoritar itens" com `?aviso=favoritar` (C1-FA1) |
| `components/Toast.tsx` | Ganhou um tom de sucesso, opcional; o padrão continua o de erro do CU04 |
| `lib/favoritosApi.ts` e `lib/itemSearch.ts` | As chamadas à API; o `GET /items/{id}` passa a enviar o token, quando há sessão |

## 3. Testes

**Resultado das suítes** (11/11/2026):

| Suíte | Executados | Aprovados | Com falha |
|---|---|---|---|
| Backend no host (`pytest`) | 348 (+ 5 módulos ignorados, os de `tests/modelo`) | 348 | 0 |
| Container do `modelo` (`modelo-testes`) | 50 | 50 | 0 |
| Frontend (`npm test`) | 58 | 58 | 0 |

O `npm run lint` deu 0 erros (2 avisos de `<img>`, um deles já existente) e o `npx tsc --noEmit` passou limpo. Os testes do CU03, do CU04 e do CU05 não mudaram e continuam passando.

**Funções de teste do CU06** (para o Quadro 82):

| Cenário | Backend | Frontend | Total |
|---|---|---|---|
| C1 | 4 | 4 | 8 |
| C2 | 4 | 4 | 8 |
| C3 | 4 | 4 | 8 |
| Regras gerais (RN20) | 1 | 0 | 1 |
| **CU06** | **13** | **12** | **25** |

Arquivos: `backend/tests/integration/test_cu06_manter_favoritos.py` e `frontend/tests/cu06-c1-favoritar.test.tsx`, `cu06-c2-remover.test.tsx` e `cu06-c3-lista.test.tsx`.

## 4. Conferência no navegador (Quadro 76)

Feita com dados reais e com um usuário de teste novo, criado pela API de cadastro local. A credencial está em `.claude/usuario-de-teste.local.json`, que não é versionado.

- **Itens:** Algari Healing Potion (211878), Bismuth (210930), Luredrop (210799) e Mycobloom (210796).
- **Alerta:** como o CU07 ainda não tinha a tela, um alerta do Mycobloom foi gravado direto no banco local, só para o usuário de teste, para conferir o C2-FA1.

| Cenário | Resultado esperado (Quadro 76) | Obtido |
|---|---|---|
| C1 | O item registrado nos favoritos, com o controle "Favoritado" | **Sim.** "Favoritar" virou "Favoritado", com "Item adicionado aos favoritos" |
| C2 | O item e os seus alertas removidos | **Sim.** Sem alertas, "Favoritado" voltou a "Favoritar", com "Item removido dos favoritos". Com o alerta, a remoção pela lista abriu o diálogo com o aviso do FA1; cancelar manteve o item e o alerta (FA2) |
| C3 | A lista dos favoritos com o valor de mercado, a variação e os alertas ativos | **Sim.** Os quatro itens em ordem alfabética, com o valor de mercado em Ouro, Prata e Cobre e o sino com 1 no Mycobloom. A variação aparece "—" (seção 6). A lista vazia mostra a mensagem do FA1 |

O console do navegador não teve erros; o único registro é o 409 do C2-FA1, que é a resposta esperada.

**Capturas** (PNG, escala 2, em `docs/capturas/`):
- `cu06-c1-antes-de-favoritar.png` e `cu06-c1-favoritado.png`;
- `cu06-c2-desfavoritado.png` e `cu06-c2-dialogo-com-alertas.png`;
- `cu06-c3-lista.png` e `cu06-c3-lista-vazia.png`.

## 5. Decisões, para o texto do TC

1. **C1-FA1:** a mensagem chega à tela de login por `/login?aviso=favoritar`. Depois do login, a tela vai para a página inicial, como no CU02-C1 passo 8, porque o CU02 não tem destino de retorno.
2. **Variação em relação ao dia anterior (C3):**
   - o valor de mercado atual (RN06, o primeiro quartil do último ciclo) é comparado com o ponto horário do ciclo da Blizzard, no mesmo mercado, mais próximo de **24 h antes do instante do valor atual**;
   - esse ponto só vale numa janela de ±2 h (`FAVORITOS_VARIACAO_TOLERANCIA_HORAS`, no `.env.example`);
   - sem ele, a variação fica "—";
   - para a Ficha do WoW, vale a mesma regra na série dela.
   - Isso evita comparar com um ponto de dias atrás quando a coleta ficou parada.
3. **FA2 do C3:** a mesma regra do CU04 (RN09 com o limiar de 24 h e RN14), agora numa função compartilhada.
4. **Remover um item que não está nos favoritos** responde com sucesso, sem erro.
5. **Um aviso extra na tela:** o "Item removido dos favoritos" aparece num aviso passageiro, e a lista é recarregada. Quando ela fica vazia, aparece a mensagem do FA1.

## 6. Pendências e observações

- **Variação "—" na conferência:** a coleta horária da Blizzard só voltou em 11/11, às 14 h, depois do loop do worker. Até completar 24 h de coleta, nenhum item tem o ponto do dia anterior, então todos mostram "—", que é o comportamento definido para a falta do ponto. Uma nova captura da lista pode ser feita amanhã para mostrar as variações.
- **Undermine:** a série diária continua parada em 20/10 (HTTP 403 da Undermine, ver `docs/relatorio-cu05.md`). Por isso o gráfico dos itens mostra só os pontos horários de hoje dentro da janela de 14 dias.
- **CU07:** vem no próximo commit, com a seção "Alertas de preço" da tela do item, que hoje ainda não aparece.
