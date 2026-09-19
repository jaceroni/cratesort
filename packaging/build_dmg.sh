#!/bin/bash
# Build the CrateSort DMG from an already-built dist/CrateSort.app.
#
# Usage:
#   .build-venv/bin/pyinstaller packaging/CrateSort.spec --noconfirm --clean
#   packaging/build_dmg.sh
#
# Replaces the old one-off-shell-commands pipeline documented in
# CLAUDE-CS.md's Packaging & Distribution section — this script IS that
# pipeline now, kept in sync with the doc's description of each step.
#
# Plain default Finder window — no background image, no custom icon
# layout. A branded background + arranged icon positions was tried
# 2026-09-16 and explicitly reverted per Jace's direction (not asked for,
# didn't like it) — don't reintroduce without being asked.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION=$(python3 -c "
ns = {}
exec(open('cratesort/src/version.py').read(), ns)
print(ns['VERSION'])
")
echo "Building DMG for CrateSort $VERSION"

APP="$ROOT/dist/CrateSort.app"
if [ ! -d "$APP" ]; then
    echo "ERROR: $APP not found — build it first with PyInstaller (see usage above)." >&2
    exit 1
fi

VOLNAME="CrateSort"
MOUNT="/Volumes/$VOLNAME"
STAGE="$ROOT/dist_dmg/.staging"
SCRATCH="$ROOT/dist_dmg/.scratch"
RW_DMG="$ROOT/dist_dmg/.CrateSort-rw.dmg"
FINAL="$ROOT/dist_dmg/CrateSort-$VERSION-beta.dmg"

rm -rf "$STAGE" "$SCRATCH" "$RW_DMG" "$FINAL"
mkdir -p "$STAGE" "$SCRATCH"

# ---------------------------------------------------------------- staging --
osacompile -o "$STAGE/Uninstall CrateSort.app" "$ROOT/packaging/uninstall.applescript"
cp -R "$APP" "$STAGE/CrateSort.app"
ln -s /Applications "$STAGE/Applications"

# ------------------------------------------------- rendered app icon -----
# Raw cratesort/assets/icons/app/CrateSort.icns is a flat, sharp-cornered
# square — the rounded/shadowed look only exists because macOS auto-
# composites that treatment onto real .app BUNDLE icons specifically. Grab
# Finder's actual rendered bitmap off the just-built .app and reuse it for
# BOTH the DMG file's own icon and the mounted volume's icon, so neither one
# looks flat/generic next to the real app icon.
cat > "$SCRATCH/extract_icon.jxa" <<'JXA'
function run(argv) {
    ObjC.import("Cocoa");
    var appPath = argv[0];
    var outPath = argv[1];
    var icon = $.NSWorkspace.sharedWorkspace.iconForFile(appPath);
    icon.setSize($.NSMakeSize(1024, 1024));
    var rep = $.NSBitmapImageRep.imageRepWithData(icon.TIFFRepresentation);
    var pngData = rep.representationUsingTypeProperties($.NSBitmapImageFileTypePNG, $());
    pngData.writeToFileAtomically(outPath, true);
}
JXA
osascript -l JavaScript "$SCRATCH/extract_icon.jxa" "$APP" "$SCRATCH/rendered_icon.png"

ICONSET="$SCRATCH/dmg_icon.iconset"
mkdir -p "$ICONSET"
for spec in "16:icon_16x16" "32:icon_16x16@2x" "32:icon_32x32" "64:icon_32x32@2x" \
            "128:icon_128x128" "256:icon_128x128@2x" "256:icon_256x256" \
            "512:icon_256x256@2x" "512:icon_512x512"; do
    size="${spec%%:*}"; name="${spec##*:}"
    sips -z "$size" "$size" "$SCRATCH/rendered_icon.png" --out "$ICONSET/$name.png" >/dev/null
done
cp "$SCRATCH/rendered_icon.png" "$ICONSET/icon_512x512@2x.png"
iconutil -c icns "$ICONSET" -o "$SCRATCH/rendered.icns"

# --------------------------------------------------- writable staging DMG --
hdiutil create -srcfolder "$STAGE" -volname "$VOLNAME" -fs HFS+ -format UDRW -size 300m "$RW_DMG"
hdiutil attach "$RW_DMG" -readwrite -noverify -noautoopen

cp "$SCRATCH/rendered.icns" "$MOUNT/.VolumeIcon.icns"
SetFile -c icnC "$MOUNT/.VolumeIcon.icns"
SetFile -a C "$MOUNT"
sync

hdiutil detach "$MOUNT"

# ------------------------------------------------ compress to final DMG ---
hdiutil convert "$RW_DMG" -format UDZO -imagekey zlib-level=9 -o "$FINAL"
rm -f "$RW_DMG"

# DMG file's own Finder icon — separate from the volume icon above; this is
# what's visible BEFORE double-clicking the file. Modern NSWorkspace API,
# not the legacy sips/DeRez/Rez resource-fork trick (see CLAUDE-CS.md for
# why that one is unreliable).
cat > "$SCRATCH/apply_file_icon.jxa" <<'JXA'
function run(argv) {
    ObjC.import("Cocoa");
    var iconPath = argv[0];
    var dmgPath = argv[1];
    var image = $.NSImage.alloc.initWithContentsOfFile(iconPath);
    $.NSWorkspace.sharedWorkspace.setIconForFileOptions(image, dmgPath, 0);
}
JXA
osascript -l JavaScript "$SCRATCH/apply_file_icon.jxa" "$SCRATCH/rendered.icns" "$FINAL"
killall Finder 2>/dev/null || true

rm -rf "$STAGE" "$SCRATCH"
echo "Built: $FINAL"
ls -la "$FINAL"
