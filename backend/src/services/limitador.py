import asyncio
import os
import time
from typing import Awaitable, Callable

# CU10-C1-FA3 (RN23): intervalo mínimo entre o início de duas requisições consecutivas à fonte. O documento não define o
# valor; o padrão é o ritmo que a importação já tinha (cerca de 125 requisições por segundo) e pode ser ajustado.
INTERVALO_MINIMO_PADRAO = 0.008


def intervalo_minimo_configurado() -> float:
    """Lê UNDERMINE_INTERVALO_MINIMO_SEGUNDOS (RN23). Valor ausente ou inválido volta ao padrão."""
    try:
        valor = float(os.getenv("UNDERMINE_INTERVALO_MINIMO_SEGUNDOS", str(INTERVALO_MINIMO_PADRAO)))
    except ValueError:
        return INTERVALO_MINIMO_PADRAO
    return valor if valor >= 0 else INTERVALO_MINIMO_PADRAO


class LimitadorDeIntervalo:
    """
    CU10-C1-FA3 (RN23): faz cada requisição esperar até que tenha passado o intervalo mínimo desde o início da anterior,
    valendo para todas as tarefas que compartilham o limitador. O relógio e a espera são injetáveis para o teste.
    """

    def __init__(
        self,
        intervalo: float,
        relogio: Callable[[], float] = time.monotonic,
        dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.intervalo = intervalo
        self._relogio = relogio
        self._dormir = dormir
        self._proximo = 0.0
        self._trava = asyncio.Lock()

    async def aguardar(self) -> None:
        """Devolve quando a requisição pode começar; cada chamada reserva o próximo horário livre."""
        if self.intervalo <= 0:
            return
        async with self._trava:
            agora = self._relogio()
            espera = self._proximo - agora
            if espera > 0:
                await self._dormir(espera)
                agora = self._relogio()
            self._proximo = max(agora, self._proximo) + self.intervalo
