"use client";

import { useMemo } from "react";
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

interface HistoricalDataPoint {
  timestamp: string;
  price: number;
  quantity: number;
}

interface PriceChartProps {
  data: HistoricalDataPoint[];
}

export default function PriceChart({ data }: PriceChartProps) {
  const formattedData = useMemo(() => {
    return data.map((d) => {
      const date = new Date(d.timestamp);
      return {
        ...d,
        goldPrice: d.price / 10000,
        displayDate: date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }),
        displayDateFull: date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' }),
        displayTime: date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
      };
    });
  }, [data]);

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const dataPoint = payload[0].payload;
      return (
        <div className="bg-[var(--color-surface-solid)] border border-[var(--color-border)] p-3 rounded shadow-xl">
          <p className="text-[var(--color-text-title)] mb-2 font-medium">
            {dataPoint.displayDateFull} {dataPoint.displayTime}
          </p>
          <p className="text-[var(--color-cta)] text-sm">
            <span className="text-[var(--color-text-secondary)]">Preço:</span> {dataPoint.goldPrice.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Ouro
          </p>
          <p className="text-[var(--color-text-main)] text-sm mt-1">
            <span className="text-[var(--color-text-secondary)]">Volume:</span> {dataPoint.quantity ? dataPoint.quantity.toLocaleString('pt-BR') : 'N/D'}
          </p>
        </div>
      );
    }
    return null;
  };

  if (!data || data.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-[var(--color-surface-translucent)] rounded-xl border border-[var(--color-border)]">
        <p className="text-[var(--color-text-secondary)]">Ainda não há dados históricos coletados suficientes para este item.</p>
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
              dataKey="displayDate" 
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
            <Tooltip content={<CustomTooltip />} />
            
            <Bar 
              yAxisId="right" 
              dataKey="quantity" 
              fill="var(--color-border)" 
              radius={[2, 2, 0, 0]} 
              maxBarSize={40}
            />
            <Line 
              yAxisId="left"
              type="monotone" 
              dataKey="goldPrice" 
              stroke="var(--color-cta)" 
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 6, fill: "var(--color-cta)", stroke: "var(--color-surface-solid)", strokeWidth: 2 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
