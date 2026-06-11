# Feature-gating das capacidades nativas pesadas (F4 · trim de tamanho)

> **Objetivo.** Tornar **opcionais** as dependências Android pesadas (CameraX, ML
> Kit barcode, Firebase/FCM, media3, maps) para encolher o APK default. O peso do
> APK **não é o CPython** (stdlib já trimada, ~25 MB descompactados) e sim o **DEX**
> (~72 MB descompactados somando `classes*.dex`). Mantê-las só quando o app declara
> que as usa devolve parte desse espaço ao default.
>
> **Resultado medido (compile-only, sem device):** lean **46,8 MB** × full
> **58,2 MB** = **−11,4 MB** (DEX descompactado −11,9 MB; 0 classes das libs
> gateadas no lean × 4.913 no full). A meta inicial de ~25–30 MB **não foi
> atingida**: as libs gateadas eram só ~11,9 MB do DEX de 72 MB — o resto é
> `material-icons-extended` (~9 MB) + Compose/coil + os ~25 MB de CPython, fora do
> escopo deste corte (ver "Próximos cortes" abaixo).

## Diagnóstico (medido em `tempest-host-0.11.1.apk`)

| Bloco | Tamanho (descompactado) | Natureza |
|---|---|---|
| `classes*.dex` (×6) | ~72 MB | ML Kit barcode, Firebase/FCM, play-services, CameraX, media3, `material-icons-extended`, okhttp |
| `assets/python/lib/python3.14` | 25 MB | stdlib + site-packages (já trimado) |
| `lib/arm64-v8a` | 16 MB | libpython 5.6 MB + ssl/crypto/sqlite + camera/mlkit + libtempest_host |

## Features gateáveis

| Feature | Deps Gradle | Widgets | Capacidades nativas |
|---|---|---|---|
| `camera` | `androidx.camera:camera-{core,camera2,view,lifecycle}` | `CameraPreview` | `take_photo` / `record_video` |
| `qr` | `com.google.mlkit:barcode-scanning` (+ camera) | `QrScanner` | — |
| `push` | `com.google.firebase:firebase-messaging` | — | `push` (token/local) |
| `video` | `androidx.media3:media3-{exoplayer,ui}` | `VideoPlayer` | — |
| `maps` | maps-compose + play-services-maps (hoje comentado) | `MapView` | — |

**Core (sempre presente):** Compose UI/Material3, `material-icons-extended`,
`coil-compose` (Image), lifecycle, activity-compose, work-runtime, biometric,
security-crypto, e o grupo nativo sem-config (clipboard/storage/database/
secure_storage/system/haptics/sensors/lifecycle/connectivity/prefs/share/geo).

> `qr` implica `camera` (ML Kit roda sobre o preview da câmera) — resolver a
> dependência transitiva ao montar o set de features.

## Contrato de build

- **Propriedade Gradle:** `-Ptempest.features=camera,qr` (CSV; vazio = lean).
- **pyproject do app:** `[tool.tempest] features = ["camera", "qr"]`.
- **CLI:** `tempest build` lê `features` do pyproject + flag repetível
  `--feature camera`; junta, resolve transitivas, repassa `-Ptempest.features`.
- **`BuildConfig.TEMPEST_FEATURES`** (CSV) exposto ao Kotlin em runtime.

### Caminho de build × features

- **Lean (sem features):** usa o **host pré-buildado** embutido no wheel
  (`_assets/host.apk`) — zero-toolchain, menor APK. É o default.
- **Com features:** exige **build from-source** (Gradle + SDK/NDK), porque um APK
  pré-buildado não tem como receber deps Gradle novas. A CLI detecta o toolchain;
  faltando, erra com orientação clara (o que instalar). O host pré-buildado
  embutido passa a ser **lean** (rebuild no release).

> **Simplicidade pro usuário final:** o modelo mental é único — declarar
> `features` (ou nada) e rodar `tempest build`. A CLI escolhe o caminho.
> Espelhamos como extras PyPI (`tempestroid[camera]`) só para descoberta/intenção;
> o que corta o APK é a flag de build.

## Mecânica Kotlin/Gradle

### Source sets por feature (código)
Cada bloco que toca uma dep pesada sai de `TempestRenderer.kt`/`NativeModules.kt`
para um arquivo top-level com **assinatura idêntica** em dois source sets:

```
src/main/java/.../<core sempre presente, chama as funções por nome>
src/feat_camera/java/.../CameraImpl.kt   # RenderCameraPreview real
src/stub_camera/java/.../CameraStub.kt   # RenderCameraPreview placeholder
… idem feat_qr/stub_qr, feat_push/stub_push, feat_video/stub_video
```

`build.gradle.kts` adiciona o srcDir real **ou** o stub conforme a feature:

```kotlin
val features = (findProperty("tempest.features") as String?)
    ?.split(",")?.map { it.trim() }?.filter { it.isNotEmpty() }?.toSet().orEmpty()
fun feat(name: String, real: String, stub: String) =
    android.sourceSets["main"].java.srcDir(if (name in features) real else stub)
feat("camera", "src/feat_camera/java", "src/stub_camera/java")
// …
```

### Dependências condicionais
```kotlin
dependencies {
    if ("camera" in features || "qr" in features) { /* camerax */ }
    if ("qr" in features) { /* mlkit */ }
    if ("push" in features) { /* firebase-messaging */ }
    if ("video" in features) { /* media3 */ }
}
```

### Manifesto
Entradas problemáticas quando a feature sai: `<service .TempestMessagingService>`
(FCM) e o `<provider>` FileProvider + perms `CAMERA`/`RECORD_AUDIO`. Gatear via
**overlay de manifesto por source set de feature** (o source set ativo mescla seu
`AndroidManifest.xml`), mantendo o `src/main/AndroidManifest.xml` enxuto. O
especialista Kotlin escolhe o mecanismo AGP-correto (overlay de manifesto do
source set, ou placeholder + `tools:node="remove"`), desde que: feature off ⇒
nenhuma classe/serviço da dep ausente referenciado, e o merge valide.

### Stubs (comportamento gated-off)
- Widget (`CameraPreview`/`QrScanner`/`VideoPlayer`/`MapView`) → `Box` com texto
  rotulado ("camera feature not built"). `MapView` já é placeholder hoje.
- Capacidade nativa (`take_photo`/`push`/…) → `reply(requestId, ok=false,
  error="feature_not_built", message=…)` → Python levanta `NativeError`.

## Mecânica Python/CLI

- `cli/branding.py` (ou config existente de `[tool.tempest]`): ler `features`.
- `cli/release_build.py` / `main.py`: novo arg `--feature` (repetível) + resolução
  transitiva (`qr` → `camera`); passar `-Ptempest.features=…` ao Gradle; decidir
  lean (prebuilt) vs from-source. Mensagem clara se faltar toolchain no opt-in.
- `native/*`: `NativeError("feature_not_built")` já cabe no contrato atual.
- `pyproject.toml` (extras PyPI): adicionar `camera`/`qr`/`push`/`video`/`maps` e
  `all` como marcadores (sem deps reais — documentação de intenção).
- Scaffold `tempest new`: comentar `features` no `[tool.tempest]` gerado.

## Verificação

- **Off-device (agora):** unit tests da resolução de features na CLI (set +
  transitivas + `-P` repassado); `framework-guard` verde; **buildar lean e full**
  e medir o delta de tamanho (evidência real do corte — compila + encolhe).
- **On-device (pendente — sem aparelho neste host):** lean instala/abre +
  widget gated-off mostra placeholder; full exerce camera/qr/video/push.

## Próximos cortes (fora do escopo desta entrega)

Para chegar perto dos ~25–30 MB seria preciso atacar o que sobra no DEX/assets:

1. **`material-icons-extended` (~9 MB)** — hoje core (o widget `Icon` importa
   ícones Material por nome em `TempestRenderer.kt`). Substituir pelo conjunto DIY
   já existente (`tempestroid.icons`, vetores próprios) dropa a dep inteira.
2. **R8 minify + `shrinkResources`** no build release — hoje `isMinifyEnabled=false`
   (R8 stripa classes refletidas pelo Python). Com `proguard-rules.pro` de `-keep`
   da superfície JNI/refletida, derruba o DEX não-usado de Compose/coil. Exige
   device pra verificar (classe refletida sumida só quebra em runtime).
3. **lib-dynload (~7,4 MB)** — dropar C-ext .so não usadas no estágio CPython.

## Feito quando

- ✅ `tempest build` (lean) produz APK **46,8 MB** (−11,4 MB × full);
  `framework-guard` (metade Python) verde.
- ✅ `tempest build --feature camera --feature qr` (ou via `[tool.tempest]`)
  reintroduz só o necessário, do from-source, com toolchain detectado.
- ✅ Delta de tamanho lean × full medido (compile-only) e documentado.
- ⬜ Verificação on-device pendente até haver aparelho (placeholder dos widgets
  gateados; `feature_not_built` das nativas; full exercendo camera/qr/video/push).
