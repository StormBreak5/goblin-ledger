"use client";

import { useMemo } from "react";
import TooltipDoPonto from "@/components/TooltipDoPonto";
import type { PontoDoHistorico } from "@/lib/historicoDoItem";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ComposedChart,
  Legend
} from "recharts";

const UM_DIA_MS = 86_400_000;
const UM_HORA_MS = 3_600_000;

interface PriceChartProps {
  data: PontoDoHistorico[];
  /** CU04-C1-FA2: texto exibido no lugar do gráfico quando não há pontos (vem do backend). */
  mensagemVazia?: string;
}

export default function PriceChart({ data, mensagemVazia = "Ainda não há dados históricos coletados suficientes para este item" }: PriceChartProps) {
  const formattedData = useMemo(() => {
    return data.map((d) => ({
      ...d,
      ts: new Date(d.timestamp).getTime(), // eixo X em tempo real: a dica acompanha o ponto mais próximo do mouse
      goldPrice: d.price / 10000, // só a escala do gráfico; a dica converte de Cobre em Ouro/Prata/Cobre (RN01)
    }));
  }, [data]);

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
    // (a mediana), proporcional ao período, entre 1 e 12 px.
    const intervalos = formattedData.slice(1).map((ponto, i) => ponto.ts - formattedData[i].ts).filter((ms) => ms > 0).sort((a, b) => a - b);
    const mediana = intervalos.length > 0 ? intervalos[Math.floor(intervalos.length / 2)] : UM_DIA_MS;
    const larguraDaBarra = Math.min(12, Math.max(1, Math.round((650 * mediana) / Math.max(1, fim - inicio))));
    return { ticks: ticks.length > 0 ? ticks : [inicio], mensal: passo >= 30, porHora: false, larguraDaBarra };
  }, [formattedData]);

  const formatarTick = (ts: number) =>
    eixo.porHora
      ? new Date(ts).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
      : new Date(ts).toLocaleDateString('pt-BR', eixo.mensal ? { month: '2-digit', year: '2-digit' } : { day: '2-digit', month: '2-digit' });

  // A Ficha do WoW não tem volume e seu preço varia pouco perto de 280 mil de ouro: sem volume, a escala acompanha os
  // preços (e não parte do zero) e as barras não são desenhadas.
  const semVolume = formattedData.every((ponto) => ponto.quantity === null || ponto.quantity === undefined);

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
        <h3 className="text-[var(--color-text-title)] mb-4 text-sm font-semibold">Histórico de Preços (Ouro)</h3>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={formattedData} margin={{ top: 5, right: 0, left: 10, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
            <XAxis 
              dataKey="ts"
              type="number"
              scale="time"
              domain={['dataMin', 'dataMax']}
              ticks={eixo.ticks}
              interval={0}
              tickFormatter={formatarTick}
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
            <Tooltip content={<TooltipDoPonto serieTemVolume={!semVolume} />} />
            
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
              dot={formattedData.length <= 60 ? { r: 3, fill: "var(--color-cta)", strokeWidth: 0 } : false}
              activeDot={{ r: 6, fill: "var(--color-cta)", stroke: "var(--color-surface-solid)", strokeWidth: 2 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
