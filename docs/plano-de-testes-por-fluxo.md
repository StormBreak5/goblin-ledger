# Plano de testes por fluxo (apêndice para o TC)

> Gerado em 19/10/2026 e atualizado em 11/11/2026 a partir dos nomes dos testes do repositório. Cada linha é um fluxo do documento (principal, alternativo FA
> ou de exceção FE) com o teste automatizado que o cobre. O nome do teste começa pelo identificador do caso de uso e do cenário
> (`test_cuXX_cY_...`), como pede o `CLAUDE.md`. Os testes das regras do modelo do CU11 (`test_rnXX_...`) ficam numa seção própria.
>
> As contagens deste plano são de **funções** de teste: um teste parametrizado (`parametrize` no backend, `it.each` no
> frontend) conta uma vez, mesmo quando os seus casos aparecem em linhas separadas, um por fluxo. As funções com identificador
> de fluxo ou de regra somam 407 (15 do CU01, 17 do CU02, 17 do CU03, 48 do CU04, 20 do CU05, 25 do CU06, 27 do CU07, 20 do
> CU08, 60 do CU09, 92 do CU10 e 66 do CU11). Há ainda 39 funções de apoio, sem prefixo de caso de uso (33 no backend:
> migrações, leitor do arquivo da Undermine, leitores de eventos e outros; 6 no frontend: formatação de moeda), que não
> substituem o teste de um fluxo.
>
> Na execução de 11/11/2026, a suíte completa rodou 513 testes, contando cada caso parametrizado como um teste, sem falhas:
> 387 no backend (`pytest`, no host), 50 do pipeline do modelo no container do serviço `modelo`
> (`docker compose run --rm modelo-testes`) e 76 no frontend (`npm test`).
>
> Para rodar: `pytest` a partir de `backend/` (usando `.venv`), `docker compose run --rm modelo-testes` a partir de `backend/` e
> `npm test` a partir de `frontend/`. Os testes de backend usam um PostgreSQL temporário, com o esquema criado pelas migrações;
> nenhum acessa a internet nem o banco real. No host, os testes de `backend/tests/modelo/` aparecem como ignorados (precisam do
> TensorFlow, que só existe na imagem do serviço `modelo`).

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

#### CU05 – Cenário 1 (15 testes)

As 20 linhas abaixo correspondem a 15 funções: os FA1 a FA6 do frontend são os casos de um mesmo `it.each`, um por fluxo, com o
nome do fluxo, e contam como uma função.

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu05_c1_fluxo_principal_exibe_a_projecao_dos_proximos_7_dias` | `backend/tests/integration/test_cu05_consultar_previsao.py` |
| principal | `test_cu05_c1_fluxo_principal_exibe_a_projecao_dos_proximos_7_dias` | `frontend/tests/cu05-c1-exibir-projecao.test.tsx` |
| principal | `test_cu05_c1_ponta_a_ponta_treino_consolidacao_e_projecao` | `backend/tests/modelo/test_cu05_projecao_ponta_a_ponta.py` |
| FA1 | `test_cu05_c1_fa1_modelo_nao_treinado` | `backend/tests/integration/test_cu05_consultar_previsao.py` |
| FA1 | `test_cu05_c1_fa1_modelo_nao_treinado` | `frontend/tests/cu05-c1-exibir-projecao.test.tsx` |
| FA2 | `test_cu05_c1_fa2_item_nao_elegivel_rn02_rn27` | `backend/tests/integration/test_cu05_consultar_previsao.py` |
| FA2 | `test_cu05_c1_fa2_item_nao_elegivel_rn02_rn27` | `frontend/tests/cu05-c1-exibir-projecao.test.tsx` |
| FA2 | `test_cu05_c1_fa2_criterio_da_api_igual_ao_do_selecao` | `backend/tests/modelo/test_cu05_projecao_ponta_a_ponta.py` |
| FA3 | `test_cu05_c1_fa3_projecao_reprovada_rn10` | `backend/tests/integration/test_cu05_consultar_previsao.py` |
| FA3 | `test_cu05_c1_fa3_projecao_reprovada_rn10` | `frontend/tests/cu05-c1-exibir-projecao.test.tsx` |
| FA4 | `test_cu05_c1_fa4_projecao_em_avaliacao` | `backend/tests/integration/test_cu05_consultar_previsao.py` |
| FA4 | `test_cu05_c1_fa4_projecao_em_avaliacao` | `frontend/tests/cu05-c1-exibir-projecao.test.tsx` |
| FA5 | `test_cu05_c1_fa5_projecao_suspensa_rn13` | `backend/tests/integration/test_cu05_consultar_previsao.py` |
| FA5 | `test_cu05_c1_fa5_projecao_suspensa_rn13` | `frontend/tests/cu05-c1-exibir-projecao.test.tsx` |
| FA6 | `test_cu05_c1_fa6_projecao_nao_disponivel` | `backend/tests/integration/test_cu05_consultar_previsao.py` |
| FA6 | `test_cu05_c1_fa6_projecao_nao_disponivel` | `frontend/tests/cu05-c1-exibir-projecao.test.tsx` |
| FA7 | `test_cu05_c1_fa7_projecao_desatualizada` | `backend/tests/integration/test_cu05_consultar_previsao.py` |
| FA7 | `test_cu05_c1_fa7_projecao_desatualizada` | `frontend/tests/cu05-c1-exibir-projecao.test.tsx` |
| FE1 | `test_cu05_c1_fe1_falha_no_banco` | `backend/tests/integration/test_cu05_consultar_previsao.py` |
| FE1 | `test_cu05_c1_fe1_falha_no_banco` | `frontend/tests/cu05-c1-exibir-projecao.test.tsx` |

#### CU05 – Cenário 2 (3 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu05_c2_fluxo_principal_tooltip_do_dia_previsto` | `frontend/tests/cu05-c2-inspecionar-dia.test.tsx` |
| FA1 | `test_cu05_c2_fa1_ponto_de_partida_usa_o_tooltip_do_historico` | `frontend/tests/cu05-c2-inspecionar-dia.test.tsx` |
| FE1 | `test_cu05_c2_fe1_falha_na_conversao_omite_o_tooltip` | `frontend/tests/cu05-c2-inspecionar-dia.test.tsx` |

#### CU05 – Cenário 3 (2 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu05_c3_fluxo_principal_oculta_a_projecao` | `frontend/tests/cu05-c3-ocultar-projecao.test.tsx` |
| FA1 | `test_cu05_c3_fa1_exibe_novamente_a_projecao` | `frontend/tests/cu05-c3-ocultar-projecao.test.tsx` |

#### CU06 – Regras gerais do caso de uso (1 teste)

| Fluxo | Teste | Arquivo |
|---|---|---|
| RN20 | `test_cu06_exclusao_da_conta_remove_favoritos_e_alertas_rn20` | `backend/tests/integration/test_cu06_manter_favoritos.py` |

#### CU06 – Cenário 1 (8 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu06_c1_fluxo_principal_adiciona_favorito` | `backend/tests/integration/test_cu06_manter_favoritos.py` |
| principal | `test_cu06_c1_fluxo_principal_adiciona_favorito` | `frontend/tests/cu06-c1-favoritar.test.tsx` |
| FA1 | `test_cu06_c1_fa1_usuario_nao_autenticado` | `backend/tests/integration/test_cu06_manter_favoritos.py` |
| FA1 | `test_cu06_c1_fa1_usuario_nao_autenticado` | `frontend/tests/cu06-c1-favoritar.test.tsx` |
| FA2 | `test_cu06_c1_fa2_item_ja_favoritado` | `backend/tests/integration/test_cu06_manter_favoritos.py` |
| FA2 | `test_cu06_c1_fa2_item_ja_favoritado` | `frontend/tests/cu06-c1-favoritar.test.tsx` |
| FE1 | `test_cu06_c1_fe1_falha_no_banco` | `backend/tests/integration/test_cu06_manter_favoritos.py` |
| FE1 | `test_cu06_c1_fe1_falha_no_banco` | `frontend/tests/cu06-c1-favoritar.test.tsx` |

#### CU06 – Cenário 2 (8 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu06_c2_fluxo_principal_remove_favorito` | `backend/tests/integration/test_cu06_manter_favoritos.py` |
| principal | `test_cu06_c2_fluxo_principal_remove_favorito` | `frontend/tests/cu06-c2-remover.test.tsx` |
| FA1 | `test_cu06_c2_fa1_remove_os_alertas_do_item` | `backend/tests/integration/test_cu06_manter_favoritos.py` |
| FA1 | `test_cu06_c2_fa1_remove_os_alertas_do_item` | `frontend/tests/cu06-c2-remover.test.tsx` |
| FA2 | `test_cu06_c2_fa2_remocao_cancelada` | `backend/tests/integration/test_cu06_manter_favoritos.py` |
| FA2 | `test_cu06_c2_fa2_remocao_cancelada` | `frontend/tests/cu06-c2-remover.test.tsx` |
| FE1 | `test_cu06_c2_fe1_falha_desfaz_remocoes` | `backend/tests/integration/test_cu06_manter_favoritos.py` |
| FE1 | `test_cu06_c2_fe1_falha_desfaz_remocoes` | `frontend/tests/cu06-c2-remover.test.tsx` |

#### CU06 – Cenário 3 (8 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu06_c3_fluxo_principal_lista_favoritos` | `backend/tests/integration/test_cu06_manter_favoritos.py` |
| principal | `test_cu06_c3_fluxo_principal_lista_favoritos` | `frontend/tests/cu06-c3-lista.test.tsx` |
| FA1 | `test_cu06_c3_fa1_lista_vazia` | `backend/tests/integration/test_cu06_manter_favoritos.py` |
| FA1 | `test_cu06_c3_fa1_lista_vazia` | `frontend/tests/cu06-c3-lista.test.tsx` |
| FA2 | `test_cu06_c3_fa2_dados_desatualizados_rn09` | `backend/tests/integration/test_cu06_manter_favoritos.py` |
| FA2 | `test_cu06_c3_fa2_dados_desatualizados_rn09` | `frontend/tests/cu06-c3-lista.test.tsx` |
| FE1 | `test_cu06_c3_fe1_falha_no_banco` | `backend/tests/integration/test_cu06_manter_favoritos.py` |
| FE1 | `test_cu06_c3_fe1_falha_no_banco` | `frontend/tests/cu06-c3-lista.test.tsx` |

#### CU07 – Regras gerais do caso de uso (2 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| regra | `test_cu07_so_o_dono_altera_e_exclui_o_alerta` | `backend/tests/integration/test_cu07_manter_alerta.py` |
| RN08 | `test_cu07_rn08_pedidos_simultaneos_nao_passam_do_limite` | `backend/tests/integration/test_cu07_manter_alerta.py` |

#### CU07 – Cenário 1 (10 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu07_c1_fluxo_principal_cria_alerta` | `backend/tests/integration/test_cu07_manter_alerta.py` |
| principal | `test_cu07_c1_fluxo_principal_cria_alerta` | `frontend/tests/cu07-c1-criar-alerta.test.tsx` |
| FA1 | `test_cu07_c1_fa1_item_fora_dos_favoritos` | `backend/tests/integration/test_cu07_manter_alerta.py` |
| FA1 | `test_cu07_c1_fa1_item_fora_dos_favoritos` | `frontend/tests/cu07-c1-criar-alerta.test.tsx` |
| FA2 | `test_cu07_c1_fa2_limite_de_alertas_rn08` | `backend/tests/integration/test_cu07_manter_alerta.py` |
| FA2 | `test_cu07_c1_fa2_limite_de_alertas_rn08` | `frontend/tests/cu07-c1-criar-alerta.test.tsx` |
| FA3 | `test_cu07_c1_fa3_dados_invalidos` | `backend/tests/integration/test_cu07_manter_alerta.py` |
| FA3 | `test_cu07_c1_fa3_dados_invalidos` | `frontend/tests/cu07-c1-criar-alerta.test.tsx` |
| FE1 | `test_cu07_c1_fe1_falha_no_banco` | `backend/tests/integration/test_cu07_manter_alerta.py` |
| FE1 | `test_cu07_c1_fe1_falha_no_banco` | `frontend/tests/cu07-c1-criar-alerta.test.tsx` |

O FA3 do backend é um `parametrize` com 11 casos de dados inválidos (tipo ou canal ausente ou desconhecido, preço vazio ou total zero, parte negativa, fracionária ou em texto, Prata ou Cobre acima de 99), numa só função.

#### CU07 – Cenário 2 (10 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu07_c2_fluxo_principal_altera_alerta` | `backend/tests/integration/test_cu07_manter_alerta.py` |
| principal | `test_cu07_c2_fluxo_principal_altera_alerta` | `frontend/tests/cu07-c2-alterar-alerta.test.tsx` |
| FA1 | `test_cu07_c2_fa1_reativa_alerta_disparado` | `backend/tests/integration/test_cu07_manter_alerta.py` |
| FA1 | `test_cu07_c2_fa1_reativa_alerta_disparado` | `frontend/tests/cu07-c2-alterar-alerta.test.tsx` |
| FA2 | `test_cu07_c2_fa2_limite_na_reativacao_rn08` | `backend/tests/integration/test_cu07_manter_alerta.py` |
| FA2 | `test_cu07_c2_fa2_limite_na_reativacao_rn08` | `frontend/tests/cu07-c2-alterar-alerta.test.tsx` |
| FA3 | `test_cu07_c2_fa3_dados_invalidos` | `backend/tests/integration/test_cu07_manter_alerta.py` |
| FA3 | `test_cu07_c2_fa3_dados_invalidos` | `frontend/tests/cu07-c2-alterar-alerta.test.tsx` |
| FE1 | `test_cu07_c2_fe1_falha_mantem_dados` | `backend/tests/integration/test_cu07_manter_alerta.py` |
| FE1 | `test_cu07_c2_fe1_falha_mantem_dados` | `frontend/tests/cu07-c2-alterar-alerta.test.tsx` |

#### CU07 – Cenário 3 (5 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu07_c3_fluxo_principal_exclui_alerta` | `backend/tests/integration/test_cu07_manter_alerta.py` |
| principal | `test_cu07_c3_fluxo_principal_exclui_alerta` | `frontend/tests/cu07-c3-excluir-alerta.test.tsx` |
| FA1 | `test_cu07_c3_fa1_exclusao_cancelada` | `frontend/tests/cu07-c3-excluir-alerta.test.tsx` |
| FE1 | `test_cu07_c3_fe1_falha_mantem_alerta` | `backend/tests/integration/test_cu07_manter_alerta.py` |
| FE1 | `test_cu07_c3_fe1_falha_mantem_alerta` | `frontend/tests/cu07-c3-excluir-alerta.test.tsx` |

O FA1 do C3 (exclusão cancelada) acontece só na tela: cancelar o diálogo não envia nada ao backend, por isso não tem teste de backend.

#### CU08 – Regras gerais do caso de uso (3 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| RN07 | `test_rn07_alerta_dispara_uma_unica_vez` | `backend/tests/integration/test_cu08_manter_notificacoes.py` |
| RN20 | `test_cu08_exclusao_da_conta_remove_notificacoes_rn20` | `backend/tests/integration/test_cu08_manter_notificacoes.py` |
| regra | `test_cu08_notificacao_permanece_quando_o_alerta_e_excluido` | `backend/tests/integration/test_cu08_manter_notificacoes.py` |

O teste da RN07 cobre o ciclo seguinte com o preço ainda além do alvo e dois ciclos simultâneos (a sessão B fica bloqueada no `UPDATE` condicional até o commit da A e não gera notificação).

#### CU08 – Cenário 1 (5 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu08_c1_fluxo_principal_dispara_alerta_de_compra_e_de_venda_rn07` | `backend/tests/integration/test_cu08_manter_notificacoes.py` |
| FA1 | `test_cu08_c1_fa1_nenhum_alerta_atingido` | `backend/tests/integration/test_cu08_manter_notificacoes.py` |
| FA2 | `test_cu08_c1_fa2_item_com_volume_anomalo_rn12` | `backend/tests/integration/test_cu08_manter_notificacoes.py` |
| FE1 | `test_cu08_c1_fe1_falha_desfaz_a_verificacao` | `backend/tests/integration/test_cu08_manter_notificacoes.py` |
| decisão | `test_cu08_c1_ficha_do_wow_dispara_alerta_sem_rn12` | `backend/tests/integration/test_cu08_manter_notificacoes.py` |

O fluxo principal, o FA2 e o FE1 rodam dentro de um ciclo real do CU09 (API da Blizzard falsa). O C1 é só do sistema, sem tela.

#### CU08 – Cenário 2 (3 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu08_c2_fluxo_principal_envia_email_rn18` | `backend/tests/integration/test_cu08_manter_notificacoes.py` |
| FA1 | `test_cu08_c2_fa1_falha_no_envio_tenta_ate_3_vezes` | `backend/tests/integration/test_cu08_manter_notificacoes.py` |
| FE1 | `test_cu08_c2_fe1_falha_no_banco` | `backend/tests/integration/test_cu08_manter_notificacoes.py` |

O envio de e-mail é substituído nos testes (`EmailFalso`). O C2 é só do sistema, sem tela.

#### CU08 – Cenário 3 (9 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu08_c3_fluxo_principal_lista_e_marca_como_lidas` | `backend/tests/integration/test_cu08_manter_notificacoes.py` |
| principal | `test_cu08_c3_fluxo_principal_lista_destaca_e_marca_como_lidas` | `frontend/tests/cu08-c3-notificacoes.test.tsx` |
| passo 1 | `test_cu08_c3_passo1_contador_ao_carregar_e_a_cada_5_minutos` | `frontend/tests/cu08-c3-notificacoes.test.tsx` |
| FA1 | `test_cu08_c3_fa1_nenhuma_notificacao` | `backend/tests/integration/test_cu08_manter_notificacoes.py` |
| FA1 | `test_cu08_c3_fa1_nenhuma_notificacao` | `frontend/tests/cu08-c3-notificacoes.test.tsx` |
| FE1 | `test_cu08_c3_fe1_falha_no_banco` | `backend/tests/integration/test_cu08_manter_notificacoes.py` |
| FE1 | `test_cu08_c3_fe1_falha_ao_carregar` | `frontend/tests/cu08-c3-notificacoes.test.tsx` |
| FE1 | `test_cu08_c3_fe1_falha_ao_marcar_como_lidas` | `frontend/tests/cu08-c3-notificacoes.test.tsx` |
| regra | `test_cu08_c3_so_as_notificacoes_do_proprio_usuario` | `backend/tests/integration/test_cu08_manter_notificacoes.py` |

A regra do C3 confere a pré-condição (sem sessão, 401) e que cada usuário vê e marca só as próprias notificações.

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

#### CU10 – Cenário 1 (45 testes)

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
| regra | `test_cu10_c1_dia_em_aberto_e_gravado_no_dia_seguinte_mesmo_com_o_arquivo_igual` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| regra | `test_cu10_c1_etag_mescla_metadata_sem_apagar_atributos` | `backend/tests/scraper/test_backfill.py` |
| regra | `test_cu10_c1_etag_sem_origem_registrada_nao_e_reaproveitado_na_recuperacao` | `backend/tests/scraper/test_backfill.py` |
| regra | `test_cu10_c1_importacao_diaria_agendada_nao_grava_junto_com_o_ciclo_da_blizzard` | `backend/tests/unit/test_cu10_c1_agendamento.py` |
| regra | `test_cu10_c1_importacao_diaria_dormindo_roda_ao_acordar_uma_vez` | `backend/tests/unit/test_cu10_c1_agendamento.py` |
| regra | `test_cu10_c1_importacao_diaria_grava_so_dias_encerrados` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| regra | `test_cu10_c1_importacao_diaria_nao_roda_com_outra_importacao_em_andamento` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| regra | `test_cu10_c1_importacao_diaria_perdida_com_o_computador_desligado_roda_ao_iniciar` | `backend/tests/unit/test_cu10_c1_agendamento.py` |
| regra | `test_cu10_c1_importacao_diaria_perdida_e_reconhecida_pelo_ultimo_disparo` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| regra | `test_cu10_c1_importacao_diaria_tenta_de_novo_depois_de_um_deadlock` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
| regra | `test_cu10_c1_importacao_incremental_regrava_o_dia_gravado_antes_de_terminar` | `backend/tests/integration/test_cu10_c1_importar_historico.py` |
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
| regra | `test_cu10_c1_worker_agenda_a_importacao_diaria` | `backend/tests/unit/test_cu10_c1_agendamento.py` |

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

#### CU11 – Regras gerais do caso de uso (3 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| regra | `test_cu11_conjunto_de_treinamento_nao_entra_nas_constantes` | `backend/tests/modelo/test_cu11_regras_do_modelo.py` |
| regra | `test_cu11_migracao_8_situacao_ignorada` | `backend/tests/integration/test_migracoes.py` |
| regra | `test_cu11_uma_versao_vigente_por_regiao` | `backend/tests/integration/test_cu11_c1_pedido.py` |

#### CU11 – Cenário 1 (19 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu11_c1_fluxo_principal_treina_e_libera_itens` | `backend/tests/modelo/test_cu11_c1_treinamento.py` |
| FA1 | `test_cu11_c1_fa1_nenhum_item_apto` | `backend/tests/modelo/test_cu11_c1_treinamento.py` |
| FA2 | `test_cu11_c1_fa2_reinicio_do_servico_libera_a_fila` | `backend/tests/integration/test_cu11_c1_pedido.py` |
| FA2 | `test_cu11_c1_fa2_treinamento_em_andamento` | `backend/tests/integration/test_cu11_c1_pedido.py` |
| FA3 | `test_cu11_c1_fa3_serie_insuficiente_item_ignorado` | `backend/tests/modelo/test_cu11_c1_treinamento.py` |
| FA4 | `test_cu11_c1_fa4_projecao_reprovada_rn10` | `backend/tests/modelo/test_cu11_c1_treinamento.py` |
| FA5 | `test_cu11_c1_fa5_avaliacao_insuficiente_rn10` | `backend/tests/modelo/test_cu11_c1_treinamento.py` |
| FE1 | `test_cu11_c1_fe1_falha_no_treinamento` | `backend/tests/modelo/test_cu11_c1_treinamento.py` |
| FE2 | `test_cu11_c1_fe2_banco_indisponivel_no_pedido` | `backend/tests/integration/test_cu11_c1_pedido.py` |
| FE2 | `test_cu11_c1_fe2_falha_no_banco` | `backend/tests/modelo/test_cu11_c1_treinamento.py` |
| regra | `test_cu11_c1_execucao_antiga_recebe_os_liberados_sem_amostra_de_treino` | `backend/tests/modelo/test_cu11_c1_treinamento.py` |
| regra | `test_cu11_c1_fila_entrega_um_treinamento_por_vez` | `backend/tests/integration/test_cu11_c1_pedido.py` |
| regra | `test_cu11_c1_liberados_sem_amostra_de_treino` | `backend/tests/modelo/test_cu11_c1_treinamento.py` |
| regra | `test_cu11_c1_passo8_rede_com_gelu` | `backend/tests/modelo/test_cu11_c1_treinamento.py` |
| regra | `test_cu11_c1_passo1_registra_o_pedido_do_admin` | `backend/tests/integration/test_cu11_c1_pedido.py` |
| regra | `test_cu11_c1_passo2_elegiveis_e_conjunto_de_treinamento` | `backend/tests/modelo/test_cu11_regras_do_modelo.py` |
| regra | `test_cu11_c1_regiao_invalida` | `backend/tests/integration/test_cu11_c1_pedido.py` |
| regra | `test_cu11_c1_restrito_ao_admin` | `backend/tests/integration/test_cu11_c1_pedido.py` |
| regra | `test_cu11_c1_resumo_do_treinamento` | `backend/tests/integration/test_cu11_c1_pedido.py` |

#### CU11 – Cenário 2 (16 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu11_c2_fluxo_principal_substitui_modelo_rn26` | `backend/tests/modelo/test_cu11_c2_retreinamento.py` |
| FA1 | `test_cu11_c2_fa1_item_deixou_de_ser_elegivel` | `backend/tests/modelo/test_cu11_c2_retreinamento.py` |
| FA2 | `test_cu11_c2_fa2_novo_modelo_inferior_mantem_vigente` | `backend/tests/modelo/test_cu11_c2_retreinamento.py` |
| FE1 | `test_cu11_c2_fe1_falha_mantem_vigente` | `backend/tests/modelo/test_cu11_c2_retreinamento.py` |
| regra | `test_cu11_c2_agendador_nao_duplica_execucao_em_andamento` | `backend/tests/integration/test_cu11_c2_agendador.py` |
| regra | `test_cu11_c2_agendador_registra_um_retreinamento_por_regiao_com_modelo_vigente` | `backend/tests/integration/test_cu11_c2_agendador.py` |
| regra | `test_cu11_c2_agendador_usa_o_horario_configurado` | `backend/tests/modelo/test_cu11_c2_retreinamento.py` |
| regra | `test_cu11_c2_aviso_de_serie_diaria_desatualizada` | `backend/tests/modelo/test_cu11_c2_retreinamento.py` |
| regra | `test_cu11_c2_comando_retreinar_registra_pelo_mesmo_caminho` | `backend/tests/modelo/test_cu11_c2_retreinamento.py` |
| regra | `test_cu11_c2_compara_os_dois_modelos_no_mesmo_periodo_com_as_constantes_de_cada_versao` | `backend/tests/modelo/test_cu11_c2_retreinamento.py` |
| regra | `test_cu11_c2_item_novo_liberado_ao_atingir_o_minimo_de_dias` | `backend/tests/modelo/test_cu11_c2_retreinamento.py` |
| regra | `test_cu11_c2_resumo_do_retreinamento` | `backend/tests/integration/test_cu11_c2_agendador.py` |
| regra | `test_cu11_c2_retreinamento_dormindo_roda_ao_acordar_uma_vez` | `backend/tests/modelo/test_cu11_c2_retreinamento.py` |
| regra | `test_cu11_c2_retreinamento_perdido_com_o_computador_desligado_e_registrado_uma_vez` | `backend/tests/integration/test_cu11_c2_agendador.py` |
| regra | `test_cu11_c2_retreinamento_perdido_com_o_computador_desligado_roda_ao_iniciar` | `backend/tests/modelo/test_cu11_c2_retreinamento.py` |
| regra | `test_cu11_c2_vigente_antigo_avaliado_com_a_propria_chave_e_ativacao` | `backend/tests/modelo/test_cu11_c2_retreinamento.py` |

#### CU11 – Cenário 3 (12 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| principal | `test_cu11_c3_fluxo_principal_registra_snapshot_rn13` | `backend/tests/integration/test_cu11_c3_consolidacao.py` |
| FA1 | `test_cu11_c3_fa1_sem_predicao_do_dia` | `backend/tests/modelo/test_cu11_c3_ponta_a_ponta.py` |
| FA2 | `test_cu11_c3_fa2_valor_real_indisponivel` | `backend/tests/integration/test_cu11_c3_consolidacao.py` |
| FA3 | `test_cu11_c3_fa3_degradacao_bloqueia_item_rn13` | `backend/tests/integration/test_cu11_c3_consolidacao.py` |
| FA4 | `test_cu11_c3_fa4_degradacao_generalizada_antecipa_retreino` | `backend/tests/modelo/test_cu11_c3_ponta_a_ponta.py` |
| FE1 | `test_cu11_c3_fe1_falha_no_banco_reprocessa` | `backend/tests/modelo/test_cu11_c3_ponta_a_ponta.py` |
| regra | `test_cu11_c3_comando_consolidar` | `backend/tests/modelo/test_cu11_c3_ponta_a_ponta.py` |
| regra | `test_cu11_c3_disparo_perdido_roda_ao_iniciar` | `backend/tests/modelo/test_cu11_c3_ponta_a_ponta.py` |
| regra | `test_cu11_c3_espera_a_importacao_diaria` | `backend/tests/integration/test_cu11_c3_consolidacao.py` |
| regra | `test_cu11_c3_gera_previsoes_dos_proximos_7_dias_em_cobre_rn01` | `backend/tests/modelo/test_cu11_c3_ponta_a_ponta.py` |
| regra | `test_cu11_c3_previsao_com_vigente_antigo_usa_a_chave_antiga` | `backend/tests/modelo/test_cu11_c3_ponta_a_ponta.py` |
| regra | `test_cu11_c3_previsao_usa_so_dados_ate_o_dia_de_referencia_rn25` | `backend/tests/modelo/test_cu11_c3_ponta_a_ponta.py` |

#### CU11 – Regras do modelo (RN03, RN10, RN24, RN25, RN27) (16 testes)

| Fluxo | Teste | Arquivo |
|---|---|---|
| regra | `test_rn03_confirma_novo_patamar_em_7_dias` | `backend/tests/modelo/test_cu11_regras_do_modelo.py` |
| regra | `test_rn03_descarta_pico_com_ema_dos_aceitos` | `backend/tests/modelo/test_cu11_regras_do_modelo.py` |
| regra | `test_rn03_salto_absurdo_exige_28_dias` | `backend/tests/modelo/test_cu11_regras_do_modelo.py` |
| regra | `test_rn10_exige_minimo_de_dias_avaliados` | `backend/tests/modelo/test_cu11_regras_do_modelo.py` |
| regra | `test_rn10_libera_por_mdape_quem_supera_o_ingenuo` | `backend/tests/modelo/test_cu11_regras_do_modelo.py` |
| regra | `test_rn24_calculos_por_item` | `backend/tests/modelo/test_cu11_regras_do_modelo.py` |
| regra | `test_rn24_ida_e_volta_recupera_o_preco` | `backend/tests/modelo/test_cu11_regras_do_modelo.py` |
| regra | `test_rn24_normalizacao_de_outra_versao_em_itens_fora_do_treino` | `backend/tests/modelo/test_cu11_regras_do_modelo.py` |
| regra | `test_rn24_par_desconhecido_vira_zero` | `backend/tests/modelo/test_cu11_regras_do_modelo.py` |
| regra | `test_rn24_subclasse_pelo_par_classe_subclasse` | `backend/tests/modelo/test_cu11_regras_do_modelo.py` |
| regra | `test_rn24_versao_antiga_mantem_o_codigo_da_subclasse` | `backend/tests/modelo/test_cu11_regras_do_modelo.py` |
| regra | `test_rn25_considera_somente_dias_encerrados` | `backend/tests/modelo/test_cu11_c1_treinamento.py` |
| regra | `test_rn25_dias_ate_patch_respeita_antecedencia` | `backend/tests/modelo/test_cu11_regras_do_modelo.py` |
| regra | `test_rn25_janelas_respeitam_os_cortes` | `backend/tests/modelo/test_cu11_regras_do_modelo.py` |
| regra | `test_rn25_sem_vazamento_do_futuro` | `backend/tests/modelo/test_cu11_regras_do_modelo.py` |
| regra | `test_rn27_historico_minimo_para_projecao` | `backend/tests/modelo/test_cu11_regras_do_modelo.py` |
