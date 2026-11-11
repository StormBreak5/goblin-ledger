"""Mensagens exibidas ao usuário nos CU01 e CU02, exatamente como nos cenários do documento do TC."""

# CU01-C1 – Cadastrar usuário
CONTA_CRIADA = "Conta criada com sucesso"
CAMPOS_INVALIDOS = "Verifique os campos destacados"  # CU01-C1-FA1 e CU02-C1-FA1
EMAIL_JA_CADASTRADO = "Já existe uma conta cadastrada com este e-mail"  # CU01-C1-FA2 (RN18)
FALHA_NO_CADASTRO = "Não foi possível concluir o cadastro no momento. Tente novamente mais tarde"  # CU01-C1-FE1

# CU01-C2 – Alterar dados do usuário
DADOS_ATUALIZADOS = "Dados atualizados com sucesso"
SENHAS_DIVERGENTES = "A nova senha e a confirmação não coincidem"  # CU01-C2-FA2 e CU02-C3-FA2
SENHA_ATUAL_INCORRETA = "Senha atual incorreta"  # CU01-C2-FA3 (RN19)
FALHA_NA_ATUALIZACAO = "Não foi possível atualizar os dados no momento. Tente novamente mais tarde"  # CU01-C2-FE1

# CU01-C3 – Excluir conta do usuário
SENHA_INCORRETA_NA_EXCLUSAO = "Senha incorreta. A conta não foi excluída"  # CU01-C3-FA2 (RN19)
FALHA_NA_EXCLUSAO = "Não foi possível excluir a conta no momento. Tente novamente mais tarde"  # CU01-C3-FE1

# CU02-C1 – Autenticar usuário
CREDENCIAIS_INVALIDAS = "Credenciais inválidas"  # CU02-C1-FA2 (genérica: não diz qual dado está errado)
ACESSO_BLOQUEADO = "Acesso temporariamente bloqueado por excesso de tentativas. Tente novamente mais tarde"  # FA3 (RN21)
FALHA_NO_LOGIN = "Não foi possível realizar o login no momento. Tente novamente mais tarde"  # CU02-C1-FE1

# CU02-C2 – Solicitar recuperação de senha
EMAIL_INVALIDO = "Informe um e-mail válido"  # CU02-C2-FA1
RECUPERACAO_SOLICITADA = "Se o e-mail estiver cadastrado, você receberá as instruções de recuperação"  # FP e FA2
FALHA_NA_RECUPERACAO = "Não foi possível processar a solicitação no momento. Tente novamente mais tarde"  # CU02-C2-FE1

# CU02-C3 – Redefinir senha
LINK_INVALIDO = "Link de recuperação inválido ou expirado. Solicite uma nova recuperação de senha"  # CU02-C3-FA1 (RN22)
SENHA_REDEFINIDA = "Senha redefinida com sucesso"
FALHA_NA_REDEFINICAO = "Não foi possível redefinir a senha no momento. Tente novamente mais tarde"  # CU02-C3-FE1

# CU09-C4 – Executar ingestão manual (o documento não define os textos abaixo)
ACESSO_RESTRITO_AO_ADMIN = "Acesso restrito ao administrador"
REGIAO_INVALIDA = "Informe uma região válida (US ou EU) com mercados monitorados"
FALHA_NA_INGESTAO_MANUAL = "Não foi possível executar a ingestão no momento. Tente novamente mais tarde"
FALHA_NO_ESTADO_DO_MERCADO = "Não foi possível consultar o estado do mercado no momento. Tente novamente mais tarde"

# CU10-C1 – Importar histórico de preços
REGIAO_OU_ITEM_INVALIDO = "Região ou item inválido. Verifique os dados informados"  # CU10-C1-FA1 (texto das Observações)
FONTE_DE_DADOS_INDISPONIVEL = "Não foi possível obter os dados da fonte informada. Tente novamente mais tarde"  # FE1
FALHA_NA_IMPORTACAO = "Não foi possível concluir a importação no momento. Tente novamente mais tarde"  # CU10-C1-FE2
FORMATO_DA_FONTE_ALTERADO = "Não foi possível interpretar os dados da fonte. Verifique se houve alteração no formato"  # FE3
# O documento não define os textos abaixo.
IMPORTACAO_EM_ANDAMENTO = "Já existe uma importação em andamento"
IMPORTACAO_NAO_ENCONTRADA = "Importação não encontrada"

# CU10-C2 – Registrar eventos de atualização do jogo
EVENTOS_NAO_EXTRAIDOS = "Não foi possível extrair os eventos da página informada. Verifique a fonte ou cadastre o evento manualmente"  # FE1
# O documento não define os textos abaixo.
FONTE_DE_EVENTOS_INVALIDA = "Informe uma fonte de eventos válida"
FALHA_NO_REGISTRO_DE_EVENTOS = "Não foi possível registrar os eventos no momento. Tente novamente mais tarde"
EXTRACAO_RECENTE = "Esta fonte foi lida há pouco. Aguarde alguns minutos antes de extrair novamente"

# CU10-C3 – Validar cobertura histórica dos itens
FALHA_NA_VALIDACAO_DA_COBERTURA = "Não foi possível concluir a validação no momento. Tente novamente mais tarde"  # FE1
APTO_AO_TREINAMENTO = "Apto ao treinamento"  # CU10-C3 passo 5
INAPTO_AO_TREINAMENTO = "Inapto ao treinamento"  # CU10-C3-FA1

# CU04 – Visualizar Histórico
SEM_HISTORICO = "Ainda não há dados históricos coletados suficientes para este item"  # CU04-C1-FA2
DADOS_DESATUALIZADOS = "Dados Desatualizados"  # CU04-C1-FA1 (RN09 / RN14)
DADOS_LIMITADOS = "Dados limitados. Exibindo todo o histórico disponível para o período selecionado."  # CU04-C2-FA1
FALHA_NO_HISTORICO = "Não foi possível carregar o histórico de mercado no momento. Tente novamente mais tarde"  # CU04-C1-FE1

# CU05-C1 – Exibir projeção de preços
PROJECAO_MODELO_NAO_TREINADO = "A projeção de preços ainda não está disponível"  # FA1
PROJECAO_POUCA_QUANTIDADE = "Projeção indisponível: este item tem pouca quantidade ofertada para uma previsão confiável"  # FA2 (RN02)
PROJECAO_HISTORICO_INSUFICIENTE = "Projeção indisponível: este item ainda não tem histórico suficiente para a previsão"  # FA2 (RN27)
PROJECAO_REPROVADA = "Projeção indisponível: as previsões deste item não atingiram a precisão mínima exigida"  # FA3 (RN10)
PROJECAO_EM_AVALIACAO = ("A projeção deste item está em avaliação e será exibida quando houver dados suficientes para medir a "
                         "sua precisão")  # FA4 (RN10)
PROJECAO_SUSPENSA = ("A projeção deste item está suspensa porque as previsões recentes ficaram abaixo da precisão mínima. Ela "
                     "será reavaliada na próxima atualização do modelo")  # FA5 (RN13)
PROJECAO_NAO_DISPONIVEL = "A projeção deste item não está disponível no momento"  # FA6
PROJECAO_DESATUALIZADA = "Projeção desatualizada"  # FA7
PROJECAO_ESTIMATIVA = "A projeção é uma estimativa estatística e não garante o preço futuro"  # passo 7
PROJECAO_ERRO_TIPICO = "Erro mediano de {pct}% nas previsões deste item"  # passo 7
# O documento não define o texto abaixo (protótipo do RF04, Figura 14).
PROJECAO_ORIGEM = "Projeção gerada em {gerada_em}, a partir do menor preço diário de {referencia}"
FALHA_NA_PROJECAO = "Não foi possível carregar a projeção no momento. Tente novamente mais tarde"  # FE1

# CU02-C4 – Encerrar sessão
SESSAO_EXPIRADA = "Sua sessão expirou. Faça login novamente"  # CU02-C4-FA1

# CU11-C1 – Executar treinamento inicial
NENHUM_ITEM_APTO = "Nenhum item apto ao treinamento. Verifique a validação da cobertura histórica"  # CU11-C1-FA1
TREINAMENTO_EM_ANDAMENTO = "Já existe um treinamento em andamento"  # CU11-C1-FA2
FALHA_NO_TREINAMENTO_DO_MODELO = "Não foi possível concluir o treinamento do modelo. Verifique o log de execução"  # FE1
FALHA_NO_TREINAMENTO = "Não foi possível concluir o treinamento no momento. Tente novamente mais tarde"  # CU11-C1-FE2
# O documento não define o texto abaixo.
TREINAMENTO_NAO_ENCONTRADO = "Treinamento não encontrado"
