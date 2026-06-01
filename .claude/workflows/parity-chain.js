export const meta = {
  name: 'parity-chain',
  description: 'Roda FASES do Trilho E em série (uma fase por entrada). Otimizado: 1 architect/fase (decompõe todas as sub-tarefas), ir-core landa o contrato, Qt ‖ Compose em paralelo (dirs disjuntos), 1 passo de testes, 1 device-verify no fim da fase, 1 review. Sonnet nos agentes leves, Opus em quem escreve código. NÃO faz git/PR — para no fim para autorização humana.',
  phases: [
    { title: 'Plan', detail: 'phase-architect decompõe a fase inteira (Sonnet, read-only)' },
    { title: 'IR/core', detail: 'ir-core-specialist landa o contrato de TODAS as sub-tarefas core (Opus)' },
    { title: 'Renderers', detail: 'qt ‖ kotlin em paralelo (Opus, dirs disjuntos renderers/qt vs android-host)' },
    { title: 'Tests', detail: 'conformance-test-author 1× pela fase (Sonnet)' },
    { title: 'Device', detail: 'device-verifier 1× no fim, cobrindo todas as sub-tarefas (Sonnet, singleton)' },
    { title: 'Review', detail: 'phase-reviewer + gates (Sonnet)' },
  ],
}

// ---- structured-output schemas -------------------------------------------
const PHASE_PLAN_SCHEMA = {
  type: "object",
  properties: {
    contract: { type: "string", description: "Contrato consolidado da fase: assinaturas IR/eventos/Style + pontos de plug reais (§0.1)" },
    subtasks: {
      type: "array",
      description: "As sub-tarefas da fase (E<n>a/b/c/d) com escopo e camada",
      items: {
        type: "object",
        properties: {
          id: { type: "string" },
          layer: { type: "string", enum: ["core", "qt", "compose", "bridge", "mixed"] },
          scope: { type: "string" },
        },
        required: ["id", "layer", "scope"],
      },
    },
    files: { type: "array", items: { type: "string" }, description: "Mapa de arquivos por camada" },
    coreWork: { type: "string", description: "O que o ir-core deve implementar (todas as sub-tarefas core/bridge-Python)" },
    qtWork: { type: "string", description: "O que o qt-specialist deve implementar (só renderers/qt + seus testes)" },
    composeWork: { type: "string", description: "O que o kotlin-specialist deve implementar (só android-host)" },
    doneWhen: { type: "array", items: { type: "string" }, description: "Feito-quando da FASE inteira, testável" },
    needs: {
      type: "object",
      properties: {
        core: { type: "boolean" }, qt: { type: "boolean" }, compose: { type: "boolean" }, tests: { type: "boolean" }, device: { type: "boolean" },
      },
      required: ["core", "qt", "compose", "tests", "device"],
    },
    risks: { type: "string" },
  },
  required: ["contract", "subtasks", "coreWork", "doneWhen", "needs"],
  additionalProperties: true,
}

const STEP_SCHEMA = {
  type: "object",
  properties: {
    filesChanged: { type: "array", items: { type: "string" } },
    commandsRun: { type: "array", items: { type: "string" } },
    result: { type: "string", description: "pass/fail das verificações + contagem de testes" },
    divergences: { type: "string", description: "divergência Qt-vs-Compose que a conformância deve documentar" },
    gaps: { type: "string", description: "o que não pôde ser exercido" },
  },
  required: ["filesChanged", "result"],
  additionalProperties: true,
}

const DEVICE_SCHEMA = {
  type: "object",
  properties: {
    deviceConfirmed: { type: "boolean" },
    evidence: {
      type: "array",
      items: {
        type: "object",
        properties: { item: { type: "string" }, screenshot: { type: "string" }, pass: { type: "boolean" } },
        required: ["item", "pass"],
      },
    },
    notExercised: { type: "array", items: { type: "string" } },
    notes: { type: "string" },
  },
  required: ["deviceConfirmed", "evidence"],
  additionalProperties: true,
}

const REVIEW_SCHEMA = {
  type: "object",
  properties: {
    verdict: { type: "string", enum: ["APROVADO", "BLOQUEADO"] },
    blockers: { type: "array", items: { type: "string" } },
    findings: { type: "array", items: { type: "string" } },
    gates: { type: "string", description: "resultado do framework-guard + docs-sync" },
  },
  required: ["verdict", "gates"],
  additionalProperties: true,
}

// ---- task normalization ---------------------------------------------------
let parsed = args
if (typeof parsed === "string") {
  const s = parsed.trim()
  if (s === "" || s === "[]") { parsed = [] }
  else { try { parsed = JSON.parse(s) } catch (e) { parsed = [s] } }
}
const raw = Array.isArray(parsed) ? parsed : (parsed ? [parsed] : [])
if (!raw.length) {
  log("Nenhuma fase fornecida. Invoque com args: [{id:\"E1\",title:\"...\",description:\"...\"}, ...] ou [\"texto da fase\"].")
  return { ran: 0, results: [], note: "no-tasks" }
}

const norm = (t, i) => (typeof t === "string")
  ? { id: "P" + (i + 1), title: t.slice(0, 60), description: t }
  : { id: t.id || ("P" + (i + 1)), title: t.title || t.description || ("fase " + (i + 1)), description: t.description || t.title || "" }

const phasesIn = raw.map(norm)
const LIGHT = "sonnet" // architect/tests/device/review
log("parity-chain (otimizado): " + phasesIn.length + " fase(s) em série. architect 1×/fase, Qt‖Compose paralelo, device-verify 1× no fim. Sem git/PR.")

// ---- per-phase pipeline ---------------------------------------------------
const results = []
for (let p = 0; p < phasesIn.length; p++) {
  const phase = phasesIn[p]
  const tag = phase.id
  log("===== FASE " + tag + ": " + phase.title + " =====")

  // 1. Architect (Sonnet, read-only): decompõe a FASE inteira.
  const plan = await agent(
    "Você é o phase-architect do tempestroid (Trilho E). LEIA docs/plan-parity.md (§0, §0.1 e a seção desta fase inteira). "
      + "Decomponha a FASE inteira: liste as sub-tarefas (E<n>a/b/c/d) com camada e escopo, e separe o trabalho em coreWork (tudo que o ir-core faz: IR/eventos/state/bridge-Python/__init__/README — inclui a parte Python de sub-tarefas bridge), qtWork (SÓ renderers/qt + seus testes), composeWork (SÓ android-host/*.kt). Dê o contrato consolidado, o mapa de arquivos, o `needs` e o 'feito quando' da FASE. Read-only.\n\nFASE " + tag + ":\n" + phase.description,
    { agentType: "phase-architect", phase: "Plan", label: "plan:" + tag, model: LIGHT, schema: PHASE_PLAN_SCHEMA }
  )

  const needs = (plan && plan.needs) ? plan.needs : { core: true, qt: true, compose: true, tests: true, device: true }
  const base = "CONTRATO DA FASE (architect):\n" + JSON.stringify(plan) + "\n\nFASE " + tag + ":\n" + phase.description
  const step = { id: tag, title: phase.title, plan, needs }

  // 2. IR/core (Opus): landa o contrato de TODAS as sub-tarefas core/bridge-Python.
  if (needs.core) {
    step.ir = await agent(
      "Você é o ir-core-specialist. Implemente TODA a metade IR/core/regra-de-negócio da fase (coreWork do contrato): widgets, events frozen + event_schemas + parse_event, reconciler/diff, App/state, bridge serialize/protocol (parte Python), modelo Style, __init__ re-exports + __all__, README sync. NÃO implemente Style→Qt nem Style→Compose. Convenções (aspas duplas, typing estrito, docstring EN). Verifique: pytest + pyright + `tempest spec`.\n\nCOREWORK:\n" + ((plan && plan.coreWork) || "(ver contrato)") + "\n\n" + base,
      { agentType: "ir-core-specialist", phase: "IR/core", label: "ir:" + tag, schema: STEP_SCHEMA }
    )
  }

  const ctx = base + (step.ir ? "\n\nIR ENTREGUE:\n" + JSON.stringify(step.ir) : "")

  // 3. Qt ‖ Compose em paralelo (Opus). Dirs disjuntos → mesma árvore, sem worktree.
  //    Qt edita SÓ renderers/qt (+ não toca __init__/tests, que são do ir-core/tests).
  //    Kotlin edita SÓ android-host. assembleDebug confirma compile; o EXERCÍCIO no
  //    device fica para o device-verifier único (corta um install/boot).
  const renderJobs = []
  if (needs.qt) {
    renderJobs.push(() => agent(
      "Você é o qt-renderer-specialist. Implemente SÓ a metade Qt da fase (qtWork): Style→Qt + widgets no renderers/qt/. EDITE SOMENTE arquivos em tempestroid/renderers/qt/ — NÃO toque __init__.py de pacotes, widgets/ ou tests/ (são de outros agentes). Verifique: pytest offscreen dos seus alvos + pyright; `make run` se útil (WSL pode não ter display → diga explícito).\n\nQTWORK:\n" + ((plan && plan.qtWork) || "(ver contrato)") + "\n\n" + ctx,
      { agentType: "qt-renderer-specialist", phase: "Renderers", label: "qt:" + tag, schema: STEP_SCHEMA }
    ))
  }
  if (needs.compose) {
    renderJobs.push(() => agent(
      "Você é o kotlin-compose-specialist. Implemente SÓ a metade Compose/Kotlin da fase (composeWork): EDITE SOMENTE android-host/. Espelhe o spec Style→Compose e os envelopes do bridge; padrão B6 sem mudança de C quando possível. Confirme o COMPILE com `cd android-host && ANDROID_SDK_ROOT=/usr/lib/android-sdk ./gradlew :app:assembleDebug` (BUILD SUCCESSFUL). NÃO faça o exercício completo no device — isso é do device-verifier (passo único no fim da fase).\n\nCOMPOSEWORK:\n" + ((plan && plan.composeWork) || "(ver contrato)") + "\n\n" + ctx,
      { agentType: "kotlin-compose-specialist", phase: "Renderers", label: "kt:" + tag, schema: STEP_SCHEMA }
    ))
  }
  if (renderJobs.length) {
    const r = await parallel(renderJobs)
    if (needs.qt) step.qt = r[0]
    if (needs.compose) step.kt = needs.qt ? r[1] : r[0]
  }

  // 4. Testes + conformância (Sonnet) — 1× pela fase, fixa os DOIS tradutores.
  if (needs.tests) {
    step.tests = await agent(
      "Você é o conformance-test-author. Escreva unit tests + goldens de conformância que fixam os DOIS tradutores (to_compose + to_qss/layout_alignment) e o diff/eventos de TODA a fase. Só edite tests/. Verifique: pytest offscreen; regenere goldens com UPDATE_GOLDEN=1 e revise o diff.\n\n" + ctx,
      { agentType: "conformance-test-author", phase: "Tests", label: "tests:" + tag, model: LIGHT, schema: STEP_SCHEMA }
    )
  }

  // 5. Device-verify (Sonnet) — UM passo no fim, cobre todas as sub-tarefas.
  if (needs.device) {
    step.device = await agent(
      "Você é o device-verifier. UM passo único cobrindo TODAS as sub-tarefas device desta fase: build/install no aparelho físico (23053RN02A, Android 15; export ANDROID_SDK_ROOT=/usr/lib/android-sdk; make apk-install ou tempest serve), exercite cada fluxo do 'feito quando' e capture screenshots confirmando os pixels. Não edite código. Reporte por item com o screenshot; liste o não-exercitado.\n\nFEITO QUANDO (fase):\n" + JSON.stringify((plan && plan.doneWhen) || []) + "\n\nFASE " + tag + ":\n" + phase.description,
      { agentType: "device-verifier", phase: "Device", label: "device:" + tag, model: LIGHT, schema: DEVICE_SCHEMA }
    )
  }

  // 6. Review adversarial + gates (Sonnet).
  step.review = await agent(
    "Você é o phase-reviewer. Audite o diff da FASE contra o 'feito quando' + invariantes (1 reconciliador/2 renderizadores espelhados, contrato tipado, bridge sem-C quando possível) + convenções, e RODE os gates: framework-guard + docs-sync. Uma linha por achado, sem elogio. Veredito APROVADO/BLOQUEADO.\n\nPLANO/FEITO-QUANDO:\n" + JSON.stringify(plan) + "\n\nFASE " + tag + ":\n" + phase.description,
    { agentType: "phase-reviewer", phase: "Review", label: "review:" + tag, model: LIGHT, schema: REVIEW_SCHEMA }
  )

  results.push(step)
  log("FASE " + tag + " encerrada — review: " + (step.review && step.review.verdict ? step.review.verdict : "n/a"))
}

const blocked = results.filter(r => r.review && r.review.verdict === "BLOQUEADO").map(r => r.id)
log("parity-chain concluído. " + results.length + " fase(s). Bloqueadas: " + (blocked.length ? blocked.join(", ") : "nenhuma") + ". Aguardando autorização humana para commit/PR.")
return { ran: results.length, blocked, results }
