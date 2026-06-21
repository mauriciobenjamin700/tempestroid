// Root build script. Plugin versions are declared here and applied in :app.
// Reconfirm AGP / Kotlin versions against the installed Android Studio / SDK.
plugins {
    id("com.android.application") version "8.7.0" apply false
    id("org.jetbrains.kotlin.android") version "2.0.20" apply false
    // Kotlin 2.0+ ships the Compose compiler as a standalone plugin (versioned
    // in lockstep with Kotlin), replacing kotlinCompilerExtensionVersion.
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.20" apply false
    // FCM (E8 PushModule): applied by :app ONLY when a google-services.json is
    // present, so the host still builds without a Firebase project. Declared here
    // (apply false) so the version resolves when :app conditionally applies it.
    id("com.google.gms.google-services") version "4.4.2" apply false
    // F7 camada B (optional): Roborazzi screen-test plugin for JVM golden images of
    // the Compose renderer. Applied by :app ONLY when -Ptempest.roborazzi=true, so
    // the default JVM-unit-test gate stays lean (deterministic asserts, no
    // Robolectric runtime download). Declared apply-false so the version resolves.
    id("io.github.takahirom.roborazzi") version "1.32.0" apply false
}
