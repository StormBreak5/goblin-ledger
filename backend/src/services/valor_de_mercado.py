from typing import Iterable, Optional

from src.services import ingestao_config


def primeiro_quartil_ponderado(ofertas: Iterable[tuple[int, int]]) -> Optional[int]:
    """
    CU09-C3 passo 4 (RN06): valor de mercado = primeiro quartil (25%) dos preços dos leilões ativos, e não o menor
    preço isolado. Cada oferta é (preço unitário em Cobre, quantidade); o quartil é ponderado pela quantidade, de
    modo que 1.000 unidades baratas pesem mais que 1 unidade barata. Devolve None se não houver oferta.
    """
    ordenadas = sorted(ofertas)
    total = sum(quantidade for _, quantidade in ordenadas)
    if total == 0:
        return None
    limite = total * 0.25
    acumulado = 0
    for preco, quantidade in ordenadas:
        acumulado += quantidade
        if acumulado >= limite:
            return preco
    return ordenadas[-1][0]  # inalcançável na prática; mantém o retorno tipado


def volume_e_anomalo(volume: int, mediana_anterior: Optional[float], pontos_anteriores: int) -> bool:
    """
    CU09-C2 passo 4 (RN12): o volume do ciclo é característico de injeção artificial de itens por bots?

    O documento não define o critério; adotado: mais de ANOMALIA_FATOR vezes a mediana dos volumes dos últimos 7 dias
    (calculada no banco), com um piso de volume e ao menos ANOMALIA_MINIMO_DE_PONTOS pontos anteriores. Sem base de
    comparação, não se julga.
    """
    if mediana_anterior is None or pontos_anteriores < ingestao_config.ANOMALIA_MINIMO_DE_PONTOS:
        return False
    if volume < ingestao_config.ANOMALIA_VOLUME_MINIMO:
        return False
    return volume > ingestao_config.ANOMALIA_FATOR * max(mediana_anterior, 1)
