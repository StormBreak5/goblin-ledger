# Checklist pós-implementação — Goblin Ledger (29/09/2026)

Origem de cada item: **DP** = `docs/decisoes-e-pendencias.md` · **PT** = `docs/plano-de-testes-por-fluxo.md` ·
**TC** = revisão do documento no Drive (versão de 29/09).

**Ordem sugerida:** 1. Decisões → 2. Documento do TC → 3. Código → 4. `docs/` do repositório.
Várias mudanças no documento dependem de uma decisão (indicada como D1…D11).

---

## 1. Decisões (anote a escolha em cada uma)

- [ ] **D1 – Fuso horário** (DP §2.1). *Sugestão:* manter o banco em UTC e converter só na tela.
  → TC: CU04-C3 passo 3 "no fuso horário do usuário". Código: nada.
- [ ] **D2 – Reinício semanal** (DP §2.2). EU: quarta-feira (confirmar). EUA: o código registra "terça 7:00 PDT", mas a
  Warcraft Wiki dá 15:00 UTC para as Américas, que no horário de verão é **8:00 PDT** (7:00 é PST). O evento é gravado por
  data, então só muda o texto da fonte. → Código: corrigir o texto, se for o caso.
- [ ] **D3 – Noblegarden e Lunar Festival** (DP §2.3). *Sugestão:* manter as datas geradas com "(aproximado)" e usar o
  cadastro manual (C2-FA2) quando houver data oficial. → TC: citar a limitação no CU10-C2.
- [ ] **D4 – Lacuna do CU10-C3: 3 ou 4 dias** (DP §2.4). O apagão da Undermine (28/06 a 01/07/2024) é da fonte, não do
  mercado. Com 3 dias, ele parte em duas todas as séries longas. *Sugestão:* 4 dias.
  → Código: `COBERTURA_LACUNA_MAXIMA_DIAS=4` e rodar a validação de novo. TC: RN15 e CU10-C3.
- [ ] **D5 – Bid/Buyout** (DP §2.5). *Sugestão:* corrigir o texto. Guardar esses valores por ciclo mudaria o esquema e a
  ingestão, e as commodities nem têm Bid. → TC: Quadro 04 (RF03) e objetivo do CU04-C3.
- [ ] **D6 – Data da última atualização na lista do CU03** (DP §2.6). A API já devolve `last_auction_update`: falta só a
  tela. *Sugestão:* mostrar. A alternativa é tirar o passo 4 do documento. → Código (frontend) ou TC.
- [ ] **D7 – Alinhamento do MR** (DP §2.7, §3 CU09 "Chaves", §7). **Obrigatório antes do CU11.** Os problemas são:
  - `items.id` é UUID, mas `item_id` é inteiro nas tabelas de preço;
  - a região aparece como `us` numa tabela e como `3209`/`32512` na outra;
  - as commodities são gravadas em `3209` pela Undermine e em `32512` pela Blizzard;
  - faltam as FKs em `leilao.item_id` e `historical_item_prices.item_id`.

  → Código: migração 0007, planejada com o Claude Code. TC: MER/MR.
- [ ] **D8 – Ficha do WoW** (DP §2.8, §4). *Sugestão:* não criar um CU. Citá-la no RF03/CU04 (o histórico exibido) e no
  RF07/CU09 (a coleta de 15 min pela Blizzard) como item especial com série própria. → TC.
- [ ] **D9 – Histórico dos itens novos** (DP §2.9). 3.381 itens entraram sem histórico. *Sugestão:* o worker agenda a
  importação (CU10-C1) dos itens recém-cadastrados. → Código + TC (CU09-C3 FA1).
- [ ] **D10 – Emenda das séries** (DP §2.10). O preço da Undermine é o menor preço; o da Blizzard é o 1º quartil.
  → Decidir no CU11. Por ora, só registrar no TC (seção de achados, abaixo).
- [ ] **D11 – Termos das fontes** (DP §2.11). → TC: novo risco R06 no Quadro 06.

---

## 2. Documento do TC

### Pré-textuais e formatação (TC)
- [ ] Quadro 1 (Revisões): incluir a V3.0, com a implementação dos CU01–CU04, CU09 e CU10.
- [ ] Todos os CUs usam "Quadro 22"/"Quadro 23": numerar em sequência.
- [ ] Os diagramas de atividades estão sem "Figura XX -": legendar e numerar.
- [ ] A Figura 06 está rotulada "CU01C01", mas é do CU04: trocar para "CU04C01".
- [ ] As seções do CU04 estão numeradas 6.4.1.1 a 6.4.1.3: trocar para 6.4.4.1 a 6.4.4.3.
- [ ] "3.4.1 Requisitos não funcionais" repete o número: trocar para 3.4.2.
- [ ] Atualizar o sumário e as listas de ilustrações e de quadros. O sumário ainda tem "5.12 … Gestão de Itens Favoritos".

### Cap. 2 – Cronograma
- [ ] Incluir as figuras do cronograma do TC2 (N1 e N2) e pintar as linhas de Entrega.
- [ ] Prazo: entregáveis do TCII.N2 até 23/10.

### Cap. 3 – Requisitos, riscos e RNs
**Quadro 04**
- [ ] RF03: tirar "(Bid e Buyout)" (D5).
- [ ] RF07: tirar "paginação". A API da Blizzard devolve o snapshot inteiro do reino em uma resposta.
- [ ] RF11: trocar "TSM/Undermine Journal … scrapping de sites como Wowhead/WoW Wiki" por "Undermine Exchange (preços) e
  Wikipedia, Warcraft Wiki e API da Blizzard (eventos)". O Wowhead carrega os eventos por JavaScript e não serve.

**Quadro 06 – Riscos**
- [ ] O R05 cita a RN04 para outliers: trocar para RN03.
- [ ] Novo **R06 – Termos de uso das fontes** (D11):
  - riscos: o `robots.txt` da Undermine bloqueia `/data/`; a Warcraft Wiki declara `ai-train=no`; a Wikipedia é
    CC BY-SA; a Blizzard tem cota de 36.000 requisições/h;
  - mitigação: ritmo limitado (RN23), `User-Agent` identificado, leitura mínima e fonte citada em cada registro.
- [ ] (Opcional) **R07 – Lacunas e mudanças de formato na fonte histórica** (apagão de 4 dias, stub de commodities).
  Mitigação: FE3 do CU10-C1 e tolerância de lacuna.

**Quadro 07 – RNs**
- [ ] RN04: acrescentar a retenção de 7 dias dos leilões Expirado/Vendido e associar ao RF07 (quem aplica é o CU09).
- [ ] RN09: definir o limiar de **24 h** para "Dados Desatualizados".
- [ ] RN11: reescrever ("só aceita contas e dados de reinos das regiões US e EU") e associar também ao RF11.
- [ ] RN12: definir o critério. Volume anômalo é o que passa de 10× a mediana dos 7 dias anteriores, com piso de
  100 unidades e pelo menos 24 pontos anteriores.
- [ ] RN14: corrigir "Provide" para "Provider" e associar a RNF07/RF07 (hoje está RNF08).
- [ ] RN15: "6 meses" = **180 dias contínuos**, aceitando lacunas de até 3 dias (ou 4, conforme a D4).
- [ ] RN16: trocar "(TSM, scrapping)" por "(Undermine Exchange, web scraping)". Registrar que cada registro guarda a
  granularidade (DIÁRIA/HORÁRIA) e a origem.
- [ ] RN17: ampliar para os tipos implementados: expansão, patch, temporada, evento sazonal, recorrente e outro.

**3.6.2 – Rastreabilidade**
- [ ] RF01 está rotulado "Integração com API Blizzard": trocar para "Autenticação de Usuário" (RN11, RN18–RN22).
- [ ] Criar a linha do RF07 (RN04, RN05, RN06, RN09, RN11, RN14) e tirar a RN05 do RF01.
- [ ] Tirar a RN12 do RF05 e criar a linha do RF10 (RN01, RN12).
- [ ] Criar as linhas RF09 → RN20 e RF11 → acrescentar RN23 e RN11.

**Glossário**
- [ ] Incluir Commodity, Reino conectado, Valor de mercado (1º quartil) e Undermine Exchange.
- [ ] Indicar que "Token WoW" é a "Ficha do WoW" no sistema.

### Cap. 5 – Quadros dos RFs
- [ ] **Quadro 09 (RF01):** senha com mínimo de 8 e máximo de 255 caracteres; sessão por JWT válida por 24 h.
- [ ] **Quadro 10 (RF02):** nenhum cenário do CU03 aplica a RN01 nem a RN04, e a descrição fala de
  "Expirado/Vendido". Tirar, ou dizer onde se aplicam.
- [ ] **Quadro 11 (RF03):** o domínio da janela é '7D','14D','30D','ALL', mas o implementado é
  **14D, 30D, 90D, 365D e ALL**.
- [ ] **Quadro 15 (RF07):** tirar "paginação".
- [ ] **Quadro 19 (RF11):**
  - incluir a RN23 (e a RN11);
  - trocar as fontes, como no RF11 do Quadro 04;
  - trocar a variável "Região e identificador do item – Texto 255 – Endereço Web Válido" por Região (US/EU) e
    ID do item (inteiro).

### Cap. 6 – Casos de uso
**CU02**
- [ ] C4-FA1: trocar "Sessão expirada por inatividade" por "Sessão expirada". A sessão vale 24 h após o login e não há
  prazo de inatividade separado.

**CU03**
- [ ] C1 e C2, passo 4: conforme a D6.
- [ ] No C2, trocar "para cada item localizado" por "para o item localizado".

**CU04**
- [ ] C1 passo 3: trocar "preço mais baixo" por valor de mercado (RN06), com o menor preço como informação secundária.
- [ ] C1-FA1 passo 1.1: citar o limiar de 24 h (RN09).
- [ ] C2, objetivo: listar as janelas 14D, 30D, 90D, 365D e ALL.
- [ ] C2-FA1 e C1-FA2: conferir se há espaço antes das aspas finais das mensagens.
- [ ] C3, objetivo: tirar Bid/Buyout (D5).
- [ ] C3 passo 3: "data e hora no fuso horário do usuário" (D1).

**CU09**
- [ ] C2 passo 4: citar o critério da RN12.
- [ ] C2-FA1: trocar "limite aceitável" por **5% do lote**.
- [ ] C3-FA1: o item é cadastrado com o nome provisório "Item {id}", e o nome e o ícone vêm depois pela API de dados do
  jogo. Se a D9 for sim, acrescentar que o sistema agenda a importação do histórico.
- [ ] C4: incluir os fluxos cujos textos o código já usa:
  - usuário sem papel de Admin: "Acesso restrito ao administrador";
  - região inválida: "Informe uma região válida (US ou EU) com mercados monitorados".

**CU10**
- [ ] Título da seção 6.4.10: trocar "Cadastrar Dados de Mercado" por **"Cadastrar Dados Passados"**.
- [ ] C1-FA1: trocar o texto de JSON/CSV por: no passo 2, região fora de US/EU ou identificador inválido →
  "Região ou item inválido. Verifique os dados informados" → retorna ao passo 1.
- [ ] C1-FE2: trocar "No passo 8" por "No passo 9".
- [ ] C1-FE3: acrescentar "3.4 Fim".
- [ ] C1: incluir o FA "Importação em andamento" ("Já existe uma importação em andamento").
- [ ] C1: no FE1 e no FE3, citar os limites (20 falhas de rede seguidas; 3 arquivos ilegíveis seguidos).
- [ ] C1 passo 3: o arquivo traz o histórico diário e cerca de 14 dias de registros horários.
- [ ] C2, objetivo: "eventos que influenciam os preços", não só patches e expansões.
- [ ] C2 passo 1: o Admin escolhe a fonte (expansões, patches, sazonais, temporadas ou recorrentes). Trocar
  "Wowhead ou WoW Wiki" por "Wikipedia ou Warcraft Wiki".
- [ ] C2 passo 5: listar os 6 tipos.
- [ ] C3: trocar "6 meses" por "180 dias".
- [ ] C3 passo 3: lacunas de até 3 dias (ou 4, conforme a D4). A base são os registros do item de qualquer região e
  origem, reduzidos a um por dia.

**Diagramas** (refazer depois do texto)
- [ ] CU04C01 (passo 3), CU10C02 (fontes e tipos) e CU10C03 (180 dias e lacuna).
- O CU10C01 já está com o FA1 e o FE2 corretos.

### Cap. 7 e 8 – Dados e arquitetura
- [ ] **MER/MR** (depois da D7):
  - incluir as tabelas `ciclo_ingestao`, `estado_mercado`, `evento_jogo`, `extracao_evento`, `aptidao_treinamento`,
    `sessao`, `token_recuperacao` e `tentativa_login`;
  - incluir as colunas `origem`, `anomalia` e `granularidade` em `historical_item_prices`, e as colunas de resumo em
    `scraper_execution_logs`;
  - em `usuario`: acrescentar `regiao` e `role`, tirar `nome_usuario` e usar e-mail de 150 caracteres.
- [ ] **Diagrama de implantação:** conferir se aparecem o worker (APScheduler), o PostgreSQL no Docker, o SMTP/Mailpit
  e as fontes externas (API Blizzard, Undermine Exchange, Wikipedia, Warcraft Wiki).

### Seções novas
- [ ] **Plano de testes** (apêndice): a tabela do PT, com 230 testes (um por fluxo). A suíte tem 314 testes: 282 no
  backend e 32 no frontend.
- [ ] **Quadro de parâmetros configuráveis** (DP §8): valor padrão e onde se aplica. Responde na banca "de onde veio
  esse número".
- [ ] **Achados sobre os dados** (DP §7), para o CU11 e os resultados:
  - o apagão de 4 dias;
  - o stub de commodities: 6.099 itens corrigidos e 12,6 milhões de registros reimportados;
  - a validação: 19.289 itens aptos e 1.800 inaptos;
  - as medidas diferentes entre as fontes.
- [ ] (Opcional) **Como executar:** Docker, migrações Alembic e variáveis de ambiente.

### Referências
- [ ] A Undermine Exchange já consta.
- [ ] Incluir a Wikipedia (tabela de expansões do WoW) e a Warcraft Wiki (*Patch history* e *Holiday*).
- [ ] Incluir o Blizzard Developer Portal (APIs de leilões, commodities e temporadas).

---

## 3. Código (Claude Code)

**Sem depender de decisão**
- [ ] Criar o teste do **CU01-C3 FA1** (exclusão cancelada). O botão "Cancelar" existe em
  `frontend/app/perfil/page.tsx`, mas é o único fluxo do documento sem teste próprio (PT).
- [ ] Renomear `test_cu04_c2_a_janela_sem_pontos_..._usa_o_texto_do_fa2`. O PT o lista como CU04-C2 FA2, que não existe
  (é o texto do C1-FA2). Depois, regerar o plano de testes.
- [ ] **Você:** preencher `JWT_SECRET` no `backend/.env` (hoje está vazio, e as sessões caem a cada reinício). Para gerar:
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- [ ] Confirmar que 32513 é o id das commodities da EU antes de colocar um reino EU em `MONITORED_REALMS`.

**Depois das decisões**
- [ ] D2: texto da fonte do reinício.
- [ ] D4: lacuna e nova validação.
- [ ] D6: data na lista do CU03.
- [ ] D7: migração 0007.
- [ ] D9: importação automática dos itens novos.
- [ ] Se algum texto de mensagem mudar no TC, trocar no código (o CLAUDE.md exige o texto exato).

## 4. `docs/` do repositório
- [ ] Depois de atualizar o TC, reexportar `docs/` (requisitos, RNs e CUs), que é a fonte da verdade do Claude Code.
- [ ] Reescrever as linhas "Situação no código" de `docs/casos-de-uso/*.md` (estão todas desatualizadas).

---

### Prompt para o Claude Code (itens da seção 3 que não dependem de decisão)

```
Leia docs/checklist-pos-implementacao.md, seção 3, "Sem depender de decisão". Em modo de planejamento:
1) crie o teste test_cu01_c3_fa1_exclusao_cancelada no frontend (o botão Cancelar já existe em app/perfil/page.tsx);
2) renomeie o teste do CU04 que cita "fa2" no Cenário 2, deixando claro que ele usa o texto do C1-FA2, e regere
   docs/plano-de-testes-por-fluxo.md;
3) verifique se 32513 é o id das commodities da EU na Undermine Exchange, sem alterar MONITORED_REALMS.
Não leia nem altere .env. Rode pytest e npm test. Um commit por item.
```
