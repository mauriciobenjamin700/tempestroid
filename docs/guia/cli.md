# CLI (`tempest`)

O ponto de entrada `tempest` cobre o ciclo de vida do app: criar, desenvolver no
simulador, empurrar para o dispositivo, empacotar e inspecionar o contrato.

```bash
uv run tempest new MyApp                        # scaffold de um novo projeto de app
uv run python examples/counter/app.py           # rodar um app direto no simulador Qt
uv run tempest dev examples/counter/app.py       # dev loop: editar + salvar → hot reload
uv run tempest serve examples/device_counter/app.py  # code-push por LAN, sem rebuild de APK
uv run tempest build MyApp/app.py               # empacotar o app em um APK
uv run tempest run MyApp/app.py                 # build + instalar no dispositivo + logs
uv run tempest spec                             # imprimir o contrato tipado (widgets/eventos) como JSON
uv run tempest --help
```

## Comandos

| Comando | Status | Descrição |
|---|---|---|
| `tempest new <nome>` | ✅ | Cria um projeto de app executável. |
| `tempest dev <app>` | ✅ | Simulador + hot reload / hot restart (precisa do extra `qt`). |
| `tempest serve <app>` | ✅ | Code-push por LAN para o dispositivo + relay de logs (fase B5). |
| `tempest spec` | ✅ | Contrato tipado de widgets/eventos como JSON. |
| `tempest build <app>` | ✅ | Empacota um app em um APK (precisa do Android SDK/NDK). |
| `tempest run <app>` | ✅ | Build + instala no dispositivo + transmite logs. |

## Cockpit do `tempest dev`

Comandos interativos enquanto o simulador roda:

| Tecla | Ação |
|---|---|
| `r` | Hot reload (estado preservado). |
| `R` | Hot restart (estado limpo). |
| `s` | Traz a janela à frente. |
| `q` | Encerra. |

Salvar o arquivo dispara o hot reload automaticamente; se a recarga for
incompatível com o estado vivo, o loop cai para um restart limpo. Uma gravação
ruim é capturada e impressa — o loop sobrevive.

!!! note "build / run precisam do toolchain Android"
    `tempest build`/`run` dirigem o projeto Gradle `android-host` + `adb`, então
    exigem um Android SDK/NDK e um checkout da árvore do host. Veja a
    [instalação](../instalacao.md) e a [pesquisa de runtime](../research/android-runtime.md).

## Contrato do arquivo de app

Para `tempest dev`/`serve`, o módulo precisa expor:

- `make_state() -> S` — fábrica do estado inicial (chamada a cada hot restart).
- `view(app) -> Widget` — construtor da UI.

O carregador compila/executa o arquivo fresco a cada carga (sem reuso de `.pyc`),
então recargas sempre veem a última edição. Mantenha o módulo livre de imports de
Qt no nível de módulo (use `if __name__ == "__main__"`) para que o mesmo arquivo
rode no desktop e no dispositivo.
