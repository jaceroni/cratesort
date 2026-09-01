from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QSettings, QStringListModel, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCompleter, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QProgressBar, QPushButton, QVBoxLayout,
)

from cratesort.src.gui.overlays import (
    _ArrowComboBox, _CrateSortDialog, _create_dialog_layout, _ov_confirm,
)
from cratesort.src.utils.ffmpeg_tools import format_elapsed, get_ffmpeg_path, get_media_duration
from cratesort.src.utils.metadata_copy import embed_artwork


# ---------------------------------------------------------------------------
# Error text cleanup
# ---------------------------------------------------------------------------

_ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')


def _strip_ansi(text: str) -> str:
    """yt-dlp colorizes its own error/log text with raw ANSI escape codes
    regardless of `quiet`/`no_warnings` — strip them before showing an
    exception message anywhere in the UI."""
    return _ANSI_ESCAPE_RE.sub('', text)


# ---------------------------------------------------------------------------
# YouTube sign-in (cookies)
# ---------------------------------------------------------------------------
#
# YouTube increasingly serves a "confirm you're not a bot" challenge instead
# of the media for unauthenticated requests. yt-dlp clears it when handed
# cookies from a browser the user is signed in to YouTube with. Label → the
# browser key yt-dlp's `cookiesfrombrowser` expects.

_COOKIE_BROWSERS: list[tuple[str, str]] = [
    ("Don't use a login", ''),
    ('Safari',        'safari'),
    ('Chrome',        'chrome'),
    ('Firefox',       'firefox'),
    ('Edge',          'edge'),
    ('Brave',         'brave'),
    ('Chromium',      'chromium'),
]
_COOKIE_FILE_LABEL = 'Cookie file…'

# Quality combo — index 0 is the default (fastest, single android request).
_QUALITY_LABELS = ['Fast — about 360p', 'Best available (slower)']
_QUALITY_VALUES = ['fast', 'best']


def _humanize_yt_error(text: str) -> str:
    """Translate the common YouTube failure walls into a short, actionable
    line that points at this dialog's own controls. Anything unrecognised
    passes through unchanged (ANSI already stripped by the caller)."""
    low = text.lower()
    if 'cookies' in low and any(k in low for k in (
        'database', 'could not', 'unable to', 'failed to', 'permission',
        'no such file', 'not found',
    )):
        return (
            "CrateSort couldn't read the login from that browser. Try a "
            "different one under YOUTUBE LOGIN, or choose \"Cookie file…\" "
            "and load a cookies.txt you exported yourself."
        )
    if ('inappropriate for some users' in low
            or 'confirm your age' in low
            or 'age-restricted' in low or 'age restricted' in low):
        return (
            "This video is age-restricted, and YouTube only serves it to a "
            "signed-in adult account. Set YOUTUBE LOGIN above to a browser "
            "where you're signed in to YouTube (18+) and try again — if that "
            "still fails, YouTube won't let CrateSort fetch it."
        )
    if ('not a bot' in low or 'sign in to confirm' in low
            or 'page needs to be reloaded' in low
            or 'requested format is not available' in low
            or 'failed to extract any player response' in low):
        return (
            "YouTube blocked every way CrateSort can fetch this video right "
            "now. This usually means YouTube has rate-limited your connection "
            "after several tries — wait a few hours or switch networks (a "
            "phone hotspot works). Setting YOUTUBE LOGIN above can sometimes "
            "help. Age- or region-restricted videos can't be fetched at all."
        )
    return text


# ---------------------------------------------------------------------------
# Title parser
# ---------------------------------------------------------------------------

def _parse_yt_title(title: str, uploader: str = '') -> tuple[str, str]:
    """Best-effort split of a YouTube title into (artist, track_title)."""
    clean = re.sub(
        r'\s*[\(\[]\s*(?:official\s*(?:video|audio|music\s*video|lyric(?:s)?\s*'
        r'video|visualizer)?|lyrics?|hd|4k|remaster(?:ed)?|explicit|clean|'
        r'radio\s*edit|extended(?:\s*mix)?|original\s*mix|full\s*(?:song|album)?|'
        r'live(?:\s+at.*)?|performance|prod\.?\s+.*?|dir\.?\s+.*?)\s*[\)\]]\s*$',
        '', title, flags=re.IGNORECASE,
    ).strip()

    clean = re.sub(
        r'\s+(?:feat\.?|ft\.?|featuring)\s+.+$', '', clean, flags=re.IGNORECASE,
    ).strip()

    for sep in (' - ', ' – ', ' — ', ': '):
        if sep in clean:
            left, right = clean.split(sep, 1)
            if left.strip() and right.strip():
                return left.strip(), right.strip()

    return (uploader.strip() or ''), clean


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------

class _MetadataFetchWorker(QThread):
    """Fetches YouTube metadata without downloading."""
    fetched = pyqtSignal(dict)
    failed  = pyqtSignal(str)

    def __init__(self, url: str, cookie_opts: dict | None = None, parent=None):
        super().__init__(parent)
        self._url = url
        self._cookie_opts = cookie_opts or {}

    def run(self) -> None:
        try:
            import yt_dlp
            opts = {'quiet': True, 'no_warnings': True, **self._cookie_opts}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self._url, download=False) or {}
            self.fetched.emit({
                'title':    info.get('title', ''),
                'uploader': info.get('uploader', info.get('channel', '')),
                'year':     str(info.get('upload_date', ''))[:4],
            })
        except Exception as exc:
            self.failed.emit(_strip_ansi(str(exc)))


class _MusicBrainzWorker(QThread):
    """Queries MusicBrainz for canonical metadata using artist + title text."""
    found     = pyqtSignal(dict)
    not_found = pyqtSignal()

    def __init__(self, artist: str, title: str, parent=None):
        super().__init__(parent)
        self._artist = artist
        self._title  = title

    def run(self) -> None:
        try:
            result = self._query()
            if result:
                self.found.emit(result)
            else:
                self.not_found.emit()
        except Exception:
            self.not_found.emit()

    def _query(self) -> Optional[dict]:
        artist = self._artist.strip()
        title  = self._title.strip()
        if not title:
            return None

        parts = []
        if artist:
            parts.append(f'artist:"{urllib.parse.quote(artist)}"')
        parts.append(f'recording:"{urllib.parse.quote(title)}"')

        url = (
            'https://musicbrainz.org/ws/2/recording/'
            f'?query={"+AND+".join(parts)}&fmt=json&limit=5'
        )
        req = urllib.request.Request(
            url, headers={'User-Agent': 'CrateSort/1.0 ( https://mycrateview.com )'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        recordings = data.get('recordings', [])
        if not recordings:
            return None

        best  = recordings[0]
        score = int(best.get('score', 0))
        if score < 60:
            return None

        mb_artist = ''
        credits = best.get('artist-credit', [])
        if credits:
            mb_artist = credits[0].get('artist', {}).get('name', '')

        mb_title = best.get('title', '')
        mb_year  = str(best.get('first-release-date', ''))[:4]

        mb_album = ''
        releases = best.get('releases', [])
        if releases:
            mb_album = releases[0].get('title', '')

        mb_genre = ''
        genres = best.get('genres', [])
        if genres:
            mb_genre = genres[0].get('name', '').title()

        return {
            'artist': mb_artist, 'title': mb_title,
            'album':  mb_album,  'year':  mb_year,
            'genre':  mb_genre,  'score': score,
        }


class _Cancelled(Exception):
    pass


class _YTWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    errored  = pyqtSignal(str)

    def __init__(self, url: str, fmt: str, dest_dir: Path,
                 cookie_opts: dict | None = None, quality: str = 'fast',
                 parent=None):
        super().__init__(parent)
        self._url         = url
        self._fmt         = fmt
        self._dest        = dest_dir
        self._cookie_opts = cookie_opts or {}
        self._quality     = quality          # 'fast' (android only) or 'best'
        self._cancelled   = False

    def cancel(self) -> None:
        self._cancelled = True

    # ── yt-dlp download with client fallback ─────────────────────────────────
    #
    # YouTube now gates its normal (`web`/`tv`) player responses behind a
    # "PO token" that yt-dlp can't mint on its own — an unauthenticated
    # request hits "Sign in to confirm you're not a bot", and a
    # cookie-authenticated one hits "The page needs to be reloaded". The one
    # client that still returns a usable stream without a token is `android`,
    # but it rejects the request outright if cookies are attached.
    #
    # `quality == 'fast'` (the default): go straight to the `android` client —
    # ~360p, but one request, no waiting on the HD attempts that almost always
    # fail. `quality == 'best'`: try the site default first (best quality when
    # it works, honouring the user's cookies), then `web_embedded` (age-gate
    # bypass), then fall back to `android`.

    _ANDROID_STRATEGY = (
        'android',
        {'extractor_args': {'youtube': {'player_client': ['android']}}},
        False,
    )

    def _download_with_fallback(self, yt_dlp, tmpdir: str, base_opts: dict) -> None:
        if self._quality == 'best':
            strategies = [
                ('default', {}, True),
                # web_embedded honours an age-verified account's cookies and is
                # the usual way past "this video may be inappropriate" — a
                # no-op for normal videos, so it just falls through.
                ('web_embedded',
                 {'extractor_args': {'youtube': {'player_client': ['web_embedded']}}},
                 True),
                self._ANDROID_STRATEGY,
            ]
        else:
            strategies = [self._ANDROID_STRATEGY]
        last_exc: Optional[Exception] = None
        for i, (label, extra, use_cookies) in enumerate(strategies):
            if self._cancelled:
                raise _Cancelled()
            # Clear anything a previous failed attempt left in the temp dir.
            for p in Path(tmpdir).glob('*'):
                if p.is_file():
                    try:
                        p.unlink()
                    except OSError:
                        pass
            opts = dict(base_opts)
            opts.update({'quiet': True, 'no_warnings': True})
            if use_cookies and self._cookie_opts:
                opts.update(self._cookie_opts)
            opts.update(extra)
            if i > 0:
                self.progress.emit(0, 'Retrying'
                                   if i < len(strategies) - 1
                                   else 'Retrying at lower quality')
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([self._url])
            except _Cancelled:
                raise
            except Exception as exc:  # noqa: BLE001 — try the next strategy
                if self._cancelled:      # hook cancellation yt-dlp wrapped
                    raise _Cancelled()
                last_exc = exc
                continue
            if any(p.is_file() and not p.name.endswith('.part')
                   for p in Path(tmpdir).glob('*')):
                return
        if last_exc is not None:
            raise last_exc
        raise RuntimeError('yt-dlp produced no output file')

    def run(self) -> None:
        tmpdir = tempfile.mkdtemp(prefix='ytcv_')
        try:
            if self._fmt == 'mp4':
                self._run_mp4(tmpdir)
            else:
                self._run_mp3(tmpdir)
        except _Cancelled:
            pass
        except Exception as exc:
            if not self._cancelled:
                self.errored.emit(_humanize_yt_error(_strip_ansi(str(exc))))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _run_mp4(self, tmpdir: str) -> None:
        import yt_dlp

        def hook(d):
            if self._cancelled:
                raise _Cancelled()
            if d['status'] == 'downloading':
                try:
                    raw = d.get('_percent_str', '0%').strip().rstrip('%')
                    self.progress.emit(int(float(raw) * 0.70), 'Fetching')
                except (ValueError, TypeError):
                    pass

        base_opts = {
            'format': (
                'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]'
                '/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best'
            ),
            'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
            'progress_hooks': [hook],
        }
        self._download_with_fallback(yt_dlp, tmpdir, base_opts)

        if self._cancelled:
            raise _Cancelled()

        files = [p for p in Path(tmpdir).iterdir()
                 if p.is_file() and not p.name.endswith('.part')]
        if not files:
            raise RuntimeError('yt-dlp produced no output file')

        input_path = str(max(files, key=lambda p: p.stat().st_size))
        stem       = Path(input_path).stem
        output_path = os.path.join(tmpdir, f'{stem}_out.mp4')

        self.progress.emit(70, 'Converting')
        duration = self._get_duration(input_path)

        vf = (
            "scale=w='min(1920,iw)':h='min(1080,ih)'"
            ":force_original_aspect_ratio=decrease"
            ",scale=trunc(iw/2)*2:trunc(ih/2)*2"
        )
        proc = subprocess.Popen(
            [get_ffmpeg_path(), '-y', '-nostdin', '-i', input_path, '-vf', vf,
             '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
             '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart',
             '-progress', 'pipe:1', '-stats_period', '0.1', '-loglevel', 'quiet', output_path],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            if self._cancelled:
                proc.terminate()
                raise _Cancelled()
            line = raw_line.decode('utf-8', errors='replace').strip()
            if line.startswith('out_time_us='):
                try:
                    us = int(line.split('=')[1])
                except (ValueError, IndexError):
                    continue
                if duration > 0:
                    pct = int(70 + min(us / (duration * 1_000_000), 1.0) * 29)
                    self.progress.emit(pct, 'Converting')
                else:
                    # Duration couldn't be probed up front for this download
                    # (rare, but not impossible) — no % is calculable, so
                    # show real elapsed processing time instead of leaving
                    # the bar frozen at 70% with no visible movement.
                    self.progress.emit(70, f'Converting — {format_elapsed(us / 1_000_000)} processed')
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f'ffmpeg failed (exit {proc.returncode})')

        if os.path.exists(input_path) and input_path != output_path:
            os.unlink(input_path)

        final_path = self._dest / f'{stem}.mp4'
        shutil.move(output_path, str(final_path))
        self.progress.emit(100, 'Done')
        self.finished.emit(str(final_path))

    def _run_mp3(self, tmpdir: str) -> None:
        import yt_dlp

        def hook(d):
            if self._cancelled:
                raise _Cancelled()
            if d['status'] == 'downloading':
                try:
                    raw = d.get('_percent_str', '0%').strip().rstrip('%')
                    self.progress.emit(int(float(raw) * 0.85), 'Fetching')
                except (ValueError, TypeError):
                    pass
            elif d['status'] == 'finished':
                self.progress.emit(87, 'Converting')

        base_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
            'progress_hooks': [hook],
            'postprocessors': [{'key': 'FFmpegExtractAudio',
                                'preferredcodec': 'mp3', 'preferredquality': '0'}],
        }
        self._download_with_fallback(yt_dlp, tmpdir, base_opts)

        if self._cancelled:
            raise _Cancelled()

        mp3_files = list(Path(tmpdir).glob('*.mp3'))
        if not mp3_files:
            raise RuntimeError('No MP3 file was produced')

        src = mp3_files[0]
        final_path = self._dest / src.name
        shutil.move(str(src), str(final_path))
        self.progress.emit(100, 'Done')
        self.finished.emit(str(final_path))

    def _get_duration(self, path: str) -> float:
        return get_media_duration(path)


# ---------------------------------------------------------------------------
# Filename sanitizer
# ---------------------------------------------------------------------------

_UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|]')
_MULTI_SPACE   = re.compile(r'\s{2,}')

def _clean_filename(artist: str, title: str, ext: str) -> str:
    """Build a clean filename from metadata: 'Artist - Title.ext'.
    Falls back to just 'Title.ext' or leaves the caller's original name if both are empty."""
    def sanitize(s: str) -> str:
        s = _UNSAFE_CHARS.sub('', s)
        s = _MULTI_SPACE.sub(' ', s)
        return s.strip().strip('.')

    a = sanitize(artist)
    t = sanitize(title)

    if t:
        stem = t
    elif a:
        stem = a
    else:
        return ''

    suffix = ext if ext.startswith('.') else f'.{ext}'
    return stem + suffix


# ---------------------------------------------------------------------------
# Tag writer
# ---------------------------------------------------------------------------

def _write_tags(file_path: str, fmt: str, artist: str, title: str,
                album: str, year: str, genre: str) -> None:
    if fmt == 'mp3':
        from mutagen.id3 import ID3, ID3NoHeaderError, TALB, TDRC, TCON, TIT2, TPE1
        try:
            tags = ID3(file_path)
        except ID3NoHeaderError:
            tags = ID3()
        if title:  tags['TIT2'] = TIT2(encoding=3, text=title)
        if artist: tags['TPE1'] = TPE1(encoding=3, text=artist)
        if album:  tags['TALB'] = TALB(encoding=3, text=album)
        if year:   tags['TDRC'] = TDRC(encoding=3, text=year)
        if genre:  tags['TCON'] = TCON(encoding=3, text=genre)
        tags.save(file_path)
    elif fmt == 'mp4':
        from mutagen.mp4 import MP4
        tags = MP4(file_path)
        if title:  tags['\xa9nam'] = [title]
        if artist: tags['\xa9ART'] = [artist]
        if album:  tags['\xa9alb'] = [album]
        if year:   tags['\xa9day'] = [year]
        if genre:  tags['\xa9gen'] = [genre]
        tags.save()


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

_YT_RE = re.compile(
    r'(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/|live/)|youtu\.be/)\S+'
)

_FIELD_INPUT_STYLE = (
    'QLineEdit { background: #383838; border: 1px solid #444444; border-radius: 6px; '
    'color: #f1e3c8; font-size: 13px; padding: 8px 10px; }'
    'QLineEdit:focus { border-color: #428175; }'
    'QLineEdit:disabled { color: #5a5248; background: #2a2a2a; }'
)
_EYEBROW_STYLE = (
    'color: #5a5a5a; font-size: 10px; letter-spacing: 0.1em; '
    'background: transparent; border: none;'
)
_IMPORT_BTN_STYLE = (
    'QPushButton { background-color: #428175; color: #ffffff; border: none; '
    'border-radius: 6px; padding: 8px 24px; font-size: 13px; font-weight: 600; }'
    'QPushButton:hover { background-color: #38706a; }'
    'QPushButton:pressed { background-color: #2d6358; }'
    'QPushButton:disabled { background-color: #2a2a2a; color: #5a5248; }'
)
_PASSIVE_BTN_STYLE = (
    'QPushButton { background: transparent; color: #a89b85; border: 1px solid #444444; '
    'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 500; }'
    'QPushButton:hover { color: #f1e3c8; border-color: #f1e3c8; '
    'background: rgba(241, 227, 200, 0.05); }'
)


class _YTImportDialog(_CrateSortDialog):
    """
    Import a YouTube video as MP4 (H.264/AAC) or MP3.

    The QUALITY combo picks how hard the download tries: 'Fast' (default) goes
    straight to the `android` client for a ~360p copy in one request; 'Best
    available' runs the full client cascade first. See
    `_YTWorker._download_with_fallback`.

    Flow:
      1. Paste URL → auto-fetch YouTube metadata → pre-populate fields
      2. User reviews / edits Artist, Title, Album, Year, Genre; picks QUALITY
      3. Import → download + convert (real-time % progress)
      4. MusicBrainz lookup → show suggestion if confident match found
      5. User accepts / skips → tags written → file saved
      6. Nothing locks after a save — paste another URL to go again (keeps the
         destination + sign-in choice), or press Done / Escape to close
    """

    def __init__(self, fmt: str, library_path: Optional[Path],
                 genres: list[str] | None = None,
                 artists: list[str] | None = None, parent=None):
        super().__init__(parent)
        self._fmt         = fmt
        self._library_path = library_path
        self._output_path: Optional[str] = None
        self._save_complete = False
        self._meta_worker:  Optional[_MetadataFetchWorker] = None
        self._dl_worker:    Optional[_YTWorker]            = None
        self._mb_worker:    Optional[_MusicBrainzWorker]   = None
        self._artwork_path: Optional[Path] = None

        # YOUTUBE LOGIN — always starts at "Don't use a login". It is NOT
        # persisted: a remembered browser choice quietly re-triggers a macOS
        # keychain / "access data from other apps" prompt (and a cookie read)
        # on every metadata fetch, for a control that rarely helps anyway.
        self._settings = QSettings('JWBC', 'CrateSort')
        self._settings.remove('yt_cookies_browser')   # purge value from older builds
        self._cookie_browser: str = ''
        self._cookie_file: Optional[str] = None

        is_mp4 = fmt == 'mp4'
        self.setMinimumWidth(520)

        layout = _create_dialog_layout(self)

        # ── Header ──────────────────────────────────────────────────────────
        title_lbl = QLabel('Import from YouTube')
        title_lbl.setStyleSheet(
            'color: #f1e3c8; font-size: 22px; font-weight: 600; '
            'font-family: "Helvetica Neue", Arial, Helvetica; background: transparent; border: none;'
        )
        layout.addWidget(title_lbl)

        mode_lbl = QLabel(
            'Video · MP4  ·  H.264 / AAC'
            if is_mp4 else
            'Audio · MP3'
        )
        mode_lbl.setStyleSheet(
            'color: #a89b85; font-size: 12px; background: transparent; border: none;'
        )
        layout.addWidget(mode_lbl)
        layout.addSpacing(10)

        # ── URL input ────────────────────────────────────────────────────────
        layout.addWidget(self._eyebrow('YOUTUBE URL'))

        url_row = QHBoxLayout()
        url_row.setSpacing(8)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText('Paste a YouTube URL…')
        self._url_input.setStyleSheet(_FIELD_INPUT_STYLE)
        self._url_input.returnPressed.connect(self._on_import)
        url_row.addWidget(self._url_input, stretch=1)

        self._meta_status = QLabel()
        self._meta_status.setStyleSheet(
            'color: #428175; font-size: 11px; background: transparent; border: none;'
        )
        self._meta_status.hide()
        url_row.addWidget(self._meta_status)
        layout.addLayout(url_row)
        layout.addSpacing(12)

        # ── Metadata form ────────────────────────────────────────────────────
        meta_frame = QFrame()
        meta_frame.setStyleSheet('QFrame { background: transparent; border: none; }')
        meta_grid = QGridLayout(meta_frame)
        meta_grid.setContentsMargins(0, 0, 0, 0)
        meta_grid.setHorizontalSpacing(10)
        meta_grid.setVerticalSpacing(8)

        # Row 0: Artist
        meta_grid.addWidget(self._eyebrow('ARTIST'), 0, 0, 1, 2)
        self._f_artist = self._field()
        if artists:
            _a_model = QStringListModel(artists, self._f_artist)
            _a_comp = QCompleter(_a_model, self._f_artist)
            _a_comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            _a_comp.setFilterMode(Qt.MatchFlag.MatchContains)
            _a_comp.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            self._f_artist.setCompleter(_a_comp)
        meta_grid.addWidget(self._f_artist, 1, 0, 1, 2)

        # Row 1: Title
        meta_grid.addWidget(self._eyebrow('TITLE'), 2, 0, 1, 2)
        self._f_title = self._field()
        meta_grid.addWidget(self._f_title, 3, 0, 1, 2)

        # Row 2: Album (wide) + Year (narrow)
        meta_grid.addWidget(self._eyebrow('ALBUM'), 4, 0)
        meta_grid.addWidget(self._eyebrow('YEAR'),  4, 1)
        self._f_album = self._field()
        self._f_year  = self._field(width=80)
        meta_grid.addWidget(self._f_album, 5, 0)
        meta_grid.addWidget(self._f_year,  5, 1)

        # Row 3: Genre (searchable autocomplete from library + canonical genres)
        meta_grid.addWidget(self._eyebrow('GENRE'), 6, 0, 1, 2)
        self._f_genre = self._field()
        if genres:
            _model = QStringListModel(genres, self._f_genre)
            _completer = QCompleter(_model, self._f_genre)
            _completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            _completer.setFilterMode(Qt.MatchFlag.MatchContains)
            _completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            self._f_genre.setCompleter(_completer)
        meta_grid.addWidget(self._f_genre, 7, 0, 1, 2)

        meta_grid.setColumnStretch(0, 1)

        layout.addWidget(meta_frame)
        layout.addSpacing(12)

        # ── Artwork ──────────────────────────────────────────────────────────
        # YouTube downloads never carry embedded art — unlike local WAV/MOV
        # conversions, which inherit it from the source file — so this is the
        # only converter that needs a manual attach-artwork option.
        layout.addWidget(self._eyebrow('ARTWORK (OPTIONAL)'))

        artwork_row = QHBoxLayout()
        artwork_row.setSpacing(10)

        self._artwork_thumb = QLabel('—')
        self._artwork_thumb.setFixedSize(48, 48)
        self._artwork_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._artwork_thumb.setStyleSheet(
            'background: #383838; border: 1px solid #444444; border-radius: 6px; '
            'color: #5a5248; font-size: 18px;'
        )
        artwork_row.addWidget(self._artwork_thumb)

        artwork_btn_col = QVBoxLayout()
        artwork_btn_col.setSpacing(6)
        choose_art_btn = QPushButton('Choose Image…')
        choose_art_btn.setFixedHeight(30)
        choose_art_btn.setStyleSheet(
            'QPushButton { background: transparent; color: #a89b85; border: 1px solid #444444; '
            'border-radius: 6px; padding: 0 14px; font-size: 13px; font-weight: 500; }'
            'QPushButton:hover { color: #f1e3c8; border-color: #a89b85; }'
        )
        choose_art_btn.clicked.connect(self._on_choose_artwork)
        artwork_btn_col.addWidget(choose_art_btn)

        self._clear_art_btn = QPushButton('Clear')
        self._clear_art_btn.setFixedHeight(26)
        self._clear_art_btn.setStyleSheet(
            'QPushButton { background: transparent; color: #a89b85; border: 1px solid #444444; '
            'border-radius: 6px; padding: 0 14px; font-size: 12px; font-weight: 500; }'
            'QPushButton:hover { color: #f1e3c8; border-color: #a89b85; }'
        )
        self._clear_art_btn.clicked.connect(self._on_clear_artwork)
        self._clear_art_btn.hide()
        artwork_btn_col.addWidget(self._clear_art_btn)

        artwork_row.addLayout(artwork_btn_col)
        artwork_row.addStretch()
        layout.addLayout(artwork_row)
        layout.addSpacing(12)

        # ── Destination ──────────────────────────────────────────────────────
        layout.addWidget(self._eyebrow('SAVE TO'))
        dest_row = QHBoxLayout()
        dest_row.setSpacing(8)

        # Last folder the user browsed to persists across dialog opens, so a
        # second import doesn't start by re-picking the destination.
        _saved_dest = self._settings.value('yt_dest_dir', '', type=str)
        if _saved_dest and Path(_saved_dest).is_dir():
            self._dest_path = Path(_saved_dest)
        else:
            self._dest_path = library_path or Path.home() / 'Downloads'
        self._dest_lbl  = QLabel(str(self._dest_path))
        self._dest_lbl.setStyleSheet(
            'color: #c9b89a; font-size: 12px; background: #222222; '
            'border: 1px solid #383838; border-radius: 6px; padding: 8px 10px;'
        )
        dest_row.addWidget(self._dest_lbl, stretch=1)

        browse_btn = QPushButton('Browse…')
        browse_btn.setFixedHeight(36)
        browse_btn.setStyleSheet(
            'QPushButton { background: transparent; color: #a89b85; border: 1px solid #444444; '
            'border-radius: 6px; padding: 0 14px; font-size: 13px; font-weight: 500; }'
            'QPushButton:hover { color: #f1e3c8; border-color: #a89b85; }'
        )
        browse_btn.clicked.connect(self._on_browse)
        dest_row.addWidget(browse_btn)
        layout.addLayout(dest_row)

        media_hint = QLabel(
            'Save to your media folder so CrateSort can find this file on the next scan.'
        )
        media_hint.setStyleSheet(
            'color: #5a5248; font-size: 11px; background: transparent; border: none;'
        )
        media_hint.setWordWrap(True)
        layout.addWidget(media_hint)
        layout.addSpacing(14)

        # ── Quality ──────────────────────────────────────────────────────────
        layout.addWidget(self._eyebrow('QUALITY'))

        self._quality_combo = _ArrowComboBox(bg='#383838')
        for _q in _QUALITY_LABELS:
            self._quality_combo.addItem(_q)
        self._quality_combo.setCurrentIndex(0)   # default: fastest, no HD wait
        layout.addWidget(self._quality_combo)

        quality_hint = QLabel(
            'Fast grabs a ~360p copy in one request. Best tries for higher '
            'quality first — slower, and often still lands at ~360p.'
        )
        quality_hint.setStyleSheet(
            'color: #5a5248; font-size: 11px; background: transparent; border: none;'
        )
        quality_hint.setWordWrap(True)
        layout.addWidget(quality_hint)
        layout.addSpacing(14)

        # ── YouTube login (reuses a browser's existing session) ──────────────
        layout.addWidget(self._eyebrow('YOUTUBE LOGIN'))

        self._cookie_combo = _ArrowComboBox(bg='#383838')
        for label, _key in _COOKIE_BROWSERS:
            self._cookie_combo.addItem(label)
        self._cookie_combo.addItem(_COOKIE_FILE_LABEL)
        self._restore_cookie_combo_selection()
        self._cookie_combo.currentIndexChanged.connect(self._on_cookie_source_changed)
        layout.addWidget(self._cookie_combo)

        cookie_hint = QLabel(
            "This doesn't sign you in — it reuses the YouTube login from a "
            "browser you're already signed into. Can help with blocked or "
            "age-restricted videos; leave it off otherwise."
        )
        cookie_hint.setStyleSheet(
            'color: #5a5248; font-size: 11px; background: transparent; border: none;'
        )
        cookie_hint.setWordWrap(True)
        layout.addWidget(cookie_hint)
        layout.addSpacing(14)

        # ── Progress ─────────────────────────────────────────────────────────
        self._stage_lbl = QLabel('FETCHING')
        self._stage_lbl.setStyleSheet(_EYEBROW_STYLE)
        self._stage_lbl.hide()
        layout.addWidget(self._stage_lbl)

        prog_row = QHBoxLayout()
        prog_row.setSpacing(10)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            'QProgressBar { background: #2a2a2a; border: none; border-radius: 3px; }'
            'QProgressBar::chunk { background: #428175; border-radius: 3px; }'
        )
        self._progress_bar.hide()
        self._pct_lbl = QLabel('0%')
        self._pct_lbl.setFixedWidth(36)
        self._pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._pct_lbl.setStyleSheet(
            'color: #a89b85; font-size: 12px; '
            'background: transparent; border: none;'
        )
        self._pct_lbl.hide()
        prog_row.addWidget(self._progress_bar, stretch=1)
        prog_row.addWidget(self._pct_lbl)
        layout.addLayout(prog_row)

        # ── MusicBrainz suggestion strip ─────────────────────────────────────
        self._mb_strip = QFrame()
        self._mb_strip.setStyleSheet(
            'QFrame { background: #1a2825; border: 1px solid #2d4a42; border-radius: 6px; }'
        )
        mb_layout = QVBoxLayout(self._mb_strip)
        mb_layout.setContentsMargins(14, 12, 14, 12)
        mb_layout.setSpacing(6)

        mb_header = QHBoxLayout()
        mb_dot = QLabel('●')
        mb_dot.setStyleSheet('color: #428175; font-size: 8px; background: transparent; border: none;')
        mb_dot.setFixedWidth(14)
        self._mb_score_lbl = QLabel('MusicBrainz match')
        self._mb_score_lbl.setStyleSheet(
            'color: #428175; font-size: 11px; font-weight: 600; '
            'letter-spacing: 0.05em; background: transparent; border: none;'
        )
        mb_header.addWidget(mb_dot)
        mb_header.addWidget(self._mb_score_lbl)
        mb_header.addStretch()
        mb_layout.addLayout(mb_header)

        self._mb_detail_lbl = QLabel()
        self._mb_detail_lbl.setStyleSheet(
            'color: #c9b89a; font-size: 12px; background: transparent; border: none;'
        )
        self._mb_detail_lbl.setWordWrap(True)
        mb_layout.addWidget(self._mb_detail_lbl)

        mb_btn_row = QHBoxLayout()
        mb_btn_row.setSpacing(8)
        self._mb_apply_btn = QPushButton('Apply Suggestion')
        self._mb_apply_btn.setFixedHeight(30)
        self._mb_apply_btn.setStyleSheet(
            'QPushButton { background: #428175; color: #ffffff; border: none; '
            'border-radius: 5px; padding: 0 14px; font-size: 12px; font-weight: 600; }'
            'QPushButton:hover { background: #38706a; }'
        )
        self._mb_skip_btn = QPushButton('Keep My Tags')
        self._mb_skip_btn.setFixedHeight(30)
        self._mb_skip_btn.setStyleSheet(
            'QPushButton { background: transparent; color: #a89b85; border: 1px solid #3a3a3a; '
            'border-radius: 5px; padding: 0 14px; font-size: 12px; }'
            'QPushButton:hover { color: #f1e3c8; border-color: #555; }'
        )
        self._mb_apply_btn.clicked.connect(self._on_mb_apply)
        self._mb_skip_btn.clicked.connect(self._on_mb_skip)
        mb_btn_row.addWidget(self._mb_apply_btn)
        mb_btn_row.addWidget(self._mb_skip_btn)
        mb_btn_row.addStretch()
        mb_layout.addLayout(mb_btn_row)

        self._mb_strip.hide()
        layout.addWidget(self._mb_strip)

        # ── Result label ──────────────────────────────────────────────────────
        self._result_lbl = QLabel()
        self._result_lbl.setWordWrap(True)
        self._result_lbl.setStyleSheet('background: transparent; border: none;')
        self._result_lbl.hide()
        layout.addWidget(self._result_lbl)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._cancel_btn = QPushButton('Cancel')
        self._cancel_btn.setFixedHeight(36)
        self._cancel_btn.setStyleSheet(_PASSIVE_BTN_STYLE)
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._cancel_btn.setAutoDefault(False)

        self._import_btn = QPushButton('Import')
        self._import_btn.setFixedHeight(36)
        self._import_btn.setStyleSheet(_IMPORT_BTN_STYLE)
        self._import_btn.clicked.connect(self._on_import)
        self._import_btn.setDefault(True)   # Return anywhere in the form starts the import
        for _f in (self._f_artist, self._f_title, self._f_album, self._f_year, self._f_genre):
            _f.returnPressed.connect(self._on_import)

        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._import_btn)
        layout.addLayout(btn_row)

        # ── Debounce timer for URL auto-fetch ─────────────────────────────────
        self._meta_timer = QTimer(self)
        self._meta_timer.setSingleShot(True)
        self._meta_timer.setInterval(800)
        self._meta_timer.timeout.connect(self._fetch_metadata)
        self._url_input.textChanged.connect(self._on_url_changed)

        # Stored MusicBrainz suggestion for deferred apply
        self._mb_suggestion: Optional[dict] = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _eyebrow(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(_EYEBROW_STYLE)
        return lbl

    @staticmethod
    def _field(width: Optional[int] = None) -> QLineEdit:
        f = QLineEdit()
        f.setStyleSheet(_FIELD_INPUT_STYLE)
        f.setEnabled(False)
        if width:
            f.setFixedWidth(width)
        return f

    def _fields_enabled(self, enabled: bool) -> None:
        for f in (self._f_artist, self._f_title, self._f_album,
                  self._f_year, self._f_genre):
            f.setEnabled(enabled)

    def _current_tags(self) -> dict:
        return {
            'artist': self._f_artist.text().strip(),
            'title':  self._f_title.text().strip(),
            'album':  self._f_album.text().strip(),
            'year':   self._f_year.text().strip(),
            'genre':  self._f_genre.text().strip(),
        }

    # ── YouTube sign-in (cookies) ────────────────────────────────────────────

    def _cookie_opts(self) -> dict:
        """yt-dlp option fragment for the chosen YouTube sign-in source."""
        if self._cookie_file:
            return {'cookiefile': self._cookie_file}
        if self._cookie_browser:
            return {'cookiesfrombrowser': (self._cookie_browser,)}
        return {}

    def _restore_cookie_combo_selection(self) -> None:
        """Point the combo at whatever source is currently active, without
        firing currentIndexChanged."""
        target = 0
        if self._cookie_file:
            target = self._cookie_combo.count() - 1          # the "Cookie file…" row
        elif self._cookie_browser:
            for i, (_label, key) in enumerate(_COOKIE_BROWSERS):
                if key == self._cookie_browser:
                    target = i
                    break
        self._cookie_combo.blockSignals(True)
        self._cookie_combo.setCurrentIndex(target)
        self._cookie_combo.blockSignals(False)

    def _on_cookie_source_changed(self, index: int) -> None:
        file_row = self._cookie_combo.count() - 1
        if index == file_row:
            path, _ = QFileDialog.getOpenFileName(
                self, 'Choose a cookies.txt file', str(Path.home()),
                'Cookie files (*.txt);;All files (*)',
            )
            if not path:
                self._restore_cookie_combo_selection()      # cancelled — revert
                return
            self._cookie_file = path
            self._cookie_browser = ''
            self._cookie_combo.setItemText(file_row, f'Cookie file: {Path(path).name}')
        else:
            self._cookie_file = None
            self._cookie_browser = _COOKIE_BROWSERS[index][1]
            self._cookie_combo.setItemText(file_row, _COOKIE_FILE_LABEL)

        # Now that we can authenticate, retry the metadata auto-fill if a
        # valid URL is already entered.
        if _YT_RE.match(self._url_input.text().strip()):
            self._fetch_metadata()

    # ── URL auto-fetch ────────────────────────────────────────────────────────

    def _on_url_changed(self, text: str) -> None:
        if self._save_complete:
            self._clear_after_save()
        self._meta_timer.stop()
        self._meta_status.hide()
        if _YT_RE.match(text.strip()):
            self._meta_timer.start()

    def _fetch_metadata(self) -> None:
        url = self._url_input.text().strip()
        if not _YT_RE.match(url):
            return
        if self._meta_worker and self._meta_worker.isRunning():
            return

        self._meta_status.setText('Identifying…')
        self._meta_status.show()
        self._fields_enabled(False)

        self._meta_worker = _MetadataFetchWorker(url, self._cookie_opts(), self)
        self._meta_worker.fetched.connect(self._on_metadata_fetched)
        self._meta_worker.failed.connect(self._on_metadata_failed)
        self._meta_worker.start()

    def _on_metadata_fetched(self, info: dict) -> None:
        self._meta_status.hide()
        artist, title = _parse_yt_title(info.get('title', ''), info.get('uploader', ''))
        self._f_artist.setText(artist)
        self._f_title.setText(title)
        self._f_year.setText(info.get('year', ''))
        self._fields_enabled(True)

    def _on_metadata_failed(self, msg: str) -> None:
        self._fields_enabled(True)
        low = msg.lower()
        if 'not a bot' in low or 'sign in to confirm' in low:
            # Non-fatal here (fields can be typed by hand) but tell the user
            # why nothing auto-filled and where the fix is.
            self._meta_status.setText('Needs a YouTube login to auto-fill')
            self._meta_status.show()
        else:
            self._meta_status.hide()

    # ── Artwork ───────────────────────────────────────────────────────────────

    def _on_choose_artwork(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, 'Choose Artwork', str(Path.home()), 'Images (*.jpg *.jpeg *.png)',
        )
        if not path:
            return
        self._artwork_path = Path(path)
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(
                48, 48, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._artwork_thumb.setPixmap(pixmap)
        self._clear_art_btn.show()

    def _on_clear_artwork(self) -> None:
        self._artwork_path = None
        self._artwork_thumb.setPixmap(QPixmap())
        self._artwork_thumb.setText('—')
        self._clear_art_btn.hide()

    # ── Browse ────────────────────────────────────────────────────────────────

    def _on_browse(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, 'Select Destination Folder', str(self._dest_path)
        )
        if path:
            self._dest_path = Path(path)
            self._dest_lbl.setText(str(self._dest_path))
            self._settings.setValue('yt_dest_dir', str(self._dest_path))

    # ── Import ────────────────────────────────────────────────────────────────

    def _on_import(self) -> None:
        url = self._url_input.text().strip()
        if not url:
            self._url_input.setFocus()
            return
        if not _YT_RE.match(url):
            self._set_result('That doesn\'t look like a YouTube URL.', error=True)
            return

        self._save_complete = False
        self._cancel_btn.setText('Cancel')
        self._import_btn.setEnabled(False)
        self._url_input.setEnabled(False)
        self._fields_enabled(False)
        self._result_lbl.hide()
        self._mb_strip.hide()

        self._stage_lbl.show()
        self._progress_bar.show()
        self._pct_lbl.show()

        quality = _QUALITY_VALUES[self._quality_combo.currentIndex()]
        self._dl_worker = _YTWorker(
            url, self._fmt, self._dest_path, self._cookie_opts(), quality, self,
        )
        self._dl_worker.progress.connect(self._on_progress)
        self._dl_worker.finished.connect(self._on_download_finished)
        self._dl_worker.errored.connect(self._on_error)
        self._dl_worker.start()

    def _on_progress(self, pct: int, stage: str) -> None:
        self._stage_lbl.setText(stage.upper())
        self._progress_bar.setValue(pct)
        self._pct_lbl.setText(f'{pct}%')

    def _on_download_finished(self, path: str) -> None:
        self._output_path = path
        self._progress_bar.setValue(100)
        self._pct_lbl.setText('100%')
        self._stage_lbl.setText('IDENTIFYING')

        # Launch MusicBrainz lookup in background
        tags = self._current_tags()
        artist, title = tags['artist'], tags['title']
        if artist or title:
            self._mb_worker = _MusicBrainzWorker(artist, title, self)
            self._mb_worker.found.connect(self._on_mb_found)
            self._mb_worker.not_found.connect(self._on_mb_not_found)
            self._mb_worker.start()
        else:
            self._finish()

    # ── MusicBrainz ───────────────────────────────────────────────────────────

    def _on_mb_found(self, suggestion: dict) -> None:
        self._mb_suggestion = suggestion
        self._stage_lbl.hide()

        score = suggestion['score']
        self._mb_score_lbl.setText(f'MusicBrainz match  {score}%')

        parts = []
        if suggestion.get('artist'): parts.append(suggestion['artist'])
        if suggestion.get('title'):  parts.append(suggestion['title'])
        if suggestion.get('album'):  parts.append(suggestion['album'])
        if suggestion.get('year'):   parts.append(suggestion['year'])
        self._mb_detail_lbl.setText('  ·  '.join(parts))

        self._mb_strip.show()

    def _on_mb_not_found(self) -> None:
        self._stage_lbl.hide()
        self._finish()

    def _on_mb_apply(self) -> None:
        if self._mb_suggestion:
            s = self._mb_suggestion
            if s.get('artist'): self._f_artist.setText(s['artist'])
            if s.get('title'):  self._f_title.setText(s['title'])
            if s.get('album'):  self._f_album.setText(s['album'])
            if s.get('year'):   self._f_year.setText(s['year'])
            if s.get('genre'):  self._f_genre.setText(s['genre'])
        self._mb_strip.hide()
        self._finish()

    def _on_mb_skip(self) -> None:
        self._mb_strip.hide()
        self._finish()

    # ── Finish ────────────────────────────────────────────────────────────────

    def _finish(self) -> None:
        if not self._output_path:
            return
        tags = self._current_tags()

        # Rename the file to match the clean metadata fields
        current = Path(self._output_path)
        clean_name = _clean_filename(tags['artist'], tags['title'], current.suffix)
        if clean_name and clean_name != current.name:
            candidate = current.parent / clean_name
            # Avoid clobbering an existing file — append a counter if needed
            if candidate.exists() and candidate != current:
                stem, ext = os.path.splitext(clean_name)
                n = 1
                while candidate.exists():
                    candidate = current.parent / f'{stem} ({n}){ext}'
                    n += 1
            try:
                current.rename(candidate)
                self._output_path = str(candidate)
            except OSError:
                pass  # rename failed — leave original name, tags still write fine

        try:
            _write_tags(
                self._output_path, self._fmt,
                tags['artist'], tags['title'],
                tags['album'],  tags['year'], tags['genre'],
            )
        except Exception as exc:
            self._set_result(f'Tags could not be written: {exc}', error=True)

        if self._artwork_path is not None:
            try:
                embed_artwork(Path(self._output_path), self._fmt, self._artwork_path)
            except Exception as exc:
                self._set_result(f'Artwork could not be embedded: {exc}', error=True)

        self._set_result(f'Saved: {self._output_path}', error=False)

        # Nothing is locked after a save. The user can paste another URL and
        # go (typing a new URL clears this result + the old metadata — see
        # `_clear_after_save`), or press Done / Escape to leave.
        self._save_complete = True
        self._url_input.setEnabled(True)
        self._fields_enabled(True)
        self._import_btn.setEnabled(True)
        self._stage_lbl.hide()
        self._progress_bar.hide()
        self._pct_lbl.hide()
        self._cancel_btn.setText('Done')

    def _clear_after_save(self) -> None:
        """Called when the user starts a new URL after a completed import —
        wipes the previous result and its now-stale metadata / artwork so the
        next auto-fetch fills in cleanly. Destination folder and the sign-in
        selection are deliberately left as-is."""
        self._save_complete = False
        self._output_path    = None
        self._mb_suggestion  = None
        for f in (self._f_artist, self._f_title, self._f_album,
                  self._f_year, self._f_genre):
            f.clear()
        self._on_clear_artwork()
        self._result_lbl.hide()
        self._mb_strip.hide()
        self._progress_bar.setValue(0)
        self._pct_lbl.setText('0%')
        self._cancel_btn.setText('Cancel')

    # ── Error / cancel ────────────────────────────────────────────────────────

    def _on_error(self, message: str) -> None:
        self._set_result(message, error=True)
        self._import_btn.setEnabled(True)
        self._url_input.setEnabled(True)
        self._fields_enabled(True)

    def keyPressEvent(self, event) -> None:
        # Route Escape through _on_cancel so an in-flight download/lookup is
        # stopped cleanly (and confirmed) instead of the dialog just closing.
        if event.key() == Qt.Key.Key_Escape:
            self._on_cancel()
            return
        super().keyPressEvent(event)

    def _on_cancel(self) -> None:
        running = [w for w in (self._meta_worker, self._dl_worker, self._mb_worker)
                   if w and w.isRunning()]
        if self._dl_worker and self._dl_worker.isRunning():
            if not _ov_confirm(
                self, 'Stop the import?',
                'The download is still running. Nothing will be added to your library '
                'if you stop now.',
                confirm_text='Stop', cancel_text='Keep Going', confirm_danger=True,
            ):
                return
        for w in running:
            if hasattr(w, 'cancel'):
                w.cancel()
            w.wait(2000)
        self.reject()

    def _set_result(self, text: str, *, error: bool) -> None:
        color = '#C75B5B' if error else '#6B9E78'
        self._result_lbl.setStyleSheet(
            f'color: {color}; font-size: 12px; background: transparent; border: none;'
        )
        self._result_lbl.setText(text)
        self._result_lbl.show()
