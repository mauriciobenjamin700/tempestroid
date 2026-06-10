# Tempestroid

Construa **apps Android nativos** em **Python tipado**.

Você escreve uma única árvore de widgets declarativa e totalmente tipada (uma IR
Pydantic). Um **reconciliador agnóstico de renderizador** faz o *diff* dessa
árvore em *patches*. Dois renderizadores-folha aplicam esses *patches*: **Qt**
para o simulador de desktop e **Jetpack Compose** para o dispositivo. O runtime é
**async-first**, com um *dev loop* estilo Expo (hot reload no simulador e
*code-push* por LAN no dispositivo).

!!! note "É um framework, não um serviço web"
    Aqui não há FastAPI, SQLAlchemy, Redis nem camadas HTTP. O foco é a árvore de
    UI tipada e o reconciliador. Veja o [plano de design](plan.md) para o desenho
    completo e o [roadmap por fases](roadmap.md).

!!! tip "🤖 Ler o projeto com sua IA (`llms.txt`)"
    Este site publica dois arquivos seguindo a convenção
    [llmstxt.org](https://llmstxt.org/) para você dar ao seu assistente de IA
    (Claude, ChatGPT, Cursor, etc.) o projeto inteiro como referência — **sem
    servidor, sem MCP**:

    - **[`/llms.txt`](https://mauriciobenjamin700.github.io/tempestroid/llms.txt)**
      — índice enxuto (resumo + links de todas as páginas). Use quando a IA puder
      navegar pelos links.
    - **[`/llms-full.txt`](https://mauriciobenjamin700.github.io/tempestroid/llms-full.txt)**
      — documentação **inteira** concatenada num só arquivo Markdown. Use para
      colar/anexar de uma vez quando a IA não navega.

    **Como usar:** cole a URL (ou o conteúdo) de `llms-full.txt` no contexto do
    seu assistente e peça para usar como referência do tempestroid. Os arquivos
    são regenerados a cada publicação das docs, então estão sempre em dia.

## Por quê

- **Tipado de ponta a ponta.** Modelo de estilo, primitivas de widget, eventos e
  o contrato de fronteira Python↔Kotlin são todos Pydantic v2 / totalmente
  tipados. O `pyright` roda em modo estrito.
- **Uma árvore, dois alvos.** O reconciliador é dado-puro-entra →
  *patches*-saem. Toda divergência de plataforma fica confinada aos dois
  tradutores de `Style` (Qt e Compose).
- **Async-first.** *Handlers* de evento e *hooks* de ciclo de vida podem ser
  síncronos ou `async`; o Python roda em um loop asyncio de fundo, nunca na
  thread de UI.
- **Loop interno rápido.** `tempest dev` observa o seu arquivo e faz hot reload
  do simulador Qt ao salvar — sem precisar de dispositivo ou emulador para
  trabalhar a UI.

## Como funciona

```text
   view(app) ──build──▶  Árvore de Node (IR)
                              │
                            diff           puro, agnóstico de renderizador
                              ▼
                          [ Patch ]        Insert / Remove / Update / Reorder / Replace
                         ╱          ╲
                  Renderizador Qt   Renderizador Compose
                   (simulador)        (dispositivo)
```

1. `view(app) -> Widget` constrói a árvore de widgets a partir do estado atual.
2. `build` rebaixa a árvore para uma IR de `Node`; `diff` compara a versão antiga
   com a nova e emite uma lista mínima de `Patch`.
3. Um renderizador aplica os *patches* nos widgets vivos. Mudanças de estado são
   coalescidas em um único rebuild por *tick*.

## Próximos passos

- [Instalação](instalacao.md) — instale o framework e o simulador.
- [Começo rápido](inicio-rapido.md) — seu primeiro app em poucas linhas.
- [Arquitetura](arquitetura.md) — IR, reconciliador, renderizadores e a ponte.
- [Guia do usuário](guia/widgets.md) — widgets, estilos, eventos e a CLI.

