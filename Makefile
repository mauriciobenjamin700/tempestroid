# tempestroid — task runner. `make` (or `make help`) lists targets.
#
# Trilho A (pure Python) targets run anywhere `uv` is installed. The Android
# (Trilho B) targets need an Android SDK/NDK host + a connected arm64 device;
# they are no-ops/failures in a bare WSL session (see CLAUDE.md "Layout").

# ---- config -----------------------------------------------------------------
APP        ?= examples/counter/app.py
ANDROID    := android-host
GRADLEW    := ./gradlew
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
release: gate docs-sync ## Tag vX.Y.Z (from pyproject) + push → triggers PyPI publish CI
	@echo "Releasing v$(VERSION)"
	@git diff --quiet || { echo "ERROR: working tree dirty — commit first"; exit 1; }
	@git rev-parse "v$(VERSION)" >/dev/null 2>&1 \
		&& { echo "ERROR: tag v$(VERSION) already exists"; exit 1; } || true
	git tag -a "v$(VERSION)" -m "release: v$(VERSION)"
	git push origin "v$(VERSION)"

# ---- android (Trilho B — needs SDK/NDK + device) ----------------------------
.PHONY: toolchain
toolchain: ## Fetch CPython 3.14 + build wheels + stage device site-packages
	cd toolchain && source env.sh && ./00_fetch_cpython.sh && ./01_build_wheels.sh && ./02_stage_deps.sh

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
	gh release upload "v$(VERSION)" "$(HOST_APK)#$(HOST_ASSET)" --clobber
	@echo "published $(HOST_ASSET) as the tempest install download fallback"

.PHONY: apk-install
apk-install: apk install ## Build + install the debug APK

.PHONY: logcat
logcat: ## Tail device logs for the host process
	adb logcat -s tempest:V python:V AndroidRuntime:E

# ---- housekeeping -----------------------------------------------------------
.PHONY: clean
clean: ## Remove build/test/cache artifacts
	rm -rf dist site .ruff_cache .pytest_cache .mypy_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
