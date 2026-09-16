#!/bin/bash
# Build the CrateSort DMG from an already-built dist/CrateSort.app.
#
# Usage:
#   .build-venv/bin/pyinstaller packaging/CrateSort.spec --noconfirm --clean
#   packaging/build_dmg.sh
#
# Regenerate packaging/dmg_background.png first (needs the build venv) if
# the brand assets or DMG layout changed:
#   .build-venv/bin/python packaging/generate_dmg_background.py
#
# Replaces the old one-off-shell-commands pipeline documented in
# CLAUDE-CS.md's Packaging & Distribution section — this script IS that
# pipeline now, kept in sync with the doc's description of each step.
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
BG_PNG="$ROOT/packaging/dmg_background.png"
if [ ! -f "$BG_PNG" ]; then
    echo "ERROR: $BG_PNG not found — run packaging/generate_dmg_background.py first." >&2
    exit 1
fi

VOLNAME="CrateSort"
MOUNT="/Volumes/$VOLNAME"
STAGE="$ROOT/dist_dmg/.staging"
SCRATCH="$ROOT/dist_dmg/.scratch"
RW_DMG="$ROOT/dist_dmg/.CrateSort-rw.dmg"
FINAL="$ROOT/dist_dmg/CrateSort-$VERSION-beta.dmg"

rm -rf "$STAGE" "$SCRATCH" "$RW_DMG" "$FINAL"
mkdir -p "$STAGE/.background" "$SCRATCH"

# ---------------------------------------------------------------- staging --
osacompile -o "$STAGE/Uninstall CrateSort.app" "$ROOT/packaging/uninstall.applescript"
cp -R "$APP" "$STAGE/CrateSort.app"
ln -s /Applications "$STAGE/Applications"
cp "$BG_PNG" "$STAGE/.background/dmg_background.png"

# ------------------------------------------------- rendered app icon -----
# Raw cratesort/assets/icons/app/CrateSort.icns is a flat, sharp-cornered
# square — the rounded/shadowed look only exists because macOS auto-
# composites that treatment onto real .app BUNDLE icons specifically. Grab
# Finder's actual rendered bitmap off the just-built .app and reuse it for
# BOTH the DMG file's own icon and the mounted volume's icon, so neither one
# looks flat/generic next to the real app icon (the volume icon previously
# just copied the raw flat asset directly — that was the actual source of
# "the DMG looks generic," alongside having no background/layout at all).
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

# ------------------------------- branded window: background + icon layout --
# CrateSort.app (primary) on the left, Applications alias on the right with
# a connecting arrow drawn into the background image (the standard drag-to-
# install convention), the optional Uninstaller in its own row below,
# secondary role. Coordinates here must match generate_dmg_background.py's
# APP_X/APPLICATIONS_X/ROW_Y/UNINSTALL_Y constants.
cat > "$SCRATCH/layout.applescript" <<APPLESCRIPT
tell application "Finder"
    tell disk "$VOLNAME"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {400, 100, 1060, 520}
        set theViewOptions to the icon view options of container window
        set arrangement of theViewOptions to not arranged
        set icon size of theViewOptions to 128
        set background picture of theViewOptions to file ".background:dmg_background.png"
        set position of item "CrateSort.app" of container window to {150, 190}
        set position of item "Applications" of container window to {510, 190}
        set position of item "Uninstall CrateSort.app" of container window to {330, 330}
        close
        open
        update without registering applications
        delay 2
    end tell
end tell
APPLESCRIPT
osascript "$SCRATCH/layout.applescript"

# Volume icon — applied AFTER the layout step, not before: Finder's own
# window/icon-view-options writes touch the same 32-byte com.apple.FinderInfo
# structure that carries the volume's custom-icon bit, and running them
# first clobbered a custom icon set beforehand (confirmed — the icon and the
# custom-icon flag were both silently gone by the time the disk was
# detached). Setting it last, with nothing running afterward but detach,
# makes it stick.
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
