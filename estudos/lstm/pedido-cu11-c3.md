# Pedido ao Claude Code: CU11, Cenário 03 (consolidação diária das predições)

Este é o **pedido 4 da etapa 3 de `estudos/lstm/ROTEIRO.md`**, o último do CU11. Use-o depois de fechar o pedido do C2 (`pedido-cu11-c2.md`), com o relatório final entregue.

Já estão prontos:
- o C1, o C2 e a importação diária da Undermine (02:00 UTC, só dias encerrados);
- a recuperação dos disparos perdidos.

A tabela `predicao_diaria` já existe (migração 0007).

## Autorização do autor

O CU11 continua provisório, especificado em `docs/casos-de-uso/CU11-treinar-modelo.md`. O CU05, a consulta da projeção pelo usuário, **não** faz parte deste pedido: o C3 só grava as previsões e o desempenho. Não crie tela de projeção.

## O que fazer

**Leia antes de planejar:**
- o Cenário 03 e as "Observações para a implementação" de `docs/casos-de-uso/CU11-treinar-modelo.md`;
- o diagrama `docs/diagramas-atualizados/cu11c03.png`;
- o código do C1 e do C2 em `backend/src/ml/`;
- `backend/src/modelo_worker.py`.

**Já decidido, não pergunte:**

- **Disparo (passo 1):**
  - um agendador no serviço `modelo`, no horário de `MODELO_CONSOLIDACAO_CRON` (sugestão: todo dia às 03:00 UTC, uma hora depois da importação diária, que leva uns 5 minutos);
  - para o disparo perdido, valem as mesmas regras do C2: computador dormindo, roda uma vez ao acordar; desligado, o serviço confere ao iniciar e roda uma vez;
  - crie um comando para rodar na hora, como o `--retreinar`. Exemplo: `python -m src.modelo_worker --consolidar`.
- **Passo 2:** a consolidação não importa nada; ela usa a importação diária do worker.
  - Antes de começar, ela confere se a importação diária do dia terminou.
  - Se a importação ainda estiver em andamento, ela espera, até um limite configurável.
  - Se a importação falhou ou não rodou, ela segue assim mesmo, com um aviso no resumo, e os valores reais que faltarem ficam "N/D" (FA2).
- **Dia de referência:** é o último dia encerrado, D, a véspera da data UTC da execução.
- **Passos 3 a 6 (snapshot, RN13):**
  - para cada predição já gravada com `data_prevista = D`, o sistema preenche `preco_real` com o preço diário da Undermine do dia D (o mesmo registro que o modelo usa, sem anomalia) e `erro_pct = |previsto − real| ÷ real`;
  - são até 7 predições por item, uma para cada horizonte, feitas de D−7 a D−1;
  - as predições de versões anteriores do modelo também são preenchidas;
  - sem preço real, `preco_real` e `erro_pct` ficam nulos ("N/D", FA2).
- **FA1:** se ainda não existe predição para D, como nos primeiros dias, o sistema segue para o passo 7.
- **FA3 (RN13):**
  - o erro do item é a mediana do `erro_pct` de todas as predições com `data_prevista` nos últimos 7 dias (D−6 a D), em todos os horizontes;
  - se ela passar do limiar da RN10 (15%), o item fica `BLOQUEADA` com o motivo "degradação" até o próximo retreinamento;
  - para não bloquear por um único dia ruim, a regra só vale com pelo menos `MODELO_DEGRADACAO_MINIMO_ALVOS` erros avaliados (sugestão: 14).
- **Passo 7:**
  - para cada item com projeção **liberada** depois do FA3, o modelo vigente prevê D+1 a D+7 a partir da janela de 30 dias que termina em D, usando só dados até D (RN25);
  - a normalização é a da versão vigente (o `normalizacao.json` dela);
  - as variáveis são calculadas como no treinamento, e a variável 6 (índice da subclasse) usa todos os itens elegíveis do dia, não só os liberados;
  - leia só o trecho de histórico necessário (os 90 dias da padronização, a EMA da RN03 e a janela), não a base inteira;
  - o preço previsto, em Cobre (RN01), é o preço de D × exp(log-retorno previsto), com a mesma conversão da avaliação;
  - grave em `predicao_diaria`, com `data_previsao = D`, `h` de 1 a 7 e a versão do modelo.
- **Passo 8 e FA4:** a conclusão vai para o log e para o registro da consolidação. Se os itens bloqueados por degradação no dia passarem de 20% dos que estavam liberados no início do dia, o sistema registra um retreinamento pelo mesmo caminho do agendador do C2, com a mesma checagem de execução em andamento.
- **Registro da consolidação:** o FE1 exige saber quais dias já foram consolidados. Crie uma tabela, por exemplo `consolidacao_diaria`, com:
  - o dia e o status;
  - as predições preenchidas e as "N/D";
  - os itens bloqueados por degradação;
  - as previsões gravadas;
  - se antecipou o retreinamento;
  - o erro.
- **FE1:** cada dia é consolidado numa transação. Uma falha desfaz os registros do dia e vai para o log, e o próximo disparo reprocessa todos os dias ainda não consolidados, na ordem.
  - Ao reprocessar um dia atrasado, ele preenche os valores reais (passos 3 a 6) e aplica o FA3.
  - Previsões novas (passo 7) só são geradas para o dia de referência mais recente, sem previsões retroativas.
  - Os dias sem previsão aparecem como lacuna, que é o FA1.

**Comece em modo de planejamento.** Proponha:
- os arquivos;
- a migração 0010;
- o agendamento e a espera pela importação diária;
- a lista de testes, um por fluxo.

Testes esperados, além dos que você achar necessários:

- `test_cu11_c3_fluxo_principal_registra_snapshot_rn13`
- `test_cu11_c3_fa1_sem_predicao_do_dia`
- `test_cu11_c3_fa2_valor_real_indisponivel`
- `test_cu11_c3_fa3_degradacao_bloqueia_item_rn13`
- `test_cu11_c3_fa4_degradacao_generalizada_antecipa_retreino`
- `test_cu11_c3_fe1_falha_no_banco_reprocessa`
- `test_cu11_c3_gera_previsoes_dos_proximos_7_dias_em_cobre_rn01`
- `test_cu11_c3_previsao_usa_so_dados_ate_o_dia_de_referencia_rn25`
- `test_cu11_c3_espera_a_importacao_diaria`
- `test_cu11_c3_disparo_perdido_roda_ao_iniciar`
- `test_rn13_degradacao_exige_minimo_de_erros`

Pergunte no plano só o que contrariar algo decidido aqui. **Espere a minha aprovação antes de implementar.**

## Regras

- Siga o `CLAUDE.md`, como no C1 e no C2: um teste por fluxo, docstrings citando o CU e a RN e valores configuráveis em `backend/.env.example`.
- Nos testes do modelo, use dados sintéticos e a rede mínima.
- **Não leia nem altere arquivos `.env`.**

## Depois de implementar

1. Rode as três suítes: host, container do `modelo` e frontend, com `npm run lint` e `npx tsc --noEmit`.
2. Rode a consolidação uma vez pelo comando, com os dados reais. Como ainda não há predições, ela deve cair no FA1 e gravar as primeiras previsões. Traga:
   - os itens liberados;
   - as previsões gravadas;
   - o tempo;
   - uma amostra de 5 itens, com o preço de D e as 7 previsões em Ouro.
3. Atualize a documentação, que entra no commit:
   - as observações do CU11, com as decisões do C3;
   - `docs/plano-de-testes-por-fluxo.md`;
   - os comandos novos no `CLAUDE.md`;
   - o `backend/.env.example`.
4. Faça o commit `feat(CU11): consolidação diária das predições (C3)`.
5. Liste o que ficou pendente e as decisões que você tomou.
6. No dia seguinte, depois da consolidação agendada, traga:
   - as primeiras predições preenchidas com o valor real e as "N/D";
   - a mediana do `erro_pct` por horizonte;
   - se algum item foi bloqueado por degradação.

Com isso, o CU11 fica completo.
