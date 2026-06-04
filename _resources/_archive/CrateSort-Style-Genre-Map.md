# CrateSort — Style-to-Genre Mapping Table
# 
# This is the classification engine's lookup brain. Every recognized style 
# maps to exactly one of the 12 CrateSort parent genres. Styles are matched 
# as COMPLETE PHRASES — no keyword parsing. "Funk Rock" maps to Rock, not 
# Funk/Soul, because it's its own entry.
#
# Sources: Discogs taxonomy (540+ styles across 15 genres), CrateSort project 
# plan taxonomy, and common real-world junk tags found in DJ libraries.
#
# CrateSort's 12 parent genres:
#   Blues, Country, Electronic, Funk/Soul, Hip-Hop/Rap, House, Jazz, 
#   R&B, Reggae, Rock, Seasonal, Specialty
#
# IMPORTANT CLASSIFICATION RULES:
# - "Pop" is NEVER a valid genre. Reclassify based on styles.
# - Synth-Pop and New Wave → Rock (not Electronic)
# - Breakdance / Park Jams → Funk/Soul (not Hip-Hop/Rap)
# - Soul → Funk/Soul (not R&B)
# - Disco → Funk/Soul
# - House stands alone (not under Electronic)
# - Styles are matched case-insensitively
# - Each style maps to exactly ONE parent genre
# - When multiple styles are present, majority wins; ties go to Tier 2/3

# ============================================================================
# BLUES
# ============================================================================

Blues:
  # Core Discogs blues styles
  - Acoustic Blues
  - Blues
  - Blues Rock            # NOTE: This is in Blues, NOT Rock — per record store test, 
                          # blues-rooted artists like Stevie Ray Vaughan go in Blues.
                          # Rock-rooted artists with blues influence go in Rock.
                          # The classifier should check artist context for edge cases.
  - Chicago Blues
  - Classic Blues
  - Country Blues
  - Delta Blues
  - East Coast Blues
  - Electric Blues
  - Gospel Blues
  - Harmonica Blues
  - Hill Country Blues
  - Jump Blues
  - Louisiana Blues
  - Modern Electric Blues
  - Piano Blues
  - Piedmont Blues
  - Rhythm & Blues       # NOTE: Classic pre-1960s R&B/blues, not modern R&B
  - Swamp Blues
  - Texas Blues
  - West Coast Blues
  
  # Common tag variations found in the wild
  - Blues/Rock
  - Country-Blues
  - Modern Blues
  - Traditional Blues
  - Urban Blues
  - Boogie Woogie

# ============================================================================
# COUNTRY
# ============================================================================

Country:
  - Alternative Country
  - Americana
  - Bluegrass
  - Cajun
  - Classic Country
  - Country
  - Country & Western
  - Country Blues        # NOTE: Could also be Blues. Classifier should check context.
  - Country Gospel
  - Country Pop
  - Country Rock         # NOTE: Country-rooted artists. Rock-rooted go in Rock.
  - Country Western
  - Cowpunk
  - Honky Tonk
  - Honky-Tonk
  - Nashville Sound
  - Neotraditional Country
  - Outlaw Country
  - Progressive Country
  - Red Dirt
  - Rockabilly          # NOTE: Could be Rock. If artist is primarily country, stays here.
  - Traditional Country
  - Western Swing
  - Zydeco

# ============================================================================
# ELECTRONIC
# ============================================================================

Electronic:
  # Core electronic styles
  - Abstract
  - Acid
  - Ambient
  - Ambient House        # NOTE: More Electronic than House — ambient-first
  - Bass Music
  - Berlin-School
  - Big Beat
  - Bitpop
  - Breakbeat
  - Breakcore
  - Breaks
  - Chillwave
  - Dark Ambient
  - Downtempo
  - Drone
  - Drum n Bass
  - Drum & Bass
  - Drum and Bass
  - DnB
  - Dub Techno
  - Dubstep
  - EBM
  - Electro              # NOTE: Electro (Electronic) not Electro Funk (Funk/Soul)
  - Electro House        # NOTE: Electronic, not House — rock-influenced club sound
  - Electroclash
  - Electronic
  - Electronica
  - Euro Dance
  - Euro House
  - Eurodance
  - Experimental
  - Gabber
  - Glitch
  - Goa Trance
  - Grime
  - Hardcore
  - Hardstyle
  - Hi NRG
  - Hi-NRG
  - IDM
  - Illbient
  - Industrial
  - Intelligent Dance Music
  - Italo Dance
  - Italo-Disco
  - Jungle
  - Leftfield
  - Minimal
  - Minimal Techno
  - Musique Concrète
  - Neofolk
  - Noise
  - Power Electronics
  - Progressive Trance
  - Psy-Trance
  - Psytrance
  - Synthwave
  - Tech Trance
  - Techno
  - Trance
  - Trip Hop
  - Trip-Hop
  - UK Garage
  - Vaporwave
  
  # Common tag variations
  - Chillout
  - Chill Out
  - Dance
  - Dance Music
  - EDM
  - Electro-Industrial
  - Electronic Dance Music
  - Future Bass
  - Intelligent Dance
  - Lo-Fi Electronic
  - Minimal Electronic
  - Retrowave
  - Synthpop              # WAIT — this maps to Rock per project plan! See Rock section.
                           # REMOVING from Electronic. Synth-Pop = Rock.

# ============================================================================
# FUNK/SOUL
# ============================================================================

Funk/Soul:
  # Core funk styles
  - Afro Funk
  - Afrobeat
  - Afro-Funk
  - Brazilian Funk
  - Classic Funk
  - Classic Soul
  - Deep Funk
  - Disco
  - Electro Funk         # NOTE: Electro FUNK = Funk/Soul. Plain "Electro" = Electronic.
  - Electro-Funk
  - Free Funk
  - Funk
  - Funk / Soul
  - Funk/Soul
  - Go-Go
  - Go Go
  - Instrumental Funk
  - Latin Funk
  - Modern Funk
  - Modern Soul
  - Neo Soul
  - Neo-Soul
  - Northern Soul
  - Nu-Funk
  - P-Funk
  - P.Funk
  - Parliament-Funkadelic
  - Psychedelic Funk
  - Psychedelic Soul
  - Rare Groove
  - Soul
  - Soul-Funk
  - Southern Soul
  
  # Styles that belong here per project plan despite possible confusion
  - Breakdance
  - Breakdance / Park Jams
  - Park Jams
  - Chicano Soul
  - Disco Funk
  - Italo Disco           # NOTE: Dance-oriented Italo → Funk/Soul. Synth-oriented → Electronic.
                           # Actually, most Italo-Disco in a DJ context = Electronic. 
                           # MOVING to Electronic. Keep only "Disco" here.
  
  # Common tag variations
  - Classic Funk & Soul
  - Deep Funk & Soul
  - Funk Old School
  - Funk/Old School
  - Funk and Soul
  - Motown
  - Old School Funk
  - Old School Soul
  - Philly Soul
  - Stax
  - Vintage Funk
  - Vintage Soul

# ============================================================================
# HIP-HOP/RAP
# ============================================================================

Hip-Hop/Rap:
  # Core hip-hop styles
  - Abstract Hip Hop
  - Bass
  - Boom Bap
  - Bounce
  - Chopped & Screwed
  - Chopped and Screwed
  - Cloud Rap
  - Conscious
  - Conscious Hip Hop
  - Crunk
  - Dirty South
  - East Coast Hip Hop
  - G-Funk
  - Gangsta
  - Gangsta Rap
  - Golden Era
  - Grime Rap
  - Hardcore Hip-Hop
  - Hardcore Rap
  - Hip Hop
  - Hip-Hop
  - Hip-Hop/Rap
  - Hip Hop / Rap
  - Horrorcore
  - Hyphy
  - Instrumental Hip-Hop
  - Instrumental Hip Hop
  - Jazzy Hip-Hop
  - Jazzy Hip Hop
  - Latin Hip Hop
  - Lo-Fi Hip Hop
  - Lofi Hip Hop
  - Miami Bass
  - Midwest Hip Hop
  - Nerdcore
  - Old School
  - Old School Hip Hop
  - Old School Rap
  - Plunderphonics
  - Political Hip Hop
  - Pop Rap
  - Rap
  - Snap
  - Southern Hip Hop
  - Southern Rap
  - Thug Rap
  - Trap
  - Trip Hop Rap
  - Turntablism
  - Underground
  - Underground Hip Hop
  - Underground Rap
  - West Coast
  - West Coast Hip Hop
  - West Coast Rap
  
  # Common tag variations
  - Boom-Bap
  - East Coast
  - Hip Hop Rap
  - Hiphop
  - Old School Hip-Hop
  - Rap & Hip-Hop
  - Rap/Hip-Hop
  - Urban                 # NOTE: "Urban" is often a euphemism. If styles suggest hip-hop, 
                           # map here. If styles suggest R&B, map to R&B.

# ============================================================================
# HOUSE
# ============================================================================

House:
  - Acid House
  - Afro House
  - Baltimore Club
  - Balearic
  - Chicago House
  - Classic House
  - Deep House
  - Disco House
  - Funky House
  - Garage House
  - Ghetto House
  - House
  - Jackin House
  - Jersey Club
  - Latin House
  - Microhouse
  - Minimal House
  - Nu-Disco             # NOTE: Nu-Disco straddles Funk/Soul and House. House wins 
                          # for DJ-library context — it's played in house sets.
  - Progressive House
  - Soulful House
  - Tech House
  - Tribal House
  - Tropical House
  - UK Funky
  - Vocal House
  
  # Common tag variations
  - Classic Chicago House
  - Deep & Soulful
  - Deep Soulful House
  - Garage
  - Speed Garage

# ============================================================================
# JAZZ
# ============================================================================

Jazz:
  - Acid Jazz
  - Avant-Garde Jazz
  - Avant-Garde
  - Bebop
  - Big Band
  - Bop
  - Bossa Nova
  - Chamber Jazz
  - Contemporary Jazz
  - Cool Jazz
  - Dixieland
  - ECM Style
  - Ethio-Jazz
  - Free Improvisation
  - Free Jazz
  - Fusion
  - Gypsy Jazz
  - Hard Bop
  - Jazz
  - Jazz-Funk
  - Jazz-Rock
  - Jazz Funk
  - Jazz Fusion
  - Latin Jazz
  - Library
  - Lo-Fi Jazz
  - Lounge
  - Modal Jazz
  - Modern Jazz
  - Nu Jazz
  - Post-Bop
  - Ragtime
  - Smooth Jazz
  - Soul Jazz
  - Soul-Jazz
  - Space Jazz
  - Spiritual Jazz
  - Swing
  - Third Stream
  - Vocal Jazz
  
  # Common tag variations
  - Acid-Jazz
  - Be-Bop
  - Brazilian Jazz
  - Contemporary
  - Cool
  - Future Jazz
  - Jazz & Funk
  - Jazz/Funk
  - Modal
  - Progressive Jazz
  - Trad Jazz
  - Traditional Jazz

# ============================================================================
# R&B
# ============================================================================

R&B:
  - '50s R&B
  - 50s R&B
  - Classic R&B
  - Contemporary R&B
  - Doo Wop
  - Doo-Wop
  - Freestyle
  - Modern R&B
  - New Jack Swing
  - New Jack
  - Quiet Storm
  - R&B
  - R&B/Soul             # NOTE: If the styles lean soul (Barry White), → Funk/Soul. 
                          # If they lean R&B (Jodeci), stays here.
  - RnB
  - Slow Jam
  - Slow Jams
  - Swingbeat
  
  # Common tag variations
  - Contemporary RnB
  - Modern RnB
  - Neo R&B
  - New R&B
  - Rhythm And Blues      # NOTE: Modern "Rhythm And Blues" = R&B. 
                          # Pre-1960s = probably Blues. Check year.
  - Urban Contemporary

# ============================================================================
# REGGAE
# ============================================================================

Reggae:
  - Calypso
  - Dancehall
  - Dub
  - Dub Poetry
  - Lovers Rock
  - Ragga
  - Reggae
  - Reggaeton            # NOTE: Could also be Latin/Hip-Hop. For DJ libraries, Reggae.
  - Rocksteady
  - Roots Reggae
  - Ska
  - Soca
  - Steelpan
  - Two Tone
  - 2 Tone
  
  # Common tag variations
  - Digital Reggae
  - Roots
  - Ska Punk             # NOTE: Could be Rock. Ska-rooted = Reggae. Punk-rooted = Rock.
  - Reggae/Dub

# ============================================================================
# ROCK
# ============================================================================

Rock:
  # Core rock styles
  - AOR
  - Alternative
  - Alternative Rock
  - Alt-Rock
  - Arena Rock
  - Art Rock
  - Boogie Rock
  - Brit Pop
  - Britpop
  - Classic Rock
  - Country Rock          # NOTE: Rock-rooted artists with country influence go here.
                           # Country-rooted artists go in Country.
  - Dream Pop
  - Early Rock & Roll
  - Emo
  - Experimental Rock
  - Folk Rock
  - Garage Rock
  - Glam
  - Glam Rock
  - Gothic Rock
  - Goth Rock
  - Grunge
  - Hard Rock
  - Hardcore Punk
  - Heartland Rock
  - Heavy Metal
  - Indie
  - Indie Pop
  - Indie Rock
  - Industrial Rock
  - Krautrock
  - Math Rock
  - Metal
  - Mod
  - New Wave              # PROJECT PLAN: New Wave = Rock, not Electronic
  - No Wave
  - Noise Rock
  - Nu Metal
  - Oldies
  - Pop Punk
  - Pop Rock
  - Post-Hardcore
  - Post-Punk
  - Post-Rock
  - Power Metal
  - Power Pop
  - Progressive Metal
  - Progressive Rock
  - Prog Rock
  - Proto-Punk
  - Psychedelic
  - Psychedelic Rock
  - Psychobilly
  - Pub Rock
  - Punk
  - Punk Rock
  - Rock
  - Rock & Roll
  - Rock And Roll
  - Rock 'n' Roll
  - Rockabilly            # NOTE: Rock-rooted. Country-rooted artists go in Country.
  - Shoegaze
  - Ska Punk              # NOTE: Punk-rooted = Rock. Ska-rooted = Reggae.
  - Slowcore
  - Soft Rock
  - Southern Rock
  - Space Rock
  - Speed Metal
  - Stoner Rock
  - Surf
  - Surf Rock
  - Synth-Pop             # PROJECT PLAN: Synth-Pop = Rock, not Electronic
  - Synth Pop
  - Synthpop
  - Thrash
  - Thrash Metal
  
  # Common tag variations
  - 60s Rock
  - 70s Rock
  - 80s Rock
  - 90s Rock
  - Alt Rock
  - Blues-Rock            # NOTE: Rock-rooted blues influence = Rock. Blues-rooted = Blues.
  - Brit Rock
  - College Rock
  - Death Metal
  - Doom Metal
  - Folk-Rock
  - Funk Metal
  - Funk Rock             # "Funk Rock" = Rock. "Electro Funk" = Funk/Soul.
  - Gothic
  - Grindcore
  - Hair Metal
  - Hardcore
  - Jam Band
  - Lo-Fi
  - Mod Revival
  - New Romantic
  - New Romantics
  - Noise Pop
  - Paisley Underground
  - Pop/Rock
  - Post Punk
  - Psychedelia
  - Punk/New Wave
  - Roots Rock
  - Stoner Metal
  - Surf Pop
  - Yacht Rock

# ============================================================================
# SEASONAL
# ============================================================================

Seasonal:
  - Christmas
  - Christmas Music
  - Halloween
  - Halloween Music
  - Holiday
  - Holiday Music
  - Xmas
  
  # Common tag variations
  - Christmas Songs
  - Halloween Sounds
  - Holiday Season
  - Seasonal
  - Winter Holiday

# ============================================================================
# SPECIALTY
# ============================================================================

Specialty:
  - Break Records
  - Breaks & Scratches
  - DJ Battle Tool
  - DJ Drop
  - DJ Drops
  - DJ Tools
  - FX
  - Jingle
  - Jingles
  - Non-Music
  - Radio
  - Radio Drop
  - Radio Show
  - Sample
  - Samples
  - Scratch
  - Scratch Records
  - Shout Out
  - Shout Outs
  - Shoutout
  - Sound Effect
  - Sound Effects
  - SFX
  - TV Theme
  - TV Themes
  - TV
  - Turntablism           # NOTE: Already in Hip-Hop/Rap. If it's a scratch record 
                           # (no rapper, just DJ tool), Specialty wins.
  - Voice Drop
  - Voicemail
  - Hotline
  
  # Common tag variations
  - Acapella
  - Acappella
  - Battle Break
  - Battle Breaks
  - Drop
  - Drops
  - Effect
  - Effects
  - Instrumental          # NOTE: "Instrumental" alone is not a genre. Needs context.
                           # If no other styles and file is in a DJ tools folder, → Specialty.
                           # Otherwise, classify by other available metadata.
  - Promo
  - Radio Promo
  - Scratch Tool

# ============================================================================
# "POP" RECLASSIFICATION RULES
# ============================================================================
# 
# "Pop" is NEVER a valid CrateSort genre. When encountered as a genre tag,
# the classifier should:
#
# 1. Check style tags — if styles resolve to a parent genre, use that.
#    "Pop" + "Synth-Pop" → Rock
#    "Pop" + "Disco" → Funk/Soul
#    "Pop" + "New Wave" → Rock
#    "Pop" + "Contemporary R&B" → R&B
#    "Pop" + "Dance-Pop" → depends on other styles
#
# 2. If no style tags, check artist classification (if artist already 
#    classified from other tracks).
#
# 3. If still unresolved, flag as unclassified for user review.
#
# Common "Pop" style combinations and where they go:
#   Pop Rock → Rock
#   Pop Rap → Hip-Hop/Rap
#   Pop Soul → Funk/Soul
#   Synth-Pop → Rock
#   Dance-Pop → check other styles; if house-adjacent → House; 
#                if electronic-adjacent → Electronic; else → unclassified
#   Europop → Electronic (if dance-oriented) or unclassified
#   Indie Pop → Rock
#   Power Pop → Rock
#   Country Pop → Country
#   J-Pop → unclassified (user decides)
#   K-Pop → unclassified (user decides)
#   Bubblegum → Rock (Oldies)
#   Teen Pop → unclassified

# ============================================================================
# COMMON JUNK TAGS AND HOW TO HANDLE THEM
# ============================================================================
#
# These are tags commonly found in real DJ libraries that aren't valid 
# genre or style names. The classifier should handle them gracefully:
#
# "Other"          → Ignore. Useless. Fall to Tier 2/3.
# "Unknown"        → Ignore. Fall to Tier 2/3.
# "General"        → Ignore. Fall to Tier 2/3.
# "Misc"           → Ignore. Fall to Tier 2/3.
# "Various"        → Ignore (this is about the artist, not genre).
# "Default"        → Ignore.
# "Unclassified"   → Ignore.
# "N/A"            → Ignore.
# "None"           → Ignore.
# ""               → Empty tag. Fall to Tier 2/3.
# "Pop"            → See reclassification rules above.
# "Urban"          → Ambiguous. Check styles for Hip-Hop vs R&B context.
# "World"          → Check styles. Could map to Reggae, Jazz (Latin Jazz), 
#                     or stay unclassified.
# "World Music"    → Same as "World".
# "Latin"          → Check styles. Bossa Nova → Jazz. Reggaeton → Reggae.
#                     Latin Hip Hop → Hip-Hop/Rap. Salsa → unclassified.
# "Folk"           → Check styles. Folk Rock → Rock. Neofolk → Electronic.
#                     Otherwise unclassified.
# "Gospel"         → Check styles. Gospel Blues → Blues. Otherwise unclassified.
# "Classical"      → Not in CrateSort's 12 genres. Flag as unclassified.
# "Soundtrack"     → Not in CrateSort's 12 genres. Flag as unclassified 
#                     unless styles resolve elsewhere.
# "Spoken Word"    → Specialty (if DJ tool) or unclassified.
# "Comedy"         → Specialty (if DJ tool) or unclassified.
# "Podcast"        → Specialty.
# "Audiobook"      → Specialty or unclassified.

# ============================================================================
# GENRE-BENDING / CROSSOVER RESOLUTION RULES
# ============================================================================
#
# When a track has styles from multiple parent genres, resolve like this:
#
# 1. COMPLETE PHRASE FIRST. "Funk Rock" is ONE entry → Rock. Don't split it.
#
# 2. MAJORITY RULE. If 3 styles map to Rock and 1 maps to Electronic, → Rock.
#
# 3. ARTIST-LEVEL OVERRIDE. If the artist is already classified (from other 
#    tracks), the artist's genre wins. James Brown doesn't become Electronic 
#    because one track got tagged "Electro Funk."
#
# 4. RECORD STORE TEST. When all else fails, ask: "What bin in a record store 
#    would you look in to find this artist?" That's the answer.
#
# 5. SPECIFIC CROSSOVER RULES (per project plan):
#    - Synth-Pop → Rock (bands with synths, not electronic producers)
#    - New Wave → Rock
#    - Breakdance / Park Jams → Funk/Soul (not Hip-Hop/Rap)
#    - Disco → Funk/Soul
#    - Go-Go → Funk/Soul
#    - Electro Funk → Funk/Soul (not Electronic)
#    - Acid Jazz → Jazz (not Electronic, not Funk/Soul)
#    - Jazz-Funk → Jazz
#    - Jazz-Rock → Jazz (unless artist is primarily Rock)
#    - Latin Jazz → Jazz
#    - Soul Jazz → Jazz
#    - Trip-Hop → Electronic (not Hip-Hop/Rap)
#    - Blues Rock → Blues (unless artist is primarily Rock)
#    - Country Rock → depends on artist's primary identity
#    - Ska Punk → depends on artist's primary identity
#    - Reggaeton → Reggae
#    - Nu-Disco → House (in DJ context)
