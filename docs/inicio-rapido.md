# Começo rápido

Todo app tempestroid honra o mesmo contrato: uma fábrica `make_state()` e um
construtor `view(app)`. Esse contrato roda **sem mudanças** no simulador Qt e no
dispositivo.

## Um contador mínimo

```python
from dataclasses import dataclass

from tempestroid import App, Button, Column, Style, Text, Widget
from tempestroid.renderers.qt import run_qt


@dataclass
class CounterState:
    value: int = 0


def make_state() -> CounterState:
    return CounterState()


def view(app: App[CounterState]) -> Widget:
    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    return Column(
        style=Style(gap=8.0),
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Button(label="+", on_click=increment, key="inc"),
        ],
    )


if __name__ == "__main__":
    raise SystemExit(run_qt(make_state(), view, title="counter"))
```

Rode direto no simulador:

```bash
uv run python app.py
```

## O contrato `make_state` / `view`

- **`make_state() -> S`** — devolve o estado inicial. É chamado a cada hot
  restart, então deve montar um estado limpo.
- **`view(app: App[S]) -> Widget`** — constrói a árvore de UI a partir de
  `app.state`. Ligue *handlers* a `app.set_state(...)`; cada mudança agenda um
  rebuild coalescido (um *diff* por *tick*).

`set_state` recebe uma função que **muta** o estado no lugar; o `App` reconstrói a
`view`, faz o *diff* contra a árvore anterior e entrega os *patches* ao
renderizador.

## Loop de desenvolvimento

```bash
uv run tempest dev app.py        # simulador + hot reload ao salvar
```

No cockpit do `tempest dev`: `r` faz hot reload (estado preservado), `R` reinicia
limpo, `s` traz a janela à frente, `q` encerra. Salvar o arquivo dispara o hot
reload; se a recarga for incompatível com o estado vivo, cai para um restart
limpo.

## Handlers assíncronos

*Handlers* podem ser `async` — o runtime os agenda no loop asyncio sem travar a
UI:

```python
import asyncio


async def increment_later() -> None:
    await asyncio.sleep(0.5)
    app.set_state(lambda s: setattr(s, "value", s.value + 1))
```

Veja o exemplo completo em
[`examples/counter/app.py`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/counter/app.py)
e a [galeria](guia/exemplos.md) para mais apps.
