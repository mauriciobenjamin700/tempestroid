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
        ndk { abiFilters += abi }
        externalNativeBuild {
            cmake {
                arguments += "-DPYTHON_VERSION=$pythonVersion"
                arguments += "-DPYTHON_PREFIX_DIR=${pythonPrefix.absolutePath}"
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

    externalNativeBuild {
        cmake {
            path = file("src/main/c/CMakeLists.txt")
            version = "3.22.1"
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
    }
}

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

    @get:OutputDirectory
    abstract val outputDir: DirectoryProperty

    @TaskAction
    fun stage() {
        val version = pythonVersion.get()
        fs.copy {
            // Nest under "python/" so the packaged assets tree is
            // assets/python/lib/python<ver>/... — MainActivity.extractAssets
            // lists the "python" subtree and copies it to filesDir/python.
            from(stdlibDir) {
                into("python/lib/python$version")
                // Trim the stdlib to shrink the APK/AAB: drop the regression
                // test suites, the IDLE editor, Tk/turtle (no Tk on Android),
                // packaging tooling (ensurepip/venv/lib2to3), the build config
                // dir (Makefile/static lib — not used at runtime), docs data and
                // bytecode caches. None are needed to run a tempestroid app; this
                // cuts the bundled CPython roughly in half.
                exclude(
                    "**/test/**", "**/tests/**", "test/**", "tests/**",
                    "idlelib/**", "**/idle_test/**",
                    "tkinter/**", "turtledemo/**", "turtle.py",
                    "ensurepip/**", "venv/**", "lib2to3/**",
                    "config-*/**", "**/__pycache__/**", "**/*.pyc", "**/*.pyo",
                    "pydoc_data/**", "**/__phello__/**", "__hello__.py",
                )
            }
            rename("""(.*)\.gz$""", "$1.gz-")
            into(outputDir)
        }
    }
}

val targetAbi = abi
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

    @get:OutputDirectory
    abstract val outputDir: DirectoryProperty

    @TaskAction
    fun stage() {
        val sp = "python/lib/python${pythonVersion.get()}/site-packages"
        fs.copy {
            from(depsDir) { into(sp) }
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

val copyPythonLibs by tasks.registering(CopyPythonLibsTask::class) {
    libDir.fileValue(file("$pythonPrefix/lib"))
    abiName.set(targetAbi)
    outputDir.set(layout.buildDirectory.dir("generated/jniLibs"))
}

val pyVer = pythonVersion
val copyPythonStdlib by tasks.registering(CopyPythonStdlibTask::class) {
    stdlibDir.fileValue(file("$pythonPrefix/lib/python$pyVer"))
    pythonVersion.set(pyVer)
    outputDir.set(layout.buildDirectory.dir("generated/assets/python"))
}

val sitePackagesDir = rootProject.file("../toolchain/dist/site-packages")
val tempestroidCore = rootProject.file("../tempestroid")
val copyPythonSitePackages by tasks.registering(CopyPythonSitePackagesTask::class) {
    depsDir.fileValue(sitePackagesDir)
    coreSrc.fileValue(tempestroidCore)
    pythonVersion.set(pyVer)
    outputDir.set(layout.buildDirectory.dir("generated/assets/site-packages"))
}

androidComponents {
    onVariants { variant ->
        variant.sources.jniLibs?.addGeneratedSourceDirectory(
            copyPythonLibs, CopyPythonLibsTask::outputDir
        )
        variant.sources.assets?.addGeneratedSourceDirectory(
            copyPythonStdlib, CopyPythonStdlibTask::outputDir
        )
        variant.sources.assets?.addGeneratedSourceDirectory(
            copyPythonSitePackages, CopyPythonSitePackagesTask::outputDir
        )
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
    implementation("androidx.compose.material:material-icons-extended")
    // Async image loading for the `Image`/`Svg` widgets (URL/asset src).
    implementation("io.coil-kt:coil-compose:2.7.0")

    // E7 media + graphics ------------------------------------------------------
    // Media3/ExoPlayer — Google's official Android video playback stack (replaces
    // the standalone ExoPlayer); backs the `VideoPlayer` widget via PlayerView.
    implementation("androidx.media3:media3-exoplayer:1.4.1")
    implementation("androidx.media3:media3-ui:1.4.1")
    // CameraX — AndroidX camera; PreviewView + lifecycle binding back the
    // `CameraPreview` and `QrScanner` widgets (CAMERA perm already in manifest).
    implementation("androidx.camera:camera-core:1.4.0")
    implementation("androidx.camera:camera-camera2:1.4.0")
    implementation("androidx.camera:camera-view:1.4.0")
    implementation("androidx.camera:camera-lifecycle:1.4.0")
    // ML Kit barcode scanning — decodes QR/barcodes off the CameraX ImageAnalysis
    // frames for the `QrScanner` widget (no DIY alternative; Google's standard lib).
    implementation("com.google.mlkit:barcode-scanning:17.3.0")
    // androidx.lifecycle.compose.LocalLifecycleOwner — needed to bind CameraX to
    // the composition's lifecycle (CameraPreview/QrScanner).
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.6")

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
    // The google-services Gradle plugin is applied CONDITIONALLY at the top of
    // this file when a `google-services.json` is present, so the host builds
    // without a Firebase project; drop the JSON into android-host/app/ to enable
    // real FCM tokens. Without it FirebaseApp never initialises and PushModule
    // replies `error="not_configured"` — see NativeModules.handlePush.
    implementation("com.google.firebase:firebase-messaging:24.0.1")
    // MapView is a documented PLACEHOLDER on both leaves: Google Maps Compose would
    // require google-services.json + a Maps API key (APK won't build without it),
    // which is out of scope for the host skeleton. Wiring it is a post-phase task:
    // implementation("com.google.maps.android:maps-compose:6.1.0")
    // implementation("com.google.android.gms:play-services-maps:19.0.0")
}
