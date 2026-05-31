// Root build script. Plugin versions are declared here and applied in :app.
// Reconfirm AGP / Kotlin versions against the installed Android Studio / SDK.
plugins {
    id("com.android.application") version "8.7.0" apply false
    id("org.jetbrains.kotlin.android") version "2.0.20" apply false
    // Kotlin 2.0+ ships the Compose compiler as a standalone plugin (versioned
    // in lockstep with Kotlin), replacing kotlinCompilerExtensionVersion.
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.20" apply false
}
