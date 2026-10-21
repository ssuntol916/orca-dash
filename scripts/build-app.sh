#!/usr/bin/env bash
# Alacritty 를 껍데기로 쓰는 "Orca Dash.app" 을 만든다.
#
#   scripts/build-app.sh [--install-dir ~/Applications] [--dmg dist/Alacritty-v0.17.0.dmg]
#
# 1) Alacritty.app 복사 → 2) 실행 파일을 래퍼로 바꾸고 전용 설정·실행 스크립트 동봉
# → 3) Info.plist 이름·식별자·아이콘 교체 → 4) ad-hoc 서명 → 5) 설치 디렉터리로 복사.
#
# Homebrew 의 alacritty cask 는 공증 미통과로 비활성화되어 있어 GitHub 릴리스 dmg 를 쓴다.
# 번들을 고친 뒤 ad-hoc 으로 다시 서명하므로 Gatekeeper 가 "손상된 앱"으로 보지 않는다.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALACRITTY_VERSION="${ALACRITTY_VERSION:-v0.17.0}"
DMG="$REPO/dist/Alacritty-${ALACRITTY_VERSION}.dmg"
INSTALL_DIR="$HOME/Applications"
APP_NAME="Orca Dash"
BUNDLE_ID="io.github.ssuntol916.orca-dash"

while [ $# -gt 0 ]; do
  case "$1" in
    --install-dir) INSTALL_DIR="$2"; shift 2 ;;
    --dmg) DMG="$2"; shift 2 ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 2 ;;
  esac
done

BUILD="$REPO/dist/$APP_NAME.app"
mkdir -p "$REPO/dist"

# 1. Alacritty 릴리스 확보 -----------------------------------------------------
if [ ! -f "$DMG" ]; then
  echo "▸ Alacritty $ALACRITTY_VERSION dmg 다운로드"
  gh release download "$ALACRITTY_VERSION" --repo alacritty/alacritty \
    --pattern "Alacritty-${ALACRITTY_VERSION}.dmg" --dir "$REPO/dist" --clobber
fi

echo "▸ dmg 마운트 및 복사"
MOUNT="$(mktemp -d)"
hdiutil attach -nobrowse -readonly -quiet -mountpoint "$MOUNT" "$DMG"
trap 'hdiutil detach -quiet "$MOUNT" 2>/dev/null || true; rmdir "$MOUNT" 2>/dev/null || true' EXIT
rm -rf "$BUILD"
ditto "$MOUNT/Alacritty.app" "$BUILD"
hdiutil detach -quiet "$MOUNT"; rmdir "$MOUNT"; trap - EXIT
xattr -dr com.apple.quarantine "$BUILD" 2>/dev/null || true

# 2. 래퍼 실행 파일과 동봉 자료 -------------------------------------------------
echo "▸ 래퍼·설정·실행 스크립트 동봉"
MACOS="$BUILD/Contents/MacOS"
RES="$BUILD/Contents/Resources"
cat > "$MACOS/orca-dash" <<'WRAP'
#!/bin/zsh
# Orca Dash.app 의 진입점. 전용 설정으로 Alacritty 를 띄우고 그 안에서 launch.sh 를 로그인 셸로 실행한다.
HERE="${0:A:h}"
RES="$HERE/../Resources"
exec "$HERE/alacritty" --config-file "$RES/alacritty.toml" --title "Orca Dash" \
  -e /bin/zsh -lc "source '$RES/launch.sh'"
WRAP
chmod +x "$MACOS/orca-dash"
cp "$REPO/app/alacritty.toml" "$RES/alacritty.toml"
sed "s|__REPO__|$REPO|" "$REPO/app/launch.sh" > "$RES/launch.sh"
chmod +x "$RES/launch.sh"
echo "▸ 입력 소스 전환 보조 도구 빌드 (bin/orca-dash-im)"
"$REPO/scripts/build-im.sh" || echo "  (건너뜀: 한글 입력기로 되돌리기가 적용되지 않을 수 있음)"

# 3. 아이콘 ----------------------------------------------------------------------
echo "▸ 아이콘 생성"
ICONSET="$(mktemp -d)/orca-dash.iconset"
mkdir -p "$ICONSET"
python3 "$REPO/app/make_icon.py" "$ICONSET/icon_1024.png"
for s in 16 32 128 256 512; do
  sips -z $s $s "$ICONSET/icon_1024.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  d=$((s * 2))
  sips -z $d $d "$ICONSET/icon_1024.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
rm "$ICONSET/icon_1024.png"
iconutil -c icns "$ICONSET" -o "$RES/orca-dash.icns"
rm -rf "$(dirname "$ICONSET")"

# 4. Info.plist --------------------------------------------------------------------
echo "▸ Info.plist 갱신"
PLIST="$BUILD/Contents/Info.plist"
pb() { /usr/libexec/PlistBuddy -c "$1" "$PLIST" >/dev/null 2>&1 || /usr/libexec/PlistBuddy -c "$2" "$PLIST" >/dev/null; }
pb "Set :CFBundleName $APP_NAME"               "Add :CFBundleName string $APP_NAME"
pb "Set :CFBundleDisplayName $APP_NAME"        "Add :CFBundleDisplayName string $APP_NAME"
pb "Set :CFBundleIdentifier $BUNDLE_ID"        "Add :CFBundleIdentifier string $BUNDLE_ID"
pb "Set :CFBundleExecutable orca-dash"         "Add :CFBundleExecutable string orca-dash"
pb "Set :CFBundleIconFile orca-dash.icns"      "Add :CFBundleIconFile string orca-dash.icns"
/usr/libexec/PlistBuddy -c "Delete :CFBundleIconName" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Delete :CFBundleURLTypes" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Delete :CFBundleDocumentTypes" "$PLIST" 2>/dev/null || true
rm -f "$RES/alacritty.icns"

# 5. 서명 --------------------------------------------------------------------------
echo "▸ ad-hoc 서명"
codesign --force --deep --sign - "$BUILD" 2>&1 | grep -v 'replacing existing signature' || true
codesign --verify --deep --strict "$BUILD"

# 6. 설치 --------------------------------------------------------------------------
mkdir -p "$INSTALL_DIR"
TARGET="$INSTALL_DIR/$APP_NAME.app"
rm -rf "$TARGET"
ditto "$BUILD" "$TARGET"
touch "$TARGET"  # Finder/Dock 아이콘 캐시 갱신 유도
echo "✔ 설치 완료: $TARGET"
echo "  실행: open \"$TARGET\"   ·  옵션 변경: 대시보드에서 o 키 (명령줄 고정값은 $TARGET/Contents/Resources/launch.sh 의 ARGS)"
