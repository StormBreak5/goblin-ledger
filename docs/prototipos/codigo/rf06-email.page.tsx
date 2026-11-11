import { formatarMoeda } from "@/lib/moeda";

/** CU08-C2 (protótipo): e-mail enviado quando um alerta de preço é disparado. */
export default function EmailPage() {
  const linhas: [string, string][] = [
    ["Item", "Mycobloom"],
    ["Tipo do alerta", "Compra (preço cair até o alvo)"],
    ["Preço-alvo", formatarMoeda(175000)],
    ["Valor de mercado", formatarMoeda(174200)],
    ["Data e hora", "21/10/2026 às 02:12"],
  ];
  return (
    <div style={{ background: "#ECEAF2", minHeight: "100vh", padding: "48px 0", fontFamily: "Inter, Arial, sans-serif" }}>
      <div style={{ maxWidth: 600, margin: "0 auto", background: "#FFFFFF", borderRadius: 10, overflow: "hidden", boxShadow: "0 4px 18px rgba(0,0,0,.08)" }}>
        <div style={{ background: "#161124", padding: "20px 28px", display: "flex", alignItems: "center", gap: 12 }}>
          <img src="/logo.png" alt="" width={36} height={36} />
          <span style={{ color: "#FFFFFF", fontWeight: 700, letterSpacing: 2 }}>GOBLIN LEDGER</span>
        </div>
        <div style={{ padding: "28px 28px 8px", color: "#2A2438" }}>
          <p style={{ fontSize: 13, color: "#8A84A3", margin: 0 }}>Assunto: Alerta de preço atingido – Mycobloom</p>
          <h1 style={{ fontSize: 22, margin: "14px 0 10px", color: "#161124" }}>Seu alerta de preço foi atingido</h1>
          <p style={{ fontSize: 15, lineHeight: 1.6, margin: 0 }}>
            Olá! O valor de mercado do item <b>Mycobloom</b> atingiu o preço do seu alerta de compra.
          </p>
          <table style={{ width: "100%", borderCollapse: "collapse", margin: "20px 0", fontSize: 14 }}>
            <tbody>
              {linhas.map(([k, v]) => (
                <tr key={k} style={{ borderBottom: "1px solid #ECEAF2" }}>
                  <td style={{ padding: "10px 0", color: "#8A84A3", width: "40%" }}>{k}</td>
                  <td style={{ padding: "10px 0", fontWeight: 600, color: k.startsWith("Valor") || k.startsWith("Preço") ? "#B7791F" : "#161124" }}>{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <a style={{ display: "inline-block", background: "#FBBF24", color: "#161124", fontWeight: 700, padding: "12px 22px", borderRadius: 8, textDecoration: "none", fontSize: 14 }}>
            Ver o item no Goblin Ledger
          </a>
          <p style={{ fontSize: 13, lineHeight: 1.6, color: "#5B5570", margin: "22px 0 0" }}>
            O alerta foi desativado após o disparo. Para voltar a acompanhar o preço, reative-o na seção &quot;Alertas de preço&quot; da tela do item.
          </p>
        </div>
        <div style={{ padding: "18px 28px 24px", fontSize: 12, color: "#8A84A3" }}>
          Você recebeu este e-mail porque configurou um alerta de preço no Goblin Ledger com notificação por e-mail.
        </div>
      </div>
    </div>
  );
}
