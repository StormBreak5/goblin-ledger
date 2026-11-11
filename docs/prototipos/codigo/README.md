# Código dos protótipos (referência visual)

Estes são os arquivos usados para gerar as imagens dos protótipos de interface do TC (seção 5, figuras em `docs/prototipos/`). As telas foram montadas sobre o front-end real, com **dados ilustrativos fixos** (`dados-ilustrativos.ts`), só para a captura.

**Use como referência visual, não como código de produção.** A implementação real consome a API, tem os fluxos alternativos e de exceção do caso de uso e segue o `CLAUDE.md`. Os imports apontam para o caminho que os arquivos tinham no front (`@/components/proto/...`). Eles não fazem parte do build.

| Arquivo | Figura do TC | Caso de uso |
| --- | --- | --- |
| `rf04-projecao.html` | Figura 14 – Protótipo do Requisito de Projeção Preditiva (`rf04-projecao.png`) | CU05 |
| `rf05-alertas-e-criar-alerta.page.tsx` | Figura 15 – Tela de Alertas de Preço do Item (`rf05-alertas.png`) e Figura 16 – Tela de Criação de Alerta de Preço (`rf05-criar-alerta.png`, com `?modal=novo`) | CU06-C1 (controle "Favoritado") e CU07 |
| `rf06-SinoDeNotificacoes.tsx` | Figura 17 – Tela de Notificações (`rf06-notificacoes.png`) | CU08-C3 |
| `rf06-email.page.tsx` | Figura 18 – Tela do E-mail de Notificação de Alerta (`rf06-email.png`) | CU08-C2 |
| `rf09-favoritos.page.tsx` | Figura 21 – Tela de Favoritos (`rf09-favoritos.png`) | CU06-C3 |
| `AuthNav.com-favoritos-e-sino.tsx` | cabeçalho das Figuras 15 a 17 e 21 | link "Favoritos" (CU06-C3) e sino (CU08-C3) |
| `dados-ilustrativos.ts` | — | dados fixos usados nas capturas |
