# Começo rápido

Este guia leva você do zero a um app rodando no simulador em poucos minutos —
mesmo que seja seu primeiro contato com o tempestroid. O caminho é sempre o
mesmo: **criar** um projeto, **rodar** no simulador, **editar** e ver a mudança
ao vivo.

!!! tip "Pré-requisitos"
    - **Python ≥ 3.11** e o [uv](https://docs.astral.sh/uv/) instalados.
    - O framework com o simulador Qt: `pip install "tempestroid[qt]"` (ou, neste
      repositório de desenvolvimento, `uv sync`). Detalhes em
      [Instalação](instalacao.md).
    - No WSL/Linux sem ambiente gráfico, o simulador Qt precisa de um servidor de
      display. Veja [Rodar no dispositivo / WSL](guia/dispositivo-wsl.md).

## Passo 1 — Crie um projeto

Você já está dentro da pasta do seu projeto (e do seu ambiente virtual). O
comando `tempest new`, **sem argumentos**, gera os arquivos iniciais **aqui
mesmo** — um `app.py` (contador de exemplo), `pyproject.toml`, `README.md` e
`.gitignore` — e usa o **nome da pasta atual como id do app**. Sem pasta extra
em volta.

```bash
mkdir meu-app && cd meu-app          # sua pasta de projeto (com seu venv)
uv run tempest new                   # scaffold AQUI; id = "meu-app"
```

> Quer uma subpasta? Passe um nome: `uv run tempest new OutroApp` cria
> `OutroApp/`. Mas o fluxo recomendado é o in-place acima.
>
> Instalou via `pip`? O binário fica disponível como `tempest new` (sem o
> `uv run`). Ao longo deste guia usamos `uv run tempest …` por ser o fluxo do
> repositório; remova o `uv run ` se instalou pelo `pip`.

O `app.py` gerado é **Python puro**, sem nenhum import de Qt no nível do módulo —
por isso o **mesmo arquivo** roda no simulador de desktop, vai pro dispositivo
via `tempest serve` e empacota com `tempest build` sem mudar uma linha.

## Passo 2 — Rode no simulador

```bash
uv run tempest dev                     # abre o simulador Qt + hot reload
```

`tempest dev` (sem argumento) lê o caminho do app de `[tool.tempest] app` no
`pyproject.toml` — por isso você roda da raiz do projeto sem apontar o arquivo.
Uma janela abre com o contador (`-`, o valor, `+`). O terminal vira um *cockpit*
interativo:

| Tecla | Ação |
|---|---|
| `r` | Hot reload — recarrega o código **preservando o estado** atual. |
| `R` | Hot restart — recarrega do zero (estado limpo via `make_state`). |
| `s` | Traz a janela do simulador à frente. |
| `q` | Encerra. |

## Passo 3 — Edite e veja ao vivo

Com o simulador aberto, abra `app.py` no editor e mude algum texto — por
exemplo o título dentro do `Text`. **Salve o arquivo.** O `tempest dev` detecta a
gravação e faz hot reload automático: a janela atualiza sem perder o contador.

Se uma edição quebrar o app, o erro é impresso no terminal e o loop **sobrevive**
— corrija e salve de novo. Se a recarga for incompatível com o estado vivo, ele
cai automaticamente para um restart limpo.

Pronto: esse é o ciclo completo de desenvolvimento. O resto deste guia explica
**o que** você acabou de rodar.

## O modelo mental

Todo app tempestroid honra um contrato de **duas funções**:

- **`make_state() -> S`** — devolve o **estado inicial**. É chamado a cada hot
  restart, então deve montar um estado limpo. `S` é qualquer objeto seu (um
  `@dataclass` é o caminho natural).
- **`view(app: App[S]) -> Widget`** — recebe o app e devolve a **árvore de UI**
  para o estado atual. É uma função pura de estado → widgets: dado o mesmo
  estado, devolve a mesma árvore.

O ciclo que conecta as duas:

```text
   estado ──view(app)──▶ árvore de widgets ──diff──▶ patches ──▶ tela
      ▲                                                            │
      └────────────── app.set_state(...) ◀── handler de evento ◀───┘
```

1. `view` constrói a árvore a partir de `app.state`.
2. Você liga *handlers* (clique, etc.) a `app.set_state(...)`.
3. Quando um handler chama `set_state`, o `App` reconstrói a `view`, faz o *diff*
   contra a árvore anterior e entrega só os *patches* (mudanças mínimas) ao
   renderizador. Várias chamadas de `set_state` no mesmo *tick* viram **um único**
   rebuild (coalescido).

`set_state` recebe uma função que **muta o estado no lugar**:

```python
app.set_state(lambda s: setattr(s, "value", s.value + 1))
```

Você nunca toca na tela diretamente — só descreve a UI em função do estado e
muda o estado. O framework cuida do resto.

## Um contador do zero

O scaffold já dá um contador completo, mas vale construir o mínimo à mão para
entender cada peça. Crie um `app.py`:

```python
from dataclasses import dataclass

from tempestroid import App, Button, Column, Style, Text, Widget
from tempestroid.renderers.qt import run_qt


@dataclass
class CounterState:
    """O estado do app: um único contador."""

    value: int = 0


def make_state() -> CounterState:
    """Devolve o estado inicial (chamado a cada hot restart)."""
    return CounterState()


def view(app: App[CounterState]) -> Widget:
    """Constrói a árvore de UI para o estado atual."""

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

Lendo de cima para baixo:

- **`CounterState`** — seu estado, um `dataclass` simples com um campo `value`.
- **`make_state`** — a fábrica do estado inicial.
- **`view`** — descreve a tela: uma `Column` (empilha verticalmente) com um
  `Text` que mostra o valor e um `Button` que incrementa. `app.state.value` lê o
  estado; `increment` chama `set_state` para mudá-lo.
- **`key="..."`** — identifica cada widget para o *diff* casar o widget velho com
  o novo entre rebuilds. Dê *keys* estáveis a filhos de listas.
- **`Style(gap=8.0)`** — espaçamento entre filhos. Estilos são objetos tipados e
  imutáveis (veja o [guia de estilos](guia/estilos.md)).
- **`if __name__ == "__main__"`** — `run_qt` abre a janela ao rodar o arquivo
  direto. Mantenha o import de Qt **dentro** deste bloco (ou só aqui no topo, sem
  ser usado por `view`/`make_state`) para o arquivo continuar rodando no
  dispositivo, que não tem Qt.

Rode direto, sem o cockpit:

```bash
uv run python app.py
```

Ou com hot reload (recomendado durante o desenvolvimento):

```bash
uv run tempest dev app.py
```

## Handlers assíncronos

*Handlers* podem ser `async` — o runtime os agenda no loop asyncio sem travar a
UI. Útil para esperar I/O (rede, disco) antes de atualizar o estado:

```python
import asyncio


def view(app: App[CounterState]) -> Widget:
    async def increment_later() -> None:
        await asyncio.sleep(0.5)
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    return Button(label="+0.5s", on_click=increment_later, key="inc")
```

## Problemas comuns

| Sintoma | Causa / solução |
|---|---|
| `ModuleNotFoundError: tempestroid` | Framework não instalado no ambiente. Rode `uv sync` (repo) ou `pip install "tempestroid[qt]"`. |
| Erro de import do `PySide6` / Qt ao rodar `dev` | O extra `qt` não está instalado. Use `pip install "tempestroid[qt]"`. |
| `app.py must define a make_state()` / `view` | O arquivo precisa expor **as duas** funções no nível do módulo, com esses nomes exatos. |
| A janela não abre no WSL/Linux headless | Falta um servidor de display. Veja [dispositivo / WSL](guia/dispositivo-wsl.md). |
| Edição não recarrega | Confirme que está rodando via `tempest dev` (não `python app.py`) e que salvou o arquivo; ou aperte `r`. |

## Próximos passos

- [Widgets](guia/widgets.md) — todas as primitivas (`Text`, `Column`, `Row`,
  `Button`, entradas, mídia…).
- [Estilos](guia/estilos.md) — o modelo de `Style` tipado.
- [Eventos](guia/eventos.md) — o contrato tipado de eventos.
- [CLI](guia/cli.md) — todos os comandos `tempest`.
- [Galeria de exemplos](guia/exemplos.md) — apps completos para estudar.

Veja também o exemplo de referência em
[`examples/counter/app.py`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/counter/app.py).
