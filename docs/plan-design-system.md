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
| H0 | **Sistema de tokens** (foundation): paleta tonal M3 + `color_scheme`s, escalas de espaçamento (grid 4pt), raio, tipografia (display/headline/title/body/label), elevação/sombra, motion; **temas customizáveis** (marca do pesquisador). `Theme` resolve tokens; `Style` referencia-os. | **alto** | ⏳ planejado |
| H1 | **API de variantes (Chakra)**: protocolo `variant`/`size`/`color_scheme` → `Style` via tema; estados visuais (hover/press/disabled/focus) como state layers M3; **transversais** (a11y/contraste/touch-target, RTL, responsividade) embutidos na resolução — ver §7. `Button` como piloto (solid/outline/ghost/link × xs–lg × colorScheme). | **alto** | ⏳ planejado |
| H2 | **Kit base ação/entrada estilizado**: Button, IconButton (+ sistema de **ícones**), Input/TextField, Checkbox, RadioGroup, Switch, Select, Slider, **inputs BR** (CPF/CNPJ/Email/Phone/Password/Address) — aplicam variant/size/color_scheme + estados sobre os inputs do E5. | médio | ⏳ planejado |
| H3 | **Superfície & layout estilizado**: Card (elevated/filled/outlined), Surface, Divider, Stack helpers (HStack/VStack/Spacer), Container responsivo, Grid, ListTile, Accordion — skins M3. | baixo | ✅ done (0.5.0) |
| H4 | **Data display & feedback estilizado**: Badge/Tag/Chip/Avatar (variants), Alert/Banner (status color_schemes), Progress/Spinner, Skeleton (reusa E3), Tooltip, Stat, Rating, EmptyState, SegmentedControl, Stepper. | baixo | ✅ done (0.6.0) |
| H5 | **Navegação estilizada**: AppBar/CollapsingAppBar (TopAppBar M3), NavBar (NavigationBar), Drawer/Sidebar (NavigationDrawer/Rail), Breadcrumb, Burger, Footer, Header, Scaffold, SearchBar, Tabs — skins M3 sobre os hosts do E0. | médio | ✅ done (0.7.0) |
| H6 | **Componentes de pesquisa** (liga ao Trilho G): MetricCard/StatCard, wrappers de gráfico (Line/Bar sobre o canvas do E7), DataTable estilizada (sort/paginate), ConfidenceBadge, DetectionOverlay (bounding boxes p/ resultados do `ort-vision-sdk`), ImagePicker→ResultView, Calendar/Clock estilizados. | médio | ⏳ planejado |
| H7 | **Galeria + docs + dark**: example app "gallery" (estilo storybook) com cada componente × variante; docs tutorial-first (padrão tiangolo) bilíngue; dark mode verificado nos dois renderers; conformância de tokens/variants (matriz representativa — ver §7). | baixo | ⏳ planejado |

`H0`→`H1` são a fundação e destravam todo o resto; `H2`–`H5` são o catálogo
completo (kit base + superfície + feedback + navegação); `H6` é o diferencial
para o público-alvo (pesquisadores) e consome o Trilho G; `H7` é o polimento e a
vitrine.

### Cobertura do catálogo (os 46 componentes do `tempest-core`)

Todo componente existente recebe o tratamento (variant/size/color_scheme +
estados), distribuído pelas fases — nenhum fica órfão:

- **H2 (ação/entrada):** Button, IconButton, inputs do E5, RadioGroup, `*Input`
  BR (CPF/CNPJ/Email/Phone/Password/Address), DocumentPicker, ImagePicker.
- **H3 (superfície/layout):** Card, Divider, Grid, Table/TableCell/TableRow,
  ListTile, Accordion, Surface/Container/Stack (novos helpers).
- **H4 (data display/feedback):** Badge, Chip, Avatar, Banner, Rating,
  EmptyState, SegmentedControl, Stepper, Tooltip/Progress/Spinner/Stat (novos).
- **H5 (navegação):** AppBar, CollapsingAppBar, NavBar, Drawer, Sidebar, Footer,
  Header, Breadcrumb, Burger, Scaffold, SearchBar.
- **H6 (pesquisa):** DataTable, ImagePicture, Calendar, Clock + os novos
  (MetricCard, gráficos, ConfidenceBadge, DetectionOverlay).

!!! note "Componentes novos vs. existentes"
    A maioria já existe e só ganha a camada de variante/token. Os marcados como
    "novos" (Surface, Stat, Progress/Spinner, Tooltip-skin, MetricCard, gráficos,
    ConfidenceBadge, DetectionOverlay) são acréscimos — lowerizam para primitivas
    via `Component.render`, como o restante.

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
- **Tema de marca (customização):** o pesquisador cria um `Theme` com seu
  `color_scheme` (ou sobrescreve tokens pontuais) e injeta via `App.set_theme`
  (já existe no E9) — sem tocar nos componentes. Um tema default M3 vem pronto.

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

## 7. Transversais do design system (atravessam todas as fases)

Quatro preocupações que **não são uma fase** — entram na resolução
`variant/size/color_scheme → Style` (H1) e valem para todo componente:

- **Acessibilidade (a11y).** A paleta tonal de cada `color_scheme` é gerada
  garantindo **contraste WCAG AA** entre cor e seu `on_*`; `size` nunca produz
  alvo de toque < **48dp** (mínimo M3); a `Semantics` + `focusable`/`focus_order`
  do E9 são **preservadas** por todos os componentes estilizados (rótulo,
  estado, role). Conformância inclui um check de contraste por scheme.
- **RTL.** Os componentes reusam o espelhamento start/end do E9 (`to_compose`/
  `to_qss` com flag `rtl`) — variantes não podem reintroduzir lados fixos
  (`left`/`right`); só `start`/`end`.
- **Ícones.** H2 introduz um **sistema de ícones** tipado (set padrão +
  registro do usuário), consumido por `IconButton`, inputs, navegação, etc. —
  fecha o gap dos "nomes de ícone arbitrários → texto cru" do renderer Qt.
- **Responsividade.** `size`/layout aceitam **valores por breakpoint** (estilo
  Chakra responsive / MUI `sx`), resolvidos contra a `MediaQueryData` do E9 —
  ex.: `size={"base": "sm", "md": "lg"}`. O tema define os breakpoints.

---

## 8. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Coordenação cross-repo (`tempest-core` ↔ `tempestroid` ↔ `android-host`) | Token/variante landa e é **released** no `tempest-core` primeiro; tempestroid bumpa a dep; renderers consomem. Cada fase é um par de PRs coordenados. |
| Divergência M3 (Compose nativo) vs emulação Qt | Suite de conformância pina os dois tradutores por token/variante (padrão Trilho D); divergências documentadas, não escondidas. |
| **Explosão combinatória da conformância** (variant × size × color_scheme × estado × componente) | Pinar uma **matriz representativa** (não o produto cartesiano): por componente, um golden por variante e um por estado, com size/color_scheme amostrados; a resolução `→Style` é função pura e tem unit tests exaustivos baratos cobrindo o resto. |
| Escopo inflar (virar "mais um MUI") | v1 = catálogo existente + transversais + componentes de pesquisa do público-alvo; extras sob demanda. |
| Tokens quebrarem apps existentes | `Style` cru continua aceito; variantes são **aditivas** — quem já estiliza na mão não quebra. |
| a11y/contraste só "no papel" | Check automático de contraste por `color_scheme` na conformância; alvo de toque mínimo validado no size. |

---

## 9. Feito quando (por fase)

- **H0** — `Theme` expõe as escalas de token + tema de marca customizável; um
  componente lê um token e ambos os renderers produzem o mesmo visual;
  conformância pina os tokens.
- **H1** — `Button` com `variant`/`size`/`color_scheme` + 4 estados renderiza
  idêntico (dentro das divergências documentadas) nos dois renderers; resolução
  `→Style` unit-testada; contraste WCAG AA e touch-target ≥ 48dp validados.
- **H2–H5** — cada componente do catálogo (entrada, superfície, feedback,
  navegação) aceita variant/size/color_scheme, preserva `Semantics`/RTL, passa
  na conformância e aparece na galeria.
- **H6** — um app de exemplo mostra resultado do `ort-vision-sdk` num
  `DetectionOverlay` + `MetricCard` + gráfico, nos dois renderers (device quando
  houver hardware).
- **H7** — galeria navegável + docs bilíngues tutorial-first publicadas; dark
  mode + RTL verificados; gate verde nos dois repos.

---

## 10. Relação com os outros trilhos

- **Consome E9** (tema/dark/MediaQuery, `text_scale`/`font_asset`, RTL,
  Semantics) como base de tokens, responsividade, espelhamento e a11y.
- **Consome E7** (canvas) para os wrappers de gráfico de H6.
- **Consome E5** (inputs) como base do kit de entrada de H2.
- **Consome E0** (navegação) como base dos hosts estilizados de H5.
- **Casa com o Trilho G** (inferência ONNX): H6 dá a UI de validação que o
  pesquisador usa para ver os resultados do modelo.
