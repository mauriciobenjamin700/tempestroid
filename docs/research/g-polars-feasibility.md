# Trilho G — Polars no device (investigação de viabilidade)

**Pergunta:** dá para rodar [Polars](https://docs.pola.rs) (DataFrame em Rust) no
app Android nativo, incluindo o caminho de **reading/writing** (CSV/JSON/Parquet)
do [getting-started](https://docs.pola.rs/user-guide/getting-started/#reading-writing)?

**Resposta curta: SIM, arquiteturalmente é o caminho MAIS tratável da família
DataFrame** — Polars é **Rust/maturin**, exatamente a classe do `pydantic-core`
que o B1 já cross-compila para Android. Não tem o calcanhar Cython/Fortran do
pandas/scipy. O único blocker android-específico (allocator jemalloc) é
**evitável por feature flag**. Falta o *build pesado* fechar (confirmação empírica).

## O que o Polars precisa (1.41.2)

O pacote foi **dividido** nesta linha:

- **`polars`** — wrapper PURO-Python (`py3-none-any`). Sem código nativo.
- **`polars-runtime-32`** — o **core Rust** (`.so`), dependência **obrigatória**.
  (`polars-runtime-64` é opcional, extra `rt64`: índices de 64-bit.)

Então o alvo de cross-compile é **`polars-runtime-32`**. Fatos do sdist (2.99 MB,
workspace Rust completo — dezenas de crates `polars-*`):

| Fato | Valor | Por que importa |
|---|---|---|
| build-backend | **`maturin>=1.3.2`** | idêntico ao `pydantic-core` (B1) — `cibuildwheel --platform android` já sabe buildar maturin/Rust |
| ABI | **`abi3`** (`cp310-abi3`) | **1 wheel serve todo CPython ≥3.10** — sem rebuild por versão (≠ numpy/pandas, que são `cp314`) |
| deps do core | **nenhuma** | numpy/pandas/pyarrow são todos `extra`s opcionais; o core não precisa de nada |
| reading/writing | **CSV / JSON / Parquet nativos no core Rust** | `read_csv`/`write_csv`/`read_parquet`/`write_parquet`/`read_json` NÃO exigem pyarrow (Polars tem impl própria de Parquet) |

## O blocker clássico (jemalloc) é evitável

Polars não amarra mais jemalloc no binário. O `#[global_allocator]`
(`crates/polars-python/src/c_api/allocator.rs`) é `polars_ooc::Allocator`, cujo
caminho C-API usa `std::alloc` (o **system allocator**, android-safe). O jemalloc
e o mimalloc vivem em `crates/polars-ooc/Cargo.toml` como deps **`optional = true`**
atrás da feature **`fast_alloc`** (`fast_alloc = ["dep:mimalloc", "dep:tikv-jemallocator"]`,
puxada só pela feature `full`).

**Receita Android:** buildar SEM `fast_alloc` (e sem `full`) → cai no system
allocator, sem `tikv-jemallocator` (que não compila para `*-linux-android`). Manter
as features de funcionalidade (IO csv/json/parquet, lazy, query engine) via
`full_functionality` — que é separada de `fast_alloc` no `polars-python`. Custo:
perde-se o allocator "fast" (mimalloc/jemalloc), não a funcionalidade.

## Caminho (= padrão B1 pydantic-core + build_numpy/pandas_x86.sh)

1. `cibuildwheel --platform android --archs x86_64` (e arm64) sobre o sdist do
   `polars-runtime-32`, `CIBW_BUILD_FRONTEND=build`, maturin resolvido por
   build-isolation. Rust targets `{x86_64,aarch64}-linux-android` via o NDK r27
   (linker = clang do NDK), igual ao `pydantic-core`.
2. Passar as features sem `fast_alloc` (provável `CIBW_*`/`config-settings` →
   `--no-default-features --features <full_functionality+io>` no maturin, a
   afinar no 1º build pelo erro).
3. Stage: `polars` (py3-none-any, do PyPI) + a wheel `polars-runtime-32` abi3
   cross-buildada → site-packages (script irmão de `stage_pandas_x86.sh`).
4. Exemplo `examples/polarsspike` (mirror do pandas/sklearn-spike):
   `pl.DataFrame(...).write_csv` + `pl.read_csv` + um `group_by().agg()` →
   prova o reading/writing no emulador.

## Riscos abertos (o que só o build fecha)

- **Build pesado (o risco real):** o workspace Polars é grande (engine + arrow +
  parquet em Rust) → compile de **dezenas de minutos + bastante RAM**. O
  `pydantic-core` (pequeno) prova o *mecanismo*; o *volume* do Polars no host WSL
  é o desconhecido. Não rodar junto com o build do pandas (contenção de CPU/RAM).
- **Feature/linker afinar:** a combinação exata de features (IO sem `fast_alloc`)
  e o cfg do `tikv-jemallocator`/`background_threads` podem precisar de 1-2
  iterações de flag, como numpy precisou (longdouble/noblas).
- **Tamanho do APK:** a `.so` do Polars é grande (engine inteiro) — alimenta o
  Trilho G7 (trim), não bloqueia a viabilidade.

## Decisão

**Caminho (A) CPython-puro** (wheel cross-compilada), **classe pydantic-core/maturin
— a mais favorável das DataFrames**: abi3, core deps-free, IO nativo, allocator
contornável por feature. **Recomendado** como alternativa leve ao pandas para
pipelines tabulares no device. Próximo passo: `toolchain/build_polars_x86.sh`
(features sem `fast_alloc`/`nightly`, sem `rust-toolchain.toml` pin), e provar
`examples/polarsspike` no emulador.

## Resultado do build (2026-06-21)

A wheel **compila** (`toolchain/build_polars_x86.sh`): `polars_runtime_32-1.41.2-cp310-abi3-android_24_x86_64.whl`, 15 min de compile do engine Rust inteiro, **abi3** (uma wheel p/ todo CPython ≥3.10). Confirmou a tese: maturin/Rust→Android fecha, o calcanhar era só feature-tuning. Blockers resolvidos no script (3 seds):

1. **`cp310-*` → `cp314-*`** — cibuildwheel só oferece o CPython android 3.14 (a wheel sai abi3 igual).
2. **Feature surgery** — um subset mínimo de IO quebra os `match` exaustivos do polars-python (`IRFunctionExpr`/`IRStringFunction`/…); usar o set coerente `full_functionality`, dropando só `nightly` (SIMD/rustc instável) + `fast_alloc` (jemalloc/mimalloc não buildam p/ android) + remover o pin nightly do `rust-toolchain.toml`.
3. **`clipboard`** — o feature `io` puxa `arboard` (sem backend android, `cannot find Clipboard in platform`); removida a linha `"clipboard"` do feature `io` do polars-python.

Dois fixes de packaging do lado tempestroid:

- **strip** — a `.so` unstripped é ~**2.4 GB** (debug do workspace Rust), que estoura o compressor de assets do AGP (limite de array de 2 GB do Java) **e** incha o APK. `CARGO_PROFILE_RELEASE_STRIP=symbols` no build → ~200 MB.
- **`noCompress("so")`** em `android-host/app/build.gradle.kts` — não comprimir as `.so` de assets (são extraídas em runtime; comprimir uma `.so` grande crasha o compressor). Correto + independente (ajuda qualquer `.so` grande, incl. G6).

**No device (emulador x86_64):** `import polars` **funciona** (o core `.so` carrega, `_plr` resolve, a versão bate, o app renderiza). **Pendente:** um `NameError: PySeries` num path de op específico (DataFrame/group_by/csv) — quirk de símbolo do build de features reduzidas; o diagnóstico on-device ficou bloqueado pela instabilidade crônica do adb no WSL (não pelo polars). Próximo: tentar `default = ["full_functionality"]` direto (o set coerente do maintainer, menos clipboard) em vez do subset à mão — capturar o traceback com adb saudável.

## Enforcement no framework

O loader de app (`tempestroid.cli.app_loader.spec_from_source` — o funil do
simulador Qt **e** do code-push no device) escaneia a fonte e emite uma
`DiscouragedImportWarning` quando o app importa `pandas`, orientando a usar Polars
(`tempestroid/cli/advisories.py`). É um **aviso**, não um erro — o import ainda
roda no simulador; o objetivo é guiar o dev pra escolha que cabe no device.

