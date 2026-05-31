# Galeria de exemplos

Um conjunto de apps de exemplo executáveis vive em `examples/`. Cada um expõe o
mesmo contrato `make_state()` + `view(app)`, então roda no simulador Qt **e** no
dispositivo via code-push, sem mudanças.

```bash
# Simulador Qt no desktop (precisa do extra `qt`; instalado por `uv sync`)
uv run python examples/<nome>/app.py
uv run tempest dev examples/<nome>/app.py     # + hot reload ao salvar

# Em um dispositivo Android, via code-push por LAN (fase B5)
adb reverse tcp:8765 tcp:8765                 # via USB; pule se na mesma Wi-Fi
uv run tempest serve examples/<nome>/app.py
```

## Apps

| App | O que mostra | Widgets / patches exercitados |
|---|---|---|
| `counter` | O básico: handlers síncronos **e** `async`. | `Text`, `Button`, `Row`/`Column`; `update`. |
| `shell` | Os componentes compostos: um `Scaffold` com `AppBar` no topo e `NavBar` embaixo, corpo por aba. | `tempestroid.components` (`AppBar`/`Scaffold`/`NavBar`/`Header`) reduzidos a primitivos via `Component.render`. |
| `todo` | Lista dirigida por toque (sem entrada de texto — itens vêm de um pool fixo). | Lista com chave estável; `insert` / `remove` / `update`. |
| `calculator` | Grade densa de botões como única entrada. | `Row`/`Column` aninhados, 16 botões com chave; `update` no display. |
| `stopwatch` | Loop async-first: um handler corrotina conta via `asyncio.sleep` sem travar a UI. | Rebuilds coalescidos a partir do loop; `update`. |
| `colorpicker` | `Style` dinâmico: swatches recolorem um preview vivo; toggles re-estilizam o texto. | Atualizações de `background` / `font_size` / `font_weight` pelo diff. |
| `form` | Os inputs com valor, cada um dobrando seu evento tipado de volta no estado. | `Input` / `Checkbox` / `DatePicker` / `FilePicker`; `TextChangeEvent` / `ToggleEvent` / `DateChangeEvent` / `FileSelectEvent`. |
| `gallery` | O conjunto expandido de componentes + estilização de input + uma transição implícita de `Style`. | `Slider` / `Switch` / `ProgressBar` / `Spinner` / `Image` / `Icon` / `ScrollView` / `TextArea`; `Input` seguro + regex; `SlideEvent`; `Style.transition`. |
| `device_counter` | Contador mínimo só de dispositivo (sem import de Qt) para o caminho de code-push. | Mesmo contrato, livre de Qt. |

## Conjunto de widgets atual

O framework e o **simulador Qt** suportam o conjunto completo — `Text` / `Button`
/ `Column` / `Row` / `Container` mais os inputs com valor `Input` / `Checkbox` /
`DatePicker` / `FilePicker` (veja o exemplo `form`) — com `on_click` e os eventos
de mudança tipados.

O **renderizador do dispositivo (Compose)** hoje renderiza `Text` / `Button` /
`Column` / `Row` / `Container` e `on_click`; os inputs com valor caem para uma
caixa vazia até o host Kotlin crescer os casos correspondentes (continuação do
Trilho B). Por isso os apps voltados ao dispositivo permanecem **dirigidos por
botão**: o `todo` adiciona de um pool predefinido em vez de texto digitado, e o
`calculator` usa o teclado numérico como superfície de entrada.

!!! tip "Handlers estáveis"
    Rebuilds comparam props de *handler* por identidade, então um `lambda` novo a
    cada build lê como mudança de prop (limitação conhecida). Os exemplos ainda
    emitem *patches* corretos — apenas mais que o mínimo estrito. Prefira
    referências de *handler* estáveis em apps de produção.
