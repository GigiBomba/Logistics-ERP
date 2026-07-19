plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.operion.operion_mobile"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.operion.operion_mobile"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            // For production releases, create a keystore and configure signing:
            // 1. Place keystore file outside version control
            // 2. Set env vars or use a keystore.properties file
            // 3. Uncomment and configure the signingConfig below
            //
            // Example:
            //   signingConfig = signingConfigs.create("release") {
            //       storeFile = file(System.getenv("KEYSTORE_PATH") ?: "release.keystore")
            //       storePassword = System.getenv("KEYSTORE_STORE_PASSWORD")
            //       keyAlias = System.getenv("KEYSTORE_KEY_ALIAS")
            //       keyPassword = System.getenv("KEYSTORE_KEY_PASSWORD")
            //   }
            //
            // For now, debug signing is used as fallback for CI/dev builds.
            // WARNING: Replace with proper release signing before publishing to any store.
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    testOptions {
        unitTests {
            isIncludeAndroidResources = true
        }
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.14.1")
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
