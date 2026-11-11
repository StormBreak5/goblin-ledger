// Dados ilustrativos dos protótipos do CU06 ao CU08.
export const icone = (nome: string) => `https://icones.local/${nome}.png`;

export interface Notificacao {
  item: string;
  icone: string;
  tipo: "Compra" | "Venda";
  alvo: number;
  valor: number;
  quando: string;
  lida: boolean;
}

export const NOTIFICACOES: Notificacao[] = [
  { item: "Mycobloom", icone: "mycobloom", tipo: "Compra", alvo: 175000, valor: 174200, quando: "21/10/2026 às 02:12", lida: false },
  { item: "Bismuth", icone: "bismuth", tipo: "Venda", alvo: 130000, valor: 132000, quando: "20/10/2026 às 18:12", lida: false },
  { item: "Algari Healing Potion", icone: "pocao_cura", tipo: "Compra", alvo: 1200000, valor: 1198000, quando: "18/10/2026 às 09:12", lida: true },
];

export interface Favorito {
  id: number;
  nome: string;
  icone: string;
  valor: number;
  variacao: number;
  alertas: number;
  desatualizado?: boolean;
}

export const FAVORITOS: Favorito[] = [
  { id: 212239, nome: "Algari Healing Potion", icone: "pocao_cura", valor: 1245000, variacao: 1.8, alertas: 1 },
  { id: 210930, nome: "Bismuth", icone: "bismuth", valor: 132000, variacao: -2.4, alertas: 0 },
  { id: 210799, nome: "Luredrop", icone: "luredrop", valor: 310500, variacao: 0.6, alertas: 0 },
  { id: 210796, nome: "Mycobloom", icone: "mycobloom", valor: 179500, variacao: 3.1, alertas: 1 },
  { id: 210802, nome: "Orbinid", icone: "orbinid", valor: 98000, variacao: -0.9, alertas: 0, desatualizado: true },
];

export interface Alerta {
  tipo: "Compra" | "Venda";
  alvo: number;
  canal: string;
  situacao: "Ativo" | "Disparado";
  disparadoEm?: string;
}

export const ALERTAS: Alerta[] = [
  { tipo: "Compra", alvo: 175000, canal: "Tela e e-mail", situacao: "Disparado", disparadoEm: "21/10/2026 às 02:12" },
  { tipo: "Venda", alvo: 210000, canal: "Tela", situacao: "Ativo" },
];
