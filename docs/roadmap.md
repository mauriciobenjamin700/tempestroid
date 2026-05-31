# Roadmap e fases

O desenvolvimento segue duas trilhas. **Trilho A** é o framework em Python puro
(desktop/CPython). **Trilho B** é o runtime Android (CPython 3.14 + host Kotlin +
ponte JNI + renderizador Compose). O plano completo está em
[Plano de design (EN)](plan.md).

## Trilho A — framework (Python puro)

| Fase | Escopo | Status |
|---|---|---|
| A0 | Fundação: pacote, ferramental, `tempest --help` | ✅ |
| A1 | Modelo de estilo + primitivas de widget tipadas | ✅ |
| A2 | Reconciliador: `build → diff → patch` | ✅ |
| A3 | Renderizador Qt: patches → `QWidget`s, `Style → Qt` | ✅ |
| A4 | Loop de eventos async: asyncio ⨉ Qt (`qasync`) | ✅ |
| A5 | `tempest dev`: watcher, hot restart, loop de comandos | ✅ |
| A6 | Contrato de eventos tipado + introspecção | ✅ |

## Trilho B — runtime Android

| Fase | Escopo | Status |
|---|---|---|
| B0 | CPython 3.14 para arm64 | ✅ |
| B1 | Wheels nativas (pydantic-core) + site-packages do dispositivo | ✅ |
| B2 | Host Kotlin: embute CPython, boota o interpretador fora da thread de UI via JNI | ✅ |
| B3 | Ponte JNI (nativa): transporte bidirecional Python↔Kotlin | ✅ |
| B4 | Renderizador Compose (nativo): renderiza a árvore serializada, aplica patches, roteia toques | ✅ |
| B5 | Dev server + QR (code-push por LAN + relay de logs) | ✅ |
| B6 | Capacidades nativas (notificações) | ✅ |

## Polimento e conformidade

| Fase | Escopo | Status |
|---|---|---|
| C | Polimento: `new`/`build`/`run` + hot reload com estado | ✅ |
| D | *Golden snapshots* de conformidade (Qt vs Compose) | ✅ |

!!! note "Suíte de conformidade (fase D)"
    `tests/conformance/` fixa os dois tradutores de `Style`: *golden snapshots* de
    `to_compose` + `to_qss`/`layout_alignment` para estilos canônicos
    (regenere com `UPDATE_GOLDEN=1`), além de uma tabela de paridade de cobertura
    por campo que falha se um tradutor passar a tratar (ou parar de tratar) um
    campo sem atualizar as divergências documentadas.

## Próximos passos abertos

- **Inputs no dispositivo (Compose):** o renderizador Kotlin hoje cai para uma
  caixa vazia em `Input` / `Checkbox` / `DatePicker` / `FilePicker`; falta crescer
  os casos correspondentes no host. No simulador Qt esses widgets já funcionam.
- **Mais capacidades nativas:** câmera, sensores — seguindo o padrão de envelope
  `native_command` + roteador de módulos no host.
