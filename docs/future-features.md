# CrateSort — Future Feature Considerations

Ideas and capabilities tabled during development. Not committed to any release timeline. 
Intended as a living reference for roadmap planning, beta feedback conversations, and marketing.

---

## Library

### Track Associations
Link two tracks together with a relationship label so that finding one surfaces the other in search results.

**Use case:** A DJ knows either the original soul record or the hip-hop song that sampled it, but not always both. Linking them means searching for either one returns both. Relationships could be labeled: "samples", "sampled by", "flip of", "edit of", etc.

**Why it matters:** DJs currently work around this by putting notes like "Redman sample" in the comment field of the original track. That's a misuse of the comment field and it breaks down — you have to remember the exact wording, and it only works in one direction.

**Implementation note:** Would live entirely in CrateSort's own metadata layer (`_CrateSort/associations.json`). No Serato dependency. Many-to-many. Surfaced in the track detail view and search results.

---

## Rinse (Duplicate Detection)

### Artwork Thumbnail on Click in Rinse Review Screen
When reviewing duplicates, clicking a track row that has `ARTWORK: Yes` should display the embedded album art in a thumbnail on the card.

**Use case:** Lets the DJ visually confirm which copy has artwork before deciding which to keep. Useful when one copy has artwork and the other doesn't.

**Implementation note:** Artwork is already detected at scan time (`has_artwork` field on `DuplicateCopy`). The remaining work is reading the actual image data at click time via mutagen, creating a `QPixmap`, and rendering it in the card layout. Needs a click handler on the row and a thumbnail widget (e.g., 64×64px) that appears inline.

---

## Crates

*(nothing tabled yet)*

---

## Classify

*(nothing tabled yet)*

---

## Organize

*(nothing tabled yet)*

---

## General / UX

*(nothing tabled yet)*

---

## CrateCleaner — Sister Tool (Separate Product)

A lightweight standalone companion app positioned as a free lead-gen piece for CrateSort. Lets users drop in any audio/video file, see all human-facing metadata fields, get AI-suggested corrections via audio fingerprinting + MusicBrainz/Discogs lookup, and write the cleaned metadata back to the file.

**Core concept:** The "Costco sample" — give someone a polished free tool that demonstrates CrateSuite's quality, speed, and personality before they commit to CrateSort.

**Key aha moments to design for:**
- "I didn't know my file was this bad" — visual health indicator on drop
- "I didn't know there were this many fields" — show all human-facing fields, empty ones included
- "My artwork is poor quality" — flag low-res art, offer to replace
- "I can add multiple artworks" — front/back/artist photo, most users don't know this exists
- Fingerprint moment — "we found this track, want us to fill everything in?"

**Scope:**
- Batch queue (HandBrake-style), no file limit or soft cap (~10)
- Metadata lookup + suggested fixes, not just manual editing
- Strictly human-facing fields only — no Hz, kbps, encoder junk
- Artwork read, replace, and multi-artwork support
- Strip encoder/muxer garbage fields in one tap

**Form factor:** Native desktop app (Tauri), custom-shaped window following the crate + mascot silhouette. The crate IS the window. Mascot reacts expressively to what he finds in the file.

**Status:** Needs design mockups and further research before build. Image generation prompts drafted — feed to Midjourney/Gemini/GPT to explore visual direction.

---

*Last updated: June 23, 2026*
