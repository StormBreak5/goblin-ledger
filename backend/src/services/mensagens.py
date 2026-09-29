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
EVENTO_CADASTRADO = "Evento cadastrado com sucesso"

# CU10-C3 – Validar cobertura histórica dos itens
FALHA_NA_VALIDACAO_DA_COBERTURA = "Não foi possível concluir a validação no momento. Tente novamente mais tarde"  # FE1
APTO_AO_TREINAMENTO = "Apto ao treinamento"  # CU10-C3 passo 5
INAPTO_AO_TREINAMENTO = "Inapto ao treinamento"  # CU10-C3-FA1

# CU02-C4 – Encerrar sessão
SESSAO_EXPIRADA = "Sua sessão expirou. Faça login novamente"  # CU02-C4-FA1
