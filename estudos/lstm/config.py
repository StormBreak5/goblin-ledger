"""Parâmetros do estudo preliminar do modelo LSTM global (CU11).

Os valores marcados com "A CONFIRMAR" estão destacados no documento de alterações do TC e ainda dependem da decisão do
autor e do orientador. Ficam todos aqui para que possam ser trocados sem mexer no restante do código.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Config:
    # Formato das amostras
    janela: int = 30                 # dias de entrada de cada amostra (A CONFIRMAR)
    horizonte: int = 7               # dias previstos de uma vez, Dense(7) (A CONFIRMAR)

    # RN24 - normalização
    zscore_janela: int = 90          # janela da padronização móvel (A CONFIRMAR)
    zscore_min_periodos: int = 30    # dias mínimos para calcular a padronização móvel
    zscore_limite: float = 3.0       # o z-score é limitado a ±3 e dividido por 3
    percentil_constante: float = 99  # constantes globais = percentil 99 do treino
    limite_dias: int = 60            # contagens de dias limitadas a 60 e divididas por 60
    preenchimento_max_dias: int = 3  # dias sem registro preenchidos com o último valor (e marcados)
    volatilidade_janela: int = 7
    volatilidade_min_periodos: int = 5
    qualidade_max: int = 5

    # RN03 - outliers: descarta preço > EMA·(1 + 3,00) ou < EMA·(1 − 0,90); EMA só com dias anteriores
    ema_span: int = 14
    rn03_acima: float = 3.00
    rn03_abaixo: float = 0.90

    # RN25 - integridade temporal
    proporcao_treino: float = 0.70     # 70/20/10 por data de calendário, igual para todos os itens
    proporcao_validacao: float = 0.20  # o teste fica com o restante (10%)
    antecedencia_anuncio_dias: int = 14  # patch só é "conhecido" 14 dias antes (evento_jogo não tem data de anúncio)

    # RN02 - liquidez (usada só para selecionar os itens do estudo)
    liquidez_min_quantidade: float = 50
    liquidez_dias: int = 7

    # RN10 - limiar de acurácia, usado na avaliação
    limiar_mape: float = 0.15        # (A CONFIRMAR)

    # Ids convencionados das commodities de cada região (src/services/ingestao_config.py)
    commodities_por_regiao: dict[str, int] = field(default_factory=lambda: {"US": 32512, "EU": 32513})

    def como_dict(self) -> dict[str, Any]:
        return asdict(self)


# Variáveis que variam no tempo: entram nos 30 passos da LSTM (formato [amostras, 30, 16]).
# Os nomes seguem os do script do orientador; f_observado e f_temporada_ativa são as duas que faltavam.
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

# Atributos fixos do item: entram uma vez por amostra, juntados à saída da LSTM.
VARIAVEIS_ESTATICAS: list[str] = [
    "f_qualidade",          # 16
    "f_nivel_item",         # 16
    "f_tem_piso",           # 17
    "f_commodity",          # 18
]

# Variável 15: índices inteiros para as camadas de embedding (0 = desconhecida).
VARIAVEIS_CATEGORICAS: list[str] = ["classe_idx", "subclasse_idx"]

PERIODOS: tuple[str, str, str] = ("treino", "validacao", "teste")
