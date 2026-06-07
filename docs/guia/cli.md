# CLI (`tempest`)

O ponto de entrada `tempest` cobre o ciclo de vida do app: criar, desenvolver no
simulador, empurrar para o dispositivo, empacotar e inspecionar o contrato.

```bash
uv run tempest new                              # scaffold na pasta atual (id = nome da pasta)
uv run python examples/counter/app.py           # rodar um app direto no simulador Qt
uv run tempest dev examples/counter/app.py       # dev loop: editar + salvar → hot reload
uv run tempest deploy examples/multifile/main.py # push offline no aparelho (sem SDK/NDK)
uv run tempest serve examples/device_counter/app.py  # code-push por LAN, sem rebuild de APK
uv run tempest build apk                        # APK com id próprio, lado a lado (JDK + SDK)
uv run tempest run                              # build + instalar no dispositivo + logs
uv run tempest spec                             # imprimir o contrato tipado (widgets/eventos) como JSON
uv run tempest --help
```

## Comandos

| Comando | Status | Descrição |
|---|---|---|
| `tempest new` | ✅ | Cria um projeto de app executável **na pasta atual** (id = nome da pasta). Passe um nome só para criar uma subpasta. |
| `tempest dev <app>` | ✅ | Simulador + hot reload / hot restart (precisa do extra `qt`). |
| `tempest deploy <app>` | ✅ | Push **offline** do projeto inteiro no aparelho (sem SDK/NDK): instala o host empacotado + empurra + abre. |
| `tempest serve <app>` | ✅ | Code-push por LAN + hot reload do projeto inteiro (fase B5). |
| `tempest install [src]` | ✅ | adb-instala o host pré-compilado (sem SDK/NDK). |
| `tempest spec` | ✅ | Contrato tipado de widgets/eventos como JSON. |
| `tempest doctor` | ✅ | Diagnostica os pré-requisitos de build/run Android (JDK, android-host, SDK, adb, dispositivo). Prontidão de build define o código de saída; device ausente é só informativo (só `run`/`install` precisam). |
| `tempest setup` | ✅ | Configura o ambiente de build: diagnostica JDK/SDK/build-tools; `--install` instala o Android SDK. |
| `tempest version` | ✅ | Imprime a versão do framework (igual a `--version`). |
| `tempest clean` | ✅ | Limpa os caches de build em `~/.tempestroid` (nativos extraídos do host, cópia do host, clone do source) — resolve falhas de cache velho após upgrade; `--keystore` também apaga o keystore de release. |
| `tempest build [apk\|prd]` | ✅ | `apk`: APK **per-app** (id próprio → N apps lado a lado), via Gradle reusando os nativos pré-compilados (**só JDK + SDK**, sem NDK/toolchain). `prd`: AAB de release. Lê `[tool.tempest]`. |
| `tempest run` | ✅ | `build apk` + instala no dispositivo + transmite logs. |
| `tempest icon <img>` | ✅ | Gera `icon.png` + `splash.png` de uma imagem (Pillow). |

Apps são **multi-arquivo**: a árvore do projeto vai junto (no `sys.path`) no
simulador e no dispositivo. Veja [Build, deploy e publicação](build.md) para a
diferença entre o push offline (`deploy`/`serve`) e o APK distribuível (`build`).

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

!!! note "build / run precisam de JDK + Android SDK"
    `tempest build`/`run` rodam o Gradle reusando os nativos pré-compilados (o
    `android-host` vem no pacote), então precisam de **JDK + Android SDK** —
    **sem NDK, sem toolchain CPython, sem `git clone`**. Para rodar no aparelho
    **sem SDK**, use `tempest deploy`/`serve`. Veja
    [Build, deploy e publicação](build.md), a [instalação](../instalacao.md) e a
    [pesquisa de runtime](../research/android-runtime.md).

## Contrato do arquivo de app

Para `tempest dev`/`serve`, o módulo precisa expor:

- `make_state() -> S` — fábrica do estado inicial (chamada a cada hot restart).
- `view(app) -> Widget` — construtor da UI.

O carregador compila/executa o arquivo fresco a cada carga (sem reuso de `.pyc`),
então recargas sempre veem a última edição. Mantenha o módulo livre de imports de
Qt no nível de módulo (use `if __name__ == "__main__"`) para que o mesmo arquivo
rode no desktop e no dispositivo.
