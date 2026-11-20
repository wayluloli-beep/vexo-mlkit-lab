plugins {
    id("com.android.application") version "8.9.2"
    id("org.jetbrains.kotlin.android") version "2.0.21"
}

android {
    namespace = "com.trackingracing.replay"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.trackingracing.replay"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "s13-candidate"
        testInstrumentationRunner = "com.trackingracing.replay.ReplaySmokeInstrumentation"
    }

    buildTypes {
        getByName("debug") { signingConfig = null }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

androidComponents {
    beforeVariants(selector().all()) { variant ->
        if (variant.buildType != "debug") variant.enable = false
    }
}

dependencies {
    add("debugImplementation", "com.google.mlkit:text-recognition:16.0.1")
    testImplementation("junit:junit:4.13.2")
}
