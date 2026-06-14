# Trilho H — design system: componentes estilizados (M3 + API Chakra)

> Plano dedicado para elevar o catálogo de componentes a um **design system
> bonito e coeso**, ancorado visualmente em **Material 3** com a **ergonomia de
> API do Chakra UI** (`variant` / `size` / `color_scheme` + tokens de tema).
> Objetivo de produto: **pesquisadores acadêmicos** montam apps Android de
> validação de resultados (junto com o Trilho G de
> inferência ONNX) com pouco esforço e visual profissional.

---

## 1. Por que (motivação)

Hoje o framework **já tem 46 componentes** no engine `tempest-core`
(`Card`, `Badge`, `Chip`, `Avatar`, `DataTable`, `Drawer`, `Rating`, `Stepper`,
`SegmentedControl`, inputs BR, `Scaffold`, `AppBar`…) e roles de cor semânticos
(`SURFACE`/`ON_SURFACE`/`ACCENT`/`MUTED`). **Não é greenfield.**

O que falta para virar um design system de verdade (nível MUI/Chakra):

1. **Tokens de design** — só existem `Color` + `ThemeMode`; faltam escalas
   sistemáticas (paleta tonal, espaçamento, raio, tipografia, elevação, motion).
2. **API de variantes** — `Button` aceita só `label`/`on_click`/`style`; não há
   `variant="outline"`, `size="lg"`, `color_scheme="primary"`. A estilização é
   `Style` cru, prop a prop — verboso e inconsistente entre telas.
3. **Estados visuais** — sem padrão de hover/press/disabled/focus (state layers).
4. **Coesão + vitrine** — sem galeria navegável nem docs tutorial-first dos
   componentes; o pesquisador não tem de onde copiar.
5. **Componentes de pesquisa** — falta `MetricCard`, wrappers de gráfico,
   `ConfidenceBadge`, overlay de detecção para os resultados do `ort-vision-sdk`.

O Trilho H fecha esses cinco gaps **reaproveitando** os componentes existentes,
não reescrevendo.

---

## 2. Decisões de design (fixadas)

- **Âncora visual = Material 3.** O renderer Compose já usa Material3 → o device
  ganha o visual quase de graça; o Qt **emula** os tokens via `Style`/QSS. Os
  roles de cor atuais (`SURFACE`/`ON_SURFACE`/…) já são M3-like.
- **Ergonomia de API = Chakra.** Props declarativas `variant` / `size` /
  `color_scheme` resolvidas contra o tema, em vez de `Style` manual. Um
  `Button(variant="solid", color_scheme="primary", size="lg")` produz o `Style`
  final pelo tema — o usuário não mexe em cor/padding na mão.
- **Tudo dentro do ecossistema — sem pacote novo.** A metade IR (tokens +
  variantes + componentes) mora no engine **`tempest-core`**; o suporte de
  renderer aos novos campos de `Style` mora em **`tempestroid`** (Qt) e
  **`android-host`** (Compose). Nenhum repositório/pacote PyPI novo.

!!! warning "Trilho cross-repo — três camadas, dois repositórios"
    Diferente do Trilho E (tudo em `tempestroid`), o Trilho H atravessa **dois
    repos**, porque o engine foi extraído (v0.13.0): **camada IR/componentes →
    `tempest-core`**; **renderer Qt → `tempestroid/renderers/qt`**; **renderer
    Compose → `android-host`**. Cada fase só fecha com as **três camadas
    casadas** + conformância nos dois tradutores `Style`, exatamente como o
    Trilho E — só que a camada 1 é versionada/publicada separado. Toda fase
    precisa coordenar bump+release do `tempest-core` antes que `tempestroid`
    consuma os tokens novos.

---

## 3. Arquitetura

```text
Theme (tokens)          # tempest-core/theme.py — escalas de token + colorSchemes
   │  resolve
   ▼
variant/size/color_scheme  # props Chakra-like nos componentes (tempest-core)
   │  → Style (frozen, já existente)
   ▼
Style translators       # os DOIS tradutores existentes, estendidos p/ novos campos
   ├─ to_qss / layout   # tempestroid/renderers/qt
   └─ to_compose (M3)   # android-host (consome o spec Compose)
```

Regra de ouro mantida: **o reconciliador continua agnóstico**; toda divergência
de plataforma fica nos dois tradutores de `Style`. Tokens e variantes resolvem
**para `Style`** antes do diff — não viram um caminho paralelo de renderização.

---

## 4. Fases

Cada fase entrega as **três camadas casadas** (token/componente em `tempest-core`,
tradutor Qt e tradutor/spec Compose) e só fecha com os **dois renderizadores
verdes** mais conformância; havendo device, verificação dual.

| Fase | Escopo | Risco | Status |
|---|---|---|---|
| H0 | **Sistema de tokens** (foundation): paleta tonal M3 + `color_scheme`s, escalas de espaçamento (grid 4pt), raio, tipografia (display/headline/title/body/label), elevação/sombra, motion. `Theme` resolve tokens; `Style` referencia-os. | **alto** | ⏳ planejado |
| H1 | **API de variantes (Chakra)**: protocolo `variant`/`size`/`color_scheme` → `Style` via tema; estados visuais (hover/press/disabled/focus) como state layers M3. `Button` como piloto (solid/outline/ghost/link × xs–lg × colorScheme). | **alto** | ⏳ planejado |
| H2 | **Kit base ação/entrada estilizado**: Button, IconButton, Input/TextField, Checkbox, Radio, Switch, Select, Slider — aplicam variant/size/color_scheme + estados sobre os inputs do E5. | médio | ⏳ planejado |
| H3 | **Superfície & layout estilizado**: Card (elevated/filled/outlined), Surface, Divider, Stack helpers (HStack/VStack/Spacer), Container responsivo, Grid — skins M3. | baixo | ⏳ planejado |
| H4 | **Data display & feedback estilizado**: Badge/Tag/Chip/Avatar (variants), Alert/Banner (status color_schemes), Progress/Spinner, Skeleton (reusa E3), Tooltip, Stat. | baixo | ⏳ planejado |
| H5 | **Componentes de pesquisa** (liga ao Trilho G): MetricCard/StatCard, wrappers de gráfico (Line/Bar sobre o canvas do E7), DataTable estilizada (sort/paginate), ConfidenceBadge, DetectionOverlay (bounding boxes p/ resultados do `ort-vision-sdk`), ImagePicker→ResultView. | médio | ⏳ planejado |
| H6 | **Galeria + docs + dark**: example app "gallery" (estilo storybook) com cada componente × variante; docs tutorial-first (padrão tiangolo) bilíngue; dark mode verificado nos dois renderers; conformância de tokens/variants. | baixo | ⏳ planejado |

`H0`→`H1` são a fundação e destravam todo o resto; `H2`–`H4` são o catálogo
base; `H5` é o diferencial para o público-alvo (pesquisadores) e consome o
Trilho G; `H6` é o polimento e a vitrine.

---

## 5. Tokens (detalhe de H0)

Espelhando Material 3 + a escala do Chakra:

- **Cor:** `color_scheme`s nomeados (`primary`/`secondary`/`tertiary`/`error`/
  `neutral`) cada um com paleta tonal (0–100, estilo M3); roles derivados
  (`on_*`, `*_container`). Mantém os roles atuais como base.
- **Espaçamento:** escala em grid de 4pt (`0,1,2,3,4,6,8,12,16…`).
- **Raio:** `none/sm/md/lg/xl/full` (M3 shape scale).
- **Tipografia:** rampa M3 (`display/headline/title/body/label` × `lg/md/sm`),
  já casando com `Style.text_scale`/`font_asset` do E9.
- **Elevação/sombra:** níveis 0–5 (M3 tonal elevation).
- **Motion:** durações + curvas padrão (reusa `Curve`/`Transition` do E3).

Os componentes nunca recebem cor/tamanho cru — recebem **token** ou
`variant`/`size`/`color_scheme`, e o tema resolve para `Style`.

---

## 6. API de variantes (detalhe de H1)

Padrão Chakra, tipado e congelado (Pydantic):

```python
Button(label="Salvar", variant="solid",   color_scheme="primary", size="lg")
Button(label="Cancelar", variant="outline", color_scheme="neutral", size="md")
Badge(label="98% conf.", variant="subtle", color_scheme="success")
Card(variant="elevated")
```

- `variant`, `size`, `color_scheme` são **enums tipados** novos em
  `tempest-core/style.py` (`Variant`, `Size`, e `color_scheme` referenciando os
  schemes do tema).
- A resolução `(variant, size, color_scheme, theme, state) → Style` é uma função
  pura no engine — testável sem renderer e pinável na conformância.
- **Estados** (`hover`/`pressed`/`disabled`/`focus`) entram como camadas
  aplicadas sobre o `Style` base (M3 state layers); o Qt emula com pseudo-estados
  QSS, o Compose usa as do Material3.

---

## 7. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Coordenação cross-repo (`tempest-core` ↔ `tempestroid` ↔ `android-host`) | Token/variante landa e é **released** no `tempest-core` primeiro; tempestroid bumpa a dep; renderers consomem. Cada fase é um par de PRs coordenados. |
| Divergência M3 (Compose nativo) vs emulação Qt | Suite de conformância pina os dois tradutores por token/variante (padrão Trilho D); divergências documentadas, não escondidas. |
| Escopo inflar (virar "mais um MUI") | v1 = catálogo enxuto coeso + os componentes de pesquisa do público-alvo; extras sob demanda. |
| Tokens quebrarem apps existentes | `Style` cru continua aceito; variantes são **aditivas** — quem já estiliza na mão não quebra. |

---

## 8. Feito quando (por fase)

- **H0** — `Theme` expõe as escalas de token; um componente lê um token e ambos
  os renderers produzem o mesmo visual; conformância pina os tokens.
- **H1** — `Button` com `variant`/`size`/`color_scheme` + 4 estados renderiza
  idêntico (dentro das divergências documentadas) nos dois renderers; resolução
  `→Style` unit-testada.
- **H2–H4** — cada componente do kit aceita variant/size/color_scheme, passa na
  conformância e aparece na galeria.
- **H5** — um app de exemplo mostra resultado do `ort-vision-sdk` num
  `DetectionOverlay` + `MetricCard` + gráfico, nos dois renderers (device quando
  houver hardware).
- **H6** — galeria navegável + docs bilíngues tutorial-first publicadas; dark
  mode verificado; gate verde nos dois repos.

---

## 9. Relação com os outros trilhos

- **Consome E9** (tema/dark/MediaQuery, `text_scale`/`font_asset`) como base de
  tokens.
- **Consome E7** (canvas) para os wrappers de gráfico de H5.
- **Consome E5** (inputs) como base do kit de entrada de H2.
- **Casa com o Trilho G** (inferência ONNX): H5 dá a UI de validação que o
  pesquisador usa para ver os resultados do modelo.
