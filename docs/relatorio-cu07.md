# Relatório do CU07: manter alerta de preço

Implementação do CU07 (seção 6.4.7 do TC), feita em 11/11/2026 conforme o `estudos/lstm/pedido-cu06-cu07.md` e o plano aprovado no chat. Este relatório é o do commit `feat(CU07): manter alerta de preço (C1 a C3, RN08)`; o do CU06 está em `docs/relatorio-cu06.md`.

O disparo e a notificação são do CU08. Até lá, um alerta só passa a `DISPARADO` nos testes e na conferência, por inserção direta no banco.

## 1. Banco de dados

**Sem migração nova.** A tabela `alerta_preco` veio na `0011_favoritos_e_alertas`, no commit do CU06, com:
- a chave estrangeira composta (`id_usuario`, `item_id`) para `favorito`, em cascata: remover o favorito remove os alertas do item (CU06-C2);
- a chave estrangeira para `usuario`, em cascata (RN20);
- o índice (`id_usuario`, `situacao`), que serve à contagem da RN08.

## 2. O que foi implementado

### Backend

| Arquivo | O que faz |
|---|---|
| `src/repositories/alerta_repository.py` | `travar_usuario` (`SELECT … FROM usuario … FOR UPDATE`), os ativos do usuário, os alertas do item, o alerta do usuário pelo id, incluir, atualizar e remover |
| `src/services/alerta_service.py` | A validação do FA3 e a conversão para Cobre (RN01); o C1 (`novo` e `criar`), o C2 (`para_editar` e `alterar`) e o C3 (`excluir`), com a RN08 |
| `src/controllers/alerta_controller.py` | As seis rotas, todas autenticadas e só sobre os alertas do próprio usuário |
| `src/models/api_models.py` | `AlertaRequest`, com os campos opcionais para a validação ser do serviço; `Alerta`, `AlertasDoItemResponse`, `FormularioDoAlertaResponse` e `AlertaSalvoResponse` |
| `src/services/mensagens.py` e `src/services/erros.py` | As mensagens do CU07 e os erros `ItemForaDosFavoritosError`, `LimiteDeAlertasError`, `DadosDoAlertaInvalidosError` e `AlertaNaoEncontradoError` |
| `backend/.env.example` | `ALERTAS_MAXIMO_ATIVOS=20` (RN08) |

**RN08 (cota):**
- conta só os alertas `ATIVO` do usuário, em todos os itens; os disparados não contam até serem reativados;
- a contagem e a gravação ficam na mesma transação, depois do bloqueio da linha do usuário;
- assim, dois pedidos simultâneos não passam do limite: o segundo espera o primeiro terminar e então recebe o FA2. Isso é coberto pelo `test_cu07_rn08_pedidos_simultaneos_nao_passam_do_limite`, com duas sessões reais.

**FA3 (dados inválidos):** a validação é do serviço, e a resposta traz sempre a mensagem do cenário, nunca o erro padrão do Pydantic. Conta como inválido:
- o tipo ou o canal ausente ou desconhecido;
- o preço vazio ou com total zero;
- uma parte negativa, fracionária ou em texto;
- Prata ou Cobre acima de 99.

O preço-alvo válido é convertido para Cobre: `ouro × 10000 + prata × 100 + cobre` (RN01).

**Respostas da API:**

| Rota | Situação | Resposta |
|---|---|---|
| todas | sem sessão válida | 401 (a tela leva ao login com "sessão expirada") |
| `GET /api/items/{id}/alerts` | a seção do item | 200 `{alertas, ativos_do_usuario, limite}` |
| `GET /api/items/{id}/alerts/new` | C1 passos 2 a 4 | 200 `{item_id, market_value, alerta: null}`, com o valor de mercado atual (RN06) |
| | C1-FA1 | 409 "Para criar um alerta, adicione o item aos favoritos" |
| | C1-FA2 | 409 "Você atingiu o limite de 20 alertas ativos. Exclua um alerta para criar outro" |
| `POST /api/items/{id}/alerts` | C1 | 201 `{alerta, message: "Alerta criado com sucesso"}`, com o alerta `ATIVO`; o favorito e a cota são conferidos de novo |
| | C1-FA3 | 422 com a mensagem do FA3; nada é gravado |
| | C1-FE1 | 503 "Não foi possível salvar o alerta no momento. Tente novamente mais tarde" |
| `GET /api/alerts/{id}/edit` | C2 passos 1 e 2 | 200 com os dados atuais e o valor de mercado |
| | C2-FA1 e FA2 (disparado) | a cota é conferida antes; no limite, 409 "… Exclua um alerta para reativar este" |
| `PUT /api/alerts/{id}` | C2 e C2-FA1 | 200 `{alerta, message: "Alerta atualizado com sucesso"}`; o alerta fica `ATIVO`, com `disparado_em` nulo, e a cota é conferida de novo na reativação |
| | C2-FA3 / C2-FE1 | 422 / 503, e o alerta mantém os dados anteriores |
| `DELETE /api/alerts/{id}` | C3 | 200 "Alerta excluído com sucesso" |
| | C3-FE1 | 503 "Não foi possível excluir o alerta no momento. Tente novamente mais tarde"; o alerta é mantido |
| `…/alerts/{id}…` | alerta de outro usuário, ou inexistente | 404 "Alerta não encontrado" |

### Frontend

| Arquivo | O que faz |
|---|---|
| `components/AlertasDoItem.tsx` | A seção "Alertas de preço" da tela do item, só para o usuário autenticado (Figura 15). Tem a linha "Você tem X de 20 alertas ativos em todos os seus itens", o botão "Criar alerta", a tabela com as colunas Tipo de gatilho, Preço-alvo, Canal, Situação e Ações, a mensagem do FA1 ou do FA2 e o diálogo "Deseja excluir este alerta?" |
| `components/FormularioDeAlerta.tsx` | O formulário num diálogo (Figura 16): o item e o valor de mercado atual, os cartões Compra/Venda, Ouro, Prata e Cobre, o canal (Tela, E-mail ou Ambos), "Cancelar" e "Salvar alerta". O erro do FA3 aparece no formulário, que continua aberto |
| `lib/alertasApi.ts` | As chamadas à API e os rótulos: tipo, canal (`WEB` = "Tela", `EMAIL` = "E-mail", `AMBOS` = "Tela e e-mail") |
| `app/item/[id]/page.tsx` | Mostra a seção depois da projeção do CU05. O estado "favorito" é compartilhado com o controle do CU06: remover o favorito esvazia a lista de alertas da tela |
| `lib/useAcoesDeFavorito.ts`, `app/favoritos/page.tsx` | Correção do aviso passageiro, ver a seção 5 |

**Na tela:**
- **C1-FA1:** a mensagem vem com o botão "Adicionar aos favoritos". Favoritando (CU06-C1), a tela confere de novo a cota (o passo 3) e abre o formulário (1.4).
- **C2:** o botão é "Editar" para um alerta ativo e "Editar e reativar" para um disparado. O formulário se chama "Alterar alerta de preço" ou "Reativar alerta de preço".
- **Situação:** "Ativo", ou o selo "Disparado" com "em dd/mm/aaaa às hh:mm" numa segunda linha, no fuso de quem vê, como o CU04.

## 3. Testes

**Resultado das suítes** (11/11/2026):

| Suíte | Executados | Aprovados | Com falha |
|---|---|---|---|
| Backend no host (`pytest`) | 372 (+ 5 módulos ignorados, os de `tests/modelo`) | 372 | 0 |
| Container do `modelo` (`modelo-testes`) | 50 | 50 | 0 |
| Frontend (`npm test`) | 71 | 71 | 0 |

O `npm run lint` deu 0 erros (3 avisos de `<img>`; o novo é o do ícone no formulário do alerta) e o `npx tsc --noEmit` passou limpo. Os testes do CU04, do CU05 e do CU06 não mudaram e continuam passando. O apoio dos testes de tela (`tests/apoioDosFavoritos.ts`) ganhou uma resposta padrão para `GET /items/{id}/alerts`, a lista vazia, porque a seção agora aparece em toda tela de item com sessão.

**Funções de teste do CU07** (para o Quadro 82):

| Cenário | Backend | Frontend | Total |
|---|---|---|---|
| C1 | 5 | 5 | 10 |
| C2 | 5 | 5 | 10 |
| C3 | 2 | 3 | 5 |
| Regras gerais (dono do alerta; RN08 simultânea) | 2 | 0 | 2 |
| **CU07** | **14** | **13** | **27** |

- **O FA3 do C1 no backend** é uma só função, com `parametrize` de 11 casos. Por isso o `pytest` executa 24 casos do CU07 a partir das 14 funções.
- **O C3-FA1 (exclusão cancelada)** não tem teste de backend: cancelar o diálogo não envia nada.

**Arquivos:**
- `backend/tests/integration/test_cu07_manter_alerta.py`;
- `frontend/tests/cu07-c1-criar-alerta.test.tsx`, `cu07-c2-alterar-alerta.test.tsx` e `cu07-c3-excluir-alerta.test.tsx`.

**Totais do plano de testes** (`docs/plano-de-testes-por-fluxo.md`): 392 testes com identificador de fluxo ou de regra; a suíte completa tem 493 (372 + 50 + 71).

## 4. Conferência no navegador (Quadro 77)

Feita com a API e o front locais, dados reais do mercado e o mesmo usuário de teste do CU06 (credencial em `.claude/usuario-de-teste.local.json`, não versionado), no Chrome. Depois de cada passo, conferi pela API o que ficou gravado.

- **Item com alertas:** Mycobloom (210796), valor de mercado 5g 55s.
- **Item do C1-FA1:** Ironclaw Ore (210936), fora dos favoritos. No fim, foi tirado de novo dos favoritos.

O texto do Quadro 77 não está no repositório, então o resultado esperado abaixo é a pós-condição de cada cenário. Vale conferir com o Quadro.

| Cenário | Resultado esperado | Obtido |
|---|---|---|
| C1 | O alerta registrado com a situação "Ativo" | **Sim.** Dois alertas criados, ambos `ATIVO` no banco, com o preço em Cobre e a mensagem "Alerta criado com sucesso" nas duas vezes. A cota foi de 0 a 2 |
|  |  | Compra de 5g, com "Tela e e-mail": 50000 Cobre |
|  |  | Venda de 6g 20s, com "E-mail": 62000 Cobre |
| C1-FA1 | A mensagem com a opção de favoritar; favoritando, o formulário | **Sim.** A mensagem do cenário com "Adicionar aos favoritos"; ao clicar, o formulário "Criar alerta de preço" abriu |
| C1-FA3 | A mensagem do FA3, com o formulário aberto | **Sim.** Salvando o formulário vazio, a mensagem apareceu dentro do formulário, que continuou aberto |
| C2 | O alerta atualizado com a situação "Ativo" | **Sim.** O de compra passou a 5g 20s, com "Tela" (52000 Cobre), com "Alerta atualizado com sucesso" |
| C2-FA1 | O alerta disparado reativado | **Sim.** O de venda foi marcado como `DISPARADO` no banco local. A linha mostrou "Disparado em 11/11/2026 às 10:42", com "Editar e reativar", e a cota caiu para 1. O formulário "Reativar alerta de preço" gravou o alerta como `ATIVO`, com `disparado_em` nulo, e a cota voltou a 2 |
| C3 | O alerta removido do banco | **Sim.** O diálogo mostrou "Deseja excluir este alerta?". Cancelar manteve a linha (FA1). Confirmar removeu o alerta do banco, com "Alerta excluído com sucesso", e a cota foi para 1 |

**Console:** só dois registros, ambos respostas esperadas: o 409 do C1-FA1 e o 422 do C1-FA3.

**Não conferidos no navegador:**
- **FA2 do C1 e do C2:** exigiriam 20 alertas ativos do usuário de teste;
- **FE1 dos três cenários:** exigiriam derrubar o banco.

Esses fluxos ficam cobertos pelos testes de backend e de tela.

**Capturas** (PNG, escala 2, em `docs/capturas/`):
- **C1:**
  - `cu07-c1-fa1-fora-dos-favoritos.png` e `cu07-c1-fa1-favoritado-e-formulario.png`;
  - `cu07-c1-fa3-dados-invalidos.png`;
  - `cu07-c1-formulario-compra.png`, `cu07-c1-compra-criado.png` e `cu07-c1-venda-criado.png`.
- **C2:**
  - `cu07-c2-formulario-editar.png` e `cu07-c2-alterado.png`;
  - `cu07-c2-fa1-disparado.png`, `cu07-c2-fa1-formulario-reativar.png` e `cu07-c2-fa1-reativado.png`.
- **C3:** `cu07-c3-confirmacao.png` e `cu07-c3-excluido.png`.

## 5. Correção feita durante a conferência

Ao criar o segundo alerta, o aviso "Alerta criado com sucesso" não apareceu.

**Causa:** duas mensagens iguais em menos de 6 s reaproveitavam o mesmo aviso na tela. O tempo do primeiro continuava correndo, e o aviso fechava logo depois do segundo salvamento. O mesmo acontecia na lista de favoritos do CU06, ao remover dois itens seguidos.

**Correção:** cada aviso ganhou uma identidade (`novoAviso`, em `lib/useAcoesDeFavorito.ts`), usada como `key` do `Toast`. Assim, cada mensagem recomeça o seu tempo.

O aviso do CU04 (`toast` da tela do item) não foi mexido.

## 6. Decisões, para o texto do TC

1. **Alerta de outro usuário, ou inexistente:** responde 404 com "Alerta não encontrado", texto que o documento não define. A tela não chega a mostrá-lo no uso normal.
2. **Falha ao carregar a seção "Alertas de preço":** mostra "Não foi possível carregar os alertas no momento. Tente novamente mais tarde", texto que o documento não define (não há FE para a leitura da seção).
3. **C1-FA1, passo 1.4:**
   - depois de favoritar pela mensagem, a tela pede de novo o formulário ao backend, que confere a cota (o passo 3), em vez de abrir direto;
   - no limite, aparece a mensagem do FA2.
4. **Cota conferida duas vezes:** ao abrir o formulário e ao gravar. Isso vale para a criação e para a reativação; entre os dois momentos, outro pedido pode ter usado a última vaga.
5. **Validação (FA3):** além do texto do cenário, conta como inválido o que não cabe no formulário de Ouro, Prata e Cobre (parte negativa, fracionária ou em texto, e Prata ou Cobre acima de 99), sempre com a mensagem do FA3.
6. **Situação "Disparado":** a data e a hora ficam numa segunda linha, abaixo do selo, no fuso de quem vê.

## 7. Pendências e observações

- **CU08:** disparar os alertas (RN07, com o gatilho e o disparo único) e notificar pelo canal escolhido. É o próximo pedido (`estudos/lstm/pedido-cu08.md`). A tela do CU07 já mostra o "Disparado em …" e a reativação.
- **Sessão do usuário de teste:** expirou durante a conferência (o tempo da sessão do CU02) e foi renovada com um novo login pela API local, sem mudar a credencial.
- **Undermine:** a série diária continua parada em 20/10 (HTTP 403, ver `docs/relatorio-cu05.md`), por isso o gráfico das capturas mostra só os pontos horários de hoje. Não afeta o CU07: o valor de mercado de referência vem do último ciclo da Blizzard.
