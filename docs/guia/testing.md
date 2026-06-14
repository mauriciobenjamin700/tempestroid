# Testes de UI (o "Playwright do nativo") 🎯

Você já sabe construir telas, ligar eventos e rodar no simulador. Agora vamos
**testar** uma tela do jeito que o Playwright testa uma página web — só que sem
um navegador, sem pixels e sem `sleep` mágico.

O driver de testes do tempestroid dirige a sua **árvore (a IR)**: ele monta o app,
encontra nós por `key`/texto/semântica, injeta os mesmos eventos tipados que um
toque real produz e afirma o resultado — com **auto-wait** em toda ação e
asserção (a árvore precisa estabilizar antes de prosseguir).

!!! tip "Por que é mais forte que o Playwright"
    O Playwright fala com o DOM. Aqui o "DOM" é a nossa **IR** — idêntica em todos
    os renderizadores. Por isso o **mesmo script** roda no backend headless (rápido,
    local) e no backend `emulator` (app Compose REAL num emulador Android) — sem
    mudar uma linha do teste.

## O exemplo mínimo

Um arquivo de teste de UI é um **módulo de app comum** — ele define `view(app)`
e `make_state()` (o mesmo contrato de um app rodável) — mais uma ou mais funções
`async def test_*(page)`.

Vamos testar o contador. O `examples/counter/app.py` já existe; criamos um
`examples/counter/test_counter.py` ao lado dele:

```python
from app import make_state, view  # reusa o contrato do app vizinho

from tempestroid.testing import Page

__all__ = ["make_state", "view"]


async def test_counter_starts_at_zero(page: Page) -> None:
    await page.expect_text("Count: 0")


async def test_increment_button_updates_count(page: Page) -> None:
    await page.expect_text("Count: 0")
    await page.tap(page.get_by_key("inc"))   # toca o botão "+"
    await page.expect_text("Count: 1")       # auto-wait até a UI estabilizar
```

Rode com:

```bash
uv run tempest uitest examples/counter/test_counter.py
```

Saída:

```text
[PASS] test_counter_starts_at_zero
[PASS] test_increment_button_updates_count

2/2 passed on target 'headless'.
```

🚀 Pronto: um teste de fluxo ponta-a-ponta (evento → estado → re-render) **sem
renderizador e sem flake de timing**.

## Entendendo peça por peça

### `page` — o app montado

Cada `test_*` recebe um `page`: um app **recém-montado** num backend. Cada teste
tem o seu próprio `page` e o seu próprio estado, então um teste nunca contamina o
outro.

### Locators — consultas preguiçosas

Um **locator** é uma *consulta*, não um nó capturado. Ele resolve contra a árvore
**atual** toda vez que uma ação ou asserção precisa — por isso sobrevive a um
rebuild. Crie-os pelo `page`:

```python
page.get_by_key("inc")                       # pela key estável da IR
page.get_by_text("Count: 0")                 # por texto (substring)
page.get_by_text("Count: 0", exact=True)     # texto inteiro exato
page.get_by_role("button", name="Salvar")    # por role/label de Semantics (E9)
page.get_by_semantics(label="contador")      # por semântica de acessibilidade
```

!!! note "Resolução tardia, sempre"
    `locator.first` / `locator.all()` / `locator.count()` percorrem a cena
    **viva**. Uma ação (`tap`/`fill`) usa `locator.resolve()`, que exige **exatamente
    um** nó: zero ou muitos → erro claro, nunca "o primeiro" silencioso.

### Ações — eventos tipados injetados

```python
await page.tap(locator)          # injeta TapEvent no on_click/on_tap do nó
await page.fill(locator, "abc")  # injeta TextChangeEvent(value="abc") no on_change
await page.back()                # pop na pilha de navegação (back do sistema)
```

A ação resolve o locator, escolhe o handler do nó, valida o payload no **evento
tipado** que o widget declara (via `event_schemas`) e chama o handler — exatamente
o caminho que o `dispatchEvent` do dispositivo e o `_invoke` do Qt percorrem.

### Auto-wait — o fim do `sleep`

Toda asserção espera a árvore **estabilizar** antes de checar:

```python
await page.expect_text("Count: 2")     # até algum nó conter o texto
await page.expect_visible(locator)     # até o locator achar ≥ 1 nó
await page.expect_count(locator, 3)    # até o locator achar exatamente 3 nós
```

"Estabilizar" = nenhum rebuild pendente no ciclo coalescido (A4) **e** dois
snapshots consecutivos iguais. Nada de `sleep`: a espera termina no instante em
que a UI para de mudar, ou estoura o `timeout` (padrão 5s) com a árvore atual
despejada para depuração.

!!! check "Handlers assíncronos funcionam de graça"
    Um handler `async` que `await`a antes de `set_state` é aguardado pela ação
    antes do `settle`. O teste do botão "+ (async)" passa sem nenhum `sleep`.

### `snapshot()` — o "screenshot" da IR

```python
dump = page.snapshot()   # dict JSON-able: {"root": {...}, "overlays": [...]}
```

É o análogo headless de um screenshot: uma serialização estável da árvore (tipos,
keys, props de string/número, filhos) para comparação golden.

!!! info "Screenshot de pixel é do renderizador"
    Um screenshot real de pixels é responsabilidade do backend Qt/dispositivo e
    chega com o Trilho F8. O `snapshot()` headless cobre o que importa para um
    teste de fluxo: a forma da árvore.

## Falhas geram diagnóstico

Quando uma asserção não se cumpre dentro do `timeout`, o erro traz a **árvore no
momento da falha**:

```text
[FAIL] test_increment
  AssertionError: expected text 'Count: 9' to be visible
    Traceback (most recent call last):
      ...
  tree at failure:
    {'root': {'type': 'Column', 'key': None, 'props': {}, 'children': [...]}}
```

## Alvos (`--target`)

```bash
uv run tempest uitest examples/counter/test_counter.py --target headless
```

| Alvo | Estado | O que dirige |
| --- | --- | --- |
| `headless` | ✅ disponível | A IR/estado/eventos em processo, sem renderizador |
| `emulator` | ✅ disponível | App REAL pelo renderizador **Compose** num emulador Android |
| `qt` | ⏳ reservado | O simulador Qt em processo |
| `device` | ⏳ reservado | Compose num dispositivo físico, pela ponte |

Como todos falam a **mesma IR + eventos tipados**, o seu teste headless roda nos
demais alvos sem mudar uma linha.

### Alvo `emulator` — render Compose REAL + N em paralelo

```bash
# 1 emulador (reaproveita um já rodando, ex.: emulator-5554)
uv run tempest uitest examples/counter/test_counter.py --target emulator

# N emuladores isolados em paralelo (limitado por CPU/RAM do host)
uv run tempest uitest examples/ --target emulator -j 3
```

O backend `emulator` (`EmulatorBackend`) dirige um app **de verdade** pelo
renderizador **Compose**: ele sobe um `DevServer` em **modo harness**, faz
`adb -s <serial> reverse` e lança o host em modo dev. O cliente code-push do
dispositivo:

- **device → host:** dá `POST` do JSON de `mount` e de cada lote de `patch` de
  volta; o servidor mantém um **espelho** (`Scene`) do lado do host (via
  `tempestroid.testing.mirror`). `page.scene()` lê esse espelho.
- **host → device:** `page.tap(...)` lê o **token** do handler do nó espelhado
  (`{"$handler": token}`), enfileira o evento; o cliente faz long-poll, consome e
  alimenta `DeviceApp.handle_event` — **o mesmo caminho de um toque Compose real**
  — e o rebuild/patch resultante volta e atualiza o espelho. **Nada de
  `adb input tap` por coordenada, nada de mudança em C/JNI.**

O **auto-wait** (`settle`) monitora a *revisão* do espelho até ela ficar quieta
por uma janela curta E o evento enfileirado ter sido consumido — sem `sleep`
fixo como mecanismo principal.

`EmulatorPool` aloca/recicla N instâncias isoladas (porta `5554 + i*2`,
serial `emulator-<porta>`), reaproveitando emuladores já rodando e **limitando N
pela CPU/RAM do host** (sempre logando quando reduz o pedido).

!!! check "Screenshots de pixels REAIS"
    No alvo `emulator`, cada teste salva um screenshot em
    `docs/assets/emulator/uitest/<teste>.png` capturado via
    `adb exec-out screencap` — **pixels Compose reais**, não a serialização da
    árvore. É a evidência de que o leaf de dispositivo se comporta como o núcleo.

## Em código (sem CLI)

Você também pode dirigir um backend direto, útil dentro de um `pytest`:

```python
from tempestroid.testing import HeadlessBackend, Page

page = Page(HeadlessBackend(make_state, view))
await page.mount()
await page.tap(page.get_by_key("inc"))
await page.expect_text("Count: 1")
```

## Recapitulando

- Um teste de UI é um **app + funções `async def test_*(page)`**.
- **Locators** (`get_by_key`/`get_by_text`/`get_by_role`/`get_by_semantics`)
  resolvem contra a **IR viva**.
- **Ações** (`tap`/`fill`/`back`) injetam **eventos tipados** — o mesmo caminho do
  renderizador real.
- **Asserções** (`expect_text`/`expect_visible`/`expect_count`) têm **auto-wait**:
  esperam a árvore estabilizar, sem `sleep`, sem flake.
- O backend `headless` dirige o **núcleo agnóstico de renderizador**; o backend
  `emulator` roda o **mesmo script** contra um app Compose REAL num emulador
  Android (`-j N` em paralelo, screenshot de pixels por teste). ✅
