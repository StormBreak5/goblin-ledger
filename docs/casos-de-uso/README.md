# Casos de Uso – Visão Geral

> Fonte: documento do TC *TCII-N2-IND-Itzac Albertin-Guiliano Rangel Alves* (Google Drive), exportado em 06/10/2026, já com as atualizações pós-implementação. O documento do TC é a fonte da verdade: se houver divergência, atualize este arquivo a partir dele.

## Relação de casos de uso (Quadro 21)

| Código | Caso de uso | Requisitos | Atores |
| --- | --- | --- | --- |
| CU01 | Manter Usuário | RF01 | Usuário |
| CU02 | Realizar Login | RF01 | Usuário |
| CU03 | Buscar Itens | RF02 | Usuário |
| CU04 | Visualizar Histórico | RF03 | Usuário |
| CU05 | Consultar Previsão Preditiva | RF04 | Usuário |
| CU06 | Manter Favoritos | RF09 | Usuário |
| CU07 | Manter Alerta | RF05 | Usuário |
| CU08 | Manter Notificações | RF06 | Usuário |
| CU09 | Cadastrar Dados de Mercado | RF07; RF10 | Admin |
| CU10 | Cadastrar Dados Passados | RF11 | Admin |
| CU11 | Treinar Modelo | RF08; RF12 | Admin |

## Escopo da implementação atual

Os casos de uso **detalhados** em `docs/casos-de-uso/` (CU01, CU02, CU03, CU04, CU05, CU06, CU07, CU08, CU09, CU10) estão implementados; cada arquivo traz a situação no código, as decisões tomadas e o que ficou pendente. A relação de testes por fluxo está em `docs/plano-de-testes-por-fluxo.md`. O CU11 (Treinar Modelo) é **provisório**: está especificado em `CU11-treinar-modelo.md`, com a v4 do documento de alterações do TC, ainda não reexportada do TC; as RNs desse arquivo prevalecem sobre `regras-de-negocio.md` e `requisitos.md`. CU05, CU06, CU07 e CU08 estão especificados nos arquivos `CU05-consultar-previsao-preditiva.md`, `CU06-manter-favoritos.md`, `CU07-manter-alerta.md` e `CU08-manter-notificacoes.md`, com o texto igual ao do TC (seções 6.4.5 a 6.4.8); o CU05 foi implementado pelo pedido `estudos/lstm/pedido-cu05.md`, o CU06 e o CU07 pelo `pedido-cu06-cu07.md` e o CU08 pelo `pedido-cu08.md`. A RN08 (limite de 20 alertas ativos) e a RN07 (gatilho e disparo único do alerta, antiga RN28) prevalecem sobre `regras-de-negocio.md`.

## Atores (seção 6.3)

A plataforma Goblin Ledger conta com dois atores:

- Usuário: a plataforma é voltada para ele, para que possa analisar os preços, o histórico e a previsão dos itens em leilão, manter os itens favoritos e os alertas de preço e consultar as suas notificações;
- Admin: tem a responsabilidade de cadastrar os dados de mercado e os dados passados dos itens e de iniciar o treinamento do modelo preditivo. No sistema, é um usuário com o papel de administrador, atribuído diretamente no banco de dados, sem tela de gestão de papéis (Apêndice C).

As rotinas automáticas, como a coleta dos dados de mercado de hora em hora, a importação diária do histórico, o retreinamento semanal e a consolidação diária do modelo e a verificação dos alertas a cada ciclo de ingestão, não são representadas como atores. São execuções agendadas do próprio sistema, descritas nos cenários dos casos de uso a que pertencem, no campo Ativação.

## Glossário do negócio (Quadro 08)

| Termo / Sigla | Definição |
| --- | --- |
| Auction House (AH) | Casa de Leilões. O mercado central dentro do jogo onde ocorrem as transações de compra e venda. |
| Bid / Buyout | Bid refere-se ao lance mínimo em um leilão; Buyout é o preço de compra imediata do item. |
| Crafting | Processo de manufatura onde matérias-primas são transformadas em itens finalizados de maior valor. |
| Flip / Flipping | Prática de comprar um item por um valor abaixo da média de mercado e revendê-lo rapidamente por um preço superior. |
| Gathering | Profissões de coleta dentro do jogo (ex.: Mineração, Herborismo), base da economia de commodities. |
| Goblin | Gíria da comunidade para jogadores focados exclusivamente em enriquecer no jogo através da Auction House. |
| Gold Farmer | Jogador que acumula riqueza no jogo de forma sistemática e massiva. |
| Item Level (iLvl) | Nível de poder de um equipamento, fator crucial que determina sua utilidade e, consequentemente, seu preço. |
| Real Money Trading (RMT) | Comércio Ilegal de Ouro Virtual por Dinheiro Real (proibido pela desenvolvedora). |
| Série Temporal | Conjunto de observações de preços ordenadas no tempo, base para a predição algorítmica. |
| Snipe | Ato de comprar um item extremamente subprecificado segundos após ele ser postado na Auction House. |
| Token WoW | Item oficial do jogo que pode ser trocado por tempo de assinatura ou saldo em dinheiro real na plataforma da empresa. No Goblin Ledger, é denominado Ficha do WoW. |
| TSM | TradeSkillMaster, principal addon concorrente voltado para economia, operando internamente no jogo. |
| Undermine Exchange | Serviço web que disponibiliza o histórico de preços da Casa de Leilões do World of Warcraft, utilizado como fonte do histórico retroativo de preços (CU10). |
| Valor de Mercado | Primeiro quartil (25%) dos preços dos leilões ativos de um item, ponderado pela quantidade de cada leilão (RN06). |
