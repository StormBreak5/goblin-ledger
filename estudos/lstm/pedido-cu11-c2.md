# Pedido ao Claude Code: CU11, Cenário 02 (retreinamento semanal), e ajustes do C1

Este é o **pedido 3 da etapa 3 de `estudos/lstm/ROTEIRO.md`**. O Cenário 01 está pronto (commit `7cf75f2`, versão 1 do modelo, região US). Este pedido tem três partes, nesta ordem: a série diária da Undermine, que o C2 e o C3 precisam atualizada; três ajustes do C1; e o C2.

## Autorização do autor

O CU11 continua provisório, especificado em `docs/casos-de-uso/CU11-treinar-modelo.md`. Autorizo também a mudança no comportamento automático do CU10 descrita na Parte 1.

## Parte 1: série diária da Undermine atualizada (pré-requisito do C2 e do C3)

**Problema.** O modelo usa só a série diária da Undermine (RN16). Hoje ela só é atualizada pela recuperação automática do worker, que roda quando o worker fica mais de 48 horas sem coletar (`ImportacaoHistoricoService.recuperar()`, importação incremental). Com o worker no ar, a série para de crescer. Aí o C2 retreinaria toda semana com os mesmos dados, e o C3 não teria o preço real do dia para comparar.

Há também um defeito de dado. A importação incremental grava só o que é mais novo que o último registro de cada item, com `ON CONFLICT DO NOTHING`. A recuperação de 19/10/2026, às 02:11 UTC, gravou o dia 19/10 ainda incompleto: cerca de 9.787 itens, contra uns 18 mil nos outros dias. Como o menor preço daquele dia só cobre as primeiras horas, esse registro parcial nunca mais vai ser corrigido.

**O que fazer:**

1. **Importação diária.** Agende no worker uma importação incremental diária, com a mesma rotina da recuperação, para todos os reinos monitorados.
   - O horário é configurável em `HISTORICO_IMPORTACAO_DIARIA_CRON`. Sugestão: todo dia às 02:00 UTC.
   - A regra das 48 horas continua como está.
   - A trava que impede duas importações ao mesmo tempo continua valendo.
2. **Só dias encerrados.** A importação não grava registros diários da data UTC corrente.
3. **Correção do dia parcial.** No plano, proponha como regravar os registros diários gravados antes de o dia terminar (o 19/10/2026) com o valor do dia completo, sem perder outros dados. Espere a minha aprovação antes de mexer em registros que já estão no banco.
4. **Tempo.** Meça quanto tempo a importação diária leva.

## Parte 2: ajustes do C1

1. **Dias encerrados no pipeline do modelo.** O C1, o C2 e o C3 consideram só os registros anteriores à data UTC da execução. Essa data é um parâmetro, para os testes poderem controlá-la. O texto novo da RN25 diz: "O histórico considera somente os dias já encerrados".
2. **Situação "Ignorada".** Troque `IGNORADO` por `IGNORADA` em todos os lugares:
   - a constante;
   - a restrição da tabela, com uma migração que atualize os registros existentes;
   - a tela;
   - os testes.

   O domínio do RF08 passa a ser 'Liberada', 'Bloqueada' ou 'Ignorada', e o passo 3.2 do C1-FA3 diz que o sistema "classifica a projeção do item como 'Ignorada'". Atualize os dois no CU11.
3. **Liberados sem amostra de treino.** Acrescente ao resumo do C1 e do C2 quantos itens liberados não têm nenhuma amostra no período de treinamento. São os itens lançados depois do fim desse período, que integram o conjunto de treinamento pela RN15 mas não ajustaram os pesos. Preencha esse número na execução 1 a partir de `backend/modelos/v1/avaliacao_teste.parquet`: o resultado tem que ser **292**. Mostre o número na tela.

## Parte 3: CU11, Cenário 02

**Leia antes de planejar:**
- o Cenário 02 e as "Observações para a implementação" de `docs/casos-de-uso/CU11-treinar-modelo.md`;
- o diagrama `docs/diagramas-atualizados/cu11c02.png`;
- o código do C1: `backend/src/ml/`, `backend/src/modelo_worker.py` e `backend/src/services/treinamento_service.py`.

As tabelas da migração 0007 já preveem o retreinamento: `TIPO_RETREINAMENTO`, `DISPARO_AGENDADO` e `substituido_em`.

**Já decidido, não pergunte:**

- **Disparo (passo 1):**
  - um agendador no serviço `modelo`, com APScheduler, como o worker, no horário de `MODELO_RETREINO_CRON` (sugestão: terça às 18:00 UTC, depois do reinício semanal dos EUA);
  - a cada disparo, ele registra uma execução `RETREINAMENTO`/`AGENDADO` na fila para cada região que tem modelo vigente;
  - região sem modelo vigente não é retreinada, e isso só vai para o log;
  - se já houver uma execução aguardando ou em andamento, ele não registra outra e registra isso no log;
  - crie um comando que dispare o mesmo caminho do agendador, para os testes e para o C3-FA4. Exemplo: `python -m src.modelo_worker --retreinar US`.
- **Passos 2 a 5:** os mesmos do C1, com o código reaproveitado. A divisão 70/20/10 é recalculada até o último dia encerrado. A divisão proporcional fica como está.
- **Passo 6 (RN26):** o modelo novo e o vigente são avaliados no **mesmo período de teste novo**.
  - O vigente usa as **próprias** constantes, vocabulário e escala do alvo (o `normalizacao.json` da versão dele), aplicados aos cortes novos.
  - **Atenção:** hoje o `preparar(normalizacao_base=...)` também reaproveita os cortes da versão de origem e confere a assinatura inteira. No C2, as constantes da versão vigente são aplicadas aos cortes novos, então a conferência passa a ser só das constantes.
  - Reaproveite as variáveis brutas, para não ler e higienizar a base duas vezes.
- **Passo 7, critério da RN26:** a mediana do MdAPE por item (a métrica da RN10), calculada só nos itens avaliados pelos dois modelos, nos mesmos dias. O novo substitui o vigente se essa mediana for **estritamente menor**.
- **Passo 8:** o novo vira o vigente, e o anterior recebe `substituido_em`.
- **FA2:** o modelo novo é descartado, mas fica registrado com as métricas e marcado como descartado. Os artefatos dele são mantidos.
- **Passo 9:** a situação de **todos** os itens elegíveis é recalculada com o modelo que ficou vigente, na avaliação do período de teste novo (RN10, com o mínimo de 30 dias). Os bloqueios por degradação (C3-FA3) caem aqui.
- **FA1:** os itens da região em `projecao_item` que deixaram de ser elegíveis viram `BLOQUEADA`, com o motivo "deixou de ser elegível". Conte quantos deles estavam liberados.
- **Passo 10:** o resumo da execução traz:
  - a versão vigente anterior e a versão nova;
  - a decisão;
  - a mediana do MdAPE de cada modelo e quantos itens foram comparados;
  - os itens liberados, bloqueados (por motivo) e ignorados;
  - os liberados sem amostra de treino e os liberados fora do conjunto de treinamento;
  - os itens que deixaram de ser elegíveis;
  - o último dia usado.

  O resumo vai também para o log. A tela do Admin já lista as execuções: mostre o tipo e, no retreinamento, a comparação. Não crie tela nova.
- **Aviso:** se o último dia encerrado da base tiver mais de 3 dias, o resumo leva o aviso "série diária desatualizada". Isso não bloqueia o retreinamento.
- **FE1:** uma falha nos passos 3 a 8 deixa a execução como `FALHA`. O modelo vigente continua, e `projecao_item` não muda.

**Comece em modo de planejamento.** Proponha:
- os arquivos;
- a migração 0008;
- o agendamento;
- a lista de testes, um por fluxo.

Testes esperados, além dos que você achar necessários:

- `test_cu11_c2_fluxo_principal_substitui_modelo_rn26`
- `test_cu11_c2_fa1_item_deixou_de_ser_elegivel`
- `test_cu11_c2_fa2_novo_modelo_inferior_mantem_vigente`
- `test_cu11_c2_fe1_falha_mantem_vigente`
- `test_cu11_c2_agendador_registra_um_retreinamento_por_regiao_com_modelo_vigente`
- `test_cu11_c2_agendador_nao_duplica_execucao_em_andamento`
- `test_cu11_c2_compara_os_dois_modelos_no_mesmo_periodo_com_as_constantes_de_cada_versao`
- `test_cu11_c2_item_novo_liberado_ao_atingir_o_minimo_de_dias`
- `test_rn25_considera_somente_dias_encerrados`
- `test_cu10_c1_importacao_diaria_grava_so_dias_encerrados`

Pergunte no plano só o que contrariar algo decidido aqui. **Espere a minha aprovação antes de implementar.**

## Regras

- Siga o `CLAUDE.md`, como no C1: um teste por fluxo, mensagens exatas, docstrings citando o CU e a RN e valores configuráveis em `backend/.env.example`.
- Nos testes do modelo, use dados sintéticos e a rede mínima. Para forçar o FA2, use um `Treinador` falso que devolva um modelo pior.
- **Não leia nem altere arquivos `.env`.**

## Depois de implementar

1. Rode as três suítes: host, container do `modelo` e frontend, com `npm run lint` e `npx tsc --noEmit`.
2. Rode a importação diária uma vez, com os dados reais. Traga o tempo, os registros gravados e a confirmação de que o 19/10/2026 ficou completo.
3. Dispare o retreinamento da região US pelo comando e traga:
   - a decisão;
   - a mediana do MdAPE dos dois modelos no mesmo período de teste e quantos itens foram comparados;
   - os itens liberados, bloqueados (por motivo) e ignorados;
   - os liberados sem amostra de treino e os liberados fora do conjunto de treinamento;
   - os itens que deixaram de ser elegíveis;
   - o tempo total.

   Com poucos dias novos, os dois modelos devem ficar muito próximos, e qualquer decisão serve para o teste funcional.
4. Atualize a documentação, que entra nos commits:
   - as observações do CU11, com as decisões do C2;
   - a situação no código do CU10, com a importação diária;
   - `docs/plano-de-testes-por-fluxo.md`, incluindo o CU11;
   - os comandos novos no `CLAUDE.md`.
5. Faça três commits:
   - `feat(CU10): importação diária da série da Undermine, só com dias encerrados`
   - `fix(CU11): dias encerrados, situação Ignorada e liberados sem amostra de treino (C1)`
   - `feat(CU11): retreinamento semanal do modelo (C2)`
6. Liste o que ficou pendente e as decisões que você tomou.
