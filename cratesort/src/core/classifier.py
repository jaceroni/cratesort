from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from cratesort.src.core.scanner import TrackRecord

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PARENT_GENRES = frozenset({
    "Blues", "Country", "Electronic", "Funk/Soul", "Hip-Hop/Rap",
    "House", "Jazz", "R&B", "Reggae", "Rock", "Seasonal", "Specialty",
    "Traditional",   # 13th genre — Standards, Vocal Pop, Easy Listening, etc.
})

# Genre tags that carry no useful information — fall through to style analysis.
# "sample" / "samples" are use-case tags, not genre tags — a file in _Samples
# is still Blues or R&B, not Specialty.
JUNK_GENRES = frozenset({
    "other", "unknown", "general", "misc", "miscellaneous", "default",
    "unclassified", "n/a", "none", "various", "",
    "sample", "samples",
})

# Folder name segments (lowercased) that indicate DJ-tools / Specialty content.
# Used by the Turntablism special-case rule.
SPECIALTY_FOLDER_HINTS = frozenset({
    "drops", "__drops", "_drops",
    "dj tools", "dj-tools", "djtools",
    "scratch", "_scratch", "scratch records",
    "break records", "_scratch & break records", "scratch & break records",
    "sound fx", "sound effects", "sfx",
    "samples", "_samples",
    "specialty",
})

# ---------------------------------------------------------------------------
# Style-to-genre map
# All keys are lowercased; values are one of the 12 PARENT_GENRES.
# Resolved ambiguities (per project decisions):
#   - Italo Disco          → Electronic   (not Funk/Soul)
#   - Synthpop             → Rock         (removed from Electronic)
#   - Country Blues        → Blues        (primary home)
#   - Country Rock         → Country      (country-rooted primary)
#   - Rockabilly           → Rock         (rock-rooted primary)
#   - Blues Rock           → Blues        (blues-rooted; "Blues-Rock" with hyphen → Rock)
#   - Ska Punk             → Reggae       (ska-rooted; "Punk Ska" → Rock)
#   - Turntablism          → Hip-Hop/Rap  (special-cased below; DJ tools folder → Specialty)
# ---------------------------------------------------------------------------

STYLE_MAP: dict[str, str] = {

    # ── Blues ────────────────────────────────────────────────────────────────
    "acoustic blues": "Blues",
    "blues": "Blues",
    "blues rock": "Blues",        # blues-rooted; "blues-rock" (hyphen) → Rock
    "blues/rock": "Blues",
    "chicago blues": "Blues",
    "classic blues": "Blues",
    "country blues": "Blues",     # resolved: primary home is Blues
    "country-blues": "Blues",
    "delta blues": "Blues",
    "east coast blues": "Blues",
    "electric blues": "Blues",
    "gospel blues": "Blues",
    "harmonica blues": "Blues",
    "hill country blues": "Blues",
    "jump blues": "Blues",
    "louisiana blues": "Blues",
    "modern electric blues": "Blues",
    "modern blues": "Blues",
    "piano blues": "Blues",
    "piedmont blues": "Blues",
    "rhythm & blues": "Blues",    # pre-1960s interpretation
    "swamp blues": "Blues",
    "texas blues": "Blues",
    "traditional blues": "Blues",
    "urban blues": "Blues",
    "west coast blues": "Blues",
    "boogie woogie": "Blues",

    # ── Country ──────────────────────────────────────────────────────────────
    "alternative country": "Country",
    "americana": "Country",
    "bluegrass": "Country",
    "cajun": "Country",
    "classic country": "Country",
    "country": "Country",
    "country & western": "Country",
    "country gospel": "Country",
    "country pop": "Country",
    "country rock": "Country",    # country-rooted primary mapping
    "country western": "Country",
    "cowpunk": "Country",
    "honky tonk": "Country",
    "honky-tonk": "Country",
    "nashville sound": "Country",
    "neotraditional country": "Country",
    "outlaw country": "Country",
    "progressive country": "Country",
    "red dirt": "Country",
    "traditional country": "Country",
    "western swing": "Country",
    "zydeco": "Country",

    # ── Electronic ───────────────────────────────────────────────────────────
    "abstract": "Electronic",
    "acid": "Electronic",
    "ambient": "Electronic",
    "ambient house": "Electronic",  # ambient-first, not house-first
    "bass music": "Electronic",
    "berlin-school": "Electronic",
    "big beat": "Electronic",
    "bitpop": "Electronic",
    "breakbeat": "Electronic",
    "breakcore": "Electronic",
    "breaks": "Electronic",
    "chillwave": "Electronic",
    "chillout": "Electronic",
    "chill out": "Electronic",
    "dark ambient": "Electronic",
    "dance": "Electronic",
    "dance music": "Electronic",
    "downtempo": "Electronic",
    "drone": "Electronic",
    "drum n bass": "Electronic",
    "drum & bass": "Electronic",
    "drum and bass": "Electronic",
    "dnb": "Electronic",
    "dub techno": "Electronic",
    "dubstep": "Electronic",
    "ebm": "Electronic",
    "edm": "Electronic",
    "electro": "Electronic",          # plain Electro ≠ Electro Funk
    "electro house": "Electronic",
    "electro-industrial": "Electronic",
    "electroclash": "Electronic",
    "electronic": "Electronic",
    "electronic dance music": "Electronic",
    "electronica": "Electronic",
    "euro dance": "Electronic",
    "euro house": "Electronic",
    "eurodance": "Electronic",
    "experimental": "Electronic",
    "future bass": "Electronic",
    "gabber": "Electronic",
    "glitch": "Electronic",
    "goa trance": "Electronic",
    "grime": "Electronic",
    "hardcore": "Electronic",         # Hardcore Techno/Rave — Hardcore Punk → Rock
    "hardstyle": "Electronic",
    "hi nrg": "Electronic",
    "hi-nrg": "Electronic",
    "idm": "Electronic",
    "illbient": "Electronic",
    "industrial": "Electronic",
    "intelligent dance music": "Electronic",
    "intelligent dance": "Electronic",
    "italo dance": "Electronic",
    "italo-disco": "Electronic",
    "italo disco": "Electronic",      # resolved: Electronic (not Funk/Soul)
    "jungle": "Electronic",
    "leftfield": "Electronic",
    "lo-fi electronic": "Electronic",
    "minimal": "Electronic",
    "minimal electronic": "Electronic",
    "minimal techno": "Electronic",
    "musique concrète": "Electronic",
    "musique concrete": "Electronic",
    "neofolk": "Electronic",
    "noise": "Electronic",
    "power electronics": "Electronic",
    "progressive trance": "Electronic",
    "psy-trance": "Electronic",
    "psytrance": "Electronic",
    "retrowave": "Electronic",
    "synthwave": "Electronic",
    "tech trance": "Electronic",
    "techno": "Electronic",
    "trance": "Electronic",
    "trip hop": "Electronic",
    "trip-hop": "Electronic",
    "uk garage": "Electronic",
    "vaporwave": "Electronic",
    # Synthpop removed from Electronic — it maps to Rock (see Rock section)

    # ── Funk/Soul ────────────────────────────────────────────────────────────
    "afro funk": "Funk/Soul",
    "afrobeat": "Funk/Soul",
    "afro-funk": "Funk/Soul",
    "brazilian funk": "Funk/Soul",
    "breakdance": "Funk/Soul",
    "breakdance / park jams": "Funk/Soul",
    "chicano soul": "Funk/Soul",
    "classic funk": "Funk/Soul",
    "classic funk & soul": "Funk/Soul",
    "classic soul": "Funk/Soul",
    "deep funk": "Funk/Soul",
    "deep funk & soul": "Funk/Soul",
    "disco": "Funk/Soul",
    "disco funk": "Funk/Soul",
    "electro funk": "Funk/Soul",      # Electro FUNK ≠ plain Electro
    "electro-funk": "Funk/Soul",
    "free funk": "Funk/Soul",
    "funk": "Funk/Soul",
    "funk / soul": "Funk/Soul",
    "funk/soul": "Funk/Soul",
    "funk and soul": "Funk/Soul",
    "funk old school": "Funk/Soul",
    "funk/old school": "Funk/Soul",
    "go-go": "Funk/Soul",
    "go go": "Funk/Soul",
    "instrumental funk": "Funk/Soul",
    "latin funk": "Funk/Soul",
    "modern funk": "Funk/Soul",
    "modern soul": "Funk/Soul",
    "motown": "Funk/Soul",
    "neo soul": "Funk/Soul",
    "neo-soul": "Funk/Soul",
    "northern soul": "Funk/Soul",
    "nu-funk": "Funk/Soul",
    "old school funk": "Funk/Soul",
    "old school soul": "Funk/Soul",
    "p-funk": "Funk/Soul",
    "p.funk": "Funk/Soul",
    "park jams": "Funk/Soul",
    "parliament-funkadelic": "Funk/Soul",
    "philly soul": "Funk/Soul",
    "psychedelic funk": "Funk/Soul",
    "psychedelic soul": "Funk/Soul",
    "rare groove": "Funk/Soul",
    "soul": "Funk/Soul",
    "soul-funk": "Funk/Soul",
    "southern soul": "Funk/Soul",
    "stax": "Funk/Soul",
    "vintage funk": "Funk/Soul",
    "vintage soul": "Funk/Soul",

    # ── Hip-Hop/Rap ──────────────────────────────────────────────────────────
    "abstract hip hop": "Hip-Hop/Rap",
    "bass": "Hip-Hop/Rap",            # Miami Bass / bass rap context
    "boom bap": "Hip-Hop/Rap",
    "boom-bap": "Hip-Hop/Rap",
    "bounce": "Hip-Hop/Rap",
    "chopped & screwed": "Hip-Hop/Rap",
    "chopped and screwed": "Hip-Hop/Rap",
    "cloud rap": "Hip-Hop/Rap",
    "conscious": "Hip-Hop/Rap",
    "conscious hip hop": "Hip-Hop/Rap",
    "crunk": "Hip-Hop/Rap",
    "dirty south": "Hip-Hop/Rap",
    "east coast": "Hip-Hop/Rap",
    "east coast hip hop": "Hip-Hop/Rap",
    "g-funk": "Hip-Hop/Rap",
    "gangsta": "Hip-Hop/Rap",
    "gangsta rap": "Hip-Hop/Rap",
    "golden era": "Hip-Hop/Rap",
    "grime rap": "Hip-Hop/Rap",
    "hardcore hip-hop": "Hip-Hop/Rap",
    "hardcore hip hop": "Hip-Hop/Rap",
    "hardcore rap": "Hip-Hop/Rap",
    "hip hop": "Hip-Hop/Rap",
    "hip-hop": "Hip-Hop/Rap",
    "hip-hop/rap": "Hip-Hop/Rap",
    "hip hop / rap": "Hip-Hop/Rap",
    "hip hop rap": "Hip-Hop/Rap",
    "hiphop": "Hip-Hop/Rap",
    "horrorcore": "Hip-Hop/Rap",
    "hyphy": "Hip-Hop/Rap",
    "instrumental hip-hop": "Hip-Hop/Rap",
    "instrumental hip hop": "Hip-Hop/Rap",
    "jazzy hip-hop": "Hip-Hop/Rap",
    "jazzy hip hop": "Hip-Hop/Rap",
    "latin hip hop": "Hip-Hop/Rap",
    "lo-fi hip hop": "Hip-Hop/Rap",
    "lofi hip hop": "Hip-Hop/Rap",
    "miami bass": "Hip-Hop/Rap",
    "midwest hip hop": "Hip-Hop/Rap",
    "nerdcore": "Hip-Hop/Rap",
    "old school": "Hip-Hop/Rap",
    "old school hip hop": "Hip-Hop/Rap",
    "old school hip-hop": "Hip-Hop/Rap",
    "old school rap": "Hip-Hop/Rap",
    "plunderphonics": "Hip-Hop/Rap",
    "political hip hop": "Hip-Hop/Rap",
    "pop rap": "Hip-Hop/Rap",
    "rap": "Hip-Hop/Rap",
    "rap & hip-hop": "Hip-Hop/Rap",
    "rap/hip-hop": "Hip-Hop/Rap",
    "snap": "Hip-Hop/Rap",
    "southern hip hop": "Hip-Hop/Rap",
    "southern rap": "Hip-Hop/Rap",
    "thug rap": "Hip-Hop/Rap",
    "trap": "Hip-Hop/Rap",
    "trip hop rap": "Hip-Hop/Rap",
    # "turntablism" is special-cased in classify() — not in this map
    "underground": "Hip-Hop/Rap",
    "underground hip hop": "Hip-Hop/Rap",
    "underground rap": "Hip-Hop/Rap",
    "urban": "Hip-Hop/Rap",           # ambiguous; hip-hop wins as primary
    "west coast": "Hip-Hop/Rap",
    "west coast hip hop": "Hip-Hop/Rap",
    "west coast rap": "Hip-Hop/Rap",

    # ── House ────────────────────────────────────────────────────────────────
    "acid house": "House",
    "afro house": "House",
    "baltimore club": "House",
    "balearic": "House",
    "chicago house": "House",
    "classic chicago house": "House",
    "classic house": "House",
    "deep & soulful": "House",
    "deep house": "House",
    "deep soulful house": "House",
    "disco house": "House",
    "funky house": "House",
    "garage": "House",
    "garage house": "House",
    "ghetto house": "House",
    "house": "House",
    "jackin house": "House",
    "jersey club": "House",
    "latin house": "House",
    "microhouse": "House",
    "minimal house": "House",
    "nu-disco": "House",              # DJ-library context: house sets
    "progressive house": "House",
    "soulful house": "House",
    "speed garage": "House",
    "tech house": "House",
    "tribal house": "House",
    "tropical house": "House",
    "uk funky": "House",
    "vocal house": "House",

    # ── Jazz ─────────────────────────────────────────────────────────────────
    "acid jazz": "Jazz",
    "acid-jazz": "Jazz",
    "avant-garde": "Jazz",
    "avant-garde jazz": "Jazz",
    "be-bop": "Jazz",
    "bebop": "Jazz",
    "big band": "Jazz",
    "bop": "Jazz",
    "bossa nova": "Jazz",
    "brazilian jazz": "Jazz",
    "chamber jazz": "Jazz",
    "contemporary": "Jazz",
    "contemporary jazz": "Jazz",
    "cool": "Jazz",
    "cool jazz": "Jazz",
    "dixieland": "Jazz",
    "ecm style": "Jazz",
    "ethio-jazz": "Jazz",
    "free improvisation": "Jazz",
    "free jazz": "Jazz",
    "fusion": "Jazz",
    "future jazz": "Jazz",
    "gypsy jazz": "Jazz",
    "hard bop": "Jazz",
    "jazz": "Jazz",
    "jazz & funk": "Jazz",
    "jazz/funk": "Jazz",
    "jazz-funk": "Jazz",
    "jazz-rock": "Jazz",
    "jazz funk": "Jazz",
    "jazz fusion": "Jazz",
    "latin jazz": "Jazz",
    "library": "Jazz",
    "lo-fi jazz": "Jazz",
    "lounge": "Jazz",
    "modal": "Jazz",
    "modal jazz": "Jazz",
    "modern jazz": "Jazz",
    "nu jazz": "Jazz",
    "post-bop": "Jazz",
    "progressive jazz": "Jazz",
    "ragtime": "Jazz",
    "smooth jazz": "Jazz",
    "soul jazz": "Jazz",
    "soul-jazz": "Jazz",
    "space jazz": "Jazz",
    "spiritual jazz": "Jazz",
    "swing": "Jazz",
    "third stream": "Jazz",
    "trad jazz": "Jazz",
    "traditional jazz": "Jazz",
    "vocal jazz": "Jazz",

    # ── R&B ──────────────────────────────────────────────────────────────────
    "'50s r&b": "R&B",
    "50s r&b": "R&B",
    "classic r&b": "R&B",
    "contemporary r&b": "R&B",
    "contemporary rnb": "R&B",
    "doo wop": "R&B",
    "doo-wop": "R&B",
    "freestyle": "R&B",
    "modern r&b": "R&B",
    "modern rnb": "R&B",
    "neo r&b": "R&B",
    "new jack": "R&B",
    "new jack swing": "R&B",
    "new r&b": "R&B",
    "quiet storm": "R&B",
    "r&b": "R&B",
    "r&b/soul": "R&B",
    "rhythm and blues": "R&B",        # modern interpretation
    "rnb": "R&B",
    "slow jam": "R&B",
    "slow jams": "R&B",
    "swingbeat": "R&B",
    "urban contemporary": "R&B",

    # ── Reggae ───────────────────────────────────────────────────────────────
    "2 tone": "Reggae",
    "calypso": "Reggae",
    "dancehall": "Reggae",
    "digital reggae": "Reggae",
    "dub": "Reggae",
    "dub poetry": "Reggae",
    "lovers rock": "Reggae",
    "ragga": "Reggae",
    "reggae": "Reggae",
    "reggae/dub": "Reggae",
    "reggaeton": "Reggae",
    "rocksteady": "Reggae",
    "roots": "Reggae",
    "roots reggae": "Reggae",
    "ska": "Reggae",
    "ska punk": "Reggae",             # ska-rooted primary
    "soca": "Reggae",
    "steelpan": "Reggae",
    "two tone": "Reggae",

    # ── Rock ─────────────────────────────────────────────────────────────────
    "60s rock": "Rock",
    "70s rock": "Rock",
    "80s rock": "Rock",
    "90s rock": "Rock",
    "aor": "Rock",
    "alt rock": "Rock",
    "alt-rock": "Rock",
    "alternative": "Rock",
    "alternative rock": "Rock",
    "arena rock": "Rock",
    "art rock": "Rock",
    "blues-rock": "Rock",             # rock-rooted; "blues rock" (no hyphen) → Blues
    "blues-rock (rock-rooted)": "Rock",
    "boogie rock": "Rock",
    "brit pop": "Rock",
    "brit rock": "Rock",
    "britpop": "Rock",
    "classic rock": "Rock",
    "college rock": "Rock",
    "country rock (rock-rooted)": "Rock",
    "death metal": "Rock",
    "doom metal": "Rock",
    "dream pop": "Rock",
    "early rock & roll": "Rock",
    "emo": "Rock",
    "experimental rock": "Rock",
    "folk rock": "Rock",
    "folk-rock": "Rock",
    "funk metal": "Rock",
    "funk rock": "Rock",              # Funk Rock = Rock; Electro Funk = Funk/Soul
    "garage rock": "Rock",
    "glam": "Rock",
    "glam rock": "Rock",
    "gothic": "Rock",
    "gothic rock": "Rock",
    "goth rock": "Rock",
    "grindcore": "Rock",
    "grunge": "Rock",
    "hair metal": "Rock",
    "hard rock": "Rock",
    "hardcore punk": "Rock",
    "heartland rock": "Rock",
    "heavy metal": "Rock",
    "indie": "Rock",
    "indie pop": "Rock",
    "indie rock": "Rock",
    "industrial rock": "Rock",
    "jam band": "Rock",
    "krautrock": "Rock",
    "lo-fi": "Rock",
    "math rock": "Rock",
    "metal": "Rock",
    "mod": "Rock",
    "mod revival": "Rock",
    "new romantic": "Rock",
    "new romantics": "Rock",
    "new wave": "Rock",               # project plan: New Wave = Rock
    "no wave": "Rock",
    "noise pop": "Rock",
    "noise rock": "Rock",
    "nu metal": "Rock",
    "oldies": "Rock",
    "paisley underground": "Rock",
    "pop punk": "Rock",
    "pop rock": "Rock",
    "pop/rock": "Rock",
    "post-hardcore": "Rock",
    "post punk": "Rock",
    "post-punk": "Rock",
    "post-rock": "Rock",
    "power metal": "Rock",
    "power pop": "Rock",
    "prog rock": "Rock",
    "progressive metal": "Rock",
    "progressive rock": "Rock",
    "proto-punk": "Rock",
    "psychedelia": "Rock",
    "psychedelic": "Rock",
    "psychedelic rock": "Rock",
    "psychobilly": "Rock",
    "pub rock": "Rock",
    "punk": "Rock",
    "punk rock": "Rock",
    "punk/new wave": "Rock",
    "rock": "Rock",
    "rock & roll": "Rock",
    "rock and roll": "Rock",
    "rock 'n' roll": "Rock",
    "rockabilly": "Rock",             # rock-rooted primary
    "roots rock": "Rock",
    "shoegaze": "Rock",
    "slowcore": "Rock",
    "soft rock": "Rock",
    "southern rock": "Rock",
    "space rock": "Rock",
    "speed metal": "Rock",
    "stoner metal": "Rock",
    "stoner rock": "Rock",
    "surf": "Rock",
    "surf pop": "Rock",
    "surf rock": "Rock",
    "synth pop": "Rock",              # project plan: Synth-Pop = Rock
    "synth-pop": "Rock",
    "synthpop": "Rock",               # removed from Electronic, maps here
    "thrash": "Rock",
    "thrash metal": "Rock",
    "yacht rock": "Rock",

    # ── Seasonal ─────────────────────────────────────────────────────────────
    "christmas": "Seasonal",
    "christmas music": "Seasonal",
    "christmas songs": "Seasonal",
    "halloween": "Seasonal",
    "halloween music": "Seasonal",
    "halloween sounds": "Seasonal",
    "holiday": "Seasonal",
    "holiday music": "Seasonal",
    "holiday season": "Seasonal",
    "seasonal": "Seasonal",
    "winter holiday": "Seasonal",
    "xmas": "Seasonal",

    # ── Specialty ────────────────────────────────────────────────────────────
    "acapella": "Specialty",
    "acappella": "Specialty",
    "battle break": "Specialty",
    "battle breaks": "Specialty",
    "break records": "Specialty",
    "breaks & scratches": "Specialty",
    "dj battle tool": "Specialty",
    "dj drop": "Specialty",
    "dj drops": "Specialty",
    "dj tools": "Specialty",
    "drop": "Specialty",
    "drops": "Specialty",
    "effect": "Specialty",
    "effects": "Specialty",
    "fx": "Specialty",
    "hotline": "Specialty",
    "jingle": "Specialty",
    "jingles": "Specialty",
    "non-music": "Specialty",
    "promo": "Specialty",
    "radio": "Specialty",
    "radio drop": "Specialty",
    "radio promo": "Specialty",
    "radio show": "Specialty",
    # "sample" / "samples" removed — moved to JUNK_GENRES (use-case tag, not genre)
    "scratch": "Specialty",
    "scratch records": "Specialty",
    "scratch tool": "Specialty",
    "sfx": "Specialty",
    "shout out": "Specialty",
    "shout outs": "Specialty",
    "shoutout": "Specialty",
    "sound effect": "Specialty",
    "sound effects": "Specialty",
    "tv": "Specialty",
    "tv theme": "Specialty",
    "tv themes": "Specialty",
    "voice drop": "Specialty",
    "voicemail": "Specialty",

    # ── Traditional ───────────────────────────────────────────────────────────
    "traditional": "Traditional",
    "traditional pop": "Traditional",
    "vocal pop": "Traditional",
    "standards": "Traditional",
    "easy listening": "Traditional",
    "vocal": "Traditional",
    "crooner": "Traditional",
    "big band vocal": "Traditional",
    "lounge vocal": "Traditional",
    "adult contemporary": "Traditional",
    "middle of the road": "Traditional",
    "novelty": "Traditional",
    "show tunes": "Traditional",
    "showtunes": "Traditional",
    "broadway": "Traditional",
    "cabaret": "Traditional",
}

# ---------------------------------------------------------------------------
# Pop reclassification table  (Pop + style → parent genre)
# ---------------------------------------------------------------------------
_POP_STYLE_OVERRIDES: dict[str, str] = {
    "pop rock": "Rock",
    "pop rap": "Hip-Hop/Rap",
    "pop soul": "Funk/Soul",
    "synth-pop": "Rock",
    "synth pop": "Rock",
    "synthpop": "Rock",
    "dance-pop": "Electronic",
    "electropop": "Electronic",
    "europop": "Electronic",
    "indie pop": "Rock",
    "power pop": "Rock",
    "country pop": "Country",
    "bubblegum": "Rock",
    "new wave": "Rock",
    "art pop": "Rock",
    "dream pop": "Rock",
}

# ISRC code pattern — common in comment fields, not a style
_ISRC_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}\d{7}$")

# Folders whose name describes PURPOSE (drops, fx, etc.) not GENRE.
# Files here are short-form utility content — short ones get Specialty automatically;
# the folder name is never used as a genre hint (fix 6).
_SHORT_SPECIALTY_FOLDERS = frozenset({
    'drops', '__drops', '_drops', 'artists',
    'fx', 'effects', 'sfx', 'sound effects', 'sound fx',
    'shoutout', 'shoutouts',
    'promo', 'promos',
    'jingle', 'jingles',
})

# Folders whose path signals a use-case, not a genre — skip Tier 4 folder hints.
_PURPOSE_FOLDER_NAMES = frozenset({
    '_samples', 'samples',
    '_tributes', 'tributes',
    '_unsorted', 'unsorted', '__unsorted',
    '_drops', '__drops', 'drops', 'artists',
    '_instrumentals', 'instrumentals',
    '_commercials', 'commercials',
    '_movie clips', 'movie clips',
    '_hotline', 'hotline',
    'bchs',
})

# Folder-name segments → genre hint (used by _genre_from_folder, module-level for performance)
_FOLDER_HINTS: dict[str, str] = {
    "blues": "Blues",
    "country": "Country",
    "electronic": "Electronic",
    "funk": "Funk/Soul",
    "soul": "Funk/Soul",
    "hip-hop": "Hip-Hop/Rap",
    "hip hop": "Hip-Hop/Rap",
    "rap": "Hip-Hop/Rap",
    "house": "House",
    "jazz": "Jazz",
    "r&b": "R&B",
    "reggae": "Reggae",
    "rock": "Rock",
    "seasonal": "Seasonal",
    "holiday": "Seasonal",
    "christmas": "Seasonal",
    "halloween": "Seasonal",
    "specialty": "Specialty",
    "sound fx": "Specialty",
}

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class Confidence(Enum):
    HIGH = "HIGH"      # Direct parent genre or unambiguous style map match
    MEDIUM = "MEDIUM"  # Style analysis or comment field
    LOW = "LOW"        # Folder hint only
    NONE = "NONE"      # Could not classify


@dataclass
class ClassificationResult:
    genre: Optional[str]
    confidence: Confidence
    reason: str
    needs_review: bool = False
    original_genre_tag: Optional[str] = None
    matched_styles: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


class GenreClassifier:
    """
    Classifies a TrackRecord into one of the 12 CrateSort parent genres.

    Classification tiers (first match wins):
      1. Genre tag is already a valid parent genre → HIGH
      2. Genre tag found in STYLE_MAP → HIGH
      3. Majority of style tokens from comment/genre field → MEDIUM
      4. Ancestor folder name hint → LOW
      5. Unclassified → NONE
    """

    def classify(self, record: TrackRecord) -> ClassificationResult:
        # ── Pre-check: short duration in purpose folder → Specialty (fix 3) ─
        if record.duration and record.duration < 30:
            for part in record.path.parts:
                if part.lower() in _SHORT_SPECIALTY_FOLDERS:
                    return ClassificationResult(
                        genre="Specialty",
                        confidence=Confidence.HIGH,
                        reason=f"Short clip ({record.duration:.0f}s) in purpose folder '{part}'",
                        original_genre_tag=(record.genre or None),
                    )

        raw_genre = (record.genre or "").strip()
        genre_lower = raw_genre.lower()

        # ── Tier 1: Already a valid parent genre ──────────────────────────
        if raw_genre in PARENT_GENRES:
            return ClassificationResult(
                genre=raw_genre,
                confidence=Confidence.HIGH,
                reason="Genre tag is a valid parent genre",
                original_genre_tag=raw_genre,
            )

        # ── Junk tag: skip to style analysis ─────────────────────────────
        if genre_lower not in JUNK_GENRES:

            # ── Pop reclassification ──────────────────────────────────────
            if genre_lower == "pop":
                return self._reclassify_pop(record)

            # ── Turntablism special case ──────────────────────────────────
            if genre_lower == "turntablism":
                return self._classify_turntablism(record, raw_genre)

            # ── Tier 2: Genre tag in style map ────────────────────────────
            mapped = STYLE_MAP.get(genre_lower)
            if mapped:
                return ClassificationResult(
                    genre=mapped,
                    confidence=Confidence.HIGH,
                    reason=f"Genre tag '{raw_genre}' resolved via style map",
                    original_genre_tag=raw_genre,
                    matched_styles=[raw_genre],
                )

        # ── Tier 3: Style tokens from comment + genre fields ──────────────
        candidate_texts = [record.comment or "", record.genre or "", record.album or ""]
        votes = self._vote_from_texts(candidate_texts, record)
        if votes:
            winner, matched = max(votes.items(), key=lambda kv: len(kv[1]))
            return ClassificationResult(
                genre=winner,
                confidence=Confidence.MEDIUM,
                reason=f"Style analysis: {', '.join(matched)}",
                original_genre_tag=raw_genre or None,
                matched_styles=matched,
            )

        # ── Tier 4: Ancestor folder name hint ────────────────────────────
        folder_genre = self._genre_from_folder(record.path)
        if folder_genre:
            return ClassificationResult(
                genre=folder_genre,
                confidence=Confidence.LOW,
                reason=f"Inferred from folder path",
                needs_review=True,
                original_genre_tag=raw_genre or None,
            )

        # ── Unclassified ─────────────────────────────────────────────────
        return ClassificationResult(
            genre=None,
            confidence=Confidence.NONE,
            reason="No matching genre or style found",
            needs_review=True,
            original_genre_tag=raw_genre or None,
        )

    def classify_all(
        self, inventory: list[TrackRecord]
    ) -> list[tuple[TrackRecord, ClassificationResult]]:
        return [(rec, self.classify(rec)) for rec in inventory]

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _reclassify_pop(self, record: TrackRecord) -> ClassificationResult:
        """Handle tracks whose genre tag is 'Pop'."""
        # Check style tags baked into other fields
        for text in [record.comment or "", record.album or ""]:
            for style, genre in _POP_STYLE_OVERRIDES.items():
                if style in text.lower():
                    return ClassificationResult(
                        genre=genre,
                        confidence=Confidence.MEDIUM,
                        reason=f"Pop reclassified via style '{style}'",
                        original_genre_tag="Pop",
                        matched_styles=[style],
                    )

        # Vote from all available text
        votes = self._vote_from_texts(
            [record.comment or "", record.album or ""], record
        )
        if votes:
            winner, matched = max(votes.items(), key=lambda kv: len(kv[1]))
            return ClassificationResult(
                genre=winner,
                confidence=Confidence.MEDIUM,
                reason=f"Pop reclassified via style analysis: {', '.join(matched)}",
                original_genre_tag="Pop",
                matched_styles=matched,
            )

        return ClassificationResult(
            genre=None,
            confidence=Confidence.NONE,
            reason="'Pop' genre tag — no reclassification style found",
            needs_review=True,
            original_genre_tag="Pop",
        )

    def _classify_turntablism(
        self, record: TrackRecord, raw_genre: str
    ) -> ClassificationResult:
        """Turntablism → Hip-Hop/Rap; unless file lives in a DJ tools folder → Specialty."""
        if self._is_specialty_folder(record.path):
            return ClassificationResult(
                genre="Specialty",
                confidence=Confidence.MEDIUM,
                reason="Turntablism in DJ tools folder → Specialty",
                original_genre_tag=raw_genre,
                matched_styles=["Turntablism"],
            )
        return ClassificationResult(
            genre="Hip-Hop/Rap",
            confidence=Confidence.HIGH,
            reason="Turntablism → Hip-Hop/Rap",
            original_genre_tag=raw_genre,
            matched_styles=["Turntablism"],
        )

    def _vote_from_texts(
        self, texts: list[str], record: TrackRecord
    ) -> dict[str, list[str]]:
        """
        Parse style tokens from a list of text fields, look each up in
        STYLE_MAP, and return genre → [matched_styles] vote tallies.
        """
        votes: dict[str, list[str]] = {}
        for text in texts:
            if not text:
                continue
            # Skip bare ISRC codes
            if _ISRC_RE.match(text.strip()):
                continue
            for token in self._tokenize(text):
                lower = token.lower()
                # Turntablism special case
                if lower == "turntablism":
                    genre = (
                        "Specialty"
                        if self._is_specialty_folder(record.path)
                        else "Hip-Hop/Rap"
                    )
                    votes.setdefault(genre, []).append(token)
                    continue
                mapped = STYLE_MAP.get(lower)
                if mapped:
                    votes.setdefault(mapped, []).append(token)
        return votes

    def _tokenize(self, text: str) -> list[str]:
        """
        Split a text field into candidate style tokens.
        Try longest-first so compound styles ("Boom Bap") beat fragments.
        """
        text = text.strip()
        if not text:
            return []

        # First try the whole string as one phrase (handles "Jump Blues" in comment)
        candidates = [text]

        # Then split on common multi-style delimiters
        parts = re.split(r"[,;|/]", text)
        candidates.extend(p.strip() for p in parts if p.strip() and p.strip() != text)

        # Deduplicate while preserving order
        seen: set[str] = set()
        result = []
        for c in candidates:
            if c and c not in seen:
                seen.add(c)
                result.append(c)
        return result

    def _is_specialty_folder(self, path: Path) -> bool:
        for part in path.parts:
            if part.lower() in SPECIALTY_FOLDER_HINTS:
                return True
        return False

    def _genre_from_folder(self, path: Path) -> Optional[str]:
        """
        Walk ancestor folder names and return a genre hint if a recognizable
        name is found.  Checks specialty folders first, then genre hints,
        deepest ancestor first for best specificity.

        Fix 6: purpose folders (drops, samples, tributes, etc.) describe USE CASE
        not genre — skip folder hints entirely when a purpose folder is in the path.
        """
        # Skip folder hints for files inside purpose/use-case folders
        for part in path.parts[:-1]:
            if part.lower() in _PURPOSE_FOLDER_NAMES:
                return None

        if self._is_specialty_folder(path):
            return "Specialty"

        for part in reversed(path.parts[:-1]):  # skip filename
            lower = part.lower()
            if lower in _FOLDER_HINTS:
                return _FOLDER_HINTS[lower]
            # Partial match for colon-separated folder names like "Funk : Classic"
            for key, genre in _FOLDER_HINTS.items():
                if key in lower:
                    return genre
        return None
