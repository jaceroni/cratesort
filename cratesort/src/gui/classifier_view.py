from __future__ import annotations

import json
import re
import subprocess
import sys as _sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QAbstractItemView, QCompleter
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QProgressBar,
    QPushButton, QSizePolicy, QSplitter, QStackedWidget,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from cratesort.src.core.classifier import PARENT_GENRES

# Regex: detect collaboration patterns in artist fields (feat., ft., &, vs., comma-not-sort)
_COLLAB_RE = re.compile(
    r'(?:feat\.?\s|ft\.?\s|\bvs\.?\s|\s+x\s+)',
    re.IGNORECASE,
)
_COMMA_NOT_SORT_RE = re.compile(
    r',\s+(?!(?:the|a|an)\s*$)',
    re.IGNORECASE,
)

# Purpose-folder patterns for DJ Tools (untagged) bucket detection
_DJ_TOOLS_FOLDER_PATTERNS = frozenset({
    'drops', '__drops', '_drops', 'artists',
    'fx', 'effects', 'sfx', 'sound effects', 'sound fx',
    'shoutout', 'shoutouts',
    'promo', 'promos', 'jingle', 'jingles',
    '_hotline', 'hotline', 'bchs', 'generic',
})

DJ_TOOLS_LABEL = 'DJ Tools (untagged)'

# TheHandler instance for sort-form artist names (Fixes 3 + 4)
from cratesort.src.utils.the_handler import TheHandler as _TheHandler
_THE_HANDLER = _TheHandler()


def _canonical_artist(primary: str) -> str:
    """Return the sort-form name (e.g. 'Gap Band, The') for grouping + display."""
    proposal = _THE_HANDLER.analyze(primary)
    return proposal.sort_name if proposal else primary


# Featured-artist extraction (item 14)
_FEAT_STRIP_RE = re.compile(
    r'\s*(?:feat\.?|ft\.?|featuring|with)\s+.+$',
    re.IGNORECASE,
)


def _looks_like_sort_form(artist: str) -> bool:
    """Return True if a comma in the artist name is a 'Last, First' sort separator, not a collab."""
    if ',' not in artist:
        return False
    # "Gap Band, The" — classic sort form ending
    if re.search(r',\s*(the|a|an)\s*$', artist, re.IGNORECASE):
        return True
    # If the text after the first comma contains no spaces it's a single token
    # (possibly hyphenated like "Jean-Jacques") → treat as sort form, not collab
    after_comma = artist.split(',', 1)[1].strip()
    return ' ' not in after_comma


def _extract_primary_artist(artist: str) -> tuple[str, bool]:
    """
    Return (primary_artist, is_collaboration).
    - Strips feat./ft./featuring suffixes and uses the part before them.
    - For comma-separated lists that aren't sort forms, uses the first name.
    """
    if not artist:
        return 'Unknown Artist', False
    cleaned = _FEAT_STRIP_RE.sub('', artist).strip()
    was_feat = cleaned != artist
    # Comma-list: only flag as collab if NOT a "Last, First" sort form
    if ',' in cleaned and not _looks_like_sort_form(cleaned):
        primary = cleaned.split(',')[0].strip()
        return primary, True
    return cleaned, was_feat

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIDENCE_COLORS = {
    'HIGH':   '#6B9E78',
    'MEDIUM': '#D4A04A',
    'LOW':    '#C75B5B',
    'NONE':   '#C75B5B',
}
STATE_LABELS = {
    'pending':  'Pending',
    'edited':   '✎ Edited',
    'approved': '✓ Approved',
    'changed':  '✎ Edited',    # legacy alias → Edited
    'flagged':  '⚑ Flagged',
}
STATE_COLORS = {
    'pending':  '#a89b85',
    'edited':   '#428175',
    'approved': '#6B9E78',
    'changed':  '#428175',
    'flagged':  '#D4A04A',
}
ALL_GENRES = sorted(PARENT_GENRES) + ['Unclassified']

# Tree column indices
COL_ARTIST  = 0
COL_TRACKS  = 1
COL_CONF    = 2
COL_GENRE   = 3
COL_CURRENT = 4
COL_COMMENT = 5   # Dedicated comments column (always visible)
COL_STATUS  = 6
COL_PATH    = 7


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class TrackInfo:
    path: str
    filename: str
    title: Optional[str]
    duration: Optional[float]
    genre_tag: Optional[str]
    tags: list[str] = field(default_factory=list)
    comment: Optional[str] = None


@dataclass
class ArtistEntry:
    artist: str
    proposed_genre: str
    confidence: str
    reason: str
    tracks: list[TrackInfo]
    original_genres: list[str]
    state: str = 'pending'
    final_genre: str = ''
    is_collaboration: bool = False
    tags: list[str] = field(default_factory=list)

    @property
    def display_genre(self) -> str:
        if self.state in ('approved', 'changed', 'edited'):
            # final_genre may be '' if state was set to 'edited' via reassignment
            # without an explicit genre change — fall back to proposed_genre in that case
            return self.final_genre or self.proposed_genre
        return self.proposed_genre

    @property
    def track_count(self) -> int:
        return len(self.tracks)


@dataclass
class ClassificationSession:
    library_path: Path
    entries: list[ArtistEntry]
    created_at: str

    @property
    def approved_count(self) -> int:
        return sum(1 for e in self.entries if e.state in ('approved', 'changed', 'edited'))

    @property
    def total_count(self) -> int:
        return len(self.entries)

    def session_file(self) -> Path:
        return self.library_path / '_CrateSort' / 'classification_session.json'

    def save(self) -> None:
        path = self.session_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'library_path': str(self.library_path),
            'created_at': self.created_at,
            'entries': [
                {
                    'artist': e.artist,
                    'proposed_genre': e.proposed_genre,
                    'confidence': e.confidence,
                    'reason': e.reason,
                    'original_genres': e.original_genres,
                    'state': e.state,
                    'final_genre': e.final_genre,
                    'is_collaboration': e.is_collaboration,
                    'tags': e.tags,
                    'tracks': [
                        {'path': t.path, 'filename': t.filename,
                         'title': t.title, 'duration': t.duration,
                         'genre_tag': t.genre_tag, 'tags': t.tags,
                         'comment': t.comment}
                        for t in e.tracks
                    ],
                }
                for e in self.entries
            ],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f'[CrateSort] Session saved → {path}')
        for e in data['entries'][:5]:
            label = e['final_genre'] or e['proposed_genre']
            print(f'  artist: {e["artist"]} → {label}')
            for t in e['tracks'][:3]:
                print(f'    track: {t["filename"]} → genre_tag={t["genre_tag"]}')

    @classmethod
    def load(cls, path: Path) -> 'ClassificationSession':
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        entries = [
            ArtistEntry(
                artist=e['artist'],
                proposed_genre=e['proposed_genre'],
                confidence=e['confidence'],
                reason=e['reason'],
                tracks=[TrackInfo(
                    path=t['path'], filename=t['filename'],
                    title=t.get('title'), duration=t.get('duration'),
                    genre_tag=t.get('genre_tag'), tags=t.get('tags', []),
                    comment=t.get('comment'),
                ) for t in e['tracks']],
                original_genres=e['original_genres'],
                state=e.get('state', 'pending'),
                final_genre=e.get('final_genre', ''),
                is_collaboration=e.get('is_collaboration', False),
                tags=e.get('tags', []),
            )
            for e in data['entries']
        ]
        return cls(
            library_path=Path(data['library_path']),
            entries=entries,
            created_at=data['created_at'],
        )

    def apply_library_edits(self) -> None:
        """Apply genre overrides and artist reassignments from library_edits.json."""
        edits_file = self.library_path / '_CrateSort' / 'library_edits.json'
        if not edits_file.exists():
            return
        try:
            with open(edits_file, encoding='utf-8') as f:
                edits = json.load(f)
        except Exception:
            return

        # 1. Handle artist reassignments
        reassignments: dict[str, str] = {}
        for path, track_edit in edits.items():
            if 'reassign_artist' in track_edit:
                reassignments[path] = track_edit['reassign_artist']

        if reassignments:
            for entry in list(self.entries):
                moved_tracks = []
                for track in list(entry.tracks):
                    if track.path in reassignments:
                        moved_tracks.append((track, reassignments[track.path]))
                        entry.tracks.remove(track)

                if moved_tracks and entry.state == 'pending':
                    entry.state = 'edited'

                if not entry.tracks:
                    self.entries.remove(entry)

                for track, new_artist in moved_tracks:
                    dest_entry = next(
                        (e for e in self.entries if e.artist == new_artist), None
                    )
                    if dest_entry:
                        dest_entry.tracks.append(track)
                        dest_entry.state = 'edited'
                    else:
                        self.entries.append(ArtistEntry(
                            artist=new_artist,
                            proposed_genre=track.genre_tag or 'Unclassified',
                            confidence='LOW',
                            reason='Manually reassigned in Library',
                            tracks=[track],
                            original_genres=[track.genre_tag] if track.genre_tag else [],
                            state='edited',
                        ))

        # 2. Apply genre overrides (artist-level and track-level)
        for entry in self.entries:
            artist_key = f'__artist__{entry.artist}'
            if 'genre' in edits.get(artist_key, {}):
                new_genre = edits[artist_key]['genre']
                entry.final_genre = new_genre
                if entry.state in ('pending', 'flagged'):
                    entry.state = 'edited'
            for track in entry.tracks:
                if 'genre' in edits.get(track.path, {}):
                    track.genre_tag = edits[track.path]['genre']


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class _ClassifyWorker(QThread):
    progress = pyqtSignal(int, int, str)   # (done, total, artist_name)
    finished = pyqtSignal(object)          # ClassificationSession
    errored  = pyqtSignal(str)

    def __init__(self, inventory, library_path: Path, parent=None):
        super().__init__(parent)
        self._inventory    = inventory
        self._library_path = library_path

    def run(self) -> None:
        try:
            from cratesort.src.core.classifier import GenreClassifier

            classifier = GenreClassifier()

            # Pre-classify every track; separate DJ-tools (untagged short clips)
            # from regular artist tracks so they don't skew artist-level votes.
            dj_tools_tracks: list = []
            artist_tracks: dict[str, list] = defaultdict(list)

            for rec in self._inventory:
                raw_artist = rec.artist or ''
                no_artist = not raw_artist or raw_artist.lower() in ('unknown artist', 'various', 'fx')

                # Fix 7: video files in purpose-video folders → DJ Tools / Specialty
                _VIDEO_PURPOSE = frozenset({
                    'movie clips', '_movie clips', 'commercials', '_commercials',
                    'clips', 'films', 'visuals', '_visuals',
                })
                if rec.is_video:
                    path_lower = str(rec.path).lower()
                    if any(p in path_lower for p in _VIDEO_PURPOSE):
                        dj_tools_tracks.append(rec)
                        continue

                # DJ Tools bucket: no artist, short, in purpose folder
                if no_artist and rec.duration and rec.duration < 60:
                    path_lower = str(rec.path).lower()
                    if any(p in path_lower for p in _DJ_TOOLS_FOLDER_PATTERNS):
                        dj_tools_tracks.append(rec)
                        continue

                # Extract primary artist, then apply sort form
                # This consolidates "The Gap Band" + "Gap Band, The" → "Gap Band, The"
                primary, _ = _extract_primary_artist(raw_artist or 'Unknown Artist')
                canonical   = _canonical_artist(primary)
                artist_tracks[canonical].append(rec)

            artists = sorted(artist_tracks.keys())
            total   = len(artists) + (1 if dj_tools_tracks else 0)
            entries: list[ArtistEntry] = []

            for i, artist in enumerate(artists):
                self.progress.emit(i + 1, total, artist)
                tracks   = artist_tracks[artist]
                results  = classifier.classify_all(tracks)

                # Separate tracks the pre-check flagged as Specialty (short clips)
                # — exclude them from the artist-level genre vote (fix 3)
                vote_results = [
                    (rec, r) for rec, r in results
                    if not (r.genre == 'Specialty'
                            and r.reason.startswith('Short clip'))
                ]
                all_track_infos = [
                    TrackInfo(
                        path=str(rec.path),
                        filename=rec.filename,
                        title=rec.title,
                        duration=rec.duration,
                        genre_tag=rec.genre,
                        comment=rec.comment,
                    )
                    for rec in tracks
                ]

                # Majority vote on genre using only vote-eligible tracks
                genre_votes = Counter(r.genre for _, r in vote_results if r.genre)
                if genre_votes:
                    proposed_genre = genre_votes.most_common(1)[0][0]
                    conf_for_genre = [
                        r.confidence.value for _, r in vote_results
                        if r.genre == proposed_genre
                    ]
                    overall_conf = (
                        'LOW'    if ('LOW' in conf_for_genre or 'NONE' in conf_for_genre) else
                        'MEDIUM' if 'MEDIUM' in conf_for_genre else
                        'HIGH'
                    )
                    reasons = [r.reason for _, r in vote_results if r.genre == proposed_genre]
                    reason  = reasons[0] if reasons else ''
                elif not vote_results and all_track_infos:
                    # ALL tracks were pre-classified as short-specialty clips
                    proposed_genre = 'Specialty'
                    overall_conf   = 'HIGH'
                    reason         = 'All tracks are short clips in purpose folders'
                else:
                    # vote_results existed but none had a classifiable genre
                    proposed_genre = 'Unclassified'
                    overall_conf   = 'NONE'
                    reason         = 'No genre could be determined'

                original_genres = sorted({rec.genre for rec in tracks if rec.genre})

                # If the classifier returned 'Unclassified' but every file already
                # carries a single valid taxonomy genre, honour it at HIGH confidence.
                # CrateSort defers to the existing tags when it has no conflicting opinion.
                if proposed_genre == 'Unclassified' and original_genres:
                    tag_genres = {g for g in original_genres if g in PARENT_GENRES}
                    if len(tag_genres) == 1:
                        proposed_genre = next(iter(tag_genres))
                        overall_conf   = 'HIGH'
                        reason         = f'Existing genre tag: {proposed_genre}'

                # Collaboration detection (fix 7): check if any track in group
                # had feat./ft. or comma-list in the original artist tag
                orig_artists = {rec.artist or '' for rec in tracks}
                is_collab = any(
                    _FEAT_STRIP_RE.search(a) or (
                        _COMMA_NOT_SORT_RE.search(a)
                        and not _looks_like_sort_form(a)
                    )
                    for a in orig_artists if a
                )
                if is_collab and proposed_genre != 'Unclassified':
                    state  = 'flagged'
                    reason = f'Collaboration — {reason}'
                else:
                    state = 'pending'

                entries.append(ArtistEntry(
                    artist=artist,
                    proposed_genre=proposed_genre,
                    confidence=overall_conf,
                    reason=reason,
                    tracks=all_track_infos,
                    original_genres=original_genres,
                    state=state,
                    is_collaboration=is_collab,
                ))

            # DJ Tools bucket (fix 4)
            if dj_tools_tracks:
                self.progress.emit(total, total, DJ_TOOLS_LABEL)
                dj_infos = [
                    TrackInfo(
                        path=str(rec.path),
                        filename=rec.filename,
                        title=rec.title,
                        duration=rec.duration,
                        genre_tag=rec.genre,
                        comment=rec.comment,
                    )
                    for rec in dj_tools_tracks
                ]
                entries.append(ArtistEntry(
                    artist=DJ_TOOLS_LABEL,
                    proposed_genre='Specialty',
                    confidence='HIGH',
                    reason='Untagged short clips in purpose folders',
                    tracks=dj_infos,
                    original_genres=sorted({r.genre for r in dj_tools_tracks if r.genre}),
                    state='pending',
                ))

            session = ClassificationSession(
                library_path=self._library_path,
                entries=entries,
                created_at=datetime.now().isoformat(),
            )
            self.finished.emit(session)
        except Exception as exc:
            import traceback
            self.errored.emit(f'{exc}\n{traceback.format_exc()}')


# ---------------------------------------------------------------------------
# Change-genre dialog
# ---------------------------------------------------------------------------

class _ChangeGenreDialog(QDialog):
    def __init__(self, artist: str, current_genre: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Change Genre')
        self.setMinimumWidth(320)
        self.setStyleSheet("""
            QDialog { background-color: #2F2F2F; }
            QLabel  { color: #f1e3c8; font-weight: 400; font-size: 13px; }
            QLineEdit, QComboBox {
                background-color: #1a1a1a; color: #f1e3c8;
                font-weight: 400; font-size: 13px;
                border: 1px solid #444444; border-radius: 4px; padding: 6px 8px;
            }
            QPushButton {
                font-weight: 400; font-size: 13px;
                padding: 8px 24px; border-radius: 6px; border: none; min-width: 80px;
                background-color: #428175; color: #ffffff;
            }
            QPushButton:hover { background-color: #38706a; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        layout.addWidget(QLabel(f'Select genre for <b>{artist}</b>:'))

        self._combo = QComboBox()
        for g in ALL_GENRES:
            self._combo.addItem(g)
        self._combo.setCurrentText(current_genre)
        layout.addWidget(self._combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        _c = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if _c:
            _c.setStyleSheet(
                'QPushButton { background-color: #C75B5B; color: #ffffff; border-radius: 6px; border: none; padding: 8px 24px; min-width: 80px; }'
                'QPushButton:hover { background-color: #b24c4c; }'
                'QPushButton:pressed { background-color: #9c3b3b; }'
            )
        layout.addWidget(buttons)

    @property
    def selected_genre(self) -> str:
        return self._combo.currentText()


# ---------------------------------------------------------------------------
# Classifier view
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Reassign artist dialog — autocomplete + protection notice (items 9, 12)
# ---------------------------------------------------------------------------

class _ReassignArtistDialog(QDialog):
    def __init__(self, existing_artists: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle('Reassign Artist')
        self.setMinimumWidth(380)
        self.setStyleSheet("""
            QDialog { background-color: #2F2F2F; }
            QLabel  { color: #f1e3c8; font-weight: 400; font-size: 13px; }
            QLineEdit, QComboBox {
                background-color: #1a1a1a; color: #f1e3c8;
                font-weight: 400; font-size: 13px;
                border: 1px solid #444444; border-radius: 4px; padding: 6px 8px;
            }
            QPushButton {
                font-weight: 400; font-size: 13px;
                padding: 8px 24px; border-radius: 6px; border: none; min-width: 80px;
                background-color: #428175; color: #ffffff;
            }
            QPushButton:hover { background-color: #38706a; }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 16)

        layout.addWidget(QLabel('Enter or select an artist name:'))

        self._edit = QLineEdit()
        self._edit.setPlaceholderText('Start typing…')

        # Autocomplete from existing artists (item 9)
        completer = QCompleter(existing_artists, self._edit)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._edit.setCompleter(completer)
        layout.addWidget(self._edit)

        # Protection notice (item 12)
        note = QLabel(
            'Only the artist grouping will change. '
            'Your comments, cue points, and Serato data are never modified.'
        )
        note.setWordWrap(True)
        note.setStyleSheet('color: #a89b85; font-size: 11px; font-style: italic;')
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        _c = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if _c:
            _c.setStyleSheet(
                'QPushButton { background-color: #C75B5B; color: #ffffff; border-radius: 6px; border: none; padding: 8px 24px; min-width: 80px; }'
                'QPushButton:hover { background-color: #b24c4c; }'
                'QPushButton:pressed { background-color: #9c3b3b; }'
            )
        layout.addWidget(buttons)

    @property
    def artist_name(self) -> str:
        return self._edit.text()


# ---------------------------------------------------------------------------
# Edit tags dialog (item 13)
# ---------------------------------------------------------------------------

class _EditTagsDialog(QDialog):
    def __init__(self, track: TrackInfo, parent=None):
        super().__init__(parent)
        self._track = track
        self.setWindowTitle(f'Edit Style Tags — {track.filename}')
        self.setMinimumWidth(400)
        self.setStyleSheet("""
            QDialog { background-color: #2F2F2F; }
            QLabel  { color: #f1e3c8; font-weight: 400; font-size: 13px; }
            QLineEdit, QComboBox {
                background-color: #1a1a1a; color: #f1e3c8;
                font-weight: 400; font-size: 13px;
                border: 1px solid #444444; border-radius: 4px; padding: 6px 8px;
            }
            QPushButton {
                font-weight: 400; font-size: 13px;
                padding: 8px 24px; border-radius: 6px; border: none; min-width: 80px;
                background-color: #428175; color: #ffffff;
            }
            QPushButton:hover { background-color: #38706a; }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 16)

        layout.addWidget(QLabel(f'<b>{track.title or track.filename}</b>'))

        info = QLabel(f'Current genre tag: {track.genre_tag or "(none)"}')
        info.setStyleSheet('color: #a89b85; font-size: 12px;')
        layout.addWidget(info)

        layout.addWidget(QLabel('Style tags (comma-separated):'))

        self._tags_edit = QLineEdit(', '.join(track.tags))
        self._tags_edit.setPlaceholderText('e.g. Boom Bap, Jazzy Hip-Hop')
        layout.addWidget(self._tags_edit)

        note = QLabel('Tags are stored as style metadata and never written to Serato frames.')
        note.setWordWrap(True)
        note.setStyleSheet('color: #a89b85; font-size: 11px; font-style: italic;')
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        raw = self._tags_edit.text()
        self._track.tags = [t.strip() for t in raw.split(',') if t.strip()]
        self.accept()


class ClassifierView(QWidget):
    """
    Two-state widget:
      0 — Loading / classifying  (progress bar)
      1 — Results / approval     (genre list + artist tree)
    """

    done             = pyqtSignal(int) # navigate to Library
    back             = pyqtSignal()    # navigate back to Dashboard
    track_selected   = pyqtSignal(str) # file path of clicked track row (for album art)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session: Optional[ClassificationSession] = None
        self._selected_genre = 'All'
        self._worker: Optional[_ClassifyWorker] = None

        self._stack = QStackedWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)

        self._stack.addWidget(self._build_loading())   # 0
        self._stack.addWidget(self._build_results())   # 1
        self._stack.setCurrentIndex(0)

    # ── Public API ────────────────────────────────────────────────────

    def start(self, inventory, library_path: Path) -> None:
        """Start classification. Checks for an existing session first."""
        session_file = library_path / '_CrateSort' / 'classification_session.json'

        # Load existing session if available
        if session_file.exists():
            try:
                existing = ClassificationSession.load(session_file)
                if str(existing.library_path) == str(library_path):
                    self._load_session(existing)
                    return
            except Exception:
                pass  # corrupt file — re-classify

        self._progress_bar.setValue(0)
        self._progress_label.setText('Classifying artists…')
        self._progress_count.setText('')
        self._stack.setCurrentIndex(0)

        self._worker = _ClassifyWorker(inventory, library_path)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.errored.connect(self._on_error)
        self._worker.start()

    def set_session(self, session: ClassificationSession) -> None:
        self._load_session(session)

    # ── Loading screen ────────────────────────────────────────────────

    def _build_loading(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)
        layout.setContentsMargins(80, 80, 80, 80)

        self._progress_label = QLabel('Classifying artists…')
        self._progress_label.setProperty('role', 'subheading')
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._progress_count = QLabel()
        self._progress_count.setProperty('role', 'muted')
        self._progress_count.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setFixedWidth(360)
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setTextVisible(False)

        layout.addWidget(self._progress_label)
        layout.addWidget(self._progress_count)
        layout.addWidget(self._progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        return w

    # ── Results screen ────────────────────────────────────────────────

    def _build_results(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        outer.addWidget(self._build_header())

        # Main content (genre list + artist tree)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        splitter.addWidget(self._build_genre_panel())
        splitter.addWidget(self._build_artist_panel())
        splitter.setSizes([220, 800])
        splitter.setHandleWidth(1)

        outer.addWidget(splitter, stretch=1)

        # Footer
        outer.addWidget(self._build_footer())
        return w

    def _build_header(self) -> QFrame:
        frame = QFrame()
        frame.setProperty('role', 'card')
        frame.setFrameShape(QFrame.Shape.NoFrame)
        frame.setStyleSheet(
            f'QFrame {{ background: #2F2F2F; border-bottom: 1px solid #444444; '
            f'border-radius: 0; }}'
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        heading = QLabel('Classification Results')
        heading.setProperty('role', 'heading')
        top_row.addWidget(heading)
        top_row.addStretch()

        self._approval_label = QLabel()
        self._approval_label.setProperty('role', 'muted')
        top_row.addWidget(self._approval_label)
        layout.addLayout(top_row)

        desc = QLabel(
            'Review the proposed genre assignments below. '
            '<b>This step only analyzes and tags — no files will be moved or '
            'renamed until you choose to organize.</b>'
        )
        desc.setStyleSheet('color: #a89b85; font-size: 12px;')
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._approval_bar = QProgressBar()
        self._approval_bar.setFixedHeight(4)
        self._approval_bar.setTextVisible(False)
        self._approval_bar.setVisible(False)

        return frame

    def _build_genre_panel(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            'QFrame { background: #2F2F2F; border-right: 1px solid #444444; '
            'border-radius: 0; }'
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        label = QLabel('GENRES')
        label.setProperty('role', 'stat_label')
        label.setContentsMargins(14, 12, 14, 8)
        layout.addWidget(label)

        self._genre_list = QListWidget()
        self._genre_list.setStyleSheet(
            'QListWidget { background: transparent; border: none; }'
            'QListWidget::item { padding: 8px 14px; border-radius: 0; }'
            'QListWidget::item:selected { background: #3d2a18; color: #f1e3c8; '
            'border-left: 3px solid #D17D34; }'
            'QListWidget::item:hover:!selected { background: #252525; }'
        )
        self._genre_list.currentItemChanged.connect(self._on_genre_selected)
        layout.addWidget(self._genre_list, stretch=1)
        return frame

    def _build_artist_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar: search + batch buttons
        toolbar = QFrame()
        toolbar.setStyleSheet(
            'QFrame { background: #252525; border-bottom: 1px solid #444; '
            'border-radius: 0; }'
        )
        tbar_layout = QHBoxLayout(toolbar)
        tbar_layout.setContentsMargins(12, 8, 12, 8)
        tbar_layout.setSpacing(8)

        self._search_bar = QLineEdit()
        self._search_bar.setPlaceholderText('Search artists…')
        self._search_bar.textChanged.connect(self._update_visibility)
        tbar_layout.addWidget(self._search_bar, stretch=1)

        tbar_layout.addStretch()

        self._select_all_btn = QPushButton('Select All')
        self._select_all_btn.setProperty('flat', 'true')
        self._select_all_btn.setMinimumWidth(90)
        self._select_all_btn.clicked.connect(self._toggle_select_all)
        tbar_layout.addWidget(self._select_all_btn)

        self._set_genre_btn = QPushButton('Set Genre…')
        self._set_genre_btn.setProperty('secondary', 'true')
        self._set_genre_btn.clicked.connect(self._batch_set_genre)
        tbar_layout.addWidget(self._set_genre_btn)

        layout.addWidget(toolbar)

        # Artist tree
        self._tree = QTreeWidget()
        self._tree.setColumnCount(8)
        self._tree.setHeaderLabels(
            ['Artist', 'Tracks', 'Confidence', 'Proposed Genre',
             'Current Genre', 'Comments', 'Status', 'File Path']
        )
        self._tree.setAlternatingRowColors(True)
        from PyQt6.QtGui import QPalette as _QPalette
        _cv_pal = self._tree.palette()
        _cv_pal.setColor(_QPalette.ColorRole.Base,          QColor('#242424'))
        _cv_pal.setColor(_QPalette.ColorRole.AlternateBase, QColor('#2a2a2a'))
        self._tree.setPalette(_cv_pal)
        self._tree.setStyleSheet(
            'QTreeWidget { gridline-color: #383838; }'
            'QTreeWidget::item { border-radius: 0;'
            ' border-right: 1px solid #383838; border-bottom: 1px solid #383838; }'
            'QTreeWidget::item:selected { border-right: 1px solid #383838;'
            ' border-bottom: 1px solid #383838; }'
            'QTreeWidget::branch { border: none; }'
        )
        self._tree.setRootIsDecorated(True)
        self._tree.setExpandsOnDoubleClick(True)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self._tree.setSortingEnabled(True)

        hdr = self._tree.header()
        # Fix 2: collapse dead space on left — reduce indentation and branch width
        self._tree.setIndentation(12)
        # All columns user-resizable (Interactive)
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hdr.setStretchLastSection(False)
        self._tree.setColumnWidth(COL_ARTIST,  200)
        self._tree.setColumnWidth(COL_TRACKS,   70)
        self._tree.setColumnWidth(COL_CONF,     85)
        self._tree.setColumnWidth(COL_GENRE,   140)
        self._tree.setColumnWidth(COL_CURRENT, 110)
        self._tree.setColumnWidth(COL_COMMENT, 120)
        self._tree.setColumnWidth(COL_STATUS,  100)
        self._tree.setColumnWidth(COL_PATH,    200)

        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        # Expanding a row shouldn't leave the parent permanently orange
        self._tree.itemExpanded.connect(
            lambda item: item.setSelected(False) if item.isSelected() else None
        )
        # Fix 7: emit track_selected when a track child is clicked (for album art)
        self._tree.itemClicked.connect(self._on_tree_item_clicked)
        layout.addWidget(self._tree, stretch=1)
        return panel

    def _build_footer(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            'QFrame { background: #2F2F2F; border-top: 1px solid #444444; '
            'border-radius: 0; }'
        )
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(20, 10, 20, 10)

        self._footer_label = QLabel()
        self._footer_label.setProperty('role', 'muted')
        layout.addWidget(self._footer_label)
        layout.addStretch()

        back_btn = QPushButton('← Back to Dashboard')
        back_btn.setProperty('flat', 'true')
        back_btn.clicked.connect(self.back.emit)
        layout.addWidget(back_btn)

        done_btn = QPushButton('Accept && Go to Library')
        done_btn.setProperty('secondary', 'true')
        done_btn.clicked.connect(self._on_done)
        layout.addWidget(done_btn)

        return frame

    # ── Session loading ───────────────────────────────────────────────

    def _apply_library_edits(self) -> None:
        """Apply any genre overrides from library_edits.json on top of the loaded session."""
        if not self._session:
            return
        edits_file = self._session.library_path / '_CrateSort' / 'library_edits.json'
        if not edits_file.exists():
            return
        try:
            with open(edits_file, encoding='utf-8') as f:
                edits = json.load(f)
        except Exception:
            return
        for entry in self._session.entries:
            artist_key = f'__artist__{entry.artist}'
            if 'genre' in edits.get(artist_key, {}):
                new_genre = edits[artist_key]['genre']
                entry.final_genre = new_genre
                if entry.state in ('pending', 'flagged'):
                    entry.state = 'edited'
            for track in entry.tracks:
                if 'genre' in edits.get(track.path, {}):
                    track.genre_tag = edits[track.path]['genre']

    def _load_session(self, session: ClassificationSession) -> None:
        self._session = session
        self._session.apply_library_edits()
        self._selected_genre = 'All'
        self._rebuild_genre_list()
        self._rebuild_tree()
        self._update_approval_display()
        self._stack.setCurrentIndex(1)

    def _rebuild_genre_list(self) -> None:
        self._genre_list.blockSignals(True)
        self._genre_list.clear()

        if not self._session:
            self._genre_list.blockSignals(False)
            return

        # Count artists per genre
        genre_artist_count: dict[str, int] = Counter(
            e.display_genre for e in self._session.entries
        )
        genre_track_count: dict[str, int] = defaultdict(int)
        genre_min_conf: dict[str, str] = {}

        for e in self._session.entries:
            g = e.display_genre
            genre_track_count[g] += e.track_count
            cur = genre_min_conf.get(g, 'HIGH')
            rank = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1, 'NONE': 0}
            if rank.get(e.confidence, 0) < rank.get(cur, 3):
                genre_min_conf[g] = e.confidence

        total_a = len(self._session.entries)
        total_t = sum(e.track_count for e in self._session.entries)

        # "All" item
        all_item = QListWidgetItem(f'All  ({total_a} artists, {total_t} tracks)')
        all_item.setData(Qt.ItemDataRole.UserRole, 'All')
        all_item.setForeground(QBrush(QColor('#f1e3c8')))
        self._genre_list.addItem(all_item)

        # Genre items
        for genre in sorted(genre_artist_count.keys()):
            if genre == 'Unclassified':
                continue
            ac = genre_artist_count[genre]
            tc = genre_track_count[genre]
            conf_color = CONFIDENCE_COLORS.get(genre_min_conf.get(genre, 'HIGH'), '#6B9E78')
            text = f'● {genre}\n   {ac} artists · {tc} tracks'
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, genre)
            item.setForeground(QBrush(QColor('#f1e3c8')))
            # Tint the dot color via tooltip (actual color set in paint would need delegate)
            item.setToolTip(f'Lowest confidence in group: {genre_min_conf.get(genre, "HIGH")}')
            self._genre_list.addItem(item)

        # Unclassified
        if 'Unclassified' in genre_artist_count:
            ac = genre_artist_count['Unclassified']
            unc_item = QListWidgetItem(f'⚠ Unclassified\n   {ac} artists')
            unc_item.setData(Qt.ItemDataRole.UserRole, 'Unclassified')
            unc_item.setForeground(QBrush(QColor('#C75B5B')))
            self._genre_list.addItem(unc_item)

        # Re-select current genre
        for i in range(self._genre_list.count()):
            if self._genre_list.item(i).data(Qt.ItemDataRole.UserRole) == self._selected_genre:
                self._genre_list.setCurrentRow(i)
                break
        else:
            self._genre_list.setCurrentRow(0)

        self._genre_list.blockSignals(False)

    def _rebuild_tree(self) -> None:
        self._tree.setSortingEnabled(False)
        self._tree.clear()

        if not self._session:
            return

        for entry in self._session.entries:
            item = self._make_artist_item(entry)
            self._tree.addTopLevelItem(item)

            # Compute common path for artist row (fix 2)
            paths = [Path(t.path) for t in entry.tracks]
            if paths:
                common = str(paths[0].parent) if len(paths) == 1 else (
                    str(paths[0].parent)
                    if all(p.parent == paths[0].parent for p in paths)
                    else 'Multiple locations'
                )
            else:
                common = '—'
            item.setText(COL_PATH, common)
            item.setForeground(COL_PATH, QBrush(QColor('#a89b85')))

            # DJ Tools entries get a distinct tint
            if entry.artist == DJ_TOOLS_LABEL:
                for col in range(8):
                    item.setForeground(col, QBrush(QColor('#888888')))

            # Track children
            for track in entry.tracks:
                self._make_track_child(item, track)

        self._tree.setSortingEnabled(True)
        self._tree.sortByColumn(COL_ARTIST, Qt.SortOrder.AscendingOrder)
        self._update_visibility()

    def _make_artist_item(self, entry: ArtistEntry) -> QTreeWidgetItem:
        item = QTreeWidgetItem()
        item.setData(COL_ARTIST, Qt.ItemDataRole.UserRole, entry)
        item.setFlags(
            item.flags()
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsEnabled
        )
        item.setCheckState(COL_ARTIST, Qt.CheckState.Unchecked)
        self._refresh_item_display(item, entry)
        return item

    def _refresh_item_display(self, item: QTreeWidgetItem, entry: ArtistEntry) -> None:
        item.setText(COL_ARTIST,  entry.artist)
        item.setText(COL_TRACKS,  str(entry.track_count))
        item.setText(COL_CONF,    entry.confidence)
        item.setForeground(COL_CONF, QBrush(QColor(
            CONFIDENCE_COLORS.get(entry.confidence, '#a89b85')
        )))
        item.setText(COL_GENRE,   entry.display_genre)
        item.setText(COL_CURRENT, ', '.join(entry.original_genres) or '—')
        item.setText(COL_COMMENT, '')
        if entry.state in ('edited', 'changed'):
            item.setText(COL_STATUS, 'Modified')
            item.setForeground(COL_STATUS, QBrush(QColor('#428175')))
        else:
            item.setText(COL_STATUS, '')
            item.setForeground(COL_STATUS, QBrush(QColor('#a89b85')))
        if entry.reason:
            item.setToolTip(COL_CONF, entry.reason)

    # ── Filtering ─────────────────────────────────────────────────────

    def _on_genre_selected(self, current: QListWidgetItem, _) -> None:
        if current:
            self._selected_genre = current.data(Qt.ItemDataRole.UserRole) or 'All'
            self._update_visibility()

    def _update_visibility(self) -> None:
        genre  = self._selected_genre
        search = self._search_bar.text().lower().strip()

        for i in range(self._tree.topLevelItemCount()):
            item  = self._tree.topLevelItem(i)
            entry = item.data(COL_ARTIST, Qt.ItemDataRole.UserRole)

            genre_match = (
                genre == 'All'
                or entry.display_genre == genre
                or (genre == 'Unclassified' and entry.proposed_genre == 'Unclassified')
            )
            search_match = not search or search in entry.artist.lower()
            item.setHidden(not (genre_match and search_match))

    # ── Approval actions ──────────────────────────────────────────────

    @staticmethod
    def _do_approve(entry: ArtistEntry) -> None:
        """
        Correctly approve an entry regardless of current state.
        Must set final_genre BEFORE setting state='approved' to avoid circular
        reference: display_genre returns final_genre when state is approved, but
        if final_genre is still empty when state changes, display_genre returns ''.
        """
        if not entry.final_genre:           # pending/flagged — no manual edit yet
            entry.final_genre = entry.proposed_genre
        # else: edited — keep the user's manual final_genre choice
        entry.state = 'approved'

    @staticmethod
    def _cascade_genre_to_children(entry: ArtistEntry, item: QTreeWidgetItem, genre: str) -> None:
        for i, track in enumerate(entry.tracks):
            track.genre_tag = genre
            if i < item.childCount():
                item.child(i).setText(COL_GENRE, genre)
        print(f'[Cascade] {entry.artist} tracks updated:')
        for t in entry.tracks:
            print(f'  {t.filename} → genre_tag={t.genre_tag}')

    def _approve_entry(self, entry: ArtistEntry, item: QTreeWidgetItem) -> None:
        self._do_approve(entry)
        self._refresh_item_display(item, entry)
        self._on_state_changed()

    def _change_entry_genre(self, entry: ArtistEntry, item: QTreeWidgetItem) -> None:
        dlg = _ChangeGenreDialog(entry.artist, entry.display_genre, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            entry.state       = 'edited'
            entry.final_genre = dlg.selected_genre
            self._refresh_item_display(item, entry)
            self._on_state_changed()
            self._tree.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)

    def _flag_entry(self, entry: ArtistEntry, item: QTreeWidgetItem) -> None:
        entry.state = 'flagged'
        self._refresh_item_display(item, entry)
        self._on_state_changed()

    def _toggle_select_all(self) -> None:
        """Fix 12: toggle Select All / Deselect All."""
        checked = [
            self._tree.topLevelItem(i)
            for i in range(self._tree.topLevelItemCount())
            if self._tree.topLevelItem(i).checkState(COL_ARTIST) == Qt.CheckState.Checked
        ]
        select = len(checked) < self._tree.topLevelItemCount()
        state  = Qt.CheckState.Checked if select else Qt.CheckState.Unchecked
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if not item.isHidden():
                item.setCheckState(COL_ARTIST, state)
        self._select_all_btn.setText('Deselect All' if select else 'Select All')

    def _get_selected_tracks(self) -> list[QTreeWidgetItem]:
        return [item for item in self._tree.selectedItems() if item.parent()]

    def _batch_set_genre(self) -> None:
        """Set Genre for selected track rows (takes priority) or checked artist rows."""
        selected_tracks = self._get_selected_tracks()
        if selected_tracks:
            first_track: TrackInfo = selected_tracks[0].data(COL_PATH, Qt.ItemDataRole.UserRole)
            current_genre = first_track.genre_tag or '' if first_track else ''
            dlg = _ChangeGenreDialog(f'{len(selected_tracks)} tracks', current_genre, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            new_genre = dlg.selected_genre
            for child in selected_tracks:
                track: TrackInfo = child.data(COL_PATH, Qt.ItemDataRole.UserRole)
                if track:
                    track.genre_tag = new_genre
                    child.setText(COL_GENRE, new_genre)
            if self._session:
                self._session.save()
            return

        checked_items = [
            self._tree.topLevelItem(i)
            for i in range(self._tree.topLevelItemCount())
            if self._tree.topLevelItem(i).checkState(COL_ARTIST) == Qt.CheckState.Checked
        ]
        if not checked_items:
            return
        first_entry = checked_items[0].data(COL_ARTIST, Qt.ItemDataRole.UserRole)
        current_genre = first_entry.display_genre if first_entry else ''
        dlg = _ChangeGenreDialog(f'{len(checked_items)} artists', current_genre, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_genre = dlg.selected_genre
        for item in checked_items:
            entry = item.data(COL_ARTIST, Qt.ItemDataRole.UserRole)
            if entry:
                entry.state       = 'edited'
                entry.final_genre = new_genre
                self._refresh_item_display(item, entry)
        self._on_state_changed()

    def _approve_all_high(self) -> None:
        for i in range(self._tree.topLevelItemCount()):
            item  = self._tree.topLevelItem(i)
            entry = item.data(COL_ARTIST, Qt.ItemDataRole.UserRole)
            if entry and entry.confidence == 'HIGH' and entry.state != 'approved':
                self._do_approve(entry)
                self._refresh_item_display(item, entry)
        self._on_state_changed()

    def _approve_selected(self) -> None:
        """Fix 3: approve checked rows, not highlighted/selected rows."""
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item.checkState(COL_ARTIST) != Qt.CheckState.Checked:
                continue
            entry = item.data(COL_ARTIST, Qt.ItemDataRole.UserRole)
            if entry and entry.state != 'approved':
                self._do_approve(entry)
                self._refresh_item_display(item, entry)
        self._on_state_changed()

    def _approve_all(self) -> None:
        for i in range(self._tree.topLevelItemCount()):
            item  = self._tree.topLevelItem(i)
            entry = item.data(COL_ARTIST, Qt.ItemDataRole.UserRole)
            if entry and entry.state != 'approved':
                self._do_approve(entry)
                self._refresh_item_display(item, entry)
        self._on_state_changed()

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Emit track_selected when a track child row is clicked (for album art)."""
        if item.parent():  # child = track row
            track: TrackInfo = item.data(COL_PATH, Qt.ItemDataRole.UserRole)
            if track and hasattr(track, 'path'):
                self.track_selected.emit(track.path)

    def _on_state_changed(self) -> None:
        if self._session:
            self._session.save()
        self._rebuild_genre_list()
        self._update_approval_display()

    def _update_approval_display(self) -> None:
        if not self._session:
            return
        total_artists = self._session.total_count
        total_tracks  = sum(e.track_count for e in self._session.entries)
        self._approval_label.setText(f'{total_artists:,} artists · {total_tracks:,} tracks')
        self._footer_label.setText('')

    # ── Context menus ─────────────────────────────────────────────────

    def _on_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if not item:
            return
        # If the right-clicked item is not currently selected, select only it.
        # If it is selected, preserve the entire multi-selection.
        if not item.isSelected():
            self._tree.clearSelection()
            item.setSelected(True)
        # Snapshot before the menu/dialog runs so selection can't be mutated
        self._context_selection: list[QTreeWidgetItem] = list(self._tree.selectedItems())
        if item.parent():
            self._track_context_menu(item, pos)
        else:
            self._artist_context_menu(item, pos)

    def _change_genre_for_selection(self, hint_label: str = '', hint_genre: str = '') -> None:
        """Apply a single genre change to every currently selected item (artist or track)."""
        selected = getattr(self, '_context_selection', None) or list(self._tree.selectedItems())
        print(f'[DEBUG ClassifierView] _change_genre_for_selection: {len(selected)} items')
        for dbg in selected:
            print(f'  {"ARTIST" if dbg.parent() is None else "TRACK"}: {dbg.text(0)!r}')
        if not selected:
            return
        dlg = _ChangeGenreDialog(hint_label or f'{len(selected)} items', hint_genre, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_genre = dlg.selected_genre
        for item in selected:
            if item.parent() is None:
                entry: ArtistEntry = item.data(COL_ARTIST, Qt.ItemDataRole.UserRole)
                if entry:
                    entry.state = 'edited'
                    entry.final_genre = new_genre
                    self._refresh_item_display(item, entry)
            else:
                track: TrackInfo = item.data(COL_PATH, Qt.ItemDataRole.UserRole)
                if track:
                    track.genre_tag = new_genre
                    item.setText(COL_GENRE, new_genre)
        self._on_state_changed()

    def _artist_context_menu(self, item: QTreeWidgetItem, pos) -> None:
        entry = item.data(COL_ARTIST, Qt.ItemDataRole.UserRole)
        if not entry:
            return
        menu = QMenu(self)
        approve_act   = menu.addAction('✓ Approve')
        change_act    = menu.addAction('↕ Change Genre…')
        edit_tags_act = menu.addAction('✏ Edit Style Tags…')
        flag_act      = menu.addAction('⚑ Mark for Review')
        action = menu.exec(self._tree.viewport().mapToGlobal(pos))
        if action == approve_act:
            self._approve_entry(entry, item)
        elif action == change_act:
            self._change_genre_for_selection(entry.artist, entry.display_genre)
        elif action == edit_tags_act:
            self._edit_artist_tags(entry)
        elif action == flag_act:
            self._flag_entry(entry, item)

    def _edit_artist_tags(self, entry: ArtistEntry) -> None:
        proxy = type('T', (), {
            'filename': entry.artist,
            'title':    entry.artist,
            'genre_tag': entry.display_genre,
            'tags':     list(entry.tags),
            'comment':  '',
        })()
        dlg = _EditTagsDialog(proxy, self)
        dlg.setWindowTitle(f'Edit Style Tags — {entry.artist}')
        if dlg.exec() == QDialog.DialogCode.Accepted:
            entry.tags = list(proxy.tags)
            if self._session:
                self._session.save()

    def _track_context_menu(self, child: QTreeWidgetItem, pos) -> None:
        """Context menu for expanded track rows."""
        track: TrackInfo = child.data(COL_PATH, Qt.ItemDataRole.UserRole)
        if not track:
            return
        parent_item  = child.parent()
        parent_entry: ArtistEntry = parent_item.data(COL_ARTIST, Qt.ItemDataRole.UserRole)

        menu = QMenu(self)
        reassign_act  = menu.addAction('↪ Reassign Artist…')
        chg_genre_act = menu.addAction('↕ Change Genre…')
        edit_tags_act = menu.addAction('✏ Edit Style Tags…')        # item 13
        menu.addSeparator()
        finder_act    = menu.addAction('📂 Show in Finder')

        action = menu.exec(self._tree.viewport().mapToGlobal(pos))

        if action == reassign_act:
            selected_tracks = [
                it for it in self._context_selection if it.parent() is not None
            ]
            if len(selected_tracks) <= 1:
                # Single track — _reassign_track shows its own dialog
                self._reassign_track(child, track, parent_item, parent_entry)
            else:
                # Multi-select: show dialog once, apply new artist to all selected tracks
                existing = [e.artist for e in self._session.entries] if self._session else []
                dlg = _ReassignArtistDialog(existing, self)
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    return
                new_artist = dlg.artist_name.strip()
                if not new_artist:
                    return
                # Snapshot parent references before any tree modifications so
                # indices stay valid across iterations (items move as children are removed)
                to_reassign = []
                for sel_item in selected_tracks:
                    t: TrackInfo = sel_item.data(COL_PATH, Qt.ItemDataRole.UserRole)
                    p_item = sel_item.parent()
                    if p_item is None:
                        continue
                    p_entry: ArtistEntry = p_item.data(COL_ARTIST, Qt.ItemDataRole.UserRole)
                    if t and p_entry:
                        to_reassign.append((sel_item, t, p_item, p_entry))
                for sel_item, t, p_item, p_entry in to_reassign:
                    self._reassign_track(sel_item, t, p_item, p_entry, new_artist=new_artist)
        elif action == chg_genre_act:
            self._change_genre_for_selection(track.filename, track.genre_tag or '')
        elif action == edit_tags_act:
            self._edit_track_tags(track)
        elif action == finder_act:
            self._show_in_finder(track.path)

    def _reassign_track(
        self,
        child: QTreeWidgetItem,
        track: TrackInfo,
        parent_item: QTreeWidgetItem,
        parent_entry: ArtistEntry,
        new_artist: Optional[str] = None,
    ) -> None:
        if new_artist is None:
            existing = [e.artist for e in self._session.entries] if self._session else []
            # Items 9 + 12: custom dialog with autocomplete and protection notice
            dlg = _ReassignArtistDialog(existing, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            new_artist = dlg.artist_name.strip()
        if not new_artist:
            return

        # Remove track from current parent
        parent_entry.tracks.remove(track)
        idx = parent_item.indexOfChild(child)
        parent_item.takeChild(idx)
        parent_item.setText(COL_TRACKS, str(len(parent_entry.tracks)))

        # If parent is now empty, remove the artist entry
        if not parent_entry.tracks:
            top_idx = self._tree.indexOfTopLevelItem(parent_item)
            self._tree.takeTopLevelItem(top_idx)
            if self._session:
                self._session.entries = [
                    e for e in self._session.entries if e is not parent_entry
                ]

        # Mark source as Edited (item 8)
        if parent_entry.state == 'pending':
            parent_entry.state = 'edited'
            self._refresh_item_display(parent_item, parent_entry)

        dest_tree_item = None  # track for auto-expand (item 11)

        # Find or create destination artist entry
        dest_entry = next(
            (e for e in (self._session.entries if self._session else [])
             if e.artist == new_artist),
            None,
        )
        if dest_entry:
            dest_entry.tracks.append(track)
            dest_entry.state = 'edited'  # item 8
            # Update destination tree item — add proper child (item 10)
            for i in range(self._tree.topLevelItemCount()):
                it = self._tree.topLevelItem(i)
                if it.data(COL_ARTIST, Qt.ItemDataRole.UserRole) is dest_entry:
                    new_child = self._make_track_child(it, track)
                    it.setText(COL_TRACKS, str(len(dest_entry.tracks)))
                    self._refresh_item_display(it, dest_entry)
                    dest_tree_item = it
                    break
        else:
            # Create new artist entry with proper expandable tree (item 10)
            new_entry = ArtistEntry(
                artist=new_artist,
                proposed_genre=track.genre_tag or 'Unclassified',
                confidence='LOW',
                reason='Manually reassigned',
                tracks=[track],
                original_genres=[track.genre_tag] if track.genre_tag else [],
                state='edited',
            )
            if self._session:
                self._session.entries.append(new_entry)
            new_item = self._make_artist_item(new_entry)
            self._make_track_child(new_item, track)   # item 10: add child immediately
            new_item.setText(COL_PATH, str(Path(track.path).parent))
            self._tree.addTopLevelItem(new_item)
            dest_tree_item = new_item

        # Item 11: auto-expand destination and show toast
        if dest_tree_item:
            dest_tree_item.setExpanded(True)
            self._footer_label.setText(f'↪ Track moved to: {new_artist}')
            QTimer.singleShot(3500, lambda: self._update_approval_display())

        if self._session:
            # Persist reassignment to library_edits.json so it propagates to plan and library browser
            edits_file = self._session.library_path / '_CrateSort' / 'library_edits.json'
            edits = {}
            if edits_file.exists():
                try:
                    with open(edits_file, encoding='utf-8') as f:
                        edits = json.load(f)
                except Exception:
                    pass
            edits.setdefault(track.path, {})['reassign_artist'] = new_artist
            edits.setdefault(track.path, {})['original_artist'] = parent_entry.artist

            edits_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(edits_file, 'w', encoding='utf-8') as f:
                    json.dump(edits, f, indent=2)
            except Exception as exc:
                print(f'[ClassifierView] Failed to save edits: {exc}')

            self._session.save()
        self._rebuild_genre_list()
        self._update_approval_display()

    def _make_track_child(self, parent_item: QTreeWidgetItem, track: TrackInfo) -> QTreeWidgetItem:
        """Create a properly styled track child item."""
        child = QTreeWidgetItem(parent_item)
        dur = (f'{int(track.duration // 60)}:{int(track.duration % 60):02d}'
               if track.duration else '—')
        ext = Path(track.path).suffix.lstrip('.').upper() or '—'
        display_title = track.title or track.filename
        comment_text = ''
        if track.comment:
            comment_text = (track.comment[:50] + '…') if len(track.comment) > 50 else track.comment
        # Fix 5: COL_GENRE shows the ARTIST's classified genre (Proposed Genre column)
        #         COL_CURRENT shows the file's raw genre tag (Current Genre column)
        parent_entry = parent_item.data(COL_ARTIST, Qt.ItemDataRole.UserRole)
        classified_genre = parent_entry.display_genre if parent_entry else (track.genre_tag or '—')
        child.setText(COL_ARTIST,  f'  {display_title}')
        child.setText(COL_TRACKS,  dur)
        child.setText(COL_CONF,    ext)
        child.setText(COL_GENRE,   classified_genre)    # artist's CrateSort genre
        child.setText(COL_CURRENT, track.genre_tag or '—')  # raw file tag
        child.setText(COL_COMMENT, comment_text)
        child.setText(COL_STATUS,  '')
        child.setText(COL_PATH,    track.path)
        child.setData(COL_PATH, Qt.ItemDataRole.UserRole, track)
        child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        if track.comment:
            child.setToolTip(COL_COMMENT, track.comment)   # full comment in tooltip
        muted = QBrush(QColor('#a89b85'))
        for col in range(8):
            child.setForeground(col, muted)
        return child

    def _change_track_genre(self, child: QTreeWidgetItem, track: TrackInfo) -> None:
        dlg = _ChangeGenreDialog(track.filename, track.genre_tag or '', self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_genre = dlg.selected_genre
            selected = self._get_selected_tracks()
            if child not in selected:
                selected = [child]
            for sel in selected:
                t: TrackInfo = sel.data(COL_PATH, Qt.ItemDataRole.UserRole)
                if t:
                    t.genre_tag = new_genre
                    sel.setText(COL_GENRE, new_genre)
            if self._session:
                self._session.save()

    def _edit_track_tags(self, track: TrackInfo) -> None:
        """Item 13: open Edit Tags dialog."""
        dlg = _EditTagsDialog(track, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if self._session:
                self._session.save()

    def _show_in_finder(self, file_path: str) -> None:
        try:
            if _sys.platform == 'darwin':
                subprocess.run(['open', '-R', file_path], check=False)
            elif _sys.platform == 'win32':
                subprocess.run(['explorer', f'/select,{file_path}'], check=False)
            else:
                subprocess.run(['xdg-open', str(Path(file_path).parent)], check=False)
        except Exception:
            pass


    def _on_genre_context_menu(self, pos) -> None:
        """Item 15: genre sidebar right-click → Approve All in [Genre]."""
        item = self._genre_list.itemAt(pos)
        if not item:
            return
        genre = item.data(Qt.ItemDataRole.UserRole)
        if not genre or genre == 'All':
            return
        menu = QMenu(self)
        approve_act = menu.addAction(f'✓ Approve All in {genre}')
        action = menu.exec(self._genre_list.viewport().mapToGlobal(pos))
        if action == approve_act:
            self._approve_all_in_genre(genre)

    def _approve_all_in_genre(self, genre: str) -> None:
        for i in range(self._tree.topLevelItemCount()):
            item  = self._tree.topLevelItem(i)
            entry = item.data(COL_ARTIST, Qt.ItemDataRole.UserRole)
            if entry and entry.display_genre == genre and entry.state != 'approved':
                self._do_approve(entry)
                self._refresh_item_display(item, entry)
        self._on_state_changed()

    # ── Worker slots ──────────────────────────────────────────────────

    def _on_progress(self, done: int, total: int, artist: str) -> None:
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(done)
        self._progress_count.setText(f'{done} of {total} artists classified… ({artist})')

    def _on_finished(self, session: ClassificationSession) -> None:
        self._load_session(session)
        session.save()

    def _on_error(self, message: str) -> None:
        self._progress_label.setText('Classification failed')
        self._progress_count.setText(message)

    def _on_done(self) -> None:
        if self._session:
            self._session.save()
        self.done.emit(0)
