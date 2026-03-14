#!/usr/bin/env bash
# =============================================================================
# build.sh – Assembles the Android Auto Diagnostic Tool APK using Android SDK
#            build-tools directly (no Gradle / AGP required).
#
# Usage: ./build.sh [--clean]
# Output: aad-tool-debug.apk (in this directory)
# =============================================================================
set -euo pipefail

ANDROID_SDK="${ANDROID_HOME:-/usr/local/lib/android/sdk}"
BUILD_TOOLS="$ANDROID_SDK/build-tools/35.0.0"
PLATFORM="$ANDROID_SDK/platforms/android-35"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_SRC="$SCRIPT_DIR/app/src/main"
BUILD_DIR="$SCRIPT_DIR/build"
LIBS_DIR="$BUILD_DIR/libs"

AAPT2="$BUILD_TOOLS/aapt2"
D8="$BUILD_TOOLS/d8"
APKSIGNER="$BUILD_TOOLS/apksigner"
ZIPALIGN="$BUILD_TOOLS/zipalign"
ANDROID_JAR="$PLATFORM/android.jar"
KEYSTORE="$BUILD_DIR/debug.keystore"

COROUTINES_VERSION="1.10.2"
BASE_MAVEN="https://repo1.maven.org/maven2/org/jetbrains/kotlinx"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║   Android Auto Diagnostic Tool – APK build               ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

if [[ "${1:-}" == "--clean" ]]; then
    echo "[clean] Removing build directory …"
    rm -rf "$BUILD_DIR"
fi

# ── 0. Setup directories ──────────────────────────────────────────────────────
mkdir -p "$BUILD_DIR"/{res-compiled,gen,classes,dex,libs}

# ── 1. Download kotlinx-coroutines JARs from Maven Central ───────────────────
echo "[1/7] Downloading kotlinx-coroutines $COROUTINES_VERSION …"
for artifact in kotlinx-coroutines-core-jvm kotlinx-coroutines-android; do
    jar_file="$LIBS_DIR/${artifact}-${COROUTINES_VERSION}.jar"
    if [ ! -f "$jar_file" ]; then
        curl -sSL --max-time 60 \
            "$BASE_MAVEN/$artifact/$COROUTINES_VERSION/${artifact}-${COROUTINES_VERSION}.jar" \
            -o "$jar_file"
        echo "   Downloaded $artifact"
    else
        echo "   Cached    $artifact"
    fi
done

CLASSPATH="$ANDROID_JAR:$LIBS_DIR/kotlinx-coroutines-core-jvm-${COROUTINES_VERSION}.jar:$LIBS_DIR/kotlinx-coroutines-android-${COROUTINES_VERSION}.jar"

# ── 2. Compile resources with aapt2 ──────────────────────────────────────────
echo "[2/7] Compiling resources …"
"$AAPT2" compile --dir "$APP_SRC/res" -o "$BUILD_DIR/res-compiled/"

# ── 3. Link resources (generates R.java + resource APK) ──────────────────────
echo "[3/7] Linking resources …"
"$AAPT2" link \
    -o "$BUILD_DIR/resources.apk" \
    -I "$ANDROID_JAR" \
    --manifest "$APP_SRC/AndroidManifest.xml" \
    --java "$BUILD_DIR/gen" \
    "$BUILD_DIR/res-compiled/"*.flat

# ── 4. Compile Kotlin sources ─────────────────────────────────────────────────
echo "[4/7] Compiling Kotlin sources …"
KOTLIN_SOURCES=$(find "$APP_SRC/java" -name "*.kt" | tr '\n' ' ')
# shellcheck disable=SC2086
kotlinc \
    $KOTLIN_SOURCES \
    "$BUILD_DIR/gen/com/example/aadtool/R.java" \
    -classpath "$CLASSPATH" \
    -d "$BUILD_DIR/classes" \
    -jvm-target 17

# ── 5. Convert .class files + coroutines JARs to DEX ─────────────────────────
echo "[5/7] Converting to DEX …"
CLASS_FILES=$(find "$BUILD_DIR/classes" -name "*.class" | tr '\n' ' ')
# shellcheck disable=SC2086
"$D8" \
    $CLASS_FILES \
    "$LIBS_DIR/kotlinx-coroutines-core-jvm-${COROUTINES_VERSION}.jar" \
    "$LIBS_DIR/kotlinx-coroutines-android-${COROUTINES_VERSION}.jar" \
    --lib "$ANDROID_JAR" \
    --min-api 29 \
    --output "$BUILD_DIR/dex/"

# ── 6. Assemble unsigned APK ─────────────────────────────────────────────────
echo "[6/7] Assembling APK …"
UNSIGNED_APK="$BUILD_DIR/aad-tool-unsigned.apk"
cp "$BUILD_DIR/resources.apk" "$UNSIGNED_APK"
(cd "$BUILD_DIR/dex" && zip -qu "$UNSIGNED_APK" classes.dex)

# Align
ALIGNED_APK="$BUILD_DIR/aad-tool-aligned.apk"
"$ZIPALIGN" -f 4 "$UNSIGNED_APK" "$ALIGNED_APK"

# ── 7. Sign APK ───────────────────────────────────────────────────────────────
echo "[7/7] Signing APK …"
if [ ! -f "$KEYSTORE" ]; then
    keytool -genkey -v \
        -keystore "$KEYSTORE" \
        -alias androiddebugkey \
        -keyalg RSA -keysize 2048 -validity 10000 \
        -storepass android -keypass android \
        -dname "CN=Android Debug,O=Android,C=US" \
        -noprompt 2>/dev/null
fi

SIGNED_APK="$SCRIPT_DIR/aad-tool-debug.apk"
"$APKSIGNER" sign \
    --ks "$KEYSTORE" \
    --ks-key-alias androiddebugkey \
    --ks-pass pass:android \
    --key-pass pass:android \
    --out "$SIGNED_APK" \
    "$ALIGNED_APK"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   BUILD SUCCESSFUL                                        ║"
printf "║   APK: %-50s ║\n" "$(basename "$SIGNED_APK")"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Install on device:  adb install -r $SIGNED_APK"
