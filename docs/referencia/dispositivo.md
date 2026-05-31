# Lado do dispositivo (ponte)

A metade Python do lado do dispositivo é independente de hardware e testada sem um
telefone; o transporte JNI (fase B3) e o renderizador Compose em Kotlin (fase B4)
estão implementados em `android-host/` e verificados em um dispositivo arm64 real.

## Tradutor `Style → Compose`

- **`to_compose(style)`** (`tempestroid.renderers.compose`) — *spec* serializável
  `Style → Compose`; o segundo tradutor de `Style` (par com `Style → Qt`). Os
  dois são fixados pela [suíte de conformidade](../roadmap.md) (fase D).

## Serialização

- **`serialize_node` / `serialize_patch`** — rebaixam a IR/patches para dicts
  JSON-able: *handlers* viram *tokens* de caminho, `Style` vira a *spec* Compose.

## Protocolo de fio

Mensagens atravessam uma única fronteira de *marshalling* (a ponte JNI no
dispositivo, um canal em memória nos testes).

- **`MountMessage`** — `mount` carrega a árvore serializada completa.
- **`PatchMessage`** — `patch` carrega uma lista incremental de *patches*.
- **`EventMessage`** — `event` carrega um callback dispositivo→Python endereçado
  por *token* de *handler*.

Um *token* de *handler* identifica um *handler* pelo **caminho** do seu nó na
árvore mais o nome da prop (ex.: `"0/1:on_click"`). É baseado em caminho (não em
chave) para que o lado que emite (serializador) e o que despacha (registry)
computem *tokens* idênticos a partir da mesma árvore.

## Transporte e app de dispositivo

- **`DeviceApp`** + **`Bridge`** / **`LoopbackBridge`** — ligam um `App` a um
  transporte de dispositivo; o análogo de `run_qt` no dispositivo. Eventos voltam
  por *token* de *handler*, são validados por `parse_event` e disparam *patches*
  coalescidos.
- **`JniBridge`** + **`run_device`** — o transporte real no dispositivo (fase
  B3): `JniBridge` envia mensagens ao Kotlin via o módulo nativo `_tempest_host`;
  `run_device(state, view)` boota um `DeviceApp` num loop asyncio fresco e
  marshala eventos de entrada de volta para ele. Importa limpo fora do dispositivo
  (o módulo nativo é carregado *lazy*), então o framework continua se
  desenvolvendo/testando no desktop.

## Dev server — code-push por LAN (fase B5)

O loop interno estilo Expo: editar na máquina de dev, hot-restart no telefone sem
reconstruir o APK (`tempest serve <app>`).

- **`DevServer`** — serve o código-fonte do app (`/version`, `/app`) e faz relay
  dos logs do dispositivo (`/log`) por HTTP.
- **`run_dev_client`** — o loop de poll do dispositivo: busca ao mudar → re-exec
  do código → hot-restart do `DeviceApp`.
- **`serve_device(url)`** — entrada do dispositivo ligando o `JniBridge` real + o
  *sink* nativo + um *fetch* `urllib` no `run_dev_client`.
- **`render_qr(url)`** — QR ASCII para pareamento (cai para a URL pura).

## Capacidades nativas (fase B6)

Recursos nativos do dispositivo dirigidos do Python como comandos `{"kind":
"native"}` que o host Kotlin roteia para módulos de capacidade.

- **`notify(title, body="")`** — posta uma notificação de sistema a partir de um
  *handler*. O padrão de extensão (envelope `native_command` + um roteador de
  módulos no host) está pronto para mais capacidades (câmera, sensores, …).
