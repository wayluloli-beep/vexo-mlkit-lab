plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.trackingracing"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.trackingracing"
        minSdk = 26
        targetSdk = 36
        // O GitHub Actions fornece GITHUB_RUN_NUMBER; builds locais mantêm 6.
        versionCode = System.getenv("GITHUB_RUN_NUMBER")?.toIntOrNull()?.coerceAtLeast(6) ?: 6
        versionName = "0.1.3-r19-interno"
    }

    // A chave nunca fica no repositório. O GitHub Actions a recria
    // temporariamente a partir dos Secrets a cada execução.
    val fixedKeystore = System.getenv("APK_KEYSTORE_FILE")
    val fixedStorePassword = System.getenv("APK_STORE_PASSWORD")
    val fixedKeyAlias = System.getenv("APK_KEY_ALIAS")
    val fixedKeyPassword = System.getenv("APK_KEY_PASSWORD")
    if (!fixedKeystore.isNullOrBlank() &&
        !fixedStorePassword.isNullOrBlank() &&
        !fixedKeyAlias.isNullOrBlank() &&
        !fixedKeyPassword.isNullOrBlank()
    ) {
        signingConfigs {
            create("fixed") {
                storeFile = file(fixedKeystore)
                storePassword = fixedStorePassword
                keyAlias = fixedKeyAlias
                keyPassword = fixedKeyPassword
            }
        }
        buildTypes {
            getByName("debug") {
                signingConfig = signingConfigs.getByName("fixed")
            }
        }
    }

    // APK experimental separado: instala AO LADO do Tracking Racing original.
    // Não alterar a aplicação de produção em main.
    buildTypes {
        getByName("debug") {
            applicationIdSuffix = ".aurora"
            versionNameSuffix = "-aurora"
        }
    }

    buildFeatures { buildConfig = true }
    androidResources { noCompress += "mp4" }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}
