# Pedido – nova execução final da suíte de testes (números do capítulo 10 do TC)

> Repete o `pedido-testes-final.md` (execução de 22/10), agora com o CU05 a CU08 implementados e a RN07 do nível de item retirada.

**Objetivo:** rodar toda a suíte e devolver os números que entram no capítulo 10 do TC: a seção 10.3, o Quadro 82 e a coluna "Resultado Obtido" dos Quadros 75 a 78.

**Não é para alterar código.** Se algum teste falhar, relate só qual falhou e por quê.

Lembrete do CLAUDE.md: não leia nem altere arquivos `.env`.

## O que rodar

1. **Back-end** (fora do serviço do modelo): a suíte do `backend`, como de costume (pytest com o banco temporário).
2. **Serviço do modelo:** `docker compose --profile testes run --rm modelo-testes` (testes de `tests/modelo`).
3. **Front-end:** `npm test` na pasta `frontend`.

## O que devolver

1. A data da execução.
2. Para cada suíte (back-end, serviço do modelo e front-end): o total de testes executados, aprovados e com falha. Conte cada caso de um teste parametrizado como um teste, como o pytest e o Vitest informam.
3. Por caso de uso e cenário, a quantidade de **funções** de teste, sem expandir os parametrizados, somando o back-end, o serviço do modelo e o front-end:
   - **CU01, CU02, CU03 e CU09:** por cenário (`test_cuXX_cY_...`);
   - **CU04 a CU08:** por cenário no back-end. No front-end, conte os testes dos arquivos `cuXX-*` pelo cenário que cada um verifica. Some também os testes gerais de cada CU (`test_cuXX_` sem cenário, como os da RN20 e o `test_cu07_so_o_dono_altera_e_exclui_o_alerta`) e o `test_rn07_alerta_dispara_uma_unica_vez`, no CU08;
   - **CU10:** por cenário, mais os testes gerais do caso de uso (`test_cu10_` sem cenário);
   - **CU11:** por cenário, mais os testes gerais (`test_cu11_` sem cenário) e os testes de `tests/modelo` que não têm o prefixo `test_cu11` (regras do modelo).
4. Quantas funções de teste não têm prefixo de caso de uso (testes de apoio: migrações, leitores da Undermine, eventos, moeda etc.).
5. Se alguma contagem do CU01 a CU04 ou do CU09 a CU11 mudou em relação à execução de 22/10, diga qual e por quê.

**Contagem de 22/10, para conferência** (Quadro 82 atual):

| CU | Funções de teste |
| --- | --- |
| CU01 | 15 |
| CU02 | 17 |
| CU03 | 17 |
| CU04 | 48 |
| CU09 | 60 |
| CU10 | 92 |
| CU11 | 60 |

Na mesma data, as suítes tinham 309 testes no back-end, 23 no serviço do modelo e 32 no front-end, e 91 testes de apoio.
