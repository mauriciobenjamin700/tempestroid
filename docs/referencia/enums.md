# Enums

Os enums do tempestroid são constantes tipadas que descrevem intenção — valores
como `AlignItems.CENTER`, `FontWeight.BOLD` ou `Curve.EASE_IN_OUT` viajam como
strings para o renderizador (Qt ou Compose) e para a ponte nativa. Todos são
importáveis do nível do pacote:

```python
from tempestroid import AlignItems, FontWeight, JustifyContent, Style
```

Cada membro expõe um atributo `.value` com o valor string (ou inteiro) que cruza
a fronteira; use sempre o nome de membro (`AlignItems.CENTER`), não o `.value`
cru.

**Exemplo rápido:**

```python
from tempestroid import AlignItems, FlexDirection, FontWeight, JustifyContent, Style

estilo = Style(
    direction=FlexDirection.COLUMN,
    justify=JustifyContent.SPACE_BETWEEN,
    align=AlignItems.CENTER,
)

texto = Style(
    font_weight=FontWeight.SEMIBOLD,
    font_size=18.0,
)
```

---

## Layout e flexbox

### AlignItems

Controla o alinhamento dos filhos no **eixo transversal** (cross-axis), equivalente
à propriedade CSS `align-items`.

| Membro | Valor | Significado |
|---|---|---|
| `START` | `"start"` | Filhos alinhados ao início do eixo transversal. |
| `END` | `"end"` | Filhos alinhados ao fim do eixo transversal. |
| `CENTER` | `"center"` | Filhos centralizados no eixo transversal. |
| `STRETCH` | `"stretch"` | Filhos esticados para preencher o eixo transversal. |

### JustifyContent

Distribui o espaço entre os filhos no **eixo principal**, equivalente a
`justify-content` do CSS.

| Membro | Valor | Significado |
|---|---|---|
| `START` | `"start"` | Filhos agrupados no início do eixo principal. |
| `END` | `"end"` | Filhos agrupados no fim do eixo principal. |
| `CENTER` | `"center"` | Filhos centralizados no eixo principal. |
| `SPACE_BETWEEN` | `"space-between"` | Espaço igual entre filhos; sem margem nas bordas. |
| `SPACE_AROUND` | `"space-around"` | Espaço igual ao redor de cada filho. |
| `SPACE_EVENLY` | `"space-evenly"` | Espaço idêntico entre todos os pontos (incluindo bordas). |

### FlexDirection

Define a direção do eixo principal do contêiner flex.

| Membro | Valor | Significado |
|---|---|---|
| `ROW` | `"row"` | Filhos dispostos em linha (horizontal). |
| `COLUMN` | `"column"` | Filhos dispostos em coluna (vertical). |

### FlexWrap

Controla se os filhos podem quebrar para a próxima linha quando o espaço acaba,
equivalente a `flex-wrap` do CSS. Usado pelo widget `Wrap` e pelo campo
`Style.flex_wrap`.

| Membro | Valor | Significado |
|---|---|---|
| `NOWRAP` | `"nowrap"` | Todos os filhos numa única linha; transborda se necessário. |
| `WRAP` | `"wrap"` | Filhos quebram para a próxima linha quando não há espaço. |
| `WRAP_REVERSE` | `"wrap-reverse"` | Como `WRAP`, mas a quebra ocorre na direção contrária. |

### Position

Controla o modo de posicionamento de um filho dentro de um `Stack`. Campos
`top`/`right`/`bottom`/`left` só têm efeito quando `position=Position.ABSOLUTE`.

| Membro | Valor | Significado |
|---|---|---|
| `STATIC` | `"static"` | Posicionamento normal no fluxo do layout. |
| `ABSOLUTE` | `"absolute"` | Posicionado com coordenadas explícitas relativas ao pai. |

### StackAlign

Alinha filhos **não posicionados** nos dois eixos dentro de um `Stack`.

| Membro | Valor | Significado |
|---|---|---|
| `TOP_START` | `"top_start"` | Canto superior esquerdo. |
| `TOP_CENTER` | `"top_center"` | Topo, centralizado horizontalmente. |
| `TOP_END` | `"top_end"` | Canto superior direito. |
| `CENTER_START` | `"center_start"` | Centralizado verticalmente, alinhado à esquerda. |
| `CENTER` | `"center"` | Centralizado nos dois eixos. |
| `CENTER_END` | `"center_end"` | Centralizado verticalmente, alinhado à direita. |
| `BOTTOM_START` | `"bottom_start"` | Canto inferior esquerdo. |
| `BOTTOM_CENTER` | `"bottom_center"` | Base, centralizado horizontalmente. |
| `BOTTOM_END` | `"bottom_end"` | Canto inferior direito. |

---

## Texto e fonte

### FontWeight

Peso da fonte em escala numérica CSS. Use `Style.font_weight`.

| Membro | Valor | Significado |
|---|---|---|
| `THIN` | `100` | Peso mais leve disponível. |
| `LIGHT` | `300` | Levemente mais fino que o normal. |
| `NORMAL` | `400` | Peso padrão. |
| `MEDIUM` | `500` | Levemente mais pesado que o normal. |
| `SEMIBOLD` | `600` | Negrito suave, bom para cabeçalhos secundários. |
| `BOLD` | `700` | Negrito padrão. |
| `BLACK` | `900` | Peso máximo. |

### FontStyle

Estilo da fonte. Use `Style.font_style`.

| Membro | Valor | Significado |
|---|---|---|
| `NORMAL` | `"normal"` | Fonte em estilo romano (padrão). |
| `ITALIC` | `"italic"` | Fonte em itálico. |

### TextAlign

Alinhamento horizontal do texto. Use `Style.text_align`.

| Membro | Valor | Significado |
|---|---|---|
| `LEFT` | `"left"` | Texto alinhado à esquerda. |
| `CENTER` | `"center"` | Texto centralizado. |
| `RIGHT` | `"right"` | Texto alinhado à direita. |
| `JUSTIFY` | `"justify"` | Texto justificado (bordas alinhadas em ambos os lados). |

### TextDecoration

Decoração de texto. Use `Style.text_decoration`.

| Membro | Valor | Significado |
|---|---|---|
| `NONE` | `"none"` | Sem decoração. |
| `UNDERLINE` | `"underline"` | Sublinhado. |
| `LINE_THROUGH` | `"line-through"` | Tachado. |

### TextOverflow

Comportamento quando o texto transborda o contêiner. Use `Style.text_overflow`.

| Membro | Valor | Significado |
|---|---|---|
| `CLIP` | `"clip"` | Texto cortado abruptamente no limite do contêiner. |
| `ELLIPSIS` | `"ellipsis"` | Texto cortado com reticências (`…`) no final. |

### KeyboardType

Tipo de teclado virtual exibido ao editar um `Input`. Use `Input.keyboard_type`.

| Membro | Valor | Significado |
|---|---|---|
| `TEXT` | `"text"` | Teclado alfanumérico padrão (padrão). |
| `NUMBER` | `"number"` | Teclado numérico. |
| `EMAIL` | `"email"` | Teclado otimizado para endereços de e-mail (sugere `@`). |
| `PHONE` | `"phone"` | Teclado de discagem telefônica. |
| `URL` | `"url"` | Teclado otimizado para URLs (sugere `.`/`/`). |
| `PASSWORD` | `"password"` | Oculta os caracteres digitados. |

---

## Cor, gradiente e imagem

### GradientDirection

Direção de um gradiente linear. Passado em `Gradient.direction`.

| Membro | Valor | Significado |
|---|---|---|
| `TOP_BOTTOM` | `"top-bottom"` | Do topo para a base. |
| `BOTTOM_TOP` | `"bottom-top"` | Da base para o topo. |
| `LEFT_RIGHT` | `"left-right"` | Da esquerda para a direita. |
| `RIGHT_LEFT` | `"right-left"` | Da direita para a esquerda. |

### ImageFit

Como a imagem preenche seu contêiner, equivalente a `object-fit` do CSS. Passado
em `Image.fit`.

| Membro | Valor | Significado |
|---|---|---|
| `CONTAIN` | `"contain"` | Imagem redimensionada para caber sem cortar (mantém proporção). |
| `COVER` | `"cover"` | Imagem redimensionada para cobrir todo o contêiner (pode cortar). |
| `FILL` | `"fill"` | Imagem esticada para preencher o contêiner (ignora proporção). |
| `NONE` | `"none"` | Sem redimensionamento; exibida em tamanho original. |

### ClipShape

Forma do recorte aplicado por `ClipPath`.

| Membro | Valor | Significado |
|---|---|---|
| `CIRCLE` | `"circle"` | Recorte circular (avatares, ícones redondos). |
| `ROUNDED_RECT` | `"rounded_rect"` | Retângulo com cantos arredondados. |
| `OVAL` | `"oval"` | Elipse — mais larga ou mais alta que um círculo. |

---

## Animação

### Curve

Curva de easing para `Transition` e para os controladores de animação do Trilho E.

| Membro | Valor | Significado |
|---|---|---|
| `LINEAR` | `"linear"` | Velocidade constante ao longo da animação. |
| `EASE_IN` | `"ease-in"` | Começa devagar, acelera até o fim. |
| `EASE_OUT` | `"ease-out"` | Começa rápido, desacelera até o fim. |
| `EASE_IN_OUT` | `"ease-in-out"` | Começa e termina devagar, acelerado no meio. |
| `EASE` | `"ease"` | Easing suave semelhante ao padrão CSS. |
| `BOUNCE` | `"bounce"` | Efeito de salto ao atingir o valor final. |
| `ELASTIC` | `"elastic"` | Ultrapassa levemente e retorna (mola). |

```python
from tempestroid import Color, Curve, Style, Transition

Style(
    background=Color.from_hex("#3b82f6"),
    transition=Transition(duration_ms=250, curve=Curve.EASE_IN_OUT),
)
```

---

## Tema e tela

### ThemeMode

Modo de tema da aplicação. Definido em `App.set_theme`.

| Membro | Valor | Significado |
|---|---|---|
| `LIGHT` | `"light"` | Tema claro forçado. |
| `DARK` | `"dark"` | Tema escuro forçado. |
| `SYSTEM` | `"system"` | Segue a preferência do sistema operacional. |

### Orientation

Orientação de tela solicitada. Passada em chamadas de plataforma.

| Membro | Valor | Significado |
|---|---|---|
| `PORTRAIT` | `"portrait"` | Orientação vertical. |
| `LANDSCAPE` | `"landscape"` | Orientação horizontal. |
| `AUTO` | `"auto"` | O sistema decide com base na posição do dispositivo. |

### StatusBarStyle

Estilo da barra de status (ícones claros ou escuros). Passado em chamadas de
plataforma.

| Membro | Valor | Significado |
|---|---|---|
| `LIGHT` | `"light"` | Ícones claros (para barras de status escuras). |
| `DARK` | `"dark"` | Ícones escuros (para barras de status claras). |

### SafeAreaEdge

Bordas a serem respeitadas pelo widget `SafeArea`. Combine múltiplos valores
passando uma lista a `SafeArea.edges`.

| Membro | Valor | Significado |
|---|---|---|
| `TOP` | `"top"` | Margem superior (barra de status / notch). |
| `RIGHT` | `"right"` | Margem direita (modo paisagem / câmera lateral). |
| `BOTTOM` | `"bottom"` | Margem inferior (barra de navegação / home indicator). |
| `LEFT` | `"left"` | Margem esquerda (modo paisagem). |

### Device

Predefinição de tela do simulador Qt. Passada para `run_qt(size=Device.PIXEL_8)`.
O valor de cada membro é o **nome de exibição** do aparelho; o simulador usa as
dimensões em dp correspondentes para dimensionar a janela.

**Famílias disponíveis:**

| Família | Membros |
|---|---|
| Google Pixel | `PIXEL_4`, `PIXEL_4A`, `PIXEL_5`, `PIXEL_6`, `PIXEL_6A`, `PIXEL_7`, `PIXEL_7A`, `PIXEL_8`, `PIXEL_8_PRO` |
| Samsung Galaxy S | `GALAXY_S8`, `GALAXY_S21`, `GALAXY_S22`, `GALAXY_S23`, `GALAXY_S23_ULTRA`, `GALAXY_S24`, `GALAXY_S24_ULTRA` |
| Samsung Galaxy A | `GALAXY_A51`, `GALAXY_A52`, `GALAXY_A54` |
| Redmi / Poco / Xiaomi | `REDMI_NOTE_10`, `REDMI_NOTE_11`, `REDMI_NOTE_12`, `REDMI_NOTE_13`, `REDMI_11`, `REDMI_12`, `POCO_X5`, `XIAOMI_13`, `XIAOMI_14` |
| Motorola | `MOTO_G_POWER`, `MOTO_G52` |
| OnePlus | `ONEPLUS_9`, `ONEPLUS_11` |

**Exemplo:**

```python
from tempestroid import Device
from tempestroid.renderers.qt import run_qt

# Simula um Pixel 8 (1080 × 2400 dp)
run_qt(state, view, title="Meu App", size=Device.PIXEL_8)
```

!!! tip "33 predefinições no total"
    Use `Device.<TAB>` no REPL para ver todas as opções disponíveis.

---

## Plataforma e sistema

### AppState

Estado do ciclo de vida do aplicativo, recebido em `LifecycleEvent.state`.

| Membro | Valor | Significado |
|---|---|---|
| `FOREGROUND` | `"foreground"` | App visível e em foco. |
| `BACKGROUND` | `"background"` | App em segundo plano (não visível). |
| `INACTIVE` | `"inactive"` | App visível mas sem foco (ex.: sobreposição de sistema). |

### ConnectivityState

Estado da conectividade de rede, recebido em `ConnectivityEvent.state`.

| Membro | Valor | Significado |
|---|---|---|
| `CONNECTED` | `"connected"` | Conectado a alguma rede. |
| `DISCONNECTED` | `"disconnected"` | Sem conectividade. |
| `WIFI` | `"wifi"` | Conectado via Wi-Fi. |
| `MOBILE` | `"mobile"` | Conectado via rede móvel (dados celulares). |

### PermissionStatus

Resultado de uma solicitação de permissão de plataforma.

| Membro | Valor | Significado |
|---|---|---|
| `GRANTED` | `"granted"` | Permissão concedida pelo usuário. |
| `DENIED` | `"denied"` | Permissão negada (pode ser solicitada novamente). |
| `PERMANENTLY_DENIED` | `"permanently_denied"` | Permissão negada permanentemente; direcione o usuário às configurações. |

### SensorType

Tipo de sensor físico para assinar via `native`. Passado ao registrar um
*callback* de sensor.

| Membro | Valor | Significado |
|---|---|---|
| `ACCELEROMETER` | `"accelerometer"` | Aceleração linear nos três eixos (m/s²). |
| `GYROSCOPE` | `"gyroscope"` | Velocidade de rotação nos três eixos (rad/s). |
| `MAGNETOMETER` | `"magnetometer"` | Campo magnético nos três eixos (μT). |
| `PRESSURE` | `"pressure"` | Pressão barométrica (hPa). |
| `LIGHT` | `"light"` | Nível de iluminância ambiente (lux). |
| `PROXIMITY` | `"proximity"` | Distância de um objeto próximo (cm ou binário). |
| `STEP_COUNTER` | `"step_counter"` | Contador de passos acumulado desde o último boot. |

### ImpactStyle

Intensidade do *haptic feedback* gerado por `native.haptics`. Passado em chamadas
de vibração.

| Membro | Valor | Significado |
|---|---|---|
| `LIGHT` | `"light"` | Toque suave (confirmações sutis). |
| `MEDIUM` | `"medium"` | Toque médio (interações padrão). |
| `HEAVY` | `"heavy"` | Toque forte (alertas ou ações destrutivas). |

---

## Gestos

### SwipeDirection

Direção de um gesto de deslize, recebido em `SwipeEvent.direction`.

| Membro | Valor | Significado |
|---|---|---|
| `LEFT` | `"left"` | Deslize para a esquerda. |
| `RIGHT` | `"right"` | Deslize para a direita. |
| `UP` | `"up"` | Deslize para cima. |
| `DOWN` | `"down"` | Deslize para baixo. |

---

## Recapitulando

- Importe sempre do nível do pacote: `from tempestroid import AlignItems, Curve`.
- Use o **nome de membro** (`FontWeight.BOLD`), não o valor string diretamente.
- O `.value` de cada membro é a string (ou inteiro) enviada ao renderizador e à
  ponte nativa — você raramente precisará acessá-la.
- Enums de layout (`AlignItems`, `JustifyContent`, `FlexDirection`, `FlexWrap`,
  `Position`, `StackAlign`) são campos de `Style`; os de plataforma (`AppState`,
  `ConnectivityState`, `SensorType`) chegam em eventos; `Device` dimensiona a
  janela do simulador.
- A referência completa de campos de `Style` está no [guia de estilos](../guia/estilos.md);
  os eventos que carregam esses enums estão no [guia de eventos](../guia/eventos.md).
