# Estratégia de Integração do Layout (Apple Premium UI)

A refatoração do layout foi desenhada para garantir **zero side-effects** na lógica de negócios e estado da aplicação.

## Como funciona a injeção do Layout?

1. **Camada de Contextos Intocada**:
   O `RootLayout` (`src/app/layout.tsx`) continua envolvendo toda a aplicação com os contextos `AuthProvider` e `FinanceiroProvider`. Isso garante que o estado global (como tokens JWT e a loja selecionada) não seja resetado ou perdido ao navegar.
2. **Substituição apenas da Camada Visual (`MainLayout.tsx`)**:
   A lógica de roteamento protegida (redirecionamento de não autenticados via `useEffect`) foi mantida exatamente como era no `MainLayout`. Apenas a renderização do HTML mudou. A estrutura flex com menus laterais foi substituída por um envelopamento puramente `relative` com elementos fixos usando alto z-index.
3. **Isolamento de Props (`{ children }`)**:
   As rotas filhas (ex: `/tesouraria`, `/despesas`) são renderizadas em um contêiner livre (`<main className="relative z-10 w-full ...">{children}</main>`). Isso significa que nenhum componente filho precisou ser alterado para adotar a nova interface.
4. **Z-Index Layering**:
   - `z-10`: Conteúdo principal rolável (`children`).
   - `z-40`: Cabeçalho superior flutuante (Seletor de Loja).
   - `z-50`: Dock de navegação inferior (`FloatingNav`).
