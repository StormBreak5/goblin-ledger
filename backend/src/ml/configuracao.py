"""CU11: parâmetros do modelo preditivo global (porte de `estudos/lstm/config.py`).

Os padrões são os da configuração final do estudo (congelada depois da etapa 2e) e os valores decididos pelo autor
na v4 do documento de alterações. Todos podem ser trocados por variável de ambiente (tabela "Valores configuráveis" do
CU11); veja `backend/.env.example`.

As opções que só existiram como experimento no estudo (eventos detalhados, máscara, variáveis 19 e 20 e sorteio de
itens reservados) não foram portadas: foram reprovadas na validação (etapas 2b e 2d).
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Optional

from src.services.ingestao_config import COMMODITIES_ID_POR_REGIAO


@dataclass(frozen=True)
class ConfigModelo:
    # Formato das amostras (RF12, RF04)
    janela: int = 30
    horizonte: int = 7

    # RN24 - normalização
    zscore_janela: int = 90
    zscore_min_periodos: int = 30
    zscore_limite: float = 3.0
    percentil_constante: float = 99
    limite_dias: int = 60
    preenchimento_max_dias: int = 3
    volatilidade_janela: int = 7
    volatilidade_min_periodos: int = 5
    qualidade_max: int = 5

    # RN03 - EMA de 14 dias só com os preços aceitos; confirmação de patamar em 7 registros (28 num salto de 1.000×)
    ema_span: int = 14
    rn03_acima: float = 3.00
    rn03_abaixo: float = 0.90
    rn03_confirmacao: int = 7
    rn03_salto_absurdo: float = 1000.0
    rn03_confirmacao_absurdo: int = 28

    # RN25 - integridade temporal
    proporcao_treino: float = 0.70
    proporcao_validacao: float = 0.20
    antecedencia_anuncio_dias: int = 14

    # Elegíveis à projeção: RN02 (liquidez), RN27 (histórico mínimo) e RN07 (equipamentos relevantes)
    liquidez_min_quantidade: float = 50
    liquidez_dias: int = 7
    historico_minimo_dias: int = 60
    ilvl_minimo: Optional[float] = None  # RN07: decisão pendente; None = desligada

    # RN10 - MdAPE ≤ 15%, menor que o do ingênuo, com ao menos 30 dias avaliados
    metrica_rn10: str = "mdape"
    limiar_rn10: float = 0.15
    minimo_dias_rn10: int = 30

    # Rede e treino (configuração final do estudo, etapa 2e)
    unidades: int = 64
    dropout: float = 0.2
    taxa_aprendizado: float = 1e-3
    perda: str = "mae"
    epocas_max: int = 100
    paciencia: int = 10
    lote: int = 512
    amostras_por_epoca: int = 400_000
    amostras_validacao: int = 200_000
    semente: int = 42

    commodities_por_regiao: dict[str, int] = field(default_factory=lambda: dict(COMMODITIES_ID_POR_REGIAO))

    def __post_init__(self) -> None:
        if self.metrica_rn10 not in ("mdape", "mape"):
            raise ValueError("MODELO_METRICA_RN10 deve ser 'mdape' ou 'mape'")
        if self.perda not in ("mae", "huber", "mse"):
            raise ValueError("MODELO_PERDA deve ser 'mae', 'huber' ou 'mse'")
        if not 0 < self.proporcao_treino < self.proporcao_treino + self.proporcao_validacao < 1:
            raise ValueError("MODELO_PROPORCAO_TREINO e MODELO_PROPORCAO_VALIDACAO devem deixar uma parte para o teste")

    def como_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def de_dict(cls, valores: dict[str, Any]) -> "ConfigModelo":
        """A configuração gravada no normalizacao.json de uma versão do modelo (campos desconhecidos são ignorados)."""
        nomes = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in valores.items() if k in nomes})

    @classmethod
    def do_ambiente(cls) -> "ConfigModelo":
        """Lê as variáveis MODELO_* (tabela "Valores configuráveis" do CU11); a ausente fica com o padrão."""
        for nome in ("MODELO_MASCARA", "MODELO_EVENTOS_DETALHADOS"):
            if _booleano(nome):
                raise ValueError(f"{nome}=true não é suportado: a opção foi reprovada no estudo (etapa 2b) e não foi "
                                 "portada para o sistema")
        padrao = cls()
        ilvl = os.getenv("MODELO_ILVL_MINIMO", "").strip()
        return cls(
            janela=_inteiro("MODELO_JANELA_DIAS", padrao.janela),
            horizonte=_inteiro("MODELO_HORIZONTE_DIAS", padrao.horizonte),
            zscore_janela=_inteiro("MODELO_ZSCORE_DIAS", padrao.zscore_janela),
            historico_minimo_dias=_inteiro("MODELO_HISTORICO_MINIMO_DIAS", padrao.historico_minimo_dias),
            proporcao_treino=_decimal("MODELO_PROPORCAO_TREINO", padrao.proporcao_treino),
            proporcao_validacao=_decimal("MODELO_PROPORCAO_VALIDACAO", padrao.proporcao_validacao),
            antecedencia_anuncio_dias=_inteiro("MODELO_ANTECEDENCIA_PATCH_DIAS", padrao.antecedencia_anuncio_dias),
            metrica_rn10=os.getenv("MODELO_METRICA_RN10", padrao.metrica_rn10).strip().lower() or padrao.metrica_rn10,
            limiar_rn10=_decimal("MODELO_LIMIAR_RN10", padrao.limiar_rn10),
            minimo_dias_rn10=_inteiro("MODELO_MINIMO_DIAS_RN10", padrao.minimo_dias_rn10),
            rn03_confirmacao=_inteiro("MODELO_RN03_CONFIRMACAO", padrao.rn03_confirmacao),
            rn03_salto_absurdo=_decimal("MODELO_RN03_SALTO_ABSURDO", padrao.rn03_salto_absurdo),
            rn03_confirmacao_absurdo=_inteiro("MODELO_RN03_CONFIRMACAO_ABSURDO", padrao.rn03_confirmacao_absurdo),
            ilvl_minimo=float(ilvl) if ilvl else None,
            unidades=_inteiro("MODELO_UNIDADES", padrao.unidades),
            perda=os.getenv("MODELO_PERDA", padrao.perda).strip().lower() or padrao.perda,
            epocas_max=_inteiro("MODELO_EPOCAS_MAX", padrao.epocas_max),
            paciencia=_inteiro("MODELO_PACIENCIA", padrao.paciencia),
            lote=_inteiro("MODELO_LOTE", padrao.lote),
            amostras_por_epoca=_inteiro("MODELO_AMOSTRAS_POR_EPOCA", padrao.amostras_por_epoca),
            amostras_validacao=_inteiro("MODELO_AMOSTRAS_VALIDACAO", padrao.amostras_validacao),
            semente=_inteiro("MODELO_SEMENTE", padrao.semente),
        )


def _texto(nome: str) -> str:
    return os.getenv(nome, "").strip()


def _inteiro(nome: str, padrao: int) -> int:
    valor = _texto(nome)
    return int(valor) if valor else padrao


def _decimal(nome: str, padrao: float) -> float:
    valor = _texto(nome).replace(",", ".")
    return float(valor) if valor else padrao


def _booleano(nome: str) -> bool:
    return _texto(nome).lower() in ("1", "true", "sim", "yes", "on")


# Variáveis que variam no tempo: entram nos 30 passos da LSTM (variáveis 1 a 14 do quadro da seção 5.12.2).
VARIAVEIS_SEQUENCIA: list[str] = [
    "f_log_return",         # 1  log-retorno diário
    "f_nivel_preco",        # 2  nível do preço (z-score móvel de 90 dias)
    "f_quantidade",         # 3  quantidade ofertada (z-score móvel de 90 dias)
    "f_preco_ema14",        # 4  desvio em relação à EMA de 14 dias da RN03
    "f_volatilidade_7d",    # 5  volatilidade de 7 dias
    "f_retorno_subclasse",  # 6  variação do índice da subclasse
    "f_preco_npc",          # 7  distância ao preço de venda ao vendedor
    "f_observado",          # 8  1 = registro observado; 0 = preenchido com o último valor
    "f_dia_sin",            # 9  dia da semana (seno)
    "f_dia_cos",            # 9  dia da semana (cosseno)
    "f_dias_desde_patch",   # 10 dias desde o último patch
    "f_dias_ate_patch",     # 11 dias até o próximo patch anunciado
    "f_expansao",           # 12 expansão ou pré-patch nos próximos 14 dias
    "f_temporada_ativa",    # 13 temporada ativa
    "f_dias_temporada",     # 13 dias desde o início da temporada
    "f_evento",             # 14 evento sazonal ativo
]

# Atributos fixos do item (variáveis 16 a 18): entram uma vez por amostra, juntados à saída da LSTM.
VARIAVEIS_ESTATICAS: list[str] = ["f_qualidade", "f_nivel_item", "f_tem_piso", "f_commodity"]

# Variável 15: índices inteiros para as camadas de embedding (0 = desconhecida).
VARIAVEIS_CATEGORICAS: list[str] = ["classe_idx", "subclasse_idx"]

PERIODOS: tuple[str, str, str] = ("treino", "validacao", "teste")
