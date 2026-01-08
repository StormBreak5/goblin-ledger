# 👺 Goblin Ledger - Frontend

Frontend do sistema de monitoramento de leilões do World of Warcraft, construído com Next.js 16 e shadcn/ui.

## 🚀 Tecnologias

- **[Next.js 16](https://nextjs.org)** - Framework React com App Router
- **[React 19](https://react.dev)** - Biblioteca UI
- **[TypeScript](https://www.typescriptlang.org)** - Tipagem estática
- **[Tailwind CSS v4](https://tailwindcss.com)** - Framework CSS utilitário
- **[shadcn/ui](https://ui.shadcn.com)** - Componentes UI reutilizáveis
- **[Lucide React](https://lucide.dev)** - Ícones

## 📦 Componentes shadcn/ui Instalados

O projeto utiliza os seguintes componentes do shadcn/ui:

- ✅ **Button** - Botões com múltiplas variantes
- ✅ **Card** - Cards com header, content e footer
- ✅ **Input** - Campos de entrada
- ✅ **Label** - Rótulos para formulários
- ✅ **Badge** - Tags e badges
- ✅ **Table** - Tabelas responsivas
- ✅ **Dialog** - Modais e diálogos
- ✅ **Alert** - Alertas e notificações
- ✅ **Dropdown Menu** - Menus dropdown
- ✅ **Select** - Seletor dropdown

Para adicionar mais componentes:
```bash
npx shadcn@latest add [component-name]
```

Consulte o arquivo [SHADCN_GUIDE.md](./SHADCN_GUIDE.md) para exemplos de uso detalhados.

## 🎨 Design System

O projeto utiliza um design system baseado em variáveis CSS, configurado em `app/globals.css`:

- **Tema**: Dark mode por padrão
- **Cores**: Paleta customizada com emerald e amber como cores principais
- **Tipografia**: Geist Sans e Geist Mono
- **Componentes**: Todos os componentes seguem o padrão shadcn/ui

## 🛠️ Desenvolvimento

### Pré-requisitos

- Node.js 18+ 
- npm, yarn, pnpm ou bun

### Instalação

```bash
# Instalar dependências
npm install
```

### Executar em desenvolvimento

```bash
npm run dev
```

Abra [http://localhost:3000](http://localhost:3000) no navegador.

### Build para produção

```bash
npm run build
npm start
```

### Lint

```bash
npm run lint
```

## 📁 Estrutura do Projeto

```
frontend/
├── app/                    # App Router do Next.js
│   ├── globals.css        # Estilos globais e variáveis CSS
│   ├── layout.tsx         # Layout raiz
│   └── page.tsx           # Página principal
├── components/            # Componentes React
│   └── ui/               # Componentes shadcn/ui
├── lib/                  # Utilitários
│   └── utils.ts         # Função cn() para classes CSS
├── types/               # Definições TypeScript
├── public/              # Arquivos estáticos
├── components.json      # Configuração shadcn/ui
├── tailwind.config.ts   # Configuração Tailwind
└── tsconfig.json        # Configuração TypeScript
```

## 🎯 Funcionalidades

- ✅ Visualização de leilões ativos
- ✅ Filtros e busca (em desenvolvimento)
- ✅ Tema escuro
- ✅ Design responsivo
- ✅ Componentes reutilizáveis

## 🔗 Integração com Backend

O frontend se comunica com a API FastAPI em `http://localhost:8000`:

- `GET /api/auctions` - Lista de leilões
- `GET /api/stats` - Estatísticas do mercado

## 📚 Recursos

- [Documentação Next.js](https://nextjs.org/docs)
- [Documentação shadcn/ui](https://ui.shadcn.com)
- [Documentação Tailwind CSS](https://tailwindcss.com/docs)
- [Guia de Uso shadcn/ui](./SHADCN_GUIDE.md)

## 🤝 Contribuindo

1. Siga o padrão de código existente
2. Use componentes shadcn/ui sempre que possível
3. Mantenha a consistência do design system
4. Teste em diferentes tamanhos de tela

## 📝 Notas

- O projeto usa Tailwind CSS v4 (versão mais recente)
- Todos os componentes são server components por padrão, use `'use client'` quando necessário
- As variáveis CSS permitem fácil customização do tema

