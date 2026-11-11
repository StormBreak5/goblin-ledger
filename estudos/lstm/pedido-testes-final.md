# Pedido – execução final da suíte de testes (números do capítulo 10 do TC)

**Objetivo:** rodar toda a suíte e devolver os números que entram no capítulo 10 do TC (seções 10.2 e 10.3). Não é para alterar código: se algum teste falhar, só relate qual falhou e por quê.

Lembrete do CLAUDE.md: não leia nem altere arquivos `.env`.

## O que rodar

1. **Back-end** (fora do serviço do modelo): a suíte do `backend` como de costume (pytest com o banco temporário).
2. **Serviço do modelo:** `docker compose --profile testes run --rm modelo-testes` (testes de `tests/modelo`).
3. **Front-end:** `npm test` na pasta `frontend`.

## O que devolver

1. A data da execução.
2. Para cada suíte (back-end, serviço do modelo, front-end): total de testes executados, aprovados e com falha. Conte cada caso de um teste parametrizado como um teste, como o pytest e o Vitest informam.
3. Por caso de uso e cenário, a quantidade de **funções** de teste (sem expandir os parametrizados), somando o back-end e o serviço do modelo:
   - CU01, CU02, CU03 e CU09: por cenário (`test_cuXX_cY_...`);
   - CU04: por cenário no back-end e, no front-end, os testes dos arquivos `cu04-*`;
   - CU10: por cenário, mais os testes gerais do caso de uso (`test_cu10_` sem cenário);
   - CU11: por cenário, mais os testes gerais (`test_cu11_` sem cenário) e os testes de `tests/modelo` que não têm o prefixo `test_cu11` (regras do modelo).
4. Quantas funções de teste não têm prefixo de caso de uso (testes de apoio: migrações, leitores da Undermine, eventos, moeda etc.).

Contagem estática feita em 22/10 (para conferência): CU10-C1 = 45, CU10-C2 = 31, CU10-C3 = 14, CU10 gerais = 2; CU11-C1 = 18, CU11-C2 = 15, CU11-C3 = 11, CU11 gerais = 3, regras do modelo = 13.
