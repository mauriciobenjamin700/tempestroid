# tempestroid — task runner. `make` (or `make help`) lists targets.
#
# Trilho A (pure Python) targets run anywhere `uv` is installed. The Android
# (Trilho B) targets need an Android SDK/NDK host + a connected arm64 device;
# they are no-ops/failures in a bare WSL session (see CLAUDE.md "Layout").

# ---- config -----------------------------------------------------------------
APP        ?= examples/counter/app.py
ANDROID    := android-host
GRADLEW    := ./gradlew
# F7 — headless x86_64 emulator target. AVD name + the adb serial it boots as.
AVD        ?= pixel8_api34
EMU_SERIAL ?= emulator-5554
# This host: SDK/NDK live here (not the stale ANDROID_HOME). Override if needed.
ANDROID_SDK_ROOT ?= /usr/lib/android-sdk
# Version read from pyproject (single source of truth) for tagging.
VERSION    := $(shell grep -m1 '^version' pyproject.toml | cut -d'"' -f2)

.DEFAULT_GOAL := help
SHELL := bash

# ---- meta -------------------------------------------------------------------
.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---- setup ------------------------------------------------------------------
.PHONY: sync
sync: ## Install core + dev deps (Qt sim included)
	uv sync

# ---- quality gates ----------------------------------------------------------
.PHONY: lint
lint: ## ruff check
	uv run ruff check .

.PHONY: format
format: ## ruff auto-fix + format
	uv run ruff check --fix .
	uv run ruff format .

.PHONY: typecheck
typecheck: ## pyright (strict)
	uv run pyright

.PHONY: test
test: ## pytest (full suite)
	uv run pytest

.PHONY: gate
gate: ## Full framework-guard gate (ruff + pyright + pytest + conventions + docs)
	bash .claude/skills/framework-guard/check.sh

.PHONY: quick
quick: ## Fast gate (lint + types + conventions, no pytest)
	bash .claude/skills/framework-guard/check.sh --quick

.PHONY: docs-sync
docs-sync: ## Verify README tracks live exports / CLI / phase tables
	uv run python .claude/skills/docs-sync-check/check.py

.PHONY: dual-verify
dual-verify: ## Enforced dual-renderer check (Qt gate + device build/flow checklist) (APP=...)
	bash .claude/skills/dual-verify/verify.sh $(APP)

.PHONY: parity
parity: ## Trilho E phase scaffold + gate (PHASE=E0|E2a|...)
	bash .claude/skills/parity-phase/plan.sh $(PHASE)

# ---- run / dev --------------------------------------------------------------
.PHONY: run
run: ## Run an app in the Qt simulator (APP=examples/counter/app.py)
	uv run python $(APP)

.PHONY: dev
dev: ## tempest dev: simulator + hot restart (APP=...)
	uv run tempest dev $(APP)

.PHONY: serve
serve: ## tempest serve: LAN code-push to a device + auto launch in dev mode (APP=...)
	uv run tempest serve $(APP)

.PHONY: spec
spec: ## Print the typed contract as JSON
	uv run tempest spec

# ---- docs site --------------------------------------------------------------
.PHONY: docs-build
docs-build: ## Build MkDocs site (--strict)
	uv run mkdocs build --strict

.PHONY: docs-serve
docs-serve: ## Serve MkDocs site locally
	uv run mkdocs serve

.PHONY: docs-shots
docs-shots: ## Render a PNG of every widget/component into docs/assets/components
	QT_QPA_PLATFORM=offscreen uv run python tools/shoot_docs.py

# ---- python package build ---------------------------------------------------
.PHONY: build
build: ## Build sdist + wheel into dist/ (bundles the host APK if staged)
	@test -f tempestroid/_assets/host.apk \
		|| echo "WARN: tempestroid/_assets/host.apk missing — wheel won't bundle the host; run 'make stage-host' (needs 'make apk' first)."
	uv build

# ---- release ----------------------------------------------------------------
.PHONY: bump
bump: ## Bump version in pyproject (PART=patch|minor|major, default patch)
	@PART="$${PART:-patch}" python toolchain/bump_version.py

.PHONY: release
release: gate docs-sync ## Attach host APK to a vX.Y.Z GitHub release + tag → triggers PyPI publish CI
	@echo "Releasing v$(VERSION)"
	@git diff --quiet || { echo "ERROR: working tree dirty — commit first"; exit 1; }
	@git rev-parse "v$(VERSION)" >/dev/null 2>&1 \
		&& { echo "ERROR: tag v$(VERSION) already exists"; exit 1; } || true
	@# The host APK (~100 MB: it embeds CPython) is too big for the PyPI wheel, so
	@# it ships as a GitHub release asset that `tempest install`/`deploy` download
	@# (cached). Create the release WITH the asset, which creates + pushes the tag;
	@# that single push triggers the publish workflow (lean wheel → PyPI).
	@test -f "$(HOST_APK)" || { echo "ERROR: $(HOST_APK) not found — run 'make apk' (needs the Android toolchain) before releasing"; exit 1; }
	cp "$(HOST_APK)" "$(dir $(HOST_APK))$(HOST_ASSET)"
	gh release create "v$(VERSION)" "$(dir $(HOST_APK))$(HOST_ASSET)" \
		--title "v$(VERSION)" --notes "tempestroid v$(VERSION)"
	@echo "released v$(VERSION) with $(HOST_ASSET) — `tempest install` downloads it"

# ---- android (Trilho B — needs SDK/NDK + device) ----------------------------
.PHONY: doctor
doctor: ## Validate the Android toolchain (SDK/NDK/Gradle/JDK/device/staging)
	bash .claude/skills/android-doctor/check.sh

.PHONY: toolchain
toolchain: ## Fetch CPython 3.14 + build wheels + stage device site-packages
	cd toolchain && source env.sh && ./00_fetch_cpython.sh && ./01_build_wheels.sh && ./02_stage_deps.sh

.PHONY: compose-test
compose-test: ## F7 camada B: JVM screen tests of the Compose renderer (no device/emulator)
	cd $(ANDROID) && ANDROID_SDK_ROOT=$(ANDROID_SDK_ROOT) $(GRADLEW) :app:testDebugUnitTest

.PHONY: compose-shots
compose-shots: ## Record Roborazzi golden PNGs of the Compose renderer (opt-in)
	cd $(ANDROID) && ANDROID_SDK_ROOT=$(ANDROID_SDK_ROOT) $(GRADLEW) :app:recordRoborazziDebug -Ptempest.roborazzi=true

.PHONY: apk
apk: ## Build debug APK (assembleDebug)
	cd $(ANDROID) && ANDROID_SDK_ROOT=$(ANDROID_SDK_ROOT) $(GRADLEW) :app:assembleDebug

.PHONY: install
install: ## adb install the debug APK onto a connected device (from-source build)
	cd $(ANDROID) && ANDROID_SDK_ROOT=$(ANDROID_SDK_ROOT) $(GRADLEW) :app:installDebug

.PHONY: install-host
install-host: ## tempest install: fetch + install the prebuilt host APK (no SDK/NDK)
	uv run tempest install

# The built host APK, the bundled asset path, and the release-asset name.
HOST_APK       := $(ANDROID)/app/build/outputs/apk/debug/app-debug.apk
BUNDLED_HOST   := tempestroid/_assets/host.apk
HOST_ASSET     := tempest-host-$(VERSION).apk

.PHONY: stage-host
stage-host: ## Copy the built host APK into the package so the wheel bundles it
	@test -f "$(HOST_APK)" || { echo "ERROR: $(HOST_APK) not found — run 'make apk' first"; exit 1; }
	@mkdir -p $(dir $(BUNDLED_HOST))
	cp "$(HOST_APK)" "$(BUNDLED_HOST)"
	@echo "staged $(BUNDLED_HOST) — `make build` will bundle it into the wheel"

.PHONY: publish-host
publish-host: ## Upload the built host APK to the GitHub release (download fallback for unstaged installs)
	@test -f "$(HOST_APK)" || { echo "ERROR: $(HOST_APK) not found — run 'make apk' first"; exit 1; }
	@gh release view "v$(VERSION)" >/dev/null 2>&1 \
		|| gh release create "v$(VERSION)" --title "v$(VERSION)" --notes "tempestroid v$(VERSION)"
	@# `gh release upload file#label` sets only the asset *label*, not its download
	@# name (which stays the file's basename), so `tempest install` — which fetches
	@# .../v<version>/tempest-host-<version>.apk — would 404. Upload a file already
	@# named like the asset instead.
	cp "$(HOST_APK)" "$(dir $(HOST_APK))$(HOST_ASSET)"
	gh release upload "v$(VERSION)" "$(dir $(HOST_APK))$(HOST_ASSET)" --clobber
	@echo "published $(HOST_ASSET) as the tempest install download fallback"

.PHONY: apk-install
apk-install: apk install ## Build + install the debug APK

.PHONY: logcat
logcat: ## Tail device logs for the host process
	adb logcat -s tempest:V python:V AndroidRuntime:E

# ---- emulator target (F7 — headless x86_64, no physical device) -------------
# Run + verify a tempestroid app on a HEADLESS x86_64 emulator, so no physical
# device is required. Every adb/gradle/serve step targets the emulator EXPLICITLY
# (-s $(EMU_SERIAL) / ANDROID_SERIAL) since a physical device may ALSO be attached.

EMU_APK := $(ANDROID)/app/build/outputs/apk/debug/app-debug.apk

.PHONY: emulator
emulator: ## Boot the headless x86_64 AVD if it's not already running (AVD=pixel8_api34)
	@if adb devices | grep -q '^$(EMU_SERIAL)[[:space:]]*device$$'; then \
		echo "emulator $(EMU_SERIAL) already running"; \
	else \
		echo "==> booting AVD $(AVD) headless as $(EMU_SERIAL)"; \
		ANDROID_SDK_ROOT=$(ANDROID_SDK_ROOT) setsid $(ANDROID_SDK_ROOT)/emulator/emulator \
			-avd $(AVD) -no-window -no-audio -no-boot-anim \
			-gpu swiftshader_indirect -no-snapshot -read-only \
			>/tmp/tempest-emulator.log 2>&1 & \
		echo "==> waiting for $(EMU_SERIAL) to come online"; \
		adb -s $(EMU_SERIAL) wait-for-device; \
		echo "==> waiting for sys.boot_completed=1"; \
		until [ "$$(adb -s $(EMU_SERIAL) shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do \
			sleep 2; \
		done; \
		echo "emulator $(EMU_SERIAL) booted"; \
	fi

.PHONY: stage-x86
stage-x86: ## Stage the x86_64 CPython prefix + site-packages for the emulator (F7)
	bash toolchain/stage_emulator_runtime.sh

.PHONY: apk-x86
apk-x86: ## Build the x86_64 debug APK (emulator target, F7)
	cd $(ANDROID) && ANDROID_SDK_ROOT=$(ANDROID_SDK_ROOT) $(GRADLEW) :app:assembleDebug \
		-Ptempest.abi=x86_64 \
		-Ptempest.pythonPrefix=../toolchain/dist/python/x86_64 \
		-Ptempest.depsDir=../toolchain/dist/site-packages-x86_64

.PHONY: emulator-verify
emulator-verify: ## End-to-end: boot emulator → stage-x86 → apk-x86 → install → serve APP → screenshot (F7)
	bash toolchain/emulator_verify.sh "$(APP)"

# ---- housekeeping -----------------------------------------------------------
.PHONY: clean
clean: ## Remove build/test/cache artifacts
	rm -rf dist site .ruff_cache .pytest_cache .mypy_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
