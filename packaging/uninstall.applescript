set homeFolder to POSIX path of (path to home folder)
set appPaths to {"/Applications/CrateSort.app", homeFolder & "Applications/CrateSort.app"}
set prefFile to homeFolder & "Library/Preferences/com.jwbc.CrateSort.plist"

set theButton to button returned of (display dialog "This will uninstall CrateSort from this Mac." & return & return & "It will remove:" & return & "• CrateSort.app" & return & "• Saved preferences" & return & return & "It will NOT remove your music library, organized files, or crates." buttons {"Cancel", "Uninstall"} default button "Uninstall" cancel button "Cancel" with icon caution)

if theButton is "Uninstall" then
	try
		tell application "CrateSort" to quit
		delay 1
	end try
	do shell script "pkill -f 'CrateSort.app/Contents/MacOS/CrateSort' >/dev/null 2>&1; exit 0"

	set removedApp to false
	repeat with p in appPaths
		set posixPath to p as text
		set exists to (do shell script "[ -d " & quoted form of posixPath & " ] && echo yes || echo no")
		if exists is "yes" then
			try
				do shell script "rm -rf " & quoted form of posixPath
			on error
				do shell script "rm -rf " & quoted form of posixPath with administrator privileges
			end try
			set removedApp to true
		end if
	end repeat

	set prefExists to (do shell script "[ -f " & quoted form of prefFile & " ] && echo yes || echo no")
	if prefExists is "yes" then
		do shell script "defaults delete com.jwbc.CrateSort >/dev/null 2>&1; rm -f " & quoted form of prefFile
	end if

	if removedApp then
		display dialog "CrateSort has been uninstalled." buttons {"OK"} default button "OK" with icon note
	else
		display dialog "CrateSort.app wasn't found in /Applications or ~/Applications. Saved preferences were removed if present." buttons {"OK"} default button "OK" with icon note
	end if
end if
