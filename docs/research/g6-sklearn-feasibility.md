# G6 — viabilidade de `scipy` + `scikit-learn` no device (Trilho G): resultados

> Spike de viabilidade do **G6** (`docs/research/onnx-ml-stack.md` §G6, o "calcanhar":
> Fortran/LAPACK + OpenMP no NDK).
> Data: 2026-06-19. Host: WSL Ubuntu, NDK r27 (`/usr/lib/android-sdk/ndk/27.3.13750724`),
> CPython 3.14 android oficial, cibuildwheel **4.1.0**.
> Alvo exercitado: **emulador x86_64** (`android_26_x86_64`, cp314).

## Veredito

**FEITO (build) — `scipy` E `scikit-learn` cross-compilam para Android x86_64
com clang puro, ZERO Fortran.** O "calcanhar" Fortran/LAPACK **deixou de existir**
na prática: o upstream do scipy terminou de portar todo o Fortran para C, e o
OpenBLAS gera um LAPACK traduzido por f2c (C puro) com o NDK clang. As três wheels
da stack científica clássica estão em `toolchain/dist/wheels-x86_64/`:

| Wheel | Tamanho | Tag | Como |
|---|---|---|---|
| `numpy-2.4.6-cp314-cp314-android_24_x86_64.whl` | 9 MB | `android_24` | G1 (já existia, `build_numpy_x86.sh`) |
| `scipy-1.18.0-cp314-cp314-android_26_x86_64.whl` | 35 MB | `android_26` | **G6** (`build_openblas_x86.sh` + `build_scipy_x86.sh`) |
| `scikit_learn-1.9.0-cp314-cp314-android_26_x86_64.whl` | 9.7 MB | `android_26` | **G6** (`build_sklearn_x86.sh`) |

Ambas as wheels novas: ELF Android x86_64 genuíno, OpenBLAS+LAPACK **embutido
estaticamente** no scipy (só `libm`/`libc`/`libpython3.14` em `NEEDED`), OpenMP
**realmente ligado** no sklearn (a NDK `libomp` foi vendorizada pelo auditwheel,
6 símbolos `omp_*`/`__kmpc` por `.so`). `scipy.odr` ausente (o único subpacote que
o `-D_without-fortran` descarta).

**Pendente (não-bloqueante):** prova on-device de `import sklearn` + `predict`. O
`adb`/emulador desta sessão WSL está com o daemon travando (poisoning de porta
conhecido — ver MEMORY `adb port poisoning`); as wheels estão validadas
estruturalmente (ABI, símbolos, OpenMP, tags) mas **o `import` em aparelho ainda
não foi exercido**. É o mesmo gate que fechou o G1 para numpy (`examples/onnxspike`).

**Esforço para chegar aqui:** ~1 sessão. Muito abaixo dos "N dias de toolchain
Fortran/LAPACK" que a pesquisa original temia — porque o trabalho pesado foi feito
**upstream** (scipy#18566 + o C_LAPACK do OpenBLAS), não por nós.

---

## 1. Por que o "calcanhar" Fortran sumiu

A pesquisa de G0 (`onnx-ml-stack.md` §2) classificou scipy/sklearn como risco
**alto** por dois motivos: (a) scipy precisa de Fortran (gfortran), que o NDK não
tem (só clang), e (b) sklearn herda isso + OpenMP. Dois fatos mudaram o quadro:

### 1a. scipy é efetivamente Fortran-free (scipy#18566 — **FECHADO**)

O inventário de Fortran do scipy ([scipy#18566](https://github.com/scipy/scipy/issues/18566))
está **fechado**: cada subpacote em Fortran foi **portado para C** ou deprecado —
`integrate` (QUADPACK/ODEPACK/dop/VODE), `interpolate` (FITPACK), `linalg`,
`optimize` (MINPACK/COBYLA/L-BFGS-B/SLSQP/NNLS), `sparse.linalg` (ARPACK/PROPACK/
iterative), `special` (AMOS/cdflib/specfun), `stats` (statlib). Sobrou **só**
`scipy.odr` (odrpack), que foi **deprecado** (aponta para `odrpack-python`).

No sdist do scipy 1.18.0, os **únicos** `.f`/`.f90` restantes são
`scipy/odr/odrpack/*.f` (5 arquivos) e um binding `.f90` opcional do HiGHS. A
opção meson **`-D_without-fortran=true`** (scipy 1.16+) **não adiciona Fortran como
linguagem** (`meson.build:89 if not get_option('_without-fortran') → add_languages('fortran')`)
e simplesmente **omite `scipy.odr`**. Resultado: **scipy builda sem NENHUM
compilador Fortran**.

### 1b. OpenBLAS gera LAPACK em C (f2c) sem Fortran

scipy precisa de **BLAS *e* LAPACK** — diferente do numpy, **não há** escape
`-Dallow-noblas`. Mas o OpenBLAS, quando compilado com **`NOFORTRAN=1 C_LAPACK=1`**,
inclui um **LAPACK traduzido por f2c para C** (a flag `-DC_LAPACK`), compilável com
clang puro. Buildamos OpenBLAS 0.3.33 para `android x86_64` com o NDK clang e o
banner confirmou: `OpenBLAS build complete. (BLAS CBLAS LAPACK LAPACKE)`, com os
símbolos LAPACK presentes (`dgetrf_`/`dpotrf_`/`dgeev_`/`dgesv_`/`dsyev_`) e
`NO_LAPACK=` vazio. scipy linka esse OpenBLAS como `libblas/liblapack` planos
(`-Dblas=openblas -Dlapack=openblas`, sem wrappers g77 porque é fortran-free).

> **A questão real deixou de ser "Fortran no scipy" e virou "LAPACK no OpenBLAS sem
> gfortran" — e o `C_LAPACK=1` resolve isso com clang.** Receita:
> `toolchain/build_openblas_x86.sh`.

### Referência: Chaquopy (o caminho antigo, hoje quebrado em NDK moderno)

O Chaquopy mantém wheels android pré-buildadas de scipy/sklearn
(<https://chaquo.com/pypi-13.1/>), mas elas **não servem** para nós: travam em
**cp310 / scipy 1.8.1 / sklearn 1.3.2 / API 21** (ABI antiga do Chaquopy), enquanto
nosso alvo é **cp314 / API 24+**. A receita deles dependia de empacotar um
**`chaquopy-libgfortran` + `chaquopy-openblas`** próprios — e o mantenedor confirma
que [a recipe do `chaquopy-libgfortran` está quebrada no NDK r27](https://github.com/chaquo/chaquopy/issues/1385)
(o NDK só traz clang 18, não gcc/gfortran). Ou seja: **o caminho "vendorizar
gfortran" que a pesquisa original cogitava está morto no NDK moderno** — e felizmente
o `C_LAPACK` + scipy-fortran-free o torna desnecessário.

---

## 2. Os 4 blockers vencidos (scipy) — reprodutível

Tentativa: `cibuildwheel --platform android --archs x86_64` sobre scipy **1.18.0**,
linkando o OpenBLAS+C_LAPACK. O configure do meson passou de primeira (achou numpy,
o OpenBLAS via pkg-config, desligou Fortran). Quatro blockers de **compilação**, em
ordem (todos em `build_openblas_x86.sh` + `build_scipy_x86.sh`):

### Blocker A — OpenBLAS+LAPACK para Android (a fundação) ✅
NDK não tem Fortran → `NOFORTRAN=1 C_LAPACK=1 TARGET=ATOM BINARY=64 HOSTCC=gcc
CC=x86_64-linux-android24-clang NO_SHARED=1`. Produz `libopenblas.a` (BLAS + f2c
LAPACK). Sem isso scipy não tem o que linkar.

### Blocker B — `boost.math` assume `long double` de 80 bits no x86_64 ✅
`scipy/special/_ufuncs_cxx` puxa `boost/math/.../fp_traits.hpp`, que **decide o
layout do `long double` pelo macro de CPU**: em `__x86_64__` assume Intel-extended
80-bit e dispara `static_assert(LDBL_MANT_DIG == 64, ...)`. Mas **Android/Bionic
x86_64 usa IEEE quad de 128 bits (`LDBL_MANT_DIG == 113`)** — igual ao Android
arm64. O `#elif` chega no ramo do macro x86 **antes** do ramo IEEE-128 (linha 439)
e estoura.
**Fix:** patch no guard — `&& (LDBL_MANT_DIG == 64)` no ramo x86, para o caso quad
cair no ramo IEEE-128 correto.
**Nuance importante:** **arm64 NÃO é afetado** (não define `__x86_64__`, então já
cai no ramo 128-bit). Este blocker é **específico do emulador x86_64** — o device
real (arm64) provavelmente o ignora.
> Aviso lateral: o cross-file do numpy declara `longdouble_format =
> 'INTEL_EXTENDED_16_BYTES_LE'` (80-bit), o que é **factualmente errado** para
> Android x86_64 (é quad/128). Não quebrou o numpy (a prop só alimenta o probe
> interno do numpy); mas é uma imprecisão a corrigir em G-futuro.

### Blocker C — `clog`/`cpow` indefinidos: piso de API 26 ✅
`scipy/special/_complexstuff.h` usa `clog`/`cpow`/`cexp` (via `<complex.h>`). A
Bionic **declara essas funções só a partir da API 26** (`__INTRODUCED_IN(26)`);
buildando contra **API 24** elas ficam escondidas → erro de declaração implícita.
(numpy escapou na API 24 por trazer seu próprio `npy_math` complexo; scipy largou o
npymath e usa o `<complex.h>` da plataforma.)
**Fix:** `ANDROID_API_LEVEL=26` (cibuildwheel respeita essa env). O emulador é API
34, então o piso 26 é seguro. As wheels saem com tag **`android_26_x86_64`**.

### Blocker D — `ducc0` (FFT) usa `pthread_*affinity_np` da glibc ✅
`subprojects/duccfft/ducc0/infra/threading.cc` guarda chamadas de afinidade de CPU
com `defined(__linux__) && defined(_GNU_SOURCE)` e chama
`pthread_getaffinity_np`/`pthread_setaffinity_np` — funções **só da glibc; a Bionic
não as tem**. Android define `__linux__`, então o guard dispara e o build quebra.
**Fix:** patch nos 3 guards — `&& !defined(__ANDROID__)` — para o ducc0 cair no
fallback (`std::thread::hardware_concurrency` + pinning no-op).

Depois de A–D: **1144/1144 objetos compilados e linkados**,
`scipy-1.18.0-cp314-cp314-android_26_x86_64.whl` (35 MB), auditwheel-repaired.

---

## 3. scikit-learn — buildou de primeira

Com scipy resolvido, o sklearn 1.9.0 **buildou sem nenhum patch** — só precisou:
- `ANDROID_API_LEVEL=26` (consistência com scipy);
- `-fopenmp` em `CFLAGS`/`CXXFLAGS` + `-L<ndk>/lib/clang/18/lib/linux/x86_64` p/ a
  `libomp` do NDK.

Fatos que ajudaram:
- O `meson.build` do sklearn **pula todas as checagens de versão de build-dep
  quando `meson.is_cross_build()`** — então o pin `scipy>=1.10,<1.18.0` do
  pyproject **não atrapalha** (ele só compara versões no caminho não-cross). O build
  consome apenas os **headers do numpy** (mesmo caminho cross que o scipy usou); as
  wheels android de scipy/numpy são deps de **runtime no device**, não do build host.
- A NDK traz **`libomp` (LLVM OpenMP)**; o auditwheel a **vendorizou** na wheel
  (`libomp-e415e7fe.so`) e os `.so` referenciam símbolos OMP de verdade → sklearn
  saiu **multithread**, não no fallback single-thread.

257/257 targets linkados → `scikit_learn-1.9.0-cp314-cp314-android_26_x86_64.whl`
(9.7 MB).

---

## 4. O que falta (honesto)

1. **Prova on-device** (`import scipy`, `import sklearn`, um `LogisticRegression.fit/predict`
   trivial fora da UI thread). É o gate que falta — bloqueado só pela instabilidade
   do `adb`/emulador desta sessão WSL, não por nada do build. Próximo passo natural:
   stage das 3 wheels no site-packages do device (como em `02_stage_deps.sh`) +
   um `examples/sklearnspike` espelhando o `examples/onnxspike`.
2. **arm64.** Tudo aqui é **x86_64** (emulador). O device real é arm64; rebuildar as
   3 wheels para `android_24_arm64_v8a`/`android_26_arm64_v8a` deve ser direto
   (OpenBLAS `TARGET=ARMV8`, mesmos patches) — e o **Blocker B (boost) não deve nem
   aparecer no arm64** (sem `__x86_64__`).
3. **Piso de API 26 vs CPython API 24.** As wheels novas são `android_26`; o CPython
   do device foi buildado para API 24. Uma wheel `android_26` instala/roda num
   device/emulador **API ≥ 26** (emulador = API 34, ok). Se quisermos manter o piso
   24 em todo o stack, teria que rebuildar o CPython em 26+ ou achar como expor
   `clog`/`cpow` na 24 (improvável). **Recomendação: subir o piso do device para 26.**
4. **Tamanho.** numpy+scipy+sklearn ≈ **52 MB** de payload (sem contar onnxruntime).
   Relevante para G7 (encolher APK): ABI splits, `strip`, trim de submódulos scipy.
5. **`scipy.odr` ausente** (consequência do `-D_without-fortran`). Se algum app
   precisar de ODR, é a única peça que exigiria um Fortran de verdade.

---

## 5. Conclusão do G6

- **scipy + scikit-learn cross-compilam para Android x86_64 com clang puro, sem
  Fortran.** O "calcanhar" foi dissolvido upstream (scipy fortran-free + OpenBLAS
  C_LAPACK), não por força bruta nossa.
- **Receitas reprodutíveis:** `build_openblas_x86.sh` (BLAS+LAPACK f2c),
  `build_scipy_x86.sh` (scipy fortran-free + os 4 patches/flags),
  `build_sklearn_x86.sh` (sklearn + OpenMP da NDK).
- **Decisão:** **G6 é VIÁVEL** — promover de "alto risco / último e opcional" para
  "buildável hoje". Falta só o `import` on-device (gate de hardware/emulador) e o
  rebuild arm64 para o device físico. Esforço estimado para fechar de verdade:
  **baixo** (1 sessão de device + 1 de rebuild arm64), não os dias de toolchain
  Fortran que se temia.

> **G6 vs roadmap:** mantém-se gated por demanda real de app (ninguém precisa de
> sklearn no device ainda), mas **a viabilidade — o entregável do spike — está
> provada**: o caminho fecha.

### Fontes primárias

- scipy — META: FORTRAN Code inventory (FECHADO): <https://github.com/scipy/scipy/issues/18566>
- scipy — `_without-fortran` (em `meson.options` 1.18.0): "build without a Fortran compiler (the deprecated `scipy.odr` will be missing)"
- scipy — BLAS/LAPACK build (g77 ABI, sem noblas): <https://docs.scipy.org/doc/scipy/building/blas_lapack.html>
- OpenBLAS — build sem Fortran usa LAPACK f2c/C (`NOFORTRAN`/`C_LAPACK`): <https://github.com/OpenMathLib/OpenBLAS/issues/1284>, <https://github.com/OpenMathLib/OpenBLAS/discussions/4386>
- OpenBLAS — Android cross-compile (NDK clang): <http://www.openmathlib.org/OpenBLAS/docs/install/>
- Chaquopy — wheels android (cp310 max, ABI antiga): <https://chaquo.com/pypi-13.1/>
- Chaquopy — `chaquopy-libgfortran` quebrado no NDK r27 (só clang 18): <https://github.com/chaquo/chaquopy/issues/1385>
- scikit-learn — release de wheels (cibuildwheel + OpenMP): <https://github.com/scikit-learn/scikit-learn/issues/30284>
- cibuildwheel 4.0 — Android maduro (auditwheel/pkg-config/Fortran): <https://iscinumpy.dev/post/cibuildwheel-4-0-0/>
