# Navegação entre telas

Um app real tem mais de uma tela: lista de produtos, detalhe, carrinho, perfil.
No tempestroid a navegação é modelada como uma **pilha de rotas** de dados simples
e serializáveis — sem nenhum widget mágico dedicado. A função `view(app)` lê
`app.nav.top` para decidir qual árvore de widgets construir; trocar de rota é
apenas o `view` produzindo uma árvore diferente, e o reconciliador existente faz o
diff normalmente, sem nenhum tipo de patch novo. O botão Voltar do Android (e o
`Esc` no simulador Qt) chama `app.pop` automaticamente — você não precisa conectar
nada.

---

## O modelo: pilha de rotas

Toda pilha de rotas é composta por dois tipos de `tempestroid.navigation`:

```python
from tempestroid import Route
from tempestroid.navigation import NavStack
```

### `Route`

Um destino imutável com um **nome** (um identificador tipo caminho de URL) e um
dicionário de **parâmetros** opcionais:

```python
from tempestroid import Route

home = Route(name="/")
details = Route(name="/details", params={"id": 42})
```

`Route` é um modelo Pydantic frozen — ele é comparado por valor, assim como
`Style`. Isso permite que o reconciliador detecte mudanças de rota como qualquer
outra mudança de prop.

### `NavStack`

A pilha de rotas do app. O fundo é a raiz; o topo é a tela visível.

```python
from tempestroid.navigation import NavStack, Route

stack = NavStack()
print(stack.top.name)   # "/"
print(stack.can_pop)    # False — estamos na raiz
```

| Propriedade | Tipo | Descrição |
|---|---|---|
| `top` | `Route` | A rota no topo da pilha (a tela visível). |
| `can_pop` | `bool` | `True` quando há mais de uma rota na pilha. |

O `App` já cria uma pilha com a rota raiz `"/"` por padrão — você nunca constrói
um `NavStack` manualmente a menos que queira configurar um estado inicial
customizado (como para deep links).

---

## Empilhar e voltar: `push` / `pop`

A forma mais comum de navegar é empilhar uma nova rota com `app.push` e voltar com
`app.pop`. O `view` lê `app.nav.top.name` para escolher qual tela renderizar:

```python
from dataclasses import dataclass

from tempestroid import App, Button, Column, Route, Text, Widget


@dataclass
class State:
    """Estado do app de exemplo."""


def make_state() -> State:
    """Retorna o estado inicial."""
    return State()


def home_screen(app: App[State]) -> Widget:
    """Tela inicial."""
    return Column(
        children=[
            Text(content="Tela inicial", key="title"),
            Button(
                label="Ver detalhes do produto 42",
                on_click=lambda: app.push(Route(name="/details", params={"id": 42})),
                key="btn",
            ),
        ],
    )


def details_screen(app: App[State]) -> Widget:
    """Tela de detalhes."""
    item_id = app.nav.top.params.get("id")
    return Column(
        children=[
            Text(content=f"Produto {item_id}", key="title"),
            Button(label="Voltar", on_click=app.pop, key="back"),
        ],
    )


def view(app: App[State]) -> Widget:
    """Escolhe a tela baseada na rota no topo da pilha."""
    if app.nav.top.name == "/details":
        return details_screen(app)
    return home_screen(app)
```

!!! tip "Parâmetros de rota"
    Passe qualquer dado serializable em `params`. Na tela de destino, leia com
    `app.nav.top.params.get("chave")`. Os parâmetros fazem parte do objeto `Route`
    imutável — o mesmo modelo que viaja pelo bridge para o dispositivo.

!!! note "Assinaturas exatas"
    ```text
    app.push(route: Route) -> None
    app.pop() -> bool          # True se houve pop, False se já estava na raiz
    ```
    `pop` retorna `False` na raiz em vez de lançar exceção — a pilha nunca fica
    vazia.

### Três telas encadeadas

O mesmo padrão escala para quantas telas quiser. Cada `push` adiciona uma rota à
pilha; cada `pop` retira a última:

```python
from dataclasses import dataclass

from tempestroid import App, Button, Column, Route, Text, Widget


@dataclass
class State:
    """Estado do app de três telas."""


def make_state() -> State:
    """Retorna o estado inicial."""
    return State()


def screen_a(app: App[State]) -> Widget:
    """Tela A."""
    return Column(
        children=[
            Text(content="Tela A", key="t"),
            Button(
                label="Ir para B",
                on_click=lambda: app.push(Route(name="/b")),
                key="btn",
            ),
        ],
    )


def screen_b(app: App[State]) -> Widget:
    """Tela B."""
    return Column(
        children=[
            Text(content="Tela B", key="t"),
            Button(
                label="Ir para C",
                on_click=lambda: app.push(Route(name="/c")),
                key="next",
            ),
            Button(label="Voltar para A", on_click=app.pop, key="back"),
        ],
    )


def screen_c(app: App[State]) -> Widget:
    """Tela C."""
    return Column(
        children=[
            Text(content="Tela C (fim da pilha)", key="t"),
            Button(label="Voltar para B", on_click=app.pop, key="back"),
        ],
    )


_SCREENS = {"/": screen_a, "/b": screen_b, "/c": screen_c}


def view(app: App[State]) -> Widget:
    """Roteia pelo nome da rota no topo."""
    screen_fn = _SCREENS.get(app.nav.top.name, screen_a)
    return screen_fn(app)
```

---

## Substituir e resetar: `replace` / `reset`

Além de empilhar e desempilhar, há dois métodos para cenários específicos.

### `replace` — trocar sem mudar a profundidade

Use quando quiser substituir a tela atual por outra sem adicionar uma entrada na
pilha (o usuário não pode "voltar" para a tela anterior):

```python
from tempestroid import Route

# Troca a tela atual por "/login" sem empilhar:
app.replace(Route(name="/login"))
```

Cenários típicos: fluxo de onboarding passo a passo (cada passo substitui o
anterior), redirecionamento após logout, confirmação que substitui um formulário.

```text
# Assinatura:
app.replace(route: Route) -> None
```

### `reset` — redefinir toda a pilha

Use quando precisar descartar toda a história de navegação e definir uma nova
pilha do zero — por exemplo, após login bem-sucedido:

```python
from tempestroid import Route

# Após login: pilha limpa com o home no topo
app.reset([Route(name="/")])
```

`reset` exige uma lista não-vazia — um app precisa sempre ter uma tela para
renderizar.

```text
# Assinatura:
app.reset(stack: list[Route]) -> None  # lança ValueError se stack for vazia
```

!!! warning "Pilha nunca vazia"
    Passar uma lista vazia para `reset` lança `ValueError`. O app sempre precisa
    ter pelo menos uma rota.

---

## Hosts visuais

Mudar de rota já troca a árvore de widgets — o reconciliador diff e aplica os
patches. Os **hosts de navegação** são widgets opcionais que adicionam animação de
transição, abas ou uma gaveta lateral ao mesmo mecanismo.

Para detalhes de todas as props e mais exemplos, veja a página de
[Widgets de Navegação](widgets/navigation.md).

### `Navigator` — pilha animada

Envolva a tela atual num `Navigator` para obter animações de slide/fade ao
navegar. Passe `depth=len(app.nav.stack)` para que os renderizadores saibam a
direção (avançar vs. voltar):

```python
from dataclasses import dataclass

from tempestroid import App, Button, Column, Navigator, Route, Text, Widget


@dataclass
class State:
    """Estado do exemplo com Navigator."""


def make_state() -> State:
    """Retorna o estado inicial."""
    return State()


def view(app: App[State]) -> Widget:
    """Tela com animação de navegação."""
    depth = len(app.nav.stack)

    if app.nav.top.name == "/details":
        content = Column(
            children=[
                Text(content="Detalhes", key="title"),
                Button(label="Voltar", on_click=app.pop, key="back"),
            ],
            key=f"screen-{depth}",
        )
    else:
        content = Column(
            children=[
                Text(content="Início", key="title"),
                Button(
                    label="Detalhes",
                    on_click=lambda: app.push(Route(name="/details")),
                    key="fwd",
                ),
            ],
            key=f"screen-{depth}",
        )

    return Navigator(child=content, transition="slide", depth=depth)
```

!!! tip "A `key` animada"
    Dê uma `key` diferente à árvore filha em cada profundidade
    (`key=f"screen-{depth}"`). O reconciliador trata a mudança de `key` como uma
    substituição, sinalizando para o renderer que deve animar a transição.

### `TabView` / `TabBar` — abas como rotas

Use `TabView` para abas integradas (barra + conteúdo) ou `TabBar` para uma barra
autônoma que você posiciona livremente. Ambas emitem `RouteChangeEvent` com
`params["index"]`:

```python
from dataclasses import dataclass

from tempestroid import App, Column, RouteChangeEvent, TabView, Text, Widget


@dataclass
class State:
    """Estado do app com abas."""

    tab: int = 0


def make_state() -> State:
    """Retorna o estado inicial."""
    return State()


def view(app: App[State]) -> Widget:
    """App de três abas."""

    def on_tab(event: RouteChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "tab", event.params["index"]))

    bodies = [
        Column(children=[Text(content="Início", key="h")], key="home"),
        Column(children=[Text(content="Busca", key="s")], key="search"),
        Column(children=[Text(content="Perfil", key="p")], key="profile"),
    ]

    return TabView(
        tabs=["Início", "Busca", "Perfil"],
        active=app.state.tab,
        child=bodies[app.state.tab],
        on_change=on_tab,
    )
```

### `RouteDrawer` — gaveta lateral

Para um menu lateral deslizante, use `RouteDrawer`. O estado `open` controla a
visibilidade; `on_change` é emitido quando o usuário fecha a gaveta por gesto ou
toque fora dela:

```python
from dataclasses import dataclass

from tempestroid import (
    App,
    Button,
    Column,
    RouteChangeEvent,
    RouteDrawer,
    Text,
    Widget,
)


@dataclass
class State:
    """Estado do app com gaveta."""

    drawer_open: bool = False


def make_state() -> State:
    """Retorna o estado inicial."""
    return State()


def view(app: App[State]) -> Widget:
    """Tela principal com gaveta lateral."""

    def on_drawer_change(event: RouteChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "drawer_open", False))

    return RouteDrawer(
        child=Column(
            children=[
                Text(content="Conteúdo", key="main"),
                Button(
                    label="Abrir menu",
                    on_click=lambda: app.set_state(
                        lambda s: setattr(s, "drawer_open", True)
                    ),
                    key="open",
                ),
            ],
        ),
        drawer=Column(
            children=[Text(content="Menu lateral", key="menu")],
        ),
        open=app.state.drawer_open,
        on_change=on_drawer_change,
    )
```

---

## Botão Voltar do Android

O botão Voltar do Android (e a tecla `Esc` no simulador Qt) é capturado
automaticamente pelo runtime e chama `app.pop()`.

- **Na raiz** (`app.nav.can_pop == False`): `pop` é um no-op — o sistema Android
  assume o comportamento padrão de fechar o app.
- **Em qualquer outra tela**: a rota do topo é removida e a rebuild coalescida
  ocorre normalmente.

Você **não precisa** conectar o botão Voltar manualmente. O botão explícito de
"Voltar" nos seus widgets (`on_click=app.pop`) é apenas para o usuário ter um
atalho visual — o botão do sistema já está tratado.

!!! info "No simulador Qt"
    A tecla `Esc` dispara o mesmo `app.pop`. Útil para testar o comportamento de
    navegação sem precisar de um dispositivo físico.

---

## Deep links

Um deep link chega como uma intenção Android (ou argumento de lançamento no
simulador) e precisa abrir o app diretamente numa tela específica, com a pilha de
volta já construída. `routes_from_path` converte um caminho em uma pilha inicial:

```python
from tempestroid.navigation import routes_from_path

# "/shop/item" → [Route("/"), Route("/shop"), Route("/shop/item")]
stack = routes_from_path("/shop/item")
```

Passe essa pilha para `app.reset(...)` no início do app, e o usuário consegue
navegar de volta pelas telas intermediárias normalmente:

```python
from dataclasses import dataclass

from tempestroid import App, Button, Column, Text, Widget
from tempestroid.navigation import routes_from_path


@dataclass
class State:
    """Estado do app com suporte a deep link."""

    deep_link: str = ""


def make_state() -> State:
    """Retorna o estado inicial."""
    return State()


def view(app: App[State]) -> Widget:
    """Tela que responde a deep links."""
    route_name = app.nav.top.name

    def open_deep() -> None:
        stack = routes_from_path(app.state.deep_link or "/shop/item")
        app.reset(stack)

    return Column(
        children=[
            Text(content=f"Rota atual: {route_name}", key="route"),
            Button(label="Simular deep link /shop/item", on_click=open_deep, key="dl"),
            Button(label="Voltar", on_click=app.pop, key="back"),
        ],
    )
```

!!! note "Caminho raiz"
    `routes_from_path("/")` e `routes_from_path("")` retornam `[Route(name="/")]`
    — o mesmo que o `NavStack` padrão, sem entradas extras.

---

## Transições

O `Navigator` aceita uma prop `transition` que é uma **dica** para os
renderizadores sobre como animar a troca de tela:

| Valor | Comportamento |
|---|---|
| `"slide"` | Desliza a nova tela de dentro para fora (Qt: `QPropertyAnimation`; Compose: `AnimatedContent`). |
| `"fade"` | Dissolve entre as telas. |
| `"none"` | Troca instantânea, sem animação. |

```python
from tempestroid import Navigator, Route

# No view:
navigator = Navigator(child=current_screen, transition="slide", depth=depth)
```

!!! tip "Transição é uma dica, não um contrato"
    Os renderizadores podem interpretar `transition` de forma ligeiramente diferente
    (Qt usa `QPropertyAnimation`; Compose usa `AnimatedContent`). Para desativar
    animações completamente, use `"none"`.

---

## Recapitulando

- O `App` mantém uma `NavStack` em `app.nav`. O `view` lê `app.nav.top` para
  decidir qual tela renderizar — navegação é apenas o `view` produzindo uma árvore
  diferente.
- `app.push(Route(name="..."))` empilha uma nova rota; `app.pop()` volta para a
  anterior (no-op na raiz).
- `app.replace(Route(...))` troca a tela atual sem mudar a profundidade da pilha.
- `app.reset([...])` redefine toda a pilha — útil após login ou num deep link.
- `routes_from_path("/a/b")` converte um caminho em uma pilha inicial para deep
  links.
- `Navigator`, `TabView`/`TabBar` e `RouteDrawer` são hosts visuais opcionais que
  adicionam animação, abas e gaveta lateral ao mesmo mecanismo.
- O botão Voltar do Android e a tecla `Esc` no simulador chamam `app.pop`
  automaticamente.

## Próximos passos

- [Widgets de Navegação](widgets/navigation.md) — props completas de `Navigator`,
  `TabView`, `TabBar` e `RouteDrawer`.
- Exemplo completo de navegação:
  [`examples/navigation/app.py`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/navigation/app.py)
- Exemplo de abas:
  [`examples/tabs/app.py`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/tabs/app.py)
