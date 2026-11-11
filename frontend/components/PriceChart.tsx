"use client";

import { useMemo } from "react";
import TooltipDoGrafico, { TooltipDaProjecao } from "@/components/TooltipDaProjecao";
import { montarDadosDoGrafico, type LinhaDoGrafico } from "@/lib/graficoDoItem";
import type { PontoDoHistorico } from "@/lib/historicoDoItem";
import type { ProjecaoExibida } from "@/lib/projecaoDoItem";
import {
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ComposedChart,
  ReferenceArea,
  ReferenceDot,
} from "recharts";

const UM_DIA_MS = 86_400_000;
const UM_HORA_MS = 3_600_000;

interface PriceChartProps {
  data: PontoDoHistorico[];
  /** CU04-C1-FA2: texto exibido no lugar do gráfico quando não há pontos (vem do backend). */
  mensagemVazia?: string;
  /** CU05-C1: a projeção a desenhar em continuação ao histórico; nula quando indisponível ou oculta (C3). */
  projecao?: ProjecaoExibida | null;
  /** CU05-C2 passo 3: o dia previsto em destaque (pelo ponto do gráfico ou pela linha da tabela). */
  diaDestacado?: string | null;
  aoDestacarDia?: (dia: string | null) => void;
  /** O destaque veio da tabela: a dica do dia aparece junto ao ponto. */
  dicaNoPonto?: boolean;
}

interface PropsDoRotulo {
  x?: number | string;
  y?: number | string;
  payload?: { value: number };
}

/**
 * CU05-C2 passo 3: o ponto do dia em destaque. Quando o destaque vem da tabela (o mouse não está no gráfico), a dica do
 * dia é desenhada junto ao ponto; pelo gráfico, a dica é a do Recharts.
 */
function MarcaDoDia({ cx = 0, cy = 0, linha, comDica }: { cx?: number; cy?: number; linha: LinhaDoGrafico; comDica: boolean }) {
  return (
    <g>
      <circle cx={cx} cy={cy} r={6} fill="var(--color-text-title)" stroke="var(--color-projection)" strokeWidth={2} />
      {comDica && (
        <foreignObject x={cx - 262} y={cy + 14} width={250} height={140} style={{ overflow: "visible" }}>
          <TooltipDaProjecao linha={linha} />
        </foreignObject>
      )}
    </g>
  );
}

/** CU05: os rótulos dos dias previstos (depois do ponto de partida) ficam na cor da projeção, como no protótipo do RF04. */
function RotuloDoEixo({ x = 0, y = 0, payload, partida, formatar }: PropsDoRotulo & { partida: number; formatar: (ts: number) => string }) {
  // Os rótulos ficam à meia-noite local; o dia de D (00:00 UTC) ainda é histórico, os seguintes são previstos.
  const previsto = payload !== undefined && payload.value > partida + UM_DIA_MS / 2;
  return (
    <text x={x} y={y} dy={16} textAnchor="middle" fontSize={12}
      fill={previsto ? "var(--color-projection)" : "var(--color-text-secondary)"}>
      {payload ? formatar(payload.value) : ""}
    </text>
  );
}

export default function PriceChart({
  data,
  mensagemVazia = "Ainda não há dados históricos coletados suficientes para este item",
  projecao = null,
  diaDestacado = null,
  aoDestacarDia,
  dicaNoPonto = false,
}: PriceChartProps) {
  // Eixo X em tempo real: a dica acompanha o ponto mais próximo do mouse. `goldPrice` é só a escala do gráfico; a dica
  // converte de Cobre em Ouro/Prata/Cobre (RN01).
  const formattedData = useMemo(() => montarDadosDoGrafico(data, projecao), [data, projecao]);
  const historico = useMemo(() => formattedData.filter((linha) => linha.tipo !== "projecao"), [formattedData]);
  const partida = formattedData.find((linha) => linha.tipo === "partida");
  const diasPrevistos = formattedData.filter((linha) => linha.tipo === "projecao");

  // Eixo X em tempo real (e não um rótulo por data): vários pontos do mesmo dia deixam de compartilhar a mesma posição, e a
  // dica mostra o ponto mais próximo do mouse. Um rótulo por dia, à meia-noite local, com o passo ajustado ao período.
  const eixo = useMemo(() => {
    if (formattedData.length === 0) return { ticks: [] as number[], mensal: false, porHora: false, larguraDaBarra: 1 };
    const inicio = formattedData[0].ts;
    const fim = formattedData[formattedData.length - 1].ts;
    const ticks: number[] = [];
    if (fim - inicio < 2 * UM_DIA_MS) {
      // Série curta (por exemplo, a Ficha do WoW logo depois de começar a ser coletada): um rótulo a cada N horas.
      const horas = Math.max(1, Math.ceil((fim - inicio) / UM_HORA_MS));
      const passoEmHoras = horas <= 8 ? 1 : horas <= 16 ? 2 : horas <= 32 ? 4 : 6;
      const hora = new Date(inicio);
      hora.setMinutes(0, 0, 0);
      if (hora.getTime() < inicio) hora.setHours(hora.getHours() + 1);
      for (; hora.getTime() <= fim; hora.setHours(hora.getHours() + passoEmHoras)) ticks.push(hora.getTime());
      return { ticks: ticks.length > 0 ? ticks : [inicio], mensal: false, porHora: true, larguraDaBarra: 3 };
    }
    const dias = Math.max(1, Math.ceil((fim - inicio) / UM_DIA_MS));
    const passo = dias <= 9 ? 1 : dias <= 18 ? 2 : dias <= 36 ? 4 : dias <= 70 ? 7 : dias <= 140 ? 14 : dias <= 420 ? 30 : 90;
    const dia = new Date(inicio);
    dia.setHours(0, 0, 0, 0);
    if (dia.getTime() < inicio) dia.setDate(dia.getDate() + 1);
    for (; dia.getTime() <= fim; dia.setDate(dia.getDate() + passo)) ticks.push(dia.getTime());
    // Num eixo em tempo real o Recharts não deduz a largura das barras de volume: ela vem do intervalo típico entre pontos
    // do histórico (a mediana), proporcional ao período, entre 1 e 12 px.
    const intervalos = historico.slice(1).map((ponto, i) => ponto.ts - historico[i].ts).filter((ms) => ms > 0).sort((a, b) => a - b);
    const mediana = intervalos.length > 0 ? intervalos[Math.floor(intervalos.length / 2)] : UM_DIA_MS;
    const larguraDaBarra = Math.min(12, Math.max(1, Math.round((650 * mediana) / Math.max(1, fim - inicio))));
    return { ticks: ticks.length > 0 ? ticks : [inicio], mensal: passo >= 30, porHora: false, larguraDaBarra };
  }, [formattedData, historico]);

  const formatarTick = (ts: number) =>
    eixo.porHora
      ? new Date(ts).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
      : new Date(ts).toLocaleDateString('pt-BR', eixo.mensal ? { month: '2-digit', year: '2-digit' } : { day: '2-digit', month: '2-digit' });

  // A Ficha do WoW não tem volume e seu preço varia pouco perto de 280 mil de ouro: sem volume, a escala acompanha os
  // preços (e não parte do zero) e as barras não são desenhadas.
  const semVolume = historico.every((ponto) => ponto.quantity === null || ponto.quantity === undefined);

  // CU05-C2: o dia em destaque, vindo do gráfico ou da tabela, abre a dica daquele dia e marca o ponto.
  const indiceDestacado = diaDestacado ? formattedData.findIndex((linha) => linha.tipo === "projecao" && linha.dia === diaDestacado) : -1;
  const destacado: LinhaDoGrafico | undefined = indiceDestacado >= 0 ? formattedData[indiceDestacado] : undefined;

  if (!data || data.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-[var(--color-surface-translucent)] rounded-xl border border-[var(--color-border)]">
        <p className="text-[var(--color-text-secondary)]">{mensagemVazia}</p>
      </div>
    );
  }

  return (
    <div className="w-full h-full flex flex-col space-y-4">
      <div className="flex-1 min-h-[300px] w-full bg-[var(--color-surface-translucent)] rounded-xl border border-[var(--color-border)] p-4 backdrop-blur-sm">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-[var(--color-text-title)] text-sm font-semibold">Histórico de Preços (Ouro)</h3>
          {partida && (
            <ul aria-label="Legenda do gráfico" className="flex items-center gap-4 text-xs text-[var(--color-text-secondary)]">
              <li className="flex items-center gap-1.5">
                <span aria-hidden className="inline-block h-0.5 w-4 bg-[var(--color-cta)]" /> Histórico
              </li>
              <li className="flex items-center gap-1.5">
                <span aria-hidden className="inline-block w-4 border-t-2 border-dashed border-[var(--color-projection)]" /> Projeção (menor preço diário)
              </li>
            </ul>
          )}
        </div>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={formattedData}
            margin={{ top: 5, right: 0, left: 10, bottom: 20 }}
            onMouseMove={(estado) => {
              if (!aoDestacarDia) return;
              const indice = Number(estado.activeTooltipIndex);
              const linha = Number.isInteger(indice) ? formattedData[indice] : undefined;
              aoDestacarDia(linha?.tipo === "projecao" && linha.dia ? linha.dia : null);
            }}
            onMouseLeave={() => aoDestacarDia?.(null)}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
            <XAxis
              dataKey="ts"
              type="number"
              scale="time"
              domain={['dataMin', 'dataMax']}
              ticks={eixo.ticks}
              interval={0}
              tickFormatter={formatarTick}
              tick={partida ? (props: PropsDoRotulo) => <RotuloDoEixo {...props} partida={partida.ts} formatar={formatarTick} /> : undefined}
              stroke="var(--color-text-secondary)"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              minTickGap={30}
              tickMargin={10}
            />
            <YAxis
              yAxisId="left"
              stroke="var(--color-text-secondary)"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              domain={semVolume ? [(min: number) => Math.floor(min * 0.98), (max: number) => Math.ceil(max * 1.02)] : [0, 'auto']}
              tickFormatter={(value) => `${value.toLocaleString('pt-BR')}`}
              width={80}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              stroke="var(--color-text-secondary)"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              hide
            />
            <Tooltip content={<TooltipDoGrafico serieTemVolume={!semVolume} />} />

            {partida && diasPrevistos.length > 0 && (
              <ReferenceArea
                yAxisId="left"
                x1={partida.ts}
                x2={diasPrevistos[diasPrevistos.length - 1].ts}
                fill="var(--color-projection)"
                fillOpacity={0.06}
                stroke="none"
                label={{
                  value: diasPrevistos.length === 1 ? "Próximo dia" : `Próximos ${diasPrevistos.length} dias`,
                  position: "insideTopLeft", fill: "var(--color-projection)", fontSize: 11,
                }}
              />
            )}
            {!semVolume && (
              <Bar
                yAxisId="right"
                dataKey="quantity"
                fill="var(--color-border)"
                radius={[2, 2, 0, 0]}
                barSize={eixo.larguraDaBarra}
              />
            )}
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="goldPrice"
              stroke="var(--color-cta)"
              strokeWidth={2}
              connectNulls
              dot={historico.length <= 60 ? { r: 3, fill: "var(--color-cta)", strokeWidth: 0 } : false}
              activeDot={{ r: 6, fill: "var(--color-cta)", stroke: "var(--color-surface-solid)", strokeWidth: 2 }}
            />
            {partida && (
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="projecaoGold"
                name="Projeção (menor preço diário)"
                stroke="var(--color-projection)"
                strokeWidth={2}
                strokeDasharray="6 4"
                // Sem animação: com "prefers-reduced-motion", a animação do Recharts zera o tracejado ("0px, 0px").
                isAnimationActive={false}
                connectNulls
                dot={{ r: 3, fill: "var(--color-projection)", strokeWidth: 0 }}
                activeDot={{ r: 6, fill: "var(--color-projection)", stroke: "var(--color-surface-solid)", strokeWidth: 2 }}
              />
            )}
            {destacado?.projecaoGold !== undefined && (
              <ReferenceDot
                yAxisId="left"
                x={destacado.ts}
                y={destacado.projecaoGold}
                r={6}
                shape={(props: { cx?: number; cy?: number }) => (
                  <MarcaDoDia cx={props.cx} cy={props.cy} linha={destacado} comDica={dicaNoPonto} />
                )}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
