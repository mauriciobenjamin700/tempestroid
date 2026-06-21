import org.gradle.api.DefaultTask
import org.gradle.api.file.DirectoryProperty
import org.gradle.api.file.FileSystemOperations
import org.gradle.api.provider.Property
import org.gradle.api.tasks.Input
import org.gradle.api.tasks.InputDirectory
import org.gradle.api.tasks.OutputDirectory
import org.gradle.api.tasks.TaskAction
import javax.inject.Inject

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// F7 camada B (optional): apply the Roborazzi screen-test plugin only when asked
// (`-Ptempest.roborazzi=true`). Off by default so the gate runs the lean
// deterministic-assert tests without pulling the Robolectric runtime.
val roborazziEnabled = (project.findProperty("tempest.roborazzi")?.toString() == "true")
if (roborazziEnabled) {
    apply(plugin = "io.github.takahirom.roborazzi")
}

// FCM (E8): apply the google-services plugin ONLY when a google-services.json is
// present, so the host builds without a Firebase project (the PushModule then
// replies `not_configured`). Drop a google-services.json into android-host/app/
// to enable real FCM tokens — the plugin processes it and initialises FirebaseApp.
if (file("google-services.json").exists()) {
    apply(plugin = "com.google.gms.google-services")
    logger.lifecycle("google-services.json present — FCM enabled (google-services applied)")
}

val pythonVersion = (project.findProperty("tempest.pythonVersion") ?: "3.14").toString()
val abi = (project.findProperty("tempest.abi") ?: "arm64-v8a").toString()
// Toolchain paths are relative to the android-host root (rootProject), not the
// :app module dir — so `../toolchain` resolves to the sibling toolchain/ tree.
val pythonPrefix = rootProject.file((project.findProperty("tempest.pythonPrefix") ?: "../toolchain/dist/python/arm64-v8a").toString())
val wheelsDir = rootProject.file((project.findProperty("tempest.wheelsDir") ?: "../toolchain/dist/wheels").toString())

// --- Prebuilt-natives build mode -------------------------------------------
// `-Ptempest.prebuiltHost=<DIR>` points at an *extracted* tempestroid host APK
// (the CLI unzips a cached host APK into a temp dir and passes it). When set, the
// build REUSES the natives + stdlib + deps already inside that APK instead of
// re-staging the CPython-Android toolchain — so it needs only the JDK + Android
// SDK (NO NDK, NO CPython toolchain): nothing is compiled from C.
//
// Expected <DIR> layout (matches an unzipped APK, see CLI extractor):
//   <DIR>/lib/arm64-v8a/                       libpython3.14.so, libpython3.so,
//                                              libcrypto_python.so, libsqlite3_python.so,
//                                              libssl_python.so, libtempest_host.so
//   <DIR>/assets/python/lib/python<ver>/       full CPython stdlib + lib-dynload/ + site-packages/
//                                              (already trimmed, .gz already renamed .gz- by AGP)
//
// When the property is UNSET the default source-build path stays byte-for-byte
// unchanged (CMake builds libtempest_host.so, toolchain/dist supplies the rest).
val prebuiltHostDir: File? =
    (project.findProperty("tempest.prebuiltHost")?.toString())?.let { rootProject.file(it) }
val isPrebuilt = prebuiltHostDir != null

// --- Feature gating (F4) ----------------------------------------------------
// `-Ptempest.features=camera,qr,push,video` (CSV; empty = lean default) selects
// which heavy optional Android dependencies + the code/manifest that uses them
// are built in. Without it the APK ships lean (~25-30 MB) and the gated widgets
// render a "<feature> not built" placeholder; gated native handlers reply
// `feature_not_built`. `qr` requires `camera` (ML Kit runs on the camera preview),
// resolved transitively below (and defensively even if the CLI didn't).
val rawFeatures: Set<String> = (project.findProperty("tempest.features") as String?)
    ?.split(",")?.map { it.trim().lowercase() }?.filter { it.isNotEmpty() }?.toSet()
    .orEmpty()
val features: Set<String> = buildSet {
    addAll(rawFeatures)
    if ("qr" in rawFeatures) add("camera")  // ML Kit decodes the CameraX preview.
}
// Whether the camera dependency stack + manifest are needed (camera or qr).
val needsCamera = "camera" in features
logger.lifecycle("tempest.features = ${features.sorted().joinToString(",").ifEmpty { "(lean)" }}")

android {
    namespace = "org.tempestroid.host"
    compileSdk = 35

    defaultConfig {
        // applicationId / version are overridable so `tempest build --release`
        // can stamp the user's own store identity (the Java/JNI package stays
        // `org.tempestroid.host` via `namespace` above — applicationId is
        // independent of it, so the JNI symbol names are unaffected).
        applicationId =
            (project.findProperty("tempest.applicationId") ?: "org.tempestroid.host").toString()
        // Per-app launcher label (the name under the icon). `tempest build` passes
        // -Ptempest.appLabel so two tempestroid apps are told apart on the device;
        // defaults to the host name for a bare Gradle build. Resolved into the
        // manifest's android:label="${appLabel}" placeholder.
        manifestPlaceholders["appLabel"] =
            (project.findProperty("tempest.appLabel") ?: "tempestroid host").toString()
        minSdk = 24          // CPython 3.14 Android minimum (API 24)
        targetSdk = 35
        versionCode =
            (project.findProperty("tempest.versionCode") ?: "1").toString().toInt()
        versionName =
            (project.findProperty("tempest.versionName") ?: "0.0.1").toString()
        // Expose the active feature CSV to Kotlin for runtime checks if useful.
        buildConfigField(
            "String",
            "TEMPEST_FEATURES",
            "\"${features.sorted().joinToString(",")}\"",
        )
        ndk { abiFilters += abi }
        // In prebuilt mode nothing is compiled from C — the prebuilt
        // libtempest_host.so is reused — so the CMake configuration is skipped
        // entirely (no NDK / no CPython headers required).
        if (!isPrebuilt) {
            externalNativeBuild {
                cmake {
                    arguments += "-DPYTHON_VERSION=$pythonVersion"
                    arguments += "-DPYTHON_PREFIX_DIR=${pythonPrefix.absolutePath}"
                }
            }
        }
    }

    // Store .so uncompressed and page-aligned so they can be mmap'd from the APK
    // (the "open .so from APK" trick). Required alongside the lib/<abi>/ layout.
    packaging {
        jniLibs.useLegacyPackaging = false
    }

    // AAPT's DEFAULT ignore pattern contains `<dir>_*`, which silently drops any
    // asset directory starting with "_" — e.g. pydantic/_internal/. Override it
    // to keep underscore dirs (Python packages rely on them) while still ignoring
    // VCS/editor junk and __pycache__.
    androidResources {
        ignoreAssetsPattern = "!.svn:!.git:!.ds_store:!*.scc:!CVS:!thumbs.db:!picasa.ini:!*~:!__pycache__"
    }

    // Register the CMake project ONLY in source-build mode. Omitting it in
    // prebuilt mode means AGP never invokes the NDK toolchain (the prebuilt
    // libtempest_host.so is staged into jniLibs instead).
    if (!isPrebuilt) {
        externalNativeBuild {
            cmake {
                path = file("src/main/c/CMakeLists.txt")
                version = "3.22.1"
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    // Release signing for the store AAB (`tempest build --release`). The keystore
    // is passed in via gradle properties; when absent, the release build stays
    // unsigned (the CLI generates/uses a keystore and supplies these).
    val keystorePath = project.findProperty("tempest.keystore")?.toString()
    signingConfigs {
        if (keystorePath != null) {
            create("release") {
                storeFile = file(keystorePath)
                storePassword = project.findProperty("tempest.storePassword")?.toString()
                keyAlias = project.findProperty("tempest.keyAlias")?.toString()
                keyPassword = project.findProperty("tempest.keyPassword")?.toString()
            }
        }
    }

    buildTypes {
        getByName("release") {
            isMinifyEnabled = false  // R8 would strip Python-reflected classes
            if (keystorePath != null) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    // --- F7 camada B: JVM screen tests of the Compose renderer -----------------
    // Robolectric-backed unit tests need merged Android resources and tolerate
    // calls into unmocked android.* (e.g. android.util.Log) by returning defaults
    // rather than throwing. The actual tempestroid tests assert on the PURE
    // Style → Modifier/Arrangement/Alignment/Color mapping functions, which do not
    // touch the Android framework — but the flags keep Robolectric-style tests
    // (and any future Roborazzi screen test) runnable in the same source set.
    testOptions {
        unitTests.isIncludeAndroidResources = true
        unitTests.isReturnDefaultValues = true
    }

    // The Roborazzi screen tests import Roborazzi/Robolectric, so their source
    // lives in a dedicated dir added to the test source set ONLY when the opt-in
    // flag is set (else they would fail to compile without those deps).
    if (roborazziEnabled) {
        sourceSets.getByName("test").java.srcDir("src/test/roborazzi")
    }

    // --- Feature source-set selection (F4) ----------------------------------
    // Each gated piece exists twice with an IDENTICAL signature: the real impl in
    // src/feat_<f>/java and a placeholder in src/stub_<f>/java. src/main's `when`
    // / module router call them by name, so it compiles against whichever set is
    // active. We add the real srcDir when the feature is on, else the stub.
    fun selectFeature(name: String, active: Boolean) {
        val dir = if (active) "src/feat_$name/java" else "src/stub_$name/java"
        sourceSets.getByName("main").java.srcDir(dir)
    }
    selectFeature("camera", needsCamera)
    selectFeature("qr", "qr" in features)
    selectFeature("video", "video" in features)
    selectFeature("push", "push" in features)
    // `vision` (Trilho G): real OnnxModule (onnxruntime-android AAR) in
    // src/feat_vision, else the feature_not_built stub in src/stub_vision.
    selectFeature("vision", "vision" in features)

    // The generated, feature-composed manifest replaces the lean base for `main`.
    sourceSets.getByName("main").manifest.srcFile(
        layout.buildDirectory.file("generated/tempest/AndroidManifest.xml").get().asFile
    )
}

// --- Feature manifest generator (F4) ----------------------------------------
// AGP auto-merges manifests only for build types / flavors, not for arbitrary
// added java srcDirs, so a per-source-set AndroidManifest.xml is NOT picked up.
// Instead we compose the final `main` manifest at configuration time from the
// lean base (src/main/AndroidManifest.xml) + per-feature XML fragments, injecting
// them at marker points, and point sourceSets["main"].manifest at the result.
// This keeps the lean APK from referencing any class/service of an absent dep
// (the FCM <service> is only present when `push` is built).
val baseManifestFile = file("src/main/AndroidManifest.xml")
val generatedManifest =
    layout.buildDirectory.file("generated/tempest/AndroidManifest.xml")

val generateFeatureManifest by tasks.registering {
    inputs.file(baseManifestFile)
    inputs.property("features", features.sorted().joinToString(","))
    val cameraPerms = file("src/feat_camera/manifest/permissions.xml")
    val cameraApp = file("src/feat_camera/manifest/application.xml")
    val pushApp = file("src/feat_push/manifest/application.xml")
    if (needsCamera) { inputs.file(cameraPerms); inputs.file(cameraApp) }
    if ("push" in features) inputs.file(pushApp)
    val outFile = generatedManifest
    outputs.file(outFile)
    doLast {
        var xml = baseManifestFile.readText()
        // Inject the camera/qr permissions just before the <application> tag.
        if (needsCamera) {
            val perms = cameraPerms.readText().trimEnd()
            xml = xml.replaceFirst(
                "    <application",
                "    $perms\n\n    <application",
            )
        }
        // Inject the per-feature <application> children at the marker comment.
        val appEntries = buildString {
            if (needsCamera) appendLine(cameraApp.readText().trimEnd())
            if ("push" in features) appendLine(pushApp.readText().trimEnd())
        }.trimEnd()
        val marker =
            "        <!-- TEMPEST_FEATURE_APPLICATION_ENTRIES:"
        if (appEntries.isNotEmpty()) {
            val indented = appEntries.lines().joinToString("\n") { "        $it" }
            // Replace the marker comment line (and continuation) wholesale, keeping
            // it simple: insert the entries right before the marker.
            xml = xml.replaceFirst(marker, "$indented\n\n$marker")
        }
        val out = outFile.get().asFile
        out.parentFile.mkdirs()
        out.writeText(xml)
    }
}

// Make every variant's manifest-processing depend on the generator so the file
// exists before AGP reads sourceSets["main"].manifest.
tasks.matching {
    it.name.startsWith("process") && it.name.contains("Manifest")
}.configureEach { dependsOn(generateFeatureManifest) }
// Also gate compile/package on it (defensive: the manifest path is consumed early).
tasks.matching { it.name.startsWith("pre") && it.name.endsWith("Build") }
    .configureEach { dependsOn(generateFeatureManifest) }

// --- Staging tasks: expose a DirectoryProperty output so AGP's -------------
// `addGeneratedSourceDirectory` can wire them as generated jniLibs/assets dirs
// (it requires `(Task) -> DirectoryProperty`, which a bare `Copy` task does not
// provide). `FileSystemOperations` is injected so the copy stays
// configuration-cache friendly.

/**
 * Stage `libpython*.so` (and bundled `lib*_python.so`) into a generated jniLibs
 * dir. AGP treats the registered dir as the jniLibs root, so the `.so` files
 * must live under an `<abi>/` subdirectory (else AGP reads the file name as an
 * ABI and fails the native-libs merge).
 */
abstract class CopyPythonLibsTask @Inject constructor(
    private val fs: FileSystemOperations,
) : DefaultTask() {
    @get:InputDirectory
    abstract val libDir: DirectoryProperty

    @get:Input
    abstract val abiName: Property<String>

    @get:OutputDirectory
    abstract val outputDir: DirectoryProperty

    @TaskAction
    fun stage() {
        val abi = abiName.get()
        fs.copy {
            from(libDir) {
                include("libpython*.so", "lib*_python.so")
                into(abi)
            }
            into(outputDir)
        }
    }
}

/**
 * Stage the CPython stdlib into a generated assets dir.
 *
 * AAPT auto-decompresses any asset ending in ".gz" and would corrupt stdlib data
 * files, so they are renamed with a trailing "-" (MainActivity reverses this on
 * extraction). Mirrors the CPython testbed's build.gradle.kts.
 */
abstract class CopyPythonStdlibTask @Inject constructor(
    private val fs: FileSystemOperations,
) : DefaultTask() {
    @get:InputDirectory
    abstract val stdlibDir: DirectoryProperty

    @get:Input
    abstract val pythonVersion: Property<String>

    // Prebuilt mode: the source tree was already trimmed + had its .gz files
    // renamed .gz- by a prior APK build, and bundles its own site-packages/. So
    // copy it verbatim (no trim, no rename) and exclude site-packages — the
    // site-packages task stages those (deps from here, tempestroid from source).
    @get:Input
    abstract val prebuilt: Property<Boolean>

    // Globs for every NON-target ABI's compiled extensions (G7) — excluded so an
    // ABI switch / prebuilt host can't leak foreign `.so` into this APK's assets.
    @get:Input
    abstract val foreignAbiSoGlobs: ListProperty<String>

    @get:OutputDirectory
    abstract val outputDir: DirectoryProperty

    @TaskAction
    fun stage() {
        val version = pythonVersion.get()
        val isPrebuilt = prebuilt.get()
        val foreignSo = foreignAbiSoGlobs.get()
        // Rebuild from scratch: the generated dir is AGP-relocated and survives
        // ABI switches, so without this an x86_64 run's .so linger into an arm64
        // build (and vice-versa). Clearing it makes the staged tree reflect only
        // this run's (single-ABI) source.
        fs.delete { delete(outputDir) }
        fs.copy {
            // Nest under "python/" so the packaged assets tree is
            // assets/python/lib/python<ver>/... — MainActivity.extractAssets
            // lists the "python" subtree and copies it to filesDir/python.
            from(stdlibDir) {
                into("python/lib/python$version")
                if (isPrebuilt) {
                    // Already-prepared stdlib from an extracted host APK: keep
                    // it as-is; only drop the bundled site-packages (staged by
                    // CopyPythonSitePackagesTask) and any caches.
                    exclude(
                        "site-packages/**",
                        "**/__pycache__/**", "**/*.pyc", "**/*.pyo",
                    )
                } else {
                    // Trim the stdlib to shrink the APK/AAB: drop the regression
                    // test suites, the IDLE editor, Tk/turtle (no Tk on Android),
                    // packaging tooling (ensurepip/venv/lib2to3), the build config
                    // dir (Makefile/static lib — not used at runtime), docs data and
                    // bytecode caches. None are needed to run a tempestroid app; this
                    // cuts the bundled CPython roughly in half. (F6 APK trim.)
                    exclude(
                        // Regression test suites + the IDLE editor.
                        "**/test/**", "**/tests/**", "test/**", "tests/**",
                        "idlelib/**", "**/idle_test/**",
                        // Tk/turtle GUI (no Tk on Android) + the turtle demo.
                        "tkinter/**", "turtledemo/**", "turtle.py",
                        // Packaging / install tooling — never run on device.
                        "ensurepip/**", "venv/**", "lib2to3/**",
                        // Build config dir (Makefile/static lib), docs data, caches,
                        // the frozen "hello" example modules.
                        "config-*/**", "**/__pycache__/**", "**/*.pyc", "**/*.pyo",
                        "pydoc_data/**", "**/__phello__/**", "__hello__.py",
                        // F6: pure-Python modules with no device use — the new
                        // interactive REPL (_pyrepl), the WSGI reference server
                        // (wsgiref), the doctest framework and the pydoc CLI. None
                        // are imported by the framework / pydantic runtime (verified
                        // off-device with an import trace); apps run headless with no
                        // REPL, no WSGI, no doctest. ~0.4 MB.
                        "_pyrepl/**", "wsgiref/**", "doctest.py", "pydoc.py",
                        // F6: lib-dynload test/example extension modules. These are
                        // CPython's own C-API test harnesses + the "xx" example
                        // extensions — never importable by an app at runtime. ~0.9 MB.
                        "lib-dynload/_test*.so",
                        "lib-dynload/_xxtestfuzz*.so",
                        "lib-dynload/xxsubtype*.so",
                        "lib-dynload/xxlimited*.so",
                    )
                }
                // Drop every non-target ABI's compiled extensions (G7 trim) — in
                // both modes, so a prebuilt host or an ABI switch can't leak them.
                exclude(foreignSo)
            }
            // The .gz files in an extracted APK are ALREADY renamed .gz- (AGP did
            // it on the host build); re-renaming would produce .gz--. Only rename
            // in source mode.
            if (!isPrebuilt) {
                rename("""(.*)\.gz$""", "$1.gz-")
            }
            into(outputDir)
        }
    }
}

val targetAbi = abi

// Foreign-ABI dead weight (G7 APK trim). Compiled CPython extensions carry their
// ABI in the filename (`*.cpython-314-<tag>-linux-android.so`, tag = aarch64 /
// x86_64 / arm / i686). The APK runs on exactly ONE ABI (`abiFilters += abi`
// restricts the native lib/<abi>/ libs), so any extension built for ANOTHER ABI
// that lands in assets/python is pure dead weight — it can never be loaded.
// It leaks in two ways: a prebuilt host whose site-packages already holds both
// ABIs, and — the one that bit us — the generated-assets dir ACCUMULATING across
// ABI switches in one checkout (build x86_64 for the emulator, then arm64 for the
// release, and the arm64 APK still carries the stale x86_64 .so). Measured: a
// ~11.6 MB foreign payload in the x86_64 emulator APK. The fix excludes every
// non-target ABI's extension at the copy step, so only the target ABI's .so are
// ever staged regardless of how the source dir got populated.
val knownPyAbiTags = listOf("aarch64", "x86_64", "arm", "i686")
val targetPyAbiTag = when (targetAbi) {
    "arm64-v8a" -> "aarch64"
    "x86_64" -> "x86_64"
    "armeabi-v7a" -> "arm"
    "x86" -> "i686"
    else -> ""
}
// Fail-safe: only strip foreign ABIs when the target tag is RECOGNIZED. A typo'd
// `-Ptempest.abi` (e.g. "arm64" instead of "arm64-v8a") would otherwise leave the
// target tag unmatched, and excluding "everything except an unknown tag" would
// drop the REAL target's extensions too — a blank-screen APK. Unknown ABI =>
// strip nothing (ship as-is) rather than risk that.
val foreignAbiSoGlobsValue: List<String> =
    if (targetPyAbiTag in knownPyAbiTags) {
        knownPyAbiTags
            .filter { it != targetPyAbiTag }
            .map { "**/*-$it-linux-android.so" }
    } else {
        emptyList()
    }

/**
 * Stage the device site-packages: the pre-built deps (pydantic + pydantic_core
 * Android wheel + friends, from `toolchain/dist/site-packages`) plus the Qt-free
 * tempestroid core copied fresh from `src/`. Lands under
 * assets/python/lib/python<ver>/site-packages so the bundled interpreter can
 * `import tempestroid` and `import pydantic`.
 */
abstract class CopyPythonSitePackagesTask @Inject constructor(
    private val fs: FileSystemOperations,
) : DefaultTask() {
    @get:InputDirectory
    abstract val depsDir: DirectoryProperty

    @get:InputDirectory
    abstract val coreSrc: DirectoryProperty

    @get:Input
    abstract val pythonVersion: Property<String>

    // Prebuilt mode: depsDir is the host APK's bundled site-packages, which also
    // contains a tempestroid/ copy — exclude it so the framework is re-staged
    // FRESH from the source tree (coreSrc), matching the source-build behaviour.
    @get:Input
    abstract val prebuilt: Property<Boolean>

    // Globs for every NON-target ABI's compiled extensions (G7) — excluded so a
    // prebuilt host carrying both ABIs (or an ABI switch) can't leak foreign
    // `.so` (e.g. pydantic_core, numpy) into this APK's assets.
    @get:Input
    abstract val foreignAbiSoGlobs: ListProperty<String>

    @get:OutputDirectory
    abstract val outputDir: DirectoryProperty

    @TaskAction
    fun stage() {
        val sp = "python/lib/python${pythonVersion.get()}/site-packages"
        val isPrebuilt = prebuilt.get()
        val foreignSo = foreignAbiSoGlobs.get()
        // Rebuild from scratch (the generated dir survives ABI switches).
        fs.delete { delete(outputDir) }
        fs.copy {
            from(depsDir) {
                into(sp)
                // Drop every non-target ABI's compiled extensions (G7 trim).
                exclude(foreignSo)
                if (isPrebuilt) {
                    exclude("tempestroid/**", "**/__pycache__/**", "**/*.pyc", "**/*.pyo")
                }
            }
            from(coreSrc) {
                into("$sp/tempestroid")
                // The Qt renderer needs PySide6 (absent on device). The CLI is
                // kept: it imports Qt lazily, and the B5 dev client reuses its
                // app loader (spec_from_source). Everything else is pure core.
                // CRITICAL: drop `_assets/` — it holds the ~100 MB prebuilt host
                // APK (staged for the desktop `tempest install`); copying it here
                // would bake a full copy of the host into the host itself (~80 MB
                // of dead weight). It is never needed on-device.
                exclude(
                    "renderers/qt/**", "_assets/**",
                    "**/__pycache__/**", "**/*.pyc", "**/*.pyo",
                )
            }
            into(outputDir)
        }
    }
}

val pyVer = pythonVersion

// Source dirs differ by mode. In prebuilt mode every input comes from the
// extracted host APK (<DIR>); in source mode they come from toolchain/dist + src.
val libsSourceDir = if (isPrebuilt) {
    File(prebuiltHostDir, "lib/$targetAbi")
} else {
    file("$pythonPrefix/lib")
}
val stdlibSourceDir = if (isPrebuilt) {
    File(prebuiltHostDir, "assets/python/lib/python$pyVer")
} else {
    file("$pythonPrefix/lib/python$pyVer")
}
// `-Ptempest.depsDir=<DIR>` overrides the source-build site-packages dir so a
// non-default ABI (e.g. the x86_64 emulator target, F7) can point at its own
// staging (../toolchain/dist/site-packages-x86_64) without clobbering the arm64
// one. Defaults to the current arm64 path, so existing arm64 builds are
// byte-for-byte unchanged. (Ignored in prebuilt mode — deps come from the APK.)
val depsSourceDir = if (isPrebuilt) {
    File(prebuiltHostDir, "assets/python/lib/python$pyVer/site-packages")
} else {
    rootProject.file(
        (project.findProperty("tempest.depsDir") ?: "../toolchain/dist/site-packages").toString()
    )
}
val tempestroidCore = rootProject.file("../tempestroid")

val copyPythonLibs by tasks.registering(CopyPythonLibsTask::class) {
    // The include pattern (libpython*.so + lib*_python.so) matches exactly the
    // CPython runtime set in BOTH layouts and never picks up libtempest_host.so
    // or the androidx/camera/mlkit libs sitting in the prebuilt lib/<abi> dir.
    libDir.fileValue(libsSourceDir)
    abiName.set(targetAbi)
    outputDir.set(layout.buildDirectory.dir("generated/jniLibs"))
}

val copyPythonStdlib by tasks.registering(CopyPythonStdlibTask::class) {
    stdlibDir.fileValue(stdlibSourceDir)
    pythonVersion.set(pyVer)
    prebuilt.set(isPrebuilt)
    foreignAbiSoGlobs.set(foreignAbiSoGlobsValue)
    outputDir.set(layout.buildDirectory.dir("generated/assets/python"))
}

val copyPythonSitePackages by tasks.registering(CopyPythonSitePackagesTask::class) {
    depsDir.fileValue(depsSourceDir)
    coreSrc.fileValue(tempestroidCore)
    pythonVersion.set(pyVer)
    prebuilt.set(isPrebuilt)
    foreignAbiSoGlobs.set(foreignAbiSoGlobsValue)
    outputDir.set(layout.buildDirectory.dir("generated/assets/site-packages"))
}

// Prebuilt-only: reuse the host APK's already-compiled libtempest_host.so (the
// JNI shim) instead of building it via CMake/NDK. Same generated-jniLibs shape
// as copyPythonLibs (the .so must sit under <abi>/).
abstract class CopyPrebuiltTempestHostTask @Inject constructor(
    private val fs: FileSystemOperations,
) : DefaultTask() {
    @get:InputDirectory
    abstract val libDir: DirectoryProperty

    @get:Input
    abstract val abiName: Property<String>

    @get:OutputDirectory
    abstract val outputDir: DirectoryProperty

    @TaskAction
    fun stage() {
        val abi = abiName.get()
        fs.copy {
            from(libDir) {
                include("libtempest_host.so")
                into(abi)
            }
            into(outputDir)
        }
    }
}

val copyPrebuiltTempestHost = if (isPrebuilt) {
    tasks.register("copyPrebuiltTempestHost", CopyPrebuiltTempestHostTask::class) {
        libDir.fileValue(libsSourceDir)
        abiName.set(targetAbi)
        outputDir.set(layout.buildDirectory.dir("generated/jniLibsTempestHost"))
    }
} else {
    null
}

// F7 camada B: the CPython staging source dirs (toolchain/dist + the natives
// prefix) are produced by `make toolchain` and are NOT needed to RUN the JVM unit
// tests of the renderer (`:app:testDebugUnitTest`) — only to assemble a runnable
// APK. When they are absent (a checkout that only runs the camada-B gate, e.g. CI
// before staging), wiring them as generated assets/jniLibs makes even unit tests
// fail at config-time (the @InputDirectory existence check). So register the
// generated source dirs ONLY when the staging inputs exist. When they exist (any
// device/emulator build) the wiring is byte-for-byte unchanged.
val pythonStagingPresent: Boolean =
    libsSourceDir.exists() && stdlibSourceDir.exists() && depsSourceDir.exists()
if (!pythonStagingPresent) {
    logger.lifecycle(
        "tempest: CPython staging dirs absent — skipping jniLibs/assets staging " +
            "(JVM unit tests run; `make toolchain` to build a runnable APK).",
    )
}

androidComponents {
    onVariants { variant ->
        if (pythonStagingPresent) {
            variant.sources.jniLibs?.addGeneratedSourceDirectory(
                copyPythonLibs, CopyPythonLibsTask::outputDir
            )
            copyPrebuiltTempestHost?.let {
                variant.sources.jniLibs?.addGeneratedSourceDirectory(
                    it, CopyPrebuiltTempestHostTask::outputDir
                )
            }
            variant.sources.assets?.addGeneratedSourceDirectory(
                copyPythonStdlib, CopyPythonStdlibTask::outputDir
            )
            variant.sources.assets?.addGeneratedSourceDirectory(
                copyPythonSitePackages, CopyPythonSitePackagesTask::outputDir
            )
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")

    // Jetpack Compose device renderer (B4). The BOM pins the module versions.
    val composeBom = platform("androidx.compose:compose-bom:2024.09.03")
    implementation(composeBom)
    implementation("androidx.activity:activity-compose:1.9.2")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.foundation:foundation")
    // Animation engine (E3): AnimatedVisibility, InfiniteTransition,
    // SharedTransitionLayout/sharedElement (shared-element Hero transitions, 1.7+).
    implementation("androidx.compose.animation:animation")
    implementation("androidx.compose.material3:material3")
    // Named Material icons for the `Icon` widget (string name -> vector glyph).
    // Only the curated core set is needed: `iconFor()` in TempestRenderer.kt maps
    // 22 names to `Icons.Filled.*` glyphs that all ship in `material-icons-core`
    // (transitive via material3), and the real source of truth is the inlined SVG
    // `iconPath` prop from `tempestroid/icons.py`. Dropping `-extended` (~9 MB DEX)
    // costs nothing — no extended glyph is referenced (F4 trim, cut #1).
    implementation("androidx.compose.material:material-icons-core")
    // Async image loading for the `Image`/`Svg` widgets (URL/asset src).
    implementation("io.coil-kt:coil-compose:2.7.0")

    // E7 media + graphics — FEATURE-GATED (F4). These are the heavy DEX blocks the
    // lean APK drops; only added when their feature is in -Ptempest.features. The
    // matching src/feat_<f> source set provides the real renderer/handler, else
    // src/stub_<f> provides a placeholder, so src/main compiles either way.
    if ("video" in features) {
        // Media3/ExoPlayer — Google's official Android video playback stack; backs
        // the `VideoPlayer` widget via PlayerView (src/feat_video).
        implementation("androidx.media3:media3-exoplayer:1.4.1")
        implementation("androidx.media3:media3-ui:1.4.1")
    }
    if (needsCamera) {
        // CameraX — PreviewView + lifecycle binding back the `CameraPreview`
        // (src/feat_camera) and `QrScanner` (src/feat_qr) widgets.
        implementation("androidx.camera:camera-core:1.4.0")
        implementation("androidx.camera:camera-camera2:1.4.0")
        implementation("androidx.camera:camera-view:1.4.0")
        implementation("androidx.camera:camera-lifecycle:1.4.0")
        // androidx.lifecycle.compose.LocalLifecycleOwner — bind CameraX to the
        // composition's lifecycle (CameraPreview/QrScanner).
        implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.6")
    }
    if ("qr" in features) {
        // ML Kit barcode scanning — decodes QR/barcodes off the CameraX
        // ImageAnalysis frames for the `QrScanner` widget (src/feat_qr).
        implementation("com.google.mlkit:barcode-scanning:17.3.0")
    }
    if ("vision" in features) {
        // ONNX Runtime Android (Trilho G) — the native inference engine the
        // OnnxModule (src/feat_vision) drives over the request/response native
        // channel for the Python AarBackend. The AAR bundles a per-ABI .so for
        // all Android ABIs; the `defaultConfig { ndk { abiFilters += abi } }`
        // above already restricts the packaged natives to the single target ABI
        // (x86_64 on the emulator, arm64-v8a on device), so the AAR contributes
        // only one ABI's library to the final APK (no all-ABI bloat).
        implementation("com.microsoft.onnxruntime:onnxruntime-android:1.26.0")
    }

    // E8 platform + system native --------------------------------------------
    // ProcessLifecycleOwner — app-wide foreground/background lifecycle for the
    // LifecycleModule (dispatches __lifecycle__ stream tokens to Python).
    implementation("androidx.lifecycle:lifecycle-process:2.8.6")
    // BiometricPrompt (fingerprint/face) for the BiometricsModule. Includes the
    // pre-30 compat shims; targets API 23+ (host mins API 24, so always available).
    implementation("androidx.biometric:biometric:1.1.0")
    // EncryptedSharedPreferences (AES-256) for the SecureStorageModule. Requires
    // API 23+ (host mins 24). 1.1.0-alpha06 is the last stable-ish release that
    // builds cleanly under AGP 8.7 (the 1.1.x line is the only one with
    // EncryptedSharedPreferences; the 1.0.0 line lacks the Tink upgrade).
    implementation("androidx.security:security-crypto:1.1.0-alpha06")
    // WorkManager — PeriodicWorkRequest backs the BackgroundModule's scheduled
    // tasks (enqueueUniquePeriodicWork / cancelUniqueWork).
    implementation("androidx.work:work-runtime-ktx:2.9.1")
    // Firebase Cloud Messaging — the PushModule reads the FCM registration token.
    // FEATURE-GATED (F4): only added when `push` is in -Ptempest.features (the real
    // handler + TempestMessagingService live in src/feat_push; src/stub_push replies
    // feature_not_built). The google-services Gradle plugin is applied CONDITIONALLY
    // at the top of this file when a `google-services.json` is present, so even the
    // push build works without a Firebase project; drop the JSON into
    // android-host/app/ to enable real FCM tokens. Without it FirebaseApp never
    // initialises and PushModule replies `error="not_configured"`.
    if ("push" in features) {
        implementation("com.google.firebase:firebase-messaging:24.0.1")
    }
    // MapView is a documented PLACEHOLDER on both leaves: Google Maps Compose would
    // require google-services.json + a Maps API key (APK won't build without it),
    // which is out of scope for the host skeleton. Wiring it is a post-phase task:
    // implementation("com.google.maps.android:maps-compose:6.1.0")
    // implementation("com.google.android.gms:play-services-maps:19.0.0")

    // --- F7 camada B: JVM unit tests of the Compose renderer -------------------
    // These pin the KOTLIN consumption of the `Style → Compose` spec — the
    // mapping the renderer does from the serialized style map to Compose
    // Modifier/Arrangement/Alignment/Color values and the mount/patch envelope
    // parse in TempestTree — running on the JVM in seconds (no device/emulator),
    // complementing the phase-D conformance suite (which pins the Python side
    // `to_compose`).
    //
    // JUnit4 is the runner; the Compose BOM (declared above for `implementation`)
    // is re-pinned here so the test classpath resolves `androidx.compose.ui.*`
    // value types (Color/Dp/Arrangement/Alignment) the asserts compare against.
    // `ui-test-junit4` is included so a future Roborazzi/`createComposeRule`
    // screen test can live in the same source set without another dependency
    // change; the current tests assert on the pure mapping functions only.
    testImplementation("junit:junit:4.13.2")
    // The mount/patch envelope parse in TempestTree uses org.json, which on the
    // JVM unit-test classpath is otherwise the empty Android stub (every method
    // returns a default → NPE on the fluent `put(...)` chain even with
    // isReturnDefaultValues=true). The real reference implementation makes the
    // parse path exercise actual JSON, matching the device's bundled org.json.
    testImplementation("org.json:json:20240303")
    testImplementation(composeBom)
    testImplementation("androidx.compose.ui:ui")
    testImplementation("androidx.compose.ui:ui-graphics")
    testImplementation("androidx.compose.foundation:foundation")
    testImplementation("androidx.compose.material3:material3")
    testImplementation("androidx.compose.ui:ui-unit")
    testImplementation("androidx.compose.ui:ui-test-junit4")

    // --- F7 camada B (optional): Roborazzi golden screen tests ----------------
    // Only on the test classpath when -Ptempest.roborazzi=true. They render the
    // actual @Composable via Robolectric (off-device) and record/compare PNG
    // goldens under app/src/test/screenshots/. Robolectric downloads its
    // android-all runtime on first run, so this path is opt-in (the default
    // deterministic-assert tests stay lean and network-free).
    if (roborazziEnabled) {
        testImplementation("org.robolectric:robolectric:4.13")
        testImplementation("io.github.takahirom.roborazzi:roborazzi:1.32.0")
        testImplementation("io.github.takahirom.roborazzi:roborazzi-compose:1.32.0")
        testImplementation("androidx.compose.ui:ui-test-manifest")
    }
}
