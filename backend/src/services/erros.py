from typing import Optional, Union

from src.services import mensagens


class ErroDeNegocio(Exception):
    """Falha prevista nos fluxos alternativos dos CU01 e CU02. O controller a traduz para a resposta HTTP."""
    status_code = 400
    mensagem_padrao = ""

    def __init__(self, mensagem: Optional[str] = None, campos: Optional[list[str]] = None):
        self.mensagem = mensagem or self.mensagem_padrao
        self.campos = campos or []
        super().__init__(self.mensagem)

    @property
    def detalhe(self) -> Union[str, dict]:
        """Texto simples, ou {"message", "fields"} quando há campos a destacar (CU01-C1-FA1 / CU02-C1-FA1)."""
        if self.campos:
            return {"message": self.mensagem, "fields": self.campos}
        return self.mensagem


class DadosInvalidosError(ErroDeNegocio):
    """CU01-C1-FA1 / CU01-C2 / CU02-C1-FA1: campo obrigatório vazio, e-mail inválido, região fora de US/EU etc."""
    status_code = 422
    mensagem_padrao = mensagens.CAMPOS_INVALIDOS


class EmailInvalidoError(ErroDeNegocio):
    """CU02-C2-FA1."""
    status_code = 422
    mensagem_padrao = mensagens.EMAIL_INVALIDO


class EmailJaCadastradoError(ErroDeNegocio):
    """CU01-C1-FA2 (RN18)."""
    status_code = 409
    mensagem_padrao = mensagens.EMAIL_JA_CADASTRADO


class SenhasDivergentesError(ErroDeNegocio):
    """CU01-C2-FA2 / CU02-C3-FA2."""
    status_code = 422
    mensagem_padrao = mensagens.SENHAS_DIVERGENTES


class SenhaIncorretaError(ErroDeNegocio):
    """CU01-C2-FA3 / CU01-C3-FA2 (RN19): a mensagem depende do fluxo."""
    status_code = 400


class CredenciaisInvalidasError(ErroDeNegocio):
    """CU02-C1-FA2."""
    status_code = 401
    mensagem_padrao = mensagens.CREDENCIAIS_INVALIDAS


class ContaBloqueadaError(ErroDeNegocio):
    """CU02-C1-FA3 (RN21)."""
    status_code = 429
    mensagem_padrao = mensagens.ACESSO_BLOQUEADO


class SessaoInvalidaError(ErroDeNegocio):
    """CU02-C4-FA1: token ausente, adulterado, expirado ou de sessão encerrada."""
    status_code = 401
    mensagem_padrao = mensagens.SESSAO_EXPIRADA


class LinkInvalidoError(ErroDeNegocio):
    """CU02-C3-FA1 (RN22)."""
    status_code = 400
    mensagem_padrao = mensagens.LINK_INVALIDO


class EmailIndisponivelError(Exception):
    """CU02-C2-FE1: o serviço de envio de e-mail não respondeu."""
