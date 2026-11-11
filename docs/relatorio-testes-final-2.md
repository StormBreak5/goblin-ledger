# Relatório da nova execução final da suíte de testes (capítulo 10 do TC)

Pedido: `estudos/lstm/pedido-testes-final-2.md`. Repete a execução de 22/10 (`pedido-testes-final.md`), agora com o CU05 a CU08 implementados e a RN07 do nível de item retirada.

- **Execução:** 11/11/2026, por volta das 19h30 (horário de Brasília), sobre o commit `cedfe7a` (CU08).
- **Sem mudança de código:** a execução não alterou código. A única mudança foi a correção do plano de testes, feita depois, a pedido do autor (seção 6), no commit `3df3228`.

## 1. O que foi rodado

| Suíte | Comando | Onde |
|---|---|---|
| Back-end | `.venv/Scripts/python -m pytest`, a partir de `backend/` | No host, com um PostgreSQL temporário criado pelas migrações (nunca o banco real) |
| Serviço do modelo | `docker compose --profile testes run --rm modelo-testes`, a partir de `backend/` | No container, com pandas e TensorFlow (testes de `tests/modelo`) |
| Front-end | `npm test`, a partir de `frontend/` | Vitest com jsdom, com o backend substituído por respostas fixas |

## 2. Testes executados por suíte (seção 10.3)

Cada caso de um teste parametrizado conta como um teste, como o pytest e o Vitest informam.

| Suíte | Executados | Aprovados | Com falha |
|---|---|---|---|
| Back-end | 387 | 387 | 0 |
| Serviço do modelo | 50 | 50 | 0 |
| Front-end | 76 | 76 | 0 |
| **Total** | **513** | **513** | **0** |

No host, o pytest também mostra 5 módulos de `tests/modelo` como ignorados, porque o pandas não está instalado fora do container. São os mesmos testes que rodam no serviço do modelo; não são falhas.

**Comparação com 22/10** (309 no back-end, 23 no serviço do modelo e 32 no front-end): o aumento vem do CU05 ao CU08 e dos 6 testes do CU11 acrescentados em 30/10 (seção 5).

## 3. Funções de teste por caso de uso e cenário (Quadro 82)

Aqui cada parametrizado conta uma vez, sem expandir os casos. A tabela soma o back-end, o serviço do modelo e o front-end. No front-end, cada teste dos arquivos `cuXX-*` conta no cenário do seu nome. Os testes gerais de cada caso de uso são os `test_cuXX_` sem cenário; no CU08, o `test_rn07_alerta_dispara_uma_unica_vez` também entra entre os gerais. No CU11, "regras do modelo" são os testes de `tests/modelo` sem o prefixo `test_cu11`.

| CU | C1 | C2 | C3 | C4 | Gerais | Regras do modelo | **Total** |
|---|---|---|---|---|---|---|---|
| CU01 | 4 | 8 | 3 | | | | **15** |
| CU02 | 6 | 4 | 4 | 3 | | | **17** |
| CU03 | 10 | 5 | 2 | | | | **17** |
| CU04 | 22 | 16 | 10 | | | | **48** |
| CU05 | 15 | 3 | 2 | | | | **20** |
| CU06 | 8 | 8 | 8 | | 1 | | **25** |
| CU07 | 10 | 10 | 5 | | 2 | | **27** |
| CU08 | 5 | 3 | 9 | | 3 | | **20** |
| CU09 | 32 | 12 | 8 | 6 | 2 | | **60** |
| CU10 | 45 | 31 | 14 | | 2 | | **92** |
| CU11 | 19 | 16 | 12 | | 3 | 16 | **66** |
| **Soma** | | | | | | | **407** |

**De onde vêm as funções do CU04 ao CU08 e do CU11:**

| CU e cenário | Back-end | Serviço do modelo | Front-end |
|---|---|---|---|
| CU04-C1 / C2 / C3 | 15 / 7 / 0 | — | 7 / 9 / 10 |
| CU05-C1 / C2 / C3 | 9 / 0 / 0 | 2 / 0 / 0 | 4 / 3 / 2 |
| CU06-C1 / C2 / C3 / gerais | 4 / 4 / 4 / 1 | — | 4 / 4 / 4 / 0 |
| CU07-C1 / C2 / C3 / gerais | 5 / 5 / 2 / 2 | — | 5 / 5 / 3 / 0 |
| CU08-C1 / C2 / C3 / gerais | 5 / 3 / 4 / 3 | — | 0 / 0 / 5 / 0 |
| CU11-C1 / C2 / C3 / gerais / regras | 8 / 4 / 4 / 2 / 0 | 11 / 12 / 8 / 1 / 16 | — |

**Observações:**
- **CU05-C1:** o front-end tem um `it.each` com os FA1 a FA6, um caso por fluxo. Ele conta como uma função, então são 4 funções no front, mas 9 testes executados.
- **CU08-C3:** inclui o `test_cu08_c3_so_as_notificacoes_do_proprio_usuario`, pelo prefixo do nome. O relatório do CU08 o tinha posto entre os gerais; foi corrigido (seção 6).
- **CU07-C3 e CU08:** o C3-FA1 do CU07 (exclusão cancelada) só acontece na tela. O C1 e o C2 do CU08 são só do sistema, sem tela.

## 4. Testes de apoio (sem prefixo de caso de uso)

São **39 funções**:
- **33 no back-end:** migrações, o leitor do arquivo da Undermine, os leitores de eventos e outros;
- **6 no front-end:** `moeda.test.ts`.

Expandindo os parametrizados, o back-end executa 38 testes de apoio.

**Diferença em relação aos 91 de 22/10:**
- O mesmo contador, aplicado aos testes do commit `83bebfb` (o estado do código em 22/10), também dá 39 funções de apoio.
- Contando os casos executados, também não se chega a 91.
- O número de 22/10 deve ter usado outro critério, e não é possível reproduzi-lo com o deste pedido.
- O valor 39, com este critério, não mudou desde 22/10.

## 5. Mudanças em relação a 22/10 (CU01 a CU04 e CU09 a CU11)

Comparei os nomes das funções do estado de 22/10 (commit `83bebfb`, extraído para uma pasta temporária) com os de agora.

| CU | 22/10 | 11/11 | Mudou? |
|---|---|---|---|
| CU01 | 15 | 15 | Não |
| CU02 | 17 | 17 | Não |
| CU03 | 17 | 17 | Não |
| CU04 | 48 | 48 | Não |
| CU09 | 60 | 60 | Não |
| CU10 | 92 | 92 | Não |
| CU11 | 60 | 66 | **Sim, +6** |

- **CU01, CU02, CU03, CU04, CU09 e CU10:** as funções têm os mesmos nomes de 22/10. A retirada da RN07 do nível de item (commit `d1bb779`) não removeu nem renomeou testes desses casos de uso.
- **CU11:** as 6 funções novas vieram do commit `c5e3d88`, de 30/10 ("GELU e subclasse dentro da classe no modelo", etapas 2g e 2i):
  - **C1 +1:** `test_cu11_c1_passo8_rede_com_gelu`;
  - **C2 +1:** `test_cu11_c2_vigente_antigo_avaliado_com_a_propria_chave_e_ativacao`;
  - **C3 +1:** `test_cu11_c3_previsao_com_vigente_antigo_usa_a_chave_antiga`;
  - **regras do modelo +3:** `test_rn24_par_desconhecido_vira_zero`, `test_rn24_subclasse_pelo_par_classe_subclasse` e `test_rn24_versao_antiga_mantem_o_codigo_da_subclasse`.
- **Com isso:** C1 passou de 18 para 19, C2 de 15 para 16, C3 de 11 para 12 e as regras do modelo de 13 para 16. Os gerais ficaram em 3.

## 6. Correção do plano de testes (commit `3df3228`)

A pedido do autor, o `docs/plano-de-testes-por-fluxo.md` passou a seguir a contagem por funções.

- **Cabeçalho:**
  - explica que se conta por função, com cada parametrizado valendo uma;
  - o total passou a 407 funções com identificador; antes eram 412, porque o CU05 contava 25 em vez de 20;
  - inclui as 39 funções de apoio e o resultado desta execução (513 testes, sem falhas).
- **CU05 – Cenário 1:** passou a 15 testes. Uma nota explica que as 20 linhas da tabela incluem os 6 casos do `it.each`.
- **CU08:** o `test_cu08_c3_so_as_notificacoes_do_proprio_usuario` passou dos gerais para o Cenário 3 (C3 = 9, gerais = 3). A tabela do Quadro 82 do `docs/relatorio-cu08.md` recebeu a mesma correção.

**Conferência depois da correção:**
- toda função de teste do código está no plano;
- as únicas linhas do plano sem uma função própria são os 5 casos extras do `it.each` do CU05-C1;
- a soma dos cabeçalhos das seções dá 407, igual à contagem do código.

## 7. Coluna "Resultado Obtido" dos Quadros 75 a 78

Nesta execução, todos os testes do CU05 ao CU08 passaram. A conferência no navegador de cada caso de uso está no seu relatório, e em todos os cenários (C1 a C3) o resultado esperado foi obtido:

| Quadro | CU | Relatório | C1 | C2 | C3 |
|---|---|---|---|---|---|
| 75 | CU05 – Consultar Previsão Preditiva | `docs/relatorio-cu05.md` | Sim | Sim | Sim |
| 76 | CU06 – Manter Favoritos | `docs/relatorio-cu06.md` | Sim | Sim | Sim |
| 77 | CU07 – Manter Alerta | `docs/relatorio-cu07.md` | Sim | Sim | Sim |
| 78 | CU08 – Manter Notificações | `docs/relatorio-cu08.md` | Sim | Sim | Sim |

Os fluxos que dependem de uma falha forçada não foram exercitados no navegador e estão cobertos pelos testes:
- a queda do banco (os FE1);
- o SMTP fora do ar (CU08-C2-FA1);
- a injeção de volume (CU08-C1-FA2);
- o limite de 20 alertas (os FA2 do CU07).

## 8. Como a contagem foi feita

- **Testes executados:** os totais vêm da saída do pytest e do Vitest.
- **Funções:** a contagem é estática, pelos nomes nos arquivos de teste:
  - no back-end, cada `def test_…` dos arquivos `test_*.py` de `backend/tests`;
  - no front-end, cada chamada `it(…)`, `test(…)` ou `it.each(…)` no início de uma linha, classificada pelo nome do teste (ou pelo nome do primeiro caso, no `it.each`).
- **Correção do contador:** o contador usado no relatório do CU07 tinha um falso positivo no front-end, porque contava linhas que começam com "it…" fora de uma chamada. Ele foi refeito para esta execução; o falso positivo não afetou nenhum número publicado.
- **Conferência:** os totais por caso de uso batem com a soma das seções do plano de testes (seção 6) e com os relatórios do CU05 ao CU08.
