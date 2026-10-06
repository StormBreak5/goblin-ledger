# Plano de testes por fluxo (apêndice para o TC)

> Gerado em 29/09/2026 a partir dos nomes dos testes do repositório. Cada linha é um fluxo do documento (principal, alternativo FA
> ou de exceção FE) com o teste automatizado que o cobre. O nome do teste começa pelo identificador do caso de uso e do cenário
> (`test_cuXX_cY_...`), como pede o `CLAUDE.md`.
>
> Os testes com identificador de fluxo somam 238 (15 do CU01, 17 do CU02, 17 do CU03, 48 do CU04, 60 do CU09 e 81 do CU10). A suíte
> completa tem 322 testes: 290 no backend (`pytest`) e 32 no frontend (`npm test`). Os demais são testes de apoio (migrações,
> leitor do arquivo da Undermine, leitores de eventos, formatação de moeda) e não substituem o teste de um fluxo.
>
> Para rodar: `pytest` a partir de `backend/` (usando `.venv`) e `npm test` a partir de `frontend/`. Os testes de backend usam um
> PostgreSQL temporário, com o esquema criado pelas migrações; nenhum acessa a internet nem o banco real.

#### CU01 – Cenário 1 (4 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu01_c1_fluxo_principal_cadastra_usuario` | `backend/tests/integration/test_cu01_manter_usuario.py` |
| FA1 | `test_cu01_c1_fa1_dados_invalidos` | `backend/tests/integration/test_cu01_manter_usuario.py` |
| FA2 | `test_cu01_c1_fa2_email_ja_cadastrado_rn18` | `backend/tests/integration/test_cu01_manter_usuario.py` |
| FE1 | `test_cu01_c1_fe1_falha_na_comunicacao_com_banco_de_dados` | `backend/tests/integration/test_cu01_manter_usuario.py` |

#### CU01 – Cenário 2 (8 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu01_c2_fluxo_principal_altera_regiao_e_senha` | `backend/tests/integration/test_cu01_manter_usuario.py` |
| FA1 | `test_cu01_c2_fa1_altera_somente_a_regiao` | `backend/tests/integration/test_cu01_manter_usuario.py` |
| FA2 | `test_cu01_c2_fa2_confirmacao_divergente` | `backend/tests/integration/test_cu01_manter_usuario.py` |
| FA3 | `test_cu01_c2_fa3_senha_atual_incorreta_rn19` | `backend/tests/integration/test_cu01_manter_usuario.py` |
| FE1 | `test_cu01_c2_fe1_falha_de_banco_mantem_dados` | `backend/tests/integration/test_cu01_manter_usuario.py` |
| regra | `test_cu01_c2_email_nao_pode_ser_alterado_rn18` | `backend/tests/integration/test_cu01_manter_usuario.py` |
| regra | `test_cu01_c2_exige_sessao_autenticada` | `backend/tests/integration/test_cu01_manter_usuario.py` |
| regra | `test_cu01_c2_regiao_invalida_e_campo_exigido_para_trocar_senha` | `backend/tests/integration/test_cu01_manter_usuario.py` |

#### CU01 – Cenário 3 (3 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu01_c3_fluxo_principal_exclui_conta_e_dados_rn20` | `backend/tests/integration/test_cu01_manter_usuario.py` |
| FA2 | `test_cu01_c3_fa2_senha_incorreta_rn19` | `backend/tests/integration/test_cu01_manter_usuario.py` |
| FE1 | `test_cu01_c3_fe1_falha_desfaz_remocoes_rn20` | `backend/tests/integration/test_cu01_manter_usuario.py` |

#### CU02 – Cenário 1 (6 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu02_c1_fluxo_principal_inicia_sessao` | `backend/tests/integration/test_cu02_realizar_login.py` |
| FA1 | `test_cu02_c1_fa1_dados_invalidos` | `backend/tests/integration/test_cu02_realizar_login.py` |
| FA2 | `test_cu02_c1_fa2_credenciais_invalidas` | `backend/tests/integration/test_cu02_realizar_login.py` |
| FA3 | `test_cu02_c1_fa3_conta_bloqueada_rn21` | `backend/tests/integration/test_cu02_realizar_login.py` |
| FA3 | `test_cu02_c1_fa3_contador_zera_apos_login_bem_sucedido_e_vale_para_email_sem_conta` | `backend/tests/integration/test_cu02_realizar_login.py` |
| FE1 | `test_cu02_c1_fe1_falha_de_banco` | `backend/tests/integration/test_cu02_realizar_login.py` |

#### CU02 – Cenário 2 (4 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu02_c2_fluxo_principal_envia_link_de_recuperacao` | `backend/tests/integration/test_cu02_realizar_login.py` |
| FA1 | `test_cu02_c2_fa1_email_invalido` | `backend/tests/integration/test_cu02_realizar_login.py` |
| FA2 | `test_cu02_c2_fa2_email_nao_cadastrado` | `backend/tests/integration/test_cu02_realizar_login.py` |
| FE1 | `test_cu02_c2_fe1_falha_no_envio_invalida_token` | `backend/tests/integration/test_cu02_realizar_login.py` |

#### CU02 – Cenário 3 (4 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu02_c3_fluxo_principal_redefine_senha_rn22` | `backend/tests/integration/test_cu02_realizar_login.py` |
| FA1 | `test_cu02_c3_fa1_link_invalido_expirado_ou_usado` | `backend/tests/integration/test_cu02_realizar_login.py` |
| FA2 | `test_cu02_c3_fa2_confirmacao_divergente` | `backend/tests/integration/test_cu02_realizar_login.py` |
| FE1 | `test_cu02_c3_fe1_falha_de_banco_mantem_senha_e_token` | `backend/tests/integration/test_cu02_realizar_login.py` |

#### CU02 – Cenário 4 (3 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu02_c4_fluxo_principal_encerra_sessao` | `backend/tests/integration/test_cu02_realizar_login.py` |
| FA1 | `test_cu02_c4_fa1_sessao_expirada` | `backend/tests/integration/test_cu02_realizar_login.py` |
| regra | `test_cu02_c4_token_adulterado_ou_de_outra_chave_e_recusado` | `backend/tests/integration/test_cu02_realizar_login.py` |

#### CU03 – Cenário 1 (10 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu03_c1_fluxo_principal_curingas_like_sao_tratados_como_texto` | `backend/tests/integration/test_cu03_buscar_itens.py` |
| principal | `test_cu03_c1_fluxo_principal_desconsidera_acentuacao_e_caixa` | `backend/tests/integration/test_cu03_buscar_itens.py` |
| principal | `test_cu03_c1_fluxo_principal_lista_itens_paginada_com_nome_e_icone` | `backend/tests/integration/test_cu03_buscar_itens.py` |
| principal | `test_cu03_c1_fluxo_principal_recupera_data_ultima_atualizacao_do_leilao` | `backend/tests/integration/test_cu03_buscar_itens.py` |
| principal | `test_cu03_c1_fluxo_principal_segunda_pagina_nao_repete_itens` | `backend/tests/integration/test_cu03_buscar_itens.py` |
| principal | `test_cu03_c1_fluxo_principal_termo_com_apostrofo_e_virgula_e_aceito` | `backend/tests/integration/test_cu03_buscar_itens.py` |
| FA1 | `test_cu03_c1_fa1_limite_de_tres_caracteres_executa_a_consulta` | `backend/tests/integration/test_cu03_buscar_itens.py` |
| FA1 | `test_cu03_c1_fa1_termo_com_menos_de_tres_caracteres` | `backend/tests/unit/test_cu03_buscar_itens_sem_banco.py` |
| FA2 | `test_cu03_c1_fa2_nenhum_item_encontrado` | `backend/tests/integration/test_cu03_buscar_itens.py` |
| FE1 | `test_cu03_c1_fe1_falha_na_comunicacao_com_banco_de_dados` | `backend/tests/unit/test_cu03_buscar_itens_sem_banco.py` |

#### CU03 – Cenário 2 (5 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu03_c2_fluxo_principal_busca_por_identificador_retorna_item_unico` | `backend/tests/integration/test_cu03_buscar_itens.py` |
| principal | `test_cu03_c2_fluxo_principal_recupera_data_ultima_atualizacao_do_leilao` | `backend/tests/integration/test_cu03_buscar_itens.py` |
| FA1 | `test_cu03_c2_fa1_identificador_inexistente` | `backend/tests/integration/test_cu03_buscar_itens.py` |
| FA2 | `test_cu03_c2_fa2_termo_alfanumerico_e_tratado_como_busca_textual` | `backend/tests/integration/test_cu03_buscar_itens.py` |
| FE1 | `test_cu03_c2_fe1_falha_na_comunicacao_com_banco_de_dados` | `backend/tests/unit/test_cu03_buscar_itens_sem_banco.py` |

#### CU03 – Cenário 3 (2 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu03_c3_fluxo_principal_detalhes_do_item_selecionado` | `backend/tests/integration/test_cu03_buscar_itens.py` |
| FE1 | `test_cu03_c3_fe1_item_removido_durante_a_navegacao` | `backend/tests/integration/test_cu03_buscar_itens.py` |

#### CU04 – Cenário 1 (22 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu04_c1_fluxo_principal_cabecalho_com_valor_de_mercado_e_menor_preco` | `frontend/tests/cu04-visualizar-historico.test.tsx` |
| principal | `test_cu04_c1_fluxo_principal_devolve_a_serie_e_o_valor_de_mercado_rn06` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| principal | `test_cu04_c1_fluxo_principal_ficha_do_wow_mostra_o_preco_sem_contagem_de_leiloes` | `frontend/tests/cu04-visualizar-historico.test.tsx` |
| principal | `test_cu04_c1_fluxo_principal_sem_valor_de_mercado_o_menor_preco_e_o_destaque` | `frontend/tests/cu04-visualizar-historico.test.tsx` |
| FA1 | `test_cu04_c1_fa1_dados_desatualizados_mostra_o_selo_e_desenha_o_grafico` | `frontend/tests/cu04-visualizar-historico.test.tsx` |
| FA1 | `test_cu04_c1_fa1_dados_desatualizados_pelo_limiar_de_24_horas` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| FA1 | `test_cu04_c1_fa1_ficha_do_wow_usa_a_idade_do_ultimo_preco` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| FA1 | `test_cu04_c1_fa1_item_que_o_ciclo_nunca_coletou_usa_o_ciclo_mais_recente_de_qualquer_mercado` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| FA1 | `test_cu04_c1_fa1_mercado_sinalizado_por_falha_rn14` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| FA1 | `test_cu04_c1_fa1_o_frescor_segue_o_mercado_do_item` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| FA2 | `test_cu04_c1_fa2_item_sem_historico_mostra_a_mensagem_do_cenario` | `frontend/tests/cu04-visualizar-historico.test.tsx` |
| FA2 | `test_cu04_c1_fa2_item_sem_historico_registrado` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| FE1 | `test_cu04_c1_fe1_backend_fora_do_ar_usa_a_mesma_mensagem` | `frontend/tests/cu04-visualizar-historico.test.tsx` |
| FE1 | `test_cu04_c1_fe1_banco_fora_do_ar_ja_na_abertura_da_sessao` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| FE1 | `test_cu04_c1_fe1_falha_ao_recuperar_o_historico_mostra_a_mensagem_do_cenario` | `frontend/tests/cu04-visualizar-historico.test.tsx` |
| FE1 | `test_cu04_c1_fe1_falha_de_banco_ao_recuperar_o_historico` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| regra | `test_cu04_c1_ficha_sem_nenhuma_coleta_ainda` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| regra | `test_cu04_c1_historico_da_ficha_vem_de_item_prices_em_cobre_e_utc` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| regra | `test_cu04_c1_o_historico_devolve_o_instante_em_utc_com_o_fuso_explicito` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| regra | `test_cu04_c1_o_mercado_do_item_vem_do_ponto_mais_recente_da_blizzard` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| regra | `test_cu04_c1_os_demais_itens_continuam_lendo_o_historico_de_leiloes` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| regra | `test_cu04_c1_preco_atual_da_ficha_e_o_da_ultima_coleta_sem_contagem_de_leiloes` | `backend/tests/integration/test_cu04_visualizar_historico.py` |

#### CU04 – Cenário 2 (16 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu04_c2_fluxo_principal_clicar_na_janela_ja_exibida_nao_pede_de_novo` | `frontend/tests/cu04-visualizar-historico.test.tsx` |
| principal | `test_cu04_c2_fluxo_principal_recorta_a_serie_pela_janela` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| principal | `test_cu04_c2_fluxo_principal_todas_as_janelas_do_documento` | `frontend/tests/cu04-visualizar-historico.test.tsx` |
| principal | `test_cu04_c2_fluxo_principal_troca_a_janela_e_pede_o_novo_recorte` | `frontend/tests/cu04-visualizar-historico.test.tsx` |
| FA1 | `test_cu04_c2_fa1_dados_limitados_mostra_o_aviso_do_cenario` | `frontend/tests/cu04-visualizar-historico.test.tsx` |
| FA1 | `test_cu04_c2_fa1_dados_limitados_quando_o_historico_nao_cobre_a_janela` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| FA1 | `test_cu04_c2_fa1_ficha_do_wow_tambem_avisa_quando_a_serie_e_curta` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| FA1 | `test_cu04_c2_fa1_o_primeiro_ponto_parte_das_linhas_do_item_e_nao_do_indice_de_timestamp` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| FA1 | `test_cu04_c2_fa1_os_avisos_de_limite_e_de_frescor_convivem` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| FA2 | `test_cu04_c2_a_janela_sem_pontos_de_um_item_com_historico_antigo_usa_o_texto_do_fa2` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| FE1 | `test_cu04_c2_fe1_backend_fora_do_ar_ao_trocar_a_janela_tem_o_mesmo_tratamento` | `frontend/tests/cu04-visualizar-historico.test.tsx` |
| FE1 | `test_cu04_c2_fe1_depois_da_falha_uma_nova_troca_funciona` | `frontend/tests/cu04-visualizar-historico.test.tsx` |
| FE1 | `test_cu04_c2_fe1_falha_ao_trocar_a_janela_mantem_a_visualizacao_atual` | `frontend/tests/cu04-visualizar-historico.test.tsx` |
| FE1 | `test_cu04_c2_fe1_o_toast_some_sozinho_e_pode_ser_fechado` | `frontend/tests/cu04-visualizar-historico.test.tsx` |
| regra | `test_cu04_c2_janela_ilegivel_volta_ao_padrao_de_14_dias` | `backend/tests/integration/test_cu04_visualizar_historico.py` |
| regra | `test_cu04_c2_o_pedido_mais_novo_cancela_o_anterior` | `frontend/tests/cu04-visualizar-historico.test.tsx` |

#### CU04 – Cenário 3 (10 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu04_c3_fluxo_principal_dica_com_data_hora_e_valores_em_cobre_prata_ouro` | `frontend/tests/cu04-c3-inspecionar-ponto.test.tsx` |
| principal | `test_cu04_c3_fluxo_principal_o_ponto_diario_e_o_dia_inteiro_em_utc` | `frontend/tests/cu04-c3-inspecionar-ponto.test.tsx` |
| principal | `test_cu04_c3_fluxo_principal_valores_grandes_e_pequenos` | `frontend/tests/cu04-c3-inspecionar-ponto.test.tsx` |
| FA1 | `test_cu04_c3_fa1_metrica_ausente_vira_nd_e_o_preco_continua` | `frontend/tests/cu04-c3-inspecionar-ponto.test.tsx` |
| FA1 | `test_cu04_c3_fa1_serie_sem_volume_como_a_ficha_do_wow_nao_mostra_a_linha` | `frontend/tests/cu04-c3-inspecionar-ponto.test.tsx` |
| FA1 | `test_cu04_c3_fa1_volume_zero_nao_e_confundido_com_ausente` | `frontend/tests/cu04-c3-inspecionar-ponto.test.tsx` |
| FE1 | `test_cu04_c3_fe1_instante_invalido_tambem_omite_a_dica` | `frontend/tests/cu04-c3-inspecionar-ponto.test.tsx` |
| FE1 | `test_cu04_c3_fe1_o_usuario_pode_inspecionar_outro_ponto_normalmente` | `frontend/tests/cu04-c3-inspecionar-ponto.test.tsx` |
| FE1 | `test_cu04_c3_fe1_valor_atipico_omite_a_dica_e_registra_no_console` | `frontend/tests/cu04-c3-inspecionar-ponto.test.tsx` |
| regra | `test_cu04_c3_sem_mouse_sobre_o_grafico_nao_ha_dica` | `frontend/tests/cu04-c3-inspecionar-ponto.test.tsx` |

#### CU09 – Regras gerais do caso de uso (2 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| regra | `test_cu09_consumo_get_current_auctions_le_do_banco` | `backend/tests/integration/test_cu09_ingestao.py` |
| regra | `test_cu09_estado_do_mercado_expoe_o_frescor_rn09_e_a_sinalizacao_rn14` | `backend/tests/integration/test_cu09_ingestao_manual.py` |

#### CU09 – Cenário 1 (32 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu09_c1_fluxo_principal_coleta_e_encaminha_payload` | `backend/tests/integration/test_cu09_ingestao.py` |
| principal | `test_cu09_c1_fluxo_principal_coleta_os_dois_endpoints_com_o_last_modified` | `backend/tests/unit/test_cu09_api_client.py` |
| FA1 | `test_cu09_c1_fa1_intervalo_minimo_nao_atingido` | `backend/tests/integration/test_cu09_ingestao.py` |
| FA2 | `test_cu09_c1_fa2_reino_fora_do_dominio_geografico_rn11` | `backend/tests/integration/test_cu09_ingestao.py` |
| FE1 | `test_cu09_c1_fe1_429_respeita_o_retry_after` | `backend/tests/unit/test_cu09_api_client.py` |
| FE1 | `test_cu09_c1_fe1_erro_4xx_nao_e_tentado_de_novo` | `backend/tests/unit/test_cu09_api_client.py` |
| FE1 | `test_cu09_c1_fe1_falha_ao_obter_o_token_tambem_e_tentada_de_novo` | `backend/tests/unit/test_cu09_api_client.py` |
| FE1 | `test_cu09_c1_fe1_falha_da_api_mantem_dados_e_sinaliza_desatualizado` | `backend/tests/integration/test_cu09_ingestao.py` |
| FE1 | `test_cu09_c1_fe1_falha_persistente_levanta_erro_apos_quatro_tentativas` | `backend/tests/unit/test_cu09_api_client.py` |
| FE1 | `test_cu09_c1_fe1_retentativas_em_5xx_com_espera_crescente` | `backend/tests/unit/test_cu09_api_client.py` |
| FE1 | `test_cu09_c1_fe1_tempo_limite_e_falha_de_rede_tambem_sao_tentados_de_novo` | `backend/tests/unit/test_cu09_api_client.py` |
| regra | `test_cu09_c1_ativacao_a_ingestao_reagenda_a_si_mesma` | `backend/tests/unit/test_cu09_agendamento.py` |
| regra | `test_cu09_c1_ativacao_a_proxima_rodada_e_agendada_mesmo_quando_a_rodada_falha` | `backend/tests/unit/test_cu09_agendamento.py` |
| regra | `test_cu09_c1_ativacao_a_proxima_rodada_vem_do_horario_calculado_pela_rodada` | `backend/tests/unit/test_cu09_agendamento.py` |
| regra | `test_cu09_c1_ativacao_agenda_para_ultimo_ciclo_mais_60_minutos` | `backend/tests/integration/test_cu09_ingestao.py` |
| regra | `test_cu09_c1_ativacao_backfill_antes_do_ciclo_apos_48h` | `backend/tests/integration/test_cu09_ingestao.py` |
| regra | `test_cu09_c1_ativacao_coleta_imediata_ao_iniciar_apos_uma_hora` | `backend/tests/integration/test_cu09_ingestao.py` |
| regra | `test_cu09_c1_ativacao_nao_ha_mais_backfill_horario` | `backend/tests/unit/test_cu09_agendamento.py` |
| regra | `test_cu09_c1_ativacao_nao_repete_a_recuperacao_em_menos_de_6_horas` | `backend/tests/unit/test_cu09_agendamento.py` |
| regra | `test_cu09_c1_ativacao_nao_roda_duas_rodadas_ao_mesmo_tempo` | `backend/tests/unit/test_cu09_agendamento.py` |
| regra | `test_cu09_c1_ativacao_planeja_backfill_apos_48h` | `backend/tests/unit/test_cu09_agendamento.py` |
| regra | `test_cu09_c1_ativacao_planeja_coleta_imediata_apos_uma_hora` | `backend/tests/unit/test_cu09_agendamento.py` |
| regra | `test_cu09_c1_ativacao_planeja_espera_ate_completar_60_minutos` | `backend/tests/unit/test_cu09_agendamento.py` |
| regra | `test_cu09_c1_ativacao_proximo_disparo_espera_o_primeiro_endpoint_liberar` | `backend/tests/unit/test_cu09_agendamento.py` |
| regra | `test_cu09_c1_ativacao_referencia_das_48h_e_a_ultima_coleta_de_qualquer_origem` | `backend/tests/integration/test_cu09_ingestao.py` |
| regra | `test_cu09_c1_ativacao_rodada_atrasada_por_dias_roda_ao_acordar` | `backend/tests/unit/test_cu09_agendamento.py` |
| regra | `test_cu09_c1_ativacao_sem_nenhuma_coleta_recompoe_o_historico_uma_vez` | `backend/tests/unit/test_cu09_agendamento.py` |
| regra | `test_cu09_c1_ativacao_so_a_ficha_do_wow_roda_a_cada_15_minutos` | `backend/tests/unit/test_cu09_agendamento.py` |
| regra | `test_cu09_c1_ativacao_vigia_nao_agenda_enquanto_a_rodada_esta_em_andamento` | `backend/tests/unit/test_cu09_agendamento.py` |
| regra | `test_cu09_c1_ativacao_vigia_nao_mexe_na_ingestao_ja_agendada` | `backend/tests/unit/test_cu09_agendamento.py` |
| regra | `test_cu09_c1_ativacao_vigia_retoma_a_ingestao_que_se_perdeu` | `backend/tests/unit/test_cu09_agendamento.py` |
| regra | `test_cu09_c1_regiao_eu_usa_o_host_e_o_locale_europeus` | `backend/tests/unit/test_cu09_api_client.py` |

#### CU09 – Cenário 2 (12 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu09_c2_fluxo_principal_commodity_usa_o_preco_unitario` | `backend/tests/unit/test_cu09_sanitizacao_e_valor_de_mercado.py` |
| principal | `test_cu09_c2_fluxo_principal_preco_unitario_arredonda_o_buyout_do_lote` | `backend/tests/unit/test_cu09_sanitizacao_e_valor_de_mercado.py` |
| principal | `test_cu09_c2_fluxo_principal_sanitiza_e_padroniza_em_cobre` | `backend/tests/integration/test_cu09_ingestao.py` |
| FA1 | `test_cu09_c2_fa1_taxa_de_descarte` | `backend/tests/unit/test_cu09_sanitizacao_e_valor_de_mercado.py` |
| FA1 | `test_cu09_c2_fa1_taxa_de_descarte_elevada_vai_para_o_log` | `backend/tests/integration/test_cu09_ingestao.py` |
| FE1 | `test_cu09_c2_fe1_payload_fora_do_formato_descarta_tudo` | `backend/tests/integration/test_cu09_ingestao.py` |
| FE1 | `test_cu09_c2_fe1_payload_fora_do_formato_levanta_erro` | `backend/tests/unit/test_cu09_sanitizacao_e_valor_de_mercado.py` |
| FE1 | `test_cu09_c2_fe1_resposta_que_nao_e_json_e_payload_fora_do_formato` | `backend/tests/unit/test_cu09_api_client.py` |
| regra | `test_cu09_c2_anomalia_de_volume_criterio_rn12` | `backend/tests/unit/test_cu09_sanitizacao_e_valor_de_mercado.py` |
| regra | `test_cu09_c2_anomalia_de_volume_rn12` | `backend/tests/integration/test_cu09_ingestao.py` |
| regra | `test_cu09_c2_conversao_para_cobre_rn01` | `backend/tests/unit/test_cu09_sanitizacao_e_valor_de_mercado.py` |
| regra | `test_cu09_c2_lista_vazia_de_leiloes_e_um_payload_valido` | `backend/tests/unit/test_cu09_sanitizacao_e_valor_de_mercado.py` |

#### CU09 – Cenário 3 (8 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu09_c3_fluxo_principal_persiste_classifica_e_calcula_valor_de_mercado` | `backend/tests/integration/test_cu09_ingestao.py` |
| FA1 | `test_cu09_c3_fa1_item_nao_cadastrado_e_criado` | `backend/tests/integration/test_cu09_ingestao.py` |
| FA1 | `test_cu09_c3_fa1_itens_novos_disparam_o_preenchimento_de_nomes_e_icones` | `backend/tests/integration/test_cu09_ingestao.py` |
| FE1 | `test_cu09_c3_fe1_falha_de_banco_desfaz_e_sinaliza` | `backend/tests/integration/test_cu09_ingestao.py` |
| regra | `test_cu09_c3_os_pontos_do_ciclo_sao_gravados_como_horarios_rn16` | `backend/tests/integration/test_cu09_ingestao.py` |
| regra | `test_cu09_c3_repetir_o_mesmo_snapshot_nao_duplica_o_historico` | `backend/tests/integration/test_cu09_ingestao.py` |
| regra | `test_cu09_c3_retencao_remove_expirados_antigos_e_preserva_o_historico` | `backend/tests/integration/test_cu09_ingestao.py` |
| regra | `test_cu09_c3_valor_de_mercado_e_o_primeiro_quartil_ponderado_rn06` | `backend/tests/unit/test_cu09_sanitizacao_e_valor_de_mercado.py` |

#### CU09 – Cenário 4 (6 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu09_c4_fluxo_principal_ingestao_manual_do_admin` | `backend/tests/integration/test_cu09_ingestao_manual.py` |
| FA1 | `test_cu09_c4_fa1_intervalo_minimo_informa_horario` | `backend/tests/integration/test_cu09_ingestao_manual.py` |
| FE1 | `test_cu09_c4_fe1_falha_informa_etapa_e_erro` | `backend/tests/integration/test_cu09_ingestao_manual.py` |
| regra | `test_cu09_c4_ingestao_de_um_reino_informado_nao_coleta_as_commodities` | `backend/tests/integration/test_cu09_ingestao_manual.py` |
| regra | `test_cu09_c4_regiao_fora_de_us_eu_e_recusada_rn11` | `backend/tests/integration/test_cu09_ingestao_manual.py` |
| regra | `test_cu09_c4_so_o_admin_executa_a_ingestao` | `backend/tests/integration/test_cu09_ingestao_manual.py` |

#### CU10 – Regras gerais do caso de uso (2 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| regra | `test_cu10_migracao_4_marca_os_pontos_da_blizzard_como_horarios_rn16` | `backend/tests/integration/test_migracoes.py` |
| regra | `test_cu10_migracao_5_corrige_a_granularidade_dos_pontos_do_ciclo_horario_rn16` | `backend/tests/integration/test_migracoes.py` |

#### CU10 – Cenário 1 (34 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu10_c1_fluxo_principal_conta_os_duplicados_de_forma_exata` | `backend/tests/scraper/test_backfill.py` |
| principal | `test_cu10_c1_fluxo_principal_descarta_registros_com_data_invalida` | `backend/tests/scraper/test_backfill.py` |
| principal | `test_cu10_c1_fluxo_principal_grava_em_paginas_na_mesma_transacao` | `backend/tests/scraper/test_backfill.py` |
| principal | `test_cu10_c1_fluxo_principal_importa_o_historico_pedido_pelo_admin` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| principal | `test_cu10_c1_fluxo_principal_insere_somente_registros_novos` | `backend/tests/scraper/test_backfill.py` |
| principal | `test_cu10_c1_fluxo_principal_marca_a_granularidade_de_cada_registro_rn16` | `backend/tests/scraper/test_backfill.py` |
| principal | `test_cu10_c1_fluxo_principal_registra_origem_do_item` | `backend/tests/scraper/test_backfill.py` |
| principal | `test_cu10_c1_fluxo_principal_sem_itens_importa_todos_os_itens_ativos` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| FA1 | `test_cu10_c1_fa1_regiao_ou_item_invalido` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| FA2 | `test_cu10_c1_fa2_item_nao_cadastrado_e_cadastrado_com_o_identificador` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| FA3 | `test_cu10_c1_fa3_cada_requisicao_espera_o_limitador_inclusive_a_da_commodity` | `backend/tests/scraper/test_backfill.py` |
| FA3 | `test_cu10_c1_fa3_intervalo_zero_desliga_a_espera` | `backend/tests/scraper/test_backfill.py` |
| FA3 | `test_cu10_c1_fa3_limitador_espera_o_intervalo_minimo_entre_requisicoes` | `backend/tests/scraper/test_backfill.py` |
| FE1 | `test_cu10_c1_fe1_falhas_isoladas_nao_interrompem_a_importacao` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| FE1 | `test_cu10_c1_fe1_fonte_indisponivel_mantem_o_que_ja_foi_gravado` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| FE2 | `test_cu10_c1_fe2_falha_de_banco_desfaz_a_importacao` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| FE2 | `test_cu10_c1_fe2_falha_de_banco_desfaz_importacao_sem_registros_parciais` | `backend/tests/scraper/test_backfill.py` |
| FE3 | `test_cu10_c1_fe3_arquivo_que_nao_decodifica_e_distinto_de_falha_de_rede` | `backend/tests/scraper/test_backfill.py` |
| FE3 | `test_cu10_c1_fe3_formato_alterado_interrompe_e_mantem_o_que_ja_foi_gravado` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| regra | `test_cu10_c1_a_importacao_do_admin_ignora_o_etag_para_contar_os_duplicados` | `backend/tests/scraper/test_backfill.py` |
| regra | `test_cu10_c1_a_importacao_do_admin_nao_conta_como_recuperacao_do_historico` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| regra | `test_cu10_c1_a_recuperacao_do_worker_importa_incrementalmente_os_itens_ativos` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| regra | `test_cu10_c1_arquivo_sem_dados_reconhece_o_stub_e_so_ele` | `backend/tests/scraper/test_backfill.py` |
| regra | `test_cu10_c1_etag_sem_origem_registrada_nao_e_reaproveitado_na_recuperacao` | `backend/tests/scraper/test_backfill.py` |
| regra | `test_cu10_c1_lista_as_importacoes_mais_recentes_e_recusa_id_desconhecido` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| regra | `test_cu10_c1_o_ritmo_entre_requisicoes_e_configuravel_rn23` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| regra | `test_cu10_c1_os_pontos_da_blizzard_nao_escondem_o_historico_ainda_nao_importado` | `backend/tests/scraper/test_backfill.py` |
| regra | `test_cu10_c1_passo3_arquivo_do_reino_com_dados_nao_consulta_as_commodities` | `backend/tests/scraper/test_backfill.py` |
| regra | `test_cu10_c1_passo3_arquivo_do_reino_sem_dados_cai_para_o_das_commodities` | `backend/tests/scraper/test_backfill.py` |
| regra | `test_cu10_c1_passo3_stub_no_reino_e_nas_commodities_e_item_sem_dados` | `backend/tests/scraper/test_backfill.py` |
| regra | `test_cu10_c1_rn16_a_importacao_le_o_tempo_dos_snapshots_em_segundos` | `backend/tests/scraper/test_backfill.py` |
| regra | `test_cu10_c1_so_o_admin_importa_e_consulta` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| regra | `test_cu10_c1_so_uma_importacao_roda_por_vez` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| regra | `test_cu10_c1_um_arquivo_ilegivel_isolado_nao_e_formato_alterado` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |

#### CU10 – Cenário 2 (31 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu10_c2_fluxo_principal_extrai_as_expansoes_da_wikipedia` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| principal | `test_cu10_c2_fluxo_principal_extrai_as_temporadas_da_api_da_blizzard` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| principal | `test_cu10_c2_fluxo_principal_extrai_e_registra_patches` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| principal | `test_cu10_c2_fluxo_principal_extrai_os_eventos_sazonais` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| principal | `test_cu10_c2_fluxo_principal_gera_os_eventos_recorrentes_por_regra` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| FA1 | `test_cu10_c2_fa1_evento_ja_registrado_e_ignorado_e_os_demais_seguem` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| FA1 | `test_cu10_c2_fa1_repetir_a_extracao_nao_duplica_os_eventos_gerados_por_regra` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| FA2 | `test_cu10_c2_fa2_cadastro_manual_do_evento` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| FA2 | `test_cu10_c2_fa2_dados_invalidos_no_cadastro_manual` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| FE1 | `test_cu10_c2_fe1_a_fonte_fora_do_ar_tem_o_mesmo_tratamento` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| FE1 | `test_cu10_c2_fe1_api_da_blizzard_fora_do_ar` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| FE1 | `test_cu10_c2_fe1_estrutura_da_pagina_alterada_nao_registra_eventos` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| FE1 | `test_cu10_c2_fe1_resposta_da_api_com_outro_formato` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| FE1 | `test_cu10_c2_fe1_uma_pagina_que_o_provider_nao_reconhece_nem_e_consultada` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| regra | `test_cu10_c2_a_mesma_pagina_nao_e_lida_de_novo_em_menos_de_10_minutos` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| regra | `test_cu10_c2_data_de_temporada_da_api_so_aceita_marcas_validas` | `backend/tests/unit/test_cu10_c2_leitores_de_eventos.py` |
| regra | `test_cu10_c2_falha_de_banco_desfaz_o_registro` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| regra | `test_cu10_c2_feira_de_negrilua_abre_no_primeiro_domingo_de_cada_mes` | `backend/tests/unit/test_cu10_c2_leitores_de_eventos.py` |
| regra | `test_cu10_c2_feriados_variaveis_sao_marcados_como_aproximados_e_pulam_anos_sem_data` | `backend/tests/unit/test_cu10_c2_leitores_de_eventos.py` |
| regra | `test_cu10_c2_fonte_desconhecida_e_recusada` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| regra | `test_cu10_c2_leitor_de_tabelas_ignora_notas_scripts_e_le_tabelas_aninhadas` | `backend/tests/unit/test_cu10_c2_leitores_de_eventos.py` |
| regra | `test_cu10_c2_leitor_de_tabelas_nunca_levanta_erro_com_html_malformado` | `backend/tests/unit/test_cu10_c2_leitores_de_eventos.py` |
| regra | `test_cu10_c2_lista_os_eventos_registrados_do_mais_recente_ao_mais_antigo` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| regra | `test_cu10_c2_o_endereco_informado_e_lido_quando_e_da_fonte` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| regra | `test_cu10_c2_o_reinicio_semanal_da_europa_pode_ser_desligado` | `backend/tests/integration/test_cu10_c2_eventos.py` |
| regra | `test_cu10_c2_pascoa_do_calendario_gregoriano` | `backend/tests/unit/test_cu10_c2_leitores_de_eventos.py` |
| regra | `test_cu10_c2_passo3_data_no_formato_padrao_dd_mm_aaaa` | `backend/tests/unit/test_cu10_c2_leitores_de_eventos.py` |
| regra | `test_cu10_c2_passo3_datas_em_ingles_viram_datas` | `backend/tests/unit/test_cu10_c2_leitores_de_eventos.py` |
| regra | `test_cu10_c2_periodos_anuais_em_dia_e_mes` | `backend/tests/unit/test_cu10_c2_leitores_de_eventos.py` |
| regra | `test_cu10_c2_reinicio_semanal_da_europa_vem_do_ambiente` | `backend/tests/unit/test_cu10_c2_leitores_de_eventos.py` |
| regra | `test_cu10_c2_so_o_admin_extrai_cadastra_e_lista_eventos` | `backend/tests/integration/test_cu10_c2_eventos.py` |

#### CU10 – Cenário 3 (14 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu10_c3_fluxo_principal_classifica_o_item_como_apto_ao_treinamento` | `backend/tests/integration/test_cu10_c3_cobertura.py` |
| FA1 | `test_cu10_c3_fa1_historico_insuficiente_bloqueia_o_item_e_segue_para_os_demais` | `backend/tests/integration/test_cu10_c3_cobertura.py` |
| FE1 | `test_cu10_c3_fe1_falha_de_banco_ao_gravar_desfaz_a_validacao` | `backend/tests/integration/test_cu10_c3_cobertura.py` |
| FE1 | `test_cu10_c3_fe1_falha_de_banco_ao_recuperar_os_registros_mantem_a_classificacao_anterior` | `backend/tests/integration/test_cu10_c3_cobertura.py` |
| regra | `test_cu10_c3_consulta_a_ultima_validacao_com_filtro_e_paginacao` | `backend/tests/integration/test_cu10_c3_cobertura.py` |
| regra | `test_cu10_c3_item_sem_nenhum_registro_e_inapto_com_periodo_zero` | `backend/tests/integration/test_cu10_c3_cobertura.py` |
| regra | `test_cu10_c3_os_limites_sao_configuraveis_rn15` | `backend/tests/integration/test_cu10_c3_cobertura.py` |
| regra | `test_cu10_c3_passo2_os_registros_de_todas_as_regioes_e_origens_contam_uma_vez_por_dia` | `backend/tests/integration/test_cu10_c3_cobertura.py` |
| regra | `test_cu10_c3_passo3_lacunas_pequenas_nao_interrompem_o_periodo` | `backend/tests/integration/test_cu10_c3_cobertura.py` |
| regra | `test_cu10_c3_passo3_vale_o_maior_periodo_e_no_empate_o_mais_recente` | `backend/tests/integration/test_cu10_c3_cobertura.py` |
| regra | `test_cu10_c3_passo4_o_minimo_e_de_seis_meses_rn15` | `backend/tests/integration/test_cu10_c3_cobertura.py` |
| regra | `test_cu10_c3_so_o_admin_valida_e_consulta` | `backend/tests/integration/test_cu10_c3_cobertura.py` |
| regra | `test_cu10_c3_so_os_itens_ativos_do_wow_sao_avaliados_e_a_ficha_fica_de_fora` | `backend/tests/integration/test_cu10_c3_cobertura.py` |
| regra | `test_cu10_c3_validar_de_novo_substitui_o_resultado_anterior` | `backend/tests/integration/test_cu10_c3_cobertura.py` |