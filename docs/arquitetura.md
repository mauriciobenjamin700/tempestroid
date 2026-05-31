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
`Column`, `Row`, `Container` e os inputs com valor (`Input`, `Checkbox`,
`DatePicker`, `FilePicker`).

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
