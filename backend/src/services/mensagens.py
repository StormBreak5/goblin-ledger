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

# CU02-C4 – Encerrar sessão
SESSAO_EXPIRADA = "Sua sessão expirou. Faça login novamente"  # CU02-C4-FA1
