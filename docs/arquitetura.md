# Arquitetura

O tempestroid separa **o que renderizar** (uma IR tipada e serializável) de
**como renderizar** (renderizadores-folha por plataforma), ligados por um
**reconciliador puro**.

## Invariantes

- **O reconciliador é agnóstico de renderizador** — dado puro entra, *patches*
  saem. Toda divergência de plataforma fica confinada aos dois tradutores de
  `Style`.
- **A árvore de widgets é a IR** — modelos Pydantic serializáveis. Percorra
  qualquer árvore via `Widget.child_nodes()`; nunca alcance o armazenamento de
  filhos específico de um renderizador.
- **O Python roda em uma thread de fundo** hospedando um loop asyncio, nunca na
  thread de UI. O *marshalling* atravessa uma única fronteira de ponte.

## O pipeline

```text
   view(app) ──build──▶  Árvore de Node (IR)
                              │
                            diff
                              ▼
                          [ Patch ]
                         ╱          ╲
                  Renderizador Qt   Renderizador Compose
```

### 1. Widgets (a IR)

`view(app)` devolve uma árvore de `Widget` — modelos Pydantic frozen onde
representam valores imutáveis. Cada widget é um nó declarativo: `Text`, `Button`,
`Column`, `Row`, `Container`, os inputs com valor (`Input`, `Checkbox`,
`DatePicker`, `FilePicker`, …) e dezenas de outros (listas virtualizadas,
navegação, overlays, animação, gestos, mídia) — todos suportados pelos **dois
renderizadores**. A lista completa está no [guia de exemplos](guia/exemplos.md#conjunto-de-widgets-atual).

### 2. build → Node

`build(widget) -> Node` rebaixa a árvore de widgets para a IR de `Node`: uma
estrutura uniforme com `type`, `key`, `props` e `children`. É essa forma que o
reconciliador e os serializadores entendem.

### 3. diff → Patch

`diff(old, new) -> list[Patch]` compara duas árvores de `Node` e emite a lista
mínima de *patches*:

| Patch | Significado |
|---|---|
| `Insert` | Inserir um novo nó em uma posição. |
| `Remove` | Remover um nó. |
| `Update` | Atualizar `props` de um nó (campos a setar / remover). |
| `Reorder` | Reordenar filhos (apenas para permutação pura de chaves). |
| `Replace` | Trocar um nó por outro de tipo diferente. |

!!! note "Diffing de filhos é posicional por padrão"
    Um único `Reorder` só é emitido para uma *permutação pura* (ambas as listas
    totalmente chaveadas, chaves únicas, mesmo conjunto, mesmo tamanho). Mistura
    de insert + reorder cai para posicional — correto, porém menos ótimo.

### 4. Renderizadores aplicam patches

Cada renderizador-folha aplica os mesmos *patches* aos seus widgets vivos:

- **Qt** (`renderers/qt`) — mapeia `Node`s para `QWidget`s e `Style` para
  `QBoxLayout` + QSS. É o simulador de desktop.
- **Compose** (`renderers/compose` + host Kotlin) — mapeia a árvore serializada
  para `@Composable`s e `Style` para `Modifier`/`Arrangement`/`Alignment`. É o
  renderizador do dispositivo.

## Fidelidade do simulador (o que ele reflete — e o que não)

O simulador Qt é um **proxy semântico fiel**, não um espelho pixel-a-pixel do
aparelho. Vale saber a fronteira para confiar nele no lugar certo.

**O que é idêntico** (a espinha dorsal): a mesma árvore IR, o mesmo reconciliador,
o mesmo fluxo `view → diff → patch`, os mesmos eventos tipados e o mesmo estado
coalescido. Layout, navegação, lógica, estado e eventos comportam-se igual. A
maioria dos campos de `Style` é honrada nos dois (alinhamento, espaçamento
`SPACE_*`, `STRETCH`, `text_align`, tamanho fixo, padding/margin, cor, fonte). Os
tamanhos do simulador são em **dp**, o mesmo espaço de layout que o Compose usa —
por isso o que cabe na janela cabe no aparelho (veja
[escolher o tamanho de tela](inicio-rapido.md#escolha-o-tamanho-de-tela-presets-de-aparelho)).

!!! check "Garantia de paridade"
    A suíte de **conformância** (`tests/conformance/`) fixa os **dois tradutores
    `Style` lado a lado** (golden snapshots de `to_qss` e `to_compose`) + uma
    tabela de cobertura por-campo. Eles **não podem divergir em silêncio** — uma
    mudança que regride a paridade quebra o *gate*.

**O que só o aparelho mostra fielmente** (divergências esperadas):

- **Aparência dos widgets** — o Qt usa QWidget/QSS; o device usa **Material 3**.
  Diálogos, menus, bottom sheets, pickers e campos têm o visual nativo de cada um.
- **Animações** — Qt usa `QPropertyAnimation`; o device dirige o motor nativo do
  Compose (`animate*AsState`/`AnimatedContent`).
- **Overlays e safe-area** — o Compose gerencia `WindowInsets.safeDrawing`/scrim
  próprios; o Qt aproxima com um scrim manual.
- **Fontes e densidade do SO** mudam métricas finas de layout.
- **Widgets de hardware** — `CameraPreview`/`QrScanner`/`MapView` são
  **device-only**; no simulador aparecem como *placeholder* sinalizado.

!!! warning "Regra: verificação dual"
    Por isso, ao mexer em superfície de UI, valide **nos dois**: o simulador Qt
    **e** o aparelho físico (Compose) quando houver um conectado — `make
    dual-verify`. O simulador acelera o desenvolvimento; o aparelho confirma a
    aparência final, animações e overlays.

## Estado: `App[S]`

`App[S]` é o container de estado agnóstico de renderizador. Ele:

- guarda o estado (`app.state`);
- constrói a UI via a função `view(app)`;
- faz o *diff* e entrega os *patches* a um callback `apply_patches`.

Rebuilds são **coalescidos**: `request_rebuild` agenda um único `_rebuild` via
`loop.call_soon`, então vários `set_state` no mesmo *tick* geram um único *diff*.
Rebuilds sem mudança não emitem *patches*.

## A fronteira tipada (Python↔Kotlin)

Sem um WebView, não há fronteira JS↔Python; o contrato tipado vive na fronteira
Python↔Kotlin. Eventos que voltam do lado nativo (um toque, uma mudança de texto)
chegam como *payloads* crus e são **validados antes** de entrar em um *handler* —
exatamente como o FastAPI valida um corpo de requisição.

- `parse_event(event_type, raw)` é o portão de validação: transforma um *payload*
  cru em um evento tipado ou levanta `EventValidationError` com os erros
  estruturados por campo.
- A serialização (`serialize_node` / `serialize_patch`) rebaixa a IR/patches para
  dicts JSON-able: *handlers* viram *tokens* de caminho, `Style` vira a *spec*
  Compose.

Veja [Lado do dispositivo (ponte)](referencia/dispositivo.md) para o protocolo de
fio e o transporte JNI.

## Recapitulando

- O tempestroid separa **o que** renderizar (IR de widgets) de **como**
  (renderizadores-folha), ligados por um reconciliador puro.
- O pipeline: `view → build → diff → patches → renderizador`.
- `App[S]` guarda o estado e coalesce rebuilds (um *diff* por *tick*).
- A fronteira Python↔Kotlin é tipada e validada (`parse_event`,
  `serialize_node`).

## Próximos passos

➡️ Conheça as primitivas em **[Widgets](guia/widgets.md)**, ou aprofunde a ponte
em **[Lado do dispositivo](referencia/dispositivo.md)**.
