from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QMimeData, QSettings, QSize, QTimer
from PyQt6.QtGui import QAction, QColor, QDragEnterEvent, QDropEvent, QPalette, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup,
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QMessageBox,
    QPushButton, QSizePolicy, QStackedWidget, QStatusBar,
    QVBoxLayout, QWidget,
)

try:
    from PyQt6.QtSvgWidgets import QSvgWidget
    _SVG_AVAILABLE = True
except ImportError:
    _SVG_AVAILABLE = False

from cratesort.src.gui.theme import apply_theme, C
from cratesort.src.gui.dashboard import DashboardWidget
from cratesort.src.gui.classifier_view import ClassifierView
from cratesort.src.gui.library_browser import LibraryBrowserView
from cratesort.src.gui.crate_manager import CrateManagerView
from cratesort.src.gui.organize_view import OrganizeView
from cratesort.src.gui.settings_view import SettingsView
from cratesort.src.utils.undo_manager import UndoManager

_ASSETS = Path(__file__).parent.parent.parent / 'assets'
_LOGO_WORDMARK = _ASSETS / 'logo' / 'cs-logo-lockup-horiz.svg'

VERSION = '0.1.0'
ORG = 'JWBC'
APP = 'CrateSort'

# Sidebar width
_SIDEBAR_W = 196

# Nav items: (id, label, emoji_icon)
_NAV_ITEMS = [
    ('dashboard', 'Dashboard',      '⌂'),
    ('classification',  'Classification', '🔍'),
    ('library',   'Library',        '📚'),
    ('crates',    'Crates',         '📦'),
    ('organize',  'Organize',       '📁'),
    ('settings',  'Settings',       '⚙'),
]


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self._settings = QSettings(ORG, APP)

        # Before building the UI, remove any stale 'library_path' whose directory
        # no longer exists on disk.  DashboardWidget.__init__() reads this key
        # during _build_ui(); if it sees a valid-looking path, it passes it to
        # _build_welcome() *and* the always_load_last block later calls start_scan()
        # on the deleted directory — resulting in a blank dashboard with no welcome
        # screen.  Clearing here means the widget sees None and shows the clean
        # first-launch UI.  QSettings key: 'library_path'.
        _stored_lib = self._settings.value('library_path', None)
        if _stored_lib and not Path(_stored_lib).exists():
            self._settings.remove('library_path')
            self._settings.setValue('always_load_last', False)

        self.setWindowTitle(f'CrateSort  {VERSION}')
        self.setMinimumSize(900, 600)

        self._undo_manager = UndoManager(on_change=self._update_undo_buttons)
        self._build_ui()
        self._update_undo_buttons()  # apply initial inactive style
        self._build_menu()
        self._build_status_bar()
        self._restore_geometry()

        from PyQt6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence('Ctrl+Z'),       self).activated.connect(self._do_undo)
        QShortcut(QKeySequence('Ctrl+Shift+Z'), self).activated.connect(self._do_redo)

        # One-time reset of any stale always_load_last=True from dev sessions.
        # Runs only once; afterward the user's checkbox choice is preserved.
        if not self._settings.value('_launch_dialog_reset_v1', False, type=bool):
            self._settings.setValue('always_load_last', False)
            self._settings.setValue('_launch_dialog_reset_v1', True)

        # Restore library path — auto-load if always_load_last, else welcome screen handles it
        saved_path = self._settings.value('library_path', None)
        always_load = self._settings.value('always_load_last', False, type=bool)
        if saved_path and always_load:
            self._dashboard.set_library_path(Path(saved_path))
        else:
            self._update_status('', '')

        # Apply initial nav state (must come after sidebar is built)
        self._app_state = self._get_app_state()
        self._apply_nav_state(self._app_state)

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        sidebar = self._build_sidebar()
        root.addWidget(sidebar)

        # Content stack
        self._content = QStackedWidget()
        self._content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Dashboard (real) — index 0
        self._dashboard = DashboardWidget()
        self._dashboard.library_path_changed.connect(self._on_library_changed)
        self._dashboard.status_message.connect(self._update_status)
        self._dashboard.classify_requested.connect(self._on_classify_requested)
        self._dashboard.crates_requested.connect(self._on_crates_requested)
        self._dashboard.organize_requested.connect(self._on_organize_requested)
        self._dashboard.new_crate_requested.connect(self._on_new_crate_requested)
        self._dashboard.new_smart_crate_requested.connect(self._on_new_smart_crate_requested)
        self._dashboard.scan_finished.connect(lambda: self._apply_nav_state(self._get_app_state()))
        self._content.addWidget(self._dashboard)

        # Classifier view — index 1
        self._classifier_view = ClassifierView()
        self._classifier_view.done.connect(self._on_classifier_done)
        self._classifier_view.back.connect(self._on_classifier_back)
        self._classifier_view.track_selected.connect(self._update_album_art)
        self._content.addWidget(self._classifier_view)

        # Library Browser — index 2
        self._library_browser = LibraryBrowserView()
        self._library_browser.album_art_requested.connect(self._update_album_art)
        self._content.addWidget(self._library_browser)

        # Crate Manager — index 3
        self._crate_manager = CrateManagerView(undo_manager=self._undo_manager)
        self._crate_manager.track_selected.connect(self._update_album_art)
        self._crate_manager.album_art_requested.connect(self._update_album_art)
        self._crate_manager.navigate_to_settings.connect(lambda: self._on_nav_by_id('settings'))
        self._content.addWidget(self._crate_manager)

        # Organize view — index 4
        self._organize_view = OrganizeView()
        self._organize_view.navigate_to_classifier.connect(self._on_classify_requested)
        self._organize_view.navigate_to_dashboard.connect(lambda: self._on_nav_by_id('dashboard'))
        self._organize_view.reorg_completed.connect(self._on_reorg_completed)
        self._organize_view.status_message.connect(self._update_status)
        self._content.addWidget(self._organize_view)

        # Settings — index 5
        self._settings_view = SettingsView(self._settings)
        self._settings_view.library_changed.connect(self._on_library_changed_from_settings)
        self._settings_view.repair_requested.connect(self._on_repair_crate_paths)
        self._content.addWidget(self._settings_view)

        root.addWidget(self._content)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setProperty('role', 'sidebar')
        sidebar.setFixedWidth(_SIDEBAR_W)
        sidebar.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo strip
        logo_strip = QWidget()
        logo_strip.setFixedHeight(88)   # 40px logo + 24px top + 24px bottom
        logo_strip.setStyleSheet(f'background-color: {C["bg_panel"]};')
        logo_layout = QHBoxLayout(logo_strip)
        logo_layout.setContentsMargins(24, 24, 24, 24)   # equal on all four sides
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if _SVG_AVAILABLE and _LOGO_WORDMARK.exists():
            logo = QSvgWidget(str(_LOGO_WORDMARK))
            logo.setFixedSize(148, 42)
            logo_layout.addWidget(logo)
        else:
            logo_text = QLabel('CrateSort')
            logo_text.setStyleSheet(
                f'color: {C["text"]}; font-size: 16px; font-weight: 700;'
                f'font-family: "Charter", "Georgia", serif;'
            )
            logo_layout.addWidget(logo_text)
        layout.addWidget(logo_strip)

        # Divider
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f'background: {C["border"]}; max-height: 1px;')
        layout.addWidget(sep)

        layout.addSpacing(8)

        # Nav buttons (exclusive, checkable)
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_btns: dict[str, QPushButton] = {}

        for i, (nav_id, label, _icon) in enumerate(_NAV_ITEMS):
            btn = QPushButton(f'   {label}')
            btn.setObjectName('nav_btn')
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

            icon_path = _ASSETS / 'icons' / f'icon-{nav_id}.svg'
            if _SVG_AVAILABLE and icon_path.exists():
                from PyQt6.QtGui import QIcon
                from PyQt6.QtCore import QSize
                btn.setIcon(QIcon(str(icon_path)))
                btn.setIconSize(QSize(16, 16))

            btn.clicked.connect(lambda checked, idx=i: self._on_nav(idx))
            self._nav_group.addButton(btn, i)
            self._nav_btns[nav_id] = btn
            layout.addWidget(btn)

        # Album art panel — ~50px space below nav buttons, no divider line (Fix 3)
        layout.addSpacing(50)

        self._art_panel = _ArtPanel()
        art_wrapper = QWidget()
        art_wrapper.setStyleSheet(f'background: {C["bg_panel"]};')
        aw_layout = QVBoxLayout(art_wrapper)
        aw_layout.setContentsMargins(13, 0, 13, 13)  # equal L/R, bottom padding
        aw_layout.addWidget(self._art_panel, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(art_wrapper)

        layout.addSpacing(16)

        undo_redo_wrapper = QWidget()
        undo_redo_wrapper.setStyleSheet(f'background: {C["bg_panel"]};')
        ur_layout = QHBoxLayout(undo_redo_wrapper)
        ur_layout.setContentsMargins(13, 0, 13, 8)
        ur_layout.setSpacing(6)

        self._undo_btn = QPushButton('← Undo')
        self._undo_btn.setEnabled(False)
        self._undo_btn.setStyleSheet(
            f'QPushButton {{ background: transparent; color: {C["text_muted"]}; '
            f'border: 1px solid {C["border"]}; border-radius: 4px; '
            f'font-size: 11px; padding: 4px 6px; }}'
            f'QPushButton:enabled {{ color: {C["teal"]}; border-color: {C["teal"]}; }}'
            f'QPushButton:enabled:hover {{ background: rgba(66,129,117,0.15); }}'
        )
        self._undo_btn.clicked.connect(self._do_undo)

        self._redo_btn = QPushButton('Redo →')
        self._redo_btn.setEnabled(False)
        self._redo_btn.setStyleSheet(self._undo_btn.styleSheet())
        self._redo_btn.clicked.connect(self._do_redo)

        ur_layout.addWidget(self._undo_btn)
        ur_layout.addWidget(self._redo_btn)
        layout.addWidget(undo_redo_wrapper)

        layout.addStretch()

        # Version label at very bottom
        ver = QLabel(f'v{VERSION}')
        ver.setProperty('role', 'muted')
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setContentsMargins(0, 8, 0, 10)
        layout.addWidget(ver)

        return sidebar

    def _build_menu(self) -> None:
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu('File')

        change_lib = QAction('Change Library Folder…', self)
        change_lib.triggered.connect(self._dashboard._on_select_library)
        file_menu.addAction(change_lib)

        file_menu.addSeparator()

        quit_action = QAction('Quit CrateSort', self)
        quit_action.setShortcut('Ctrl+Q')
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # View
        view_menu = mb.addMenu('View')
        for nav_id, label, _ in _NAV_ITEMS:
            action = QAction(label, self)
            action.triggered.connect(
                lambda checked, nid=nav_id: self._on_nav_by_id(nid)
            )
            view_menu.addAction(action)

        # Help
        help_menu = mb.addMenu('Help')
        about = QAction('About CrateSort', self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

    def _build_status_bar(self) -> None:
        sb = QStatusBar()
        self.setStatusBar(sb)

        self._status_library = QLabel()
        # Explicit left margin so the path text has breathing room matching the right side
        self._status_library.setStyleSheet(
            f'color: {C["text_muted"]}; font-size: 11px; margin-left: 8px;'
        )

        self._status_state = QLabel()
        self._status_state.setStyleSheet(
            f'color: {C["text_muted"]}; font-size: 11px; margin-right: 4px;'
        )
        self._status_state.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        sb.addWidget(self._status_library, 1)
        sb.addPermanentWidget(self._status_state)

    def _placeholder(self, title: str) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(f'{title}')
        label.setProperty('role', 'heading')
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = QLabel('Coming in the next session.')
        sub.setProperty('role', 'muted')
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        layout.addSpacing(8)
        layout.addWidget(sub)
        return w

    # ── Slots ─────────────────────────────────────────────────────────

    def _show_sync_warning(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle('Sync Required')
        box.setText('Please review and sync the detected Serato changes on the Dashboard first.')
        box.exec()

    def _on_nav(self, index: int) -> None:
        # Fix 5: silent no-op for nav items disabled in States 1 and 2
        if index in (1, 2, 3, 4) and getattr(self, '_app_state', 3) < 3:
            return

        if index != 0 and hasattr(self, '_dashboard') and self._dashboard.is_sync_pending():
            self._show_sync_warning()
            self._nav_btns['dashboard'].setChecked(True)
            self._content.setCurrentIndex(0)
            return

        self._content.setCurrentIndex(index)
        inv = self._dashboard._inventory
        lib = self._dashboard._library_path
        if index == 1:   # Classifier
            if not inv or not lib:
                # Fix 4: redirect to Settings (recovery path) not Dashboard
                self._nav_btns['settings'].setChecked(True)
                self._content.setCurrentIndex(5)
                self._update_status('Load a library first.', 'amber')
                return
            self._classifier_view.start(inv, lib)
            self._update_status('Classifying library…', 'amber')
        elif index == 2:  # Library Browser
            if inv and lib:
                self._library_browser.load(inv, lib)
        elif index == 3:  # Crate Manager
            if inv and lib:
                self._crate_manager.load(inv, lib)
        elif index == 4:  # Organize
            if inv and lib:
                self._organize_view.load(inv, lib, lib / '_Serato_')
        elif index == 5:  # Settings
            self._settings_view.load(lib)
        if index not in (1, 2, 3):  # Clear art when leaving media views
            self._art_panel.clear()

    def _on_nav_by_id(self, nav_id: str) -> None:
        for i, (nid, _, _) in enumerate(_NAV_ITEMS):
            if nid == nav_id:
                self._nav_btns[nav_id].setChecked(True)
                self._on_nav(i)
                break

    def _on_library_changed(self, path: Path) -> None:
        self._settings.setValue('library_path', str(path))
        self._status_library.setText(str(path))
        self._undo_manager.clear()
        self._apply_nav_state(self._get_app_state())

    def _update_undo_buttons(self) -> None:
        _active = (
            'QPushButton { background: #428175; color: #ffffff; border: none;'
            ' border-radius: 6px; font-size: 13px; font-weight: 400; padding: 6px 8px;'
            ' min-height: 28px; cursor: pointer; }'
            'QPushButton:hover { background: #38706a; }'
            'QPushButton:pressed { background: #2d6358; }'
        )
        _inactive = (
            'QPushButton { background: #3a3a3a; color: #7a7a7a; border: none;'
            ' border-radius: 6px; font-size: 13px; font-weight: 400; padding: 6px 8px;'
            ' min-height: 28px; }'
        )
        if not hasattr(self, '_undo_btn'):
            return
        can_undo = self._undo_manager.can_undo()
        can_redo = self._undo_manager.can_redo()
        self._undo_btn.setEnabled(can_undo)
        self._undo_btn.setStyleSheet(_active if can_undo else _inactive)
        self._redo_btn.setEnabled(can_redo)
        self._redo_btn.setStyleSheet(_active if can_redo else _inactive)

    # ── App state (library / Serato availability) ──────────────────────

    def _get_app_state(self) -> int:
        """
        1 — No library path saved, or saved path no longer exists on disk.
        2 — Library path exists but contains no _Serato_ folder.
        3 — Library path exists AND _Serato_ folder is present. Normal operation.
        """
        saved = self._settings.value('library_path', None)
        if not saved:
            return 1
        lib = Path(saved)
        if not lib.exists():
            return 1
        if not (lib / '_Serato_').exists():
            return 2
        return 3

    def _apply_nav_state(self, state: int) -> None:
        """Enable/disable nav buttons and set tooltips based on app state."""
        self._app_state = state
        disabled = state < 3  # States 1 and 2 disable items 1-4
        tip = (
            'Load a library to get started' if state == 1
            else 'Serato folder not found at this library location'
        )
        for i, (nav_id, _, _) in enumerate(_NAV_ITEMS):
            btn = self._nav_btns.get(nav_id)
            if btn is None:
                continue
            if i in (1, 2, 3, 4):
                btn.setEnabled(not disabled)
                btn.setToolTip(tip if disabled else '')
            else:
                btn.setEnabled(True)
                btn.setToolTip('')

    def _switch_to_command_tab(self, cmd) -> None:
        """Switch to the tab where the command originated if not already there."""
        source = getattr(cmd, 'source_tab', None)
        if not source:
            return
        for i, (nav_id, _, _) in enumerate(_NAV_ITEMS):
            if nav_id == source:
                if self._content.currentIndex() != i:
                    self._nav_btns[nav_id].setChecked(True)
                    self._on_nav(i)
                break

    def _do_undo(self) -> None:
        if not self._undo_manager.can_undo():
            return
        self._switch_to_command_tab(self._undo_manager._undo_stack[-1])
        msg = self._undo_manager.undo()
        if msg and hasattr(self, '_crate_manager'):
            self._crate_manager._set_status(msg, teal=True)

    def _do_redo(self) -> None:
        if not self._undo_manager.can_redo():
            return
        self._switch_to_command_tab(self._undo_manager._redo_stack[-1])
        msg = self._undo_manager.redo()
        if msg and hasattr(self, '_crate_manager'):
            self._crate_manager._set_status(msg, teal=True)

    def _update_status(self, message: str, state: str) -> None:
        """state: 'amber' | 'green' | 'error' | ''"""
        dot_color = {
            'amber': C['warning'],
            'green': C['success'],
            'error': C['error'],
        }.get(state, C['text_muted'])

        if message:
            self._status_state.setText(
                f'<span style="color:{dot_color}; font-size:14px;">●</span>'
                f'  <span style="color:{C["text_muted"]}">{message}</span>'
            )
        else:
            self._status_state.clear()

        saved_path = self._settings.value('library_path', None)
        if saved_path:
            self._status_library.setText(str(saved_path))

    def _update_album_art(self, file_path: str) -> None:
        """Read embedded album art and display in the sidebar panel."""
        self._art_panel.set_track(file_path)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            'About CrateSort',
            f'<b>CrateSort</b> v{VERSION}<br><br>'
            f'Get your shit together.<br><br>'
            f'A DJ library organizer and Serato crate manager.<br>'
            f'&copy; JWBC',
        )

    def _on_classify_requested(self) -> None:
        if hasattr(self, '_dashboard') and self._dashboard.is_sync_pending():
            self._show_sync_warning()
            return
        self._on_nav_by_id('classification')

    def _on_classifier_back(self) -> None:
        self._on_nav_by_id('dashboard')

    def _on_classifier_done(self, _count: int = 0) -> None:
        inv = self._dashboard._inventory
        lib = self._dashboard._library_path
        if inv and lib:
            self._library_browser.load(inv, lib)
            self._library_browser._count_label.setText('Classification complete.')
            def _restore_count():
                try:
                    self._library_browser._count_label.setText(
                        f'{self._library_browser._tree.topLevelItemCount():,} artists · '
                        f'{len(self._library_browser._inventory):,} tracks'
                    )
                except Exception:
                    pass
            QTimer.singleShot(3000, _restore_count)
        self._nav_btns['library'].setChecked(True)
        self._content.setCurrentIndex(2)  # library is now index 2
        self._update_status('Classification complete. Ready.', 'green')

    def _on_crates_requested(self) -> None:
        if hasattr(self, '_dashboard') and self._dashboard.is_sync_pending():
            self._show_sync_warning()
            return
        self._on_nav_by_id('crates')

    def _on_organize_requested(self) -> None:
        if hasattr(self, '_dashboard') and self._dashboard.is_sync_pending():
            self._show_sync_warning()
            return
        self._on_nav_by_id('organize')

    def _on_library_changed_from_settings(self, path: Path) -> None:
        self._on_library_changed(path)
        self._dashboard.start_scan(path)
        self._on_nav_by_id('dashboard')

    def _on_repair_crate_paths(self) -> None:
        lib = self._dashboard._library_path
        if not lib:
            return
        serato_dir = lib / '_Serato_'
        logs_dir   = lib / '_CrateSort'
        if not serato_dir.exists() or not logs_dir.exists():
            return

        import json as _json
        from cratesort.src.serato.path_rewriter import PathRewriter, PathChange

        current_loc: dict[str, str] = {}
        for log_file in sorted(logs_dir.glob('reorganization_log_*.json')):
            with open(log_file) as f:
                log = _json.load(f)
            moves   = [m for m in log.get('moves', []) if m.get('status') == 'completed']
            rolled  = bool(log.get('rolled_back_at'))
            if not rolled:
                for m in moves:
                    src, dst = m['source'], m['destination']
                    key = next((k for k, v in current_loc.items() if v == src), None)
                    if key:
                        current_loc[key] = dst
                    else:
                        current_loc[src] = dst
            else:
                for m in reversed(moves):
                    src, dst = m['source'], m['destination']
                    key = next((k for k, v in current_loc.items() if v == dst), None)
                    if key:
                        current_loc[key] = src

        changes = []
        for orig, curr in current_loc.items():
            if orig == curr:
                continue
            orig_p, curr_p = Path(orig), Path(curr)
            try:
                rel_old = orig_p.relative_to(lib).as_posix()
                rel_new = curr_p.relative_to(lib).as_posix()
            except ValueError:
                continue
            changes.append(PathChange(old_path=rel_old,  new_path=rel_new))
            changes.append(PathChange(old_path=orig, new_path=curr))

        if not changes:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, 'Repair Crate Paths', 'No stale paths found — crates are up to date.')
            return

        result = PathRewriter(serato_dir).rewrite(changes, dry_run=False)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, 'Repair Crate Paths',
            f'Done.\n\n{result.crates_modified} crate(s) updated, '
            f'{result.paths_rewritten} track path(s) fixed.',
        )

    def _on_reorg_completed(self) -> None:
        """Re-scan the library after a reorganization or rollback so the in-memory
        inventory and crate manager reflect the new file locations immediately."""
        lib = self._dashboard._library_path
        if lib:
            self._dashboard.start_scan(lib)

    def _on_new_crate_requested(self) -> None:
        if hasattr(self, '_dashboard') and self._dashboard.is_sync_pending():
            self._show_sync_warning()
            return
        self._on_nav_by_id('crates')
        inv = self._dashboard._inventory
        lib = self._dashboard._library_path
        if inv and lib:
            self._crate_manager.load(inv, lib)
        if hasattr(self._crate_manager, '_on_new_crate'):
            self._crate_manager._on_new_crate()

    def _on_new_smart_crate_requested(self) -> None:
        if hasattr(self, '_dashboard') and self._dashboard.is_sync_pending():
            self._show_sync_warning()
            return
        self._on_nav_by_id('crates')
        inv = self._dashboard._inventory
        lib = self._dashboard._library_path
        if inv and lib:
            self._crate_manager.load(inv, lib)
        if hasattr(self._crate_manager, '_on_new_smart_crate'):
            self._crate_manager._on_new_smart_crate()

    # ── Window state ──────────────────────────────────────────────────

    def _restore_geometry(self) -> None:
        geom = self._settings.value('geometry')
        if geom:
            self.restoreGeometry(geom)
        else:
            self.resize(1200, 800)
            self._center_on_screen()

    def _center_on_screen(self) -> None:
        screen = self.screen()
        if screen:
            rect = screen.availableGeometry()
            self.move(
                rect.center().x() - self.width() // 2,
                rect.center().y() - self.height() // 2,
            )

    def closeEvent(self, event) -> None:
        self._settings.setValue('geometry', self.saveGeometry())
        if hasattr(self, '_library_browser'):
            self._library_browser.save_state()
        if hasattr(self, '_crate_manager'):
            self._crate_manager.save_state()
        if hasattr(self, '_dashboard') and self._dashboard._worker:
            self._dashboard._worker.cancel()
            self._dashboard._worker.wait(1000)
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Album art reader
# ---------------------------------------------------------------------------

def _read_album_art(file_path: str) -> Optional['QPixmap']:
    """Extract embedded album art from a media file using mutagen."""
    try:
        import mutagen
        pixmap = QPixmap()

        audio = mutagen.File(file_path, easy=False)
        if audio is None:
            return None

        # ID3 (MP3, WAV, AIFF) — APIC frames
        tags = getattr(audio, 'tags', None)
        if tags:
            for key in list(tags.keys()):
                if key.startswith('APIC'):
                    data = tags[key].data
                    if pixmap.loadFromData(data):
                        return pixmap

        # MP4 / M4A / M4V — covr atom
        if hasattr(audio, 'tags') and audio.tags and 'covr' in audio.tags:
            data = bytes(audio.tags['covr'][0])
            if pixmap.loadFromData(data):
                return pixmap

        # FLAC — picture blocks
        if hasattr(audio, 'pictures'):
            for pic in audio.pictures:
                if pixmap.loadFromData(pic.data):
                    return pixmap

    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Album art write / remove utilities (Fixes 5, 6)
# ---------------------------------------------------------------------------

def _write_album_art(file_path: str, image_path: str) -> bool:
    """Embed image_path as cover art into file_path. Returns True on success."""
    try:
        import mutagen
        from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
        from PyQt6.QtGui import QImage

        # Scale to max 500×500 and encode as JPEG (quality 85)
        img = QImage(image_path)
        if img.isNull():
            return False
        if img.width() > 500 or img.height() > 500:
            img = img.scaled(500, 500,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
        buf = QByteArray()
        buffer = QBuffer(buf)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buffer, 'JPEG', 85)
        img_bytes = bytes(buf)
        mime = 'image/jpeg'

        ext = Path(file_path).suffix.lower()
        audio = mutagen.File(file_path, easy=False)
        if audio is None:
            return False

        if ext in ('.mp3', '.wav', '.aif', '.aiff'):
            if audio.tags is None:
                audio.add_tags()
            from mutagen.id3 import APIC
            # Remove existing art
            audio.tags.delall('APIC')
            audio.tags.add(APIC(encoding=0, mime=mime, type=3, desc='Cover', data=img_bytes))
            audio.save()
        elif ext in ('.m4a', '.mp4', '.m4v', '.mov'):
            from mutagen.mp4 import MP4Cover
            audio.tags['covr'] = [MP4Cover(img_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
            audio.save()
        elif ext == '.flac':
            from mutagen.flac import Picture
            pic = Picture()
            pic.data = img_bytes
            pic.type = 3
            pic.mime = mime
            pic.width = img.width()
            pic.height = img.height()
            audio.clear_pictures()
            audio.add_picture(pic)
            audio.save()
        else:
            return False
        return True
    except Exception:
        return False


def _remove_album_art(file_path: str) -> bool:
    """Strip embedded cover art from file_path. Returns True on success."""
    try:
        import mutagen
        ext   = Path(file_path).suffix.lower()
        audio = mutagen.File(file_path, easy=False)
        if audio is None:
            return False
        if ext in ('.mp3', '.wav', '.aif', '.aiff'):
            if audio.tags:
                audio.tags.delall('APIC')
                audio.save()
        elif ext in ('.m4a', '.mp4', '.m4v', '.mov'):
            if audio.tags and 'covr' in audio.tags:
                del audio.tags['covr']
                audio.save()
        elif ext == '.flac':
            audio.clear_pictures()
            audio.save()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Album art panel widget — supports drag-and-drop + right-click (Fixes 5, 6)
# ---------------------------------------------------------------------------

class _ArtPanel(QLabel):
    """
    170×170 sidebar panel for embedded album art.
    Accepts image file drops and provides a right-click context menu.
    """

    def __init__(self, parent=None):
        super().__init__('♪', parent)
        self.setFixedSize(170, 170)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet('QLabel { background-color: #222222; color: #444444; font-size: 36px; }')
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_right_click)
        # State tracking
        self._current_path:  str = ''
        self._current_title: str = ''
        self._current_pixmap: Optional[QPixmap] = None

    def clear(self) -> None:
        self._current_path = ''
        self._show_pixmap(None)

    def set_track(self, file_path: str, title: str = '') -> None:
        self._current_path  = file_path
        self._current_title = title
        pixmap = _read_album_art(file_path)
        self._show_pixmap(pixmap)

    def _show_pixmap(self, pixmap: Optional[QPixmap]) -> None:
        self._current_pixmap = pixmap
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(168, 168,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(scaled)
            self.setText('')
        else:
            self.setPixmap(QPixmap())
            self.setText('♪')

    # ── Drag-and-drop (Fix 5) ──────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(('.jpg', '.jpeg', '.png')):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        url = event.mimeData().urls()[0].toLocalFile()
        self._replace_art(url)

    # ── Right-click menu (Fix 6) ───────────────────────────────────────

    def _on_right_click(self, pos) -> None:
        if not self._current_path:
            return
        menu = QMenu(self)
        replace_act = menu.addAction('Replace Art…')
        remove_act  = menu.addAction('Remove Art')
        save_act    = menu.addAction('Save Art As…')

        remove_act.setEnabled(self._current_pixmap is not None)
        save_act.setEnabled(self._current_pixmap is not None)

        action = menu.exec(self.mapToGlobal(pos))
        if action == replace_act:
            path, _ = QFileDialog.getOpenFileName(
                self, 'Select Image', '', 'Images (*.jpg *.jpeg *.png)'
            )
            if path:
                self._replace_art(path)
        elif action == remove_act:
            self._remove_art()
        elif action == save_act:
            self._save_art()

    def _replace_art(self, image_path: str) -> None:
        """Replace art immediately — no confirmation (Fix 4). Flash on success."""
        if _write_album_art(self._current_path, image_path):
            self.set_track(self._current_path, self._current_title)
            self._flash_success()
        else:
            QMessageBox.warning(self, 'Error', 'Could not write album art to file.')

    def _remove_art(self) -> None:
        """Remove art immediately — no confirmation dialog, teal flash on success."""
        if _remove_album_art(self._current_path):
            self._show_pixmap(None)
            self._flash_success()
        else:
            QMessageBox.warning(self, 'Error', 'Could not remove album art from file.')

    def _flash_success(self) -> None:
        """Flash the panel border teal for 800ms to confirm an art write."""
        self.setStyleSheet(
            'QLabel { background-color: #222222; color: #444444; font-size: 36px; '
            'border: 3px solid #428175; border-radius: 3px; }'
        )
        QTimer.singleShot(800, lambda: self.setStyleSheet(
            'QLabel { background-color: #222222; color: #444444; font-size: 36px; }'
        ))

    def _save_art(self) -> None:
        if not self._current_pixmap:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Save Album Art As', 'cover.jpg', 'JPEG (*.jpg *.jpeg);;PNG (*.png)'
        )
        if path:
            self._current_pixmap.save(path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import traceback
    def _exception_hook(exc_type, exc_value, exc_tb):
        traceback.print_exception(exc_type, exc_value, exc_tb)
    sys.excepthook = _exception_hook

    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setOrganizationName(ORG)
    # Item 10: kill system blue at the palette level BEFORE the stylesheet
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Highlight,        QColor('#D17D34'))
    palette.setColor(QPalette.ColorRole.HighlightedText,  QColor('#2F2F2F'))
    app.setPalette(palette)
    apply_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
