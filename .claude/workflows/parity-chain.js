export const meta = {
  name: 'parity-chain',
  description: 'Roda tasks do Trilho E em série pela cadeia de agentes (architect → ir-core → qt → kotlin → conformance → device-verify → review). Sem pausa entre tasks. NÃO faz git/PR — para no fim para autorização humana.',
  phases: [
    { title: 'Plan', detail: 'phase-architect decompõe a task (read-only)' },
    { title: 'IR/core', detail: 'ir-core-specialist landa o contrato' },
    { title: 'Qt', detail: 'qt-renderer-specialist' },
    { title: 'Compose', detail: 'kotlin-compose-specialist (usa o device)' },
    { title: 'Tests', detail: 'conformance-test-author' },
    { title: 'Device', detail: 'device-verifier (singleton, serial)' },
    { title: 'Review', detail: 'phase-reviewer + gates' },
  ],
}

// ---- structured-output schemas -------------------------------------------
const PLAN_SCHEMA = {
  type: "object",
  properties: {
    contract: { type: "string", description: "Contrato IR: widgets/events/Style novos + shape serializado" },
    files: { type: "array", items: { type: "string" }, description: "Mapa de arquivos por agente" },
    order: { type: "string", description: "Ordem de execução / o que é serial por tocar arquivo quente" },
    doneWhen: { type: "array", items: { type: "string" }, description: "Feito-quando concreto e testável" },
    risks: { type: "string" },
  },
  required: ["contract", "files", "doneWhen"],
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
        properties: {
          item: { type: "string" },
          screenshot: { type: "string" },
          pass: { type: "boolean" },
        },
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
// `args` pode chegar como valor JSON real OU como string (o harness às vezes
// serializa). Normaliza ambos: string vazia / "[]" → sem tasks; string JSON →
// parse; string simples → uma task; array/objeto → como está.
let parsed = args
if (typeof parsed === "string") {
  const s = parsed.trim()
  if (s === "" || s === "[]") {
    parsed = []
  } else {
    try { parsed = JSON.parse(s) } catch (e) { parsed = [s] }
  }
}
const raw = Array.isArray(parsed) ? parsed : (parsed ? [parsed] : [])
if (!raw.length) {
  log("Nenhuma task fornecida. Invoque com args: [\"texto da task 1\", \"texto da task 2\", ...] ou [{id,title,description}].")
  return { ran: 0, results: [], note: "no-tasks" }
}

const norm = (t, i) => (typeof t === "string")
  ? { id: "T" + (i + 1), title: t.slice(0, 60), description: t }
  : {
      id: t.id || ("T" + (i + 1)),
      title: t.title || t.description || ("task " + (i + 1)),
      description: t.description || t.title || "",
    }

const tasks = raw.map(norm)
log("parity-chain: " + tasks.length + " task(s) em série. Sem pausa entre elas; sem git/PR no fim.")

// ---- the serial agent chain, one task at a time ---------------------------
const results = []
for (let i = 0; i < tasks.length; i++) {
  const task = tasks[i]
  const tag = task.id
  log("===== Task " + tag + ": " + task.title + " =====")

  // 1. Architect (read-only) — produz o contrato que o resto consome.
  const plan = await agent(
    "Você é o phase-architect do tempestroid (Trilho E, docs/plan-parity.md). "
      + "Decomponha esta task num contrato IR + mapa de arquivos por agente + ordem de execução + checklist 'feito quando' testável. "
      + "Read-only: NÃO edite código.\n\nTASK " + tag + ":\n" + task.description,
    { agentType: "phase-architect", phase: "Plan", label: "plan:" + tag, schema: PLAN_SCHEMA }
  )

  const ctx = "CONTRATO DO ARQUITETO:\n" + JSON.stringify(plan) + "\n\nTASK " + tag + ":\n" + task.description

  // 2. IR/core — o contrato landa primeiro.
  const ir = await agent(
    "Você é o ir-core-specialist. Implemente SÓ a metade IR/core/regra-de-negócio (widgets, events frozen + event_schemas + parse_event, reconciler/diff, App/state, bridge, modelo Style, __init__ re-exports). "
      + "Defina os campos/eventos que os renderizadores vão consumir; não implemente Style→Qt nem Style→Compose. Honre as convenções (aspas duplas, typing estrito, docstring EN). Verifique com pytest+pyright+`tempest spec`.\n\n" + ctx,
    { agentType: "ir-core-specialist", phase: "IR/core", label: "ir:" + tag, schema: STEP_SCHEMA }
  )

  const ctx2 = ctx + "\n\nIR ENTREGUE:\n" + JSON.stringify(ir)

  // 3. Qt renderer.
  const qt = await agent(
    "Você é o qt-renderer-specialist. Implemente SÓ a metade Qt (Style→Qt em renderers/qt/translate.py, QtRenderer, app_runner/dev_loop), consumindo o contrato IR. "
      + "Verifique com pytest offscreen + pyright; abra janela Qt via `make run` se útil (em WSL pode não ter display → diga explícito).\n\n" + ctx2,
    { agentType: "qt-renderer-specialist", phase: "Qt", label: "qt:" + tag, schema: STEP_SCHEMA }
  )

  // 4. Kotlin/Compose (usa o device para build/install).
  const kt = await agent(
    "Você é o kotlin-compose-specialist. Implemente SÓ a metade Compose/Kotlin device (android-host/.../*.kt), espelhando o spec Style→Compose e os envelopes do bridge. Prefira o padrão B6 sem mudança de C. "
      + "Verifique com `make apk-install` (BUILD SUCCESSFUL + Installed) no device 23053RN02A; export ANDROID_SDK_ROOT=/usr/lib/android-sdk.\n\n" + ctx2,
    { agentType: "kotlin-compose-specialist", phase: "Compose", label: "kt:" + tag, schema: STEP_SCHEMA }
  )

  // 5. Testes + conformância (fixam os DOIS tradutores).
  const tests = await agent(
    "Você é o conformance-test-author. Escreva unit tests + goldens de conformância que fixam os DOIS tradutores (to_compose + to_qss/layout_alignment) e o diff/eventos desta task. Só edite tests/. "
      + "Verifique com pytest offscreen; regenere goldens com UPDATE_GOLDEN=1 e revise o diff.\n\n" + ctx2,
    { agentType: "conformance-test-author", phase: "Tests", label: "tests:" + tag, schema: STEP_SCHEMA }
  )

  // 6. Verificação on-device (device é singleton → sempre serial).
  const device = await agent(
    "Você é o device-verifier. Prove no aparelho físico (23053RN02A, Android 15) que esta task funciona: build/push (make apk-install ou tempest serve), exercite o fluxo, capture screenshots e confirme os pixels. Não edite código. "
      + "Reporte por item do 'feito quando' com o caminho do screenshot, e liste o que não pôde exercitar.\n\nFEITO QUANDO:\n" + JSON.stringify((plan && plan.doneWhen) || []) + "\n\nTASK " + tag + ":\n" + task.description,
    { agentType: "device-verifier", phase: "Device", label: "device:" + tag, schema: DEVICE_SCHEMA }
  )

  // 7. Review adversarial + gates (não edita; devolve veredito).
  const review = await agent(
    "Você é o phase-reviewer. Audite o diff desta task contra o 'feito quando' + invariantes (1 reconciliador/2 renderizadores espelhados, contrato tipado, bridge sem-C quando possível) + convenções, e RODE os gates: framework-guard + docs-sync. Uma linha por achado, sem elogio. Veredito final APROVADO/BLOQUEADO.\n\n"
      + "PLANO/FEITO-QUANDO:\n" + JSON.stringify(plan) + "\n\nTASK " + tag + ":\n" + task.description,
    { agentType: "phase-reviewer", phase: "Review", label: "review:" + tag, schema: REVIEW_SCHEMA }
  )

  results.push({ id: tag, title: task.title, plan, ir, qt, kt, tests, device, review })
  log("Task " + tag + " encerrada — review: " + (review && review.verdict ? review.verdict : "n/a"))
}

const blocked = results.filter(r => r.review && r.review.verdict === "BLOQUEADO").map(r => r.id)
log("parity-chain concluído. " + results.length + " task(s). Bloqueadas: " + (blocked.length ? blocked.join(", ") : "nenhuma") + ". Aguardando autorização humana para commit/PR.")
return { ran: results.length, blocked, results }
