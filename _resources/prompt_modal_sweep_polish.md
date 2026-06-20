# CrateSort — Modal Sweep Polish & Welcome Screen Alignment

Apply these final polish updates to complete the modal standardization and welcome screen formatting. Run at Sonnet high effort. Read all referenced files fully before modifying any code.

---

## Changes Required

### 1. Update [main_window.py](file:///Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort/src/gui/main_window.py)
* Import `_ov_alert` from `cratesort.src.gui.overlays` at the top of the file.
* Remove `QMessageBox` from the `PyQt6.QtWidgets` import list.
* Replace all `QMessageBox` calls with `_ov_alert`:
  - In `_show_sync_warning()` (line 343):
    ```diff
    -    def _show_sync_warning(self) -> None:
    -        box = QMessageBox(self)
    -        box.setWindowTitle('Sync Required')
    -        box.setText('Please review and sync the detected Serato changes on the Dashboard first.')
    -        box.exec()
    +    def _show_sync_warning(self) -> None:
    +        _ov_alert(
    +            self,
    +            'Sync Required',
    +            'Please review and sync the detected Serato changes on the Dashboard first.'
    +        )
    ```
  - In `_show_about()` (line 522):
    ```diff
    -    def _show_about(self) -> None:
    -        QMessageBox.about(
    -            self,
    -            'About CrateSort',
    -            f'<b>CrateSort</b> v{VERSION}<br><br>'
    -            f'Get your shit together.<br><br>'
    -            f'A DJ library organizer and Serato crate manager.<br>'
    -            f'&copy; JWBC',
    -        )
    +    def _show_about(self) -> None:
    +        _ov_alert(
    +            self,
    +            'About CrateSort',
    +            f'<b>CrateSort</b> v{VERSION}<br><br>'
    +            f'Get your shit together.<br><br>'
    +            f'A DJ library organizer and Serato crate manager.<br>'
    +            f'&copy; JWBC'
    +        )
    ```
  - In `_on_repair_crates()` (lines 602–612):
    Replace both `QMessageBox.information` calls with `_ov_alert`:
    ```diff
    -        if not changes:
    -            from PyQt6.QtWidgets import QMessageBox
    -            QMessageBox.information(self, 'Repair Crate Paths', 'No stale paths found — crates are up to date.')
    -            return
    +        if not changes:
    +            _ov_alert(self, 'Repair Crate Paths', 'No stale paths found — crates are up to date.')
    +            return
    ```
    and:
    ```diff
    -        from PyQt6.QtWidgets import QMessageBox
    -        QMessageBox.information(
    -            self, 'Repair Crate Paths',
    -            f'Done.\n\n{result.crates_modified} crate(s) updated, '
    -            f'{result.paths_rewritten} track path(s) fixed.',
    -        )
    +        _ov_alert(
    +            self, 'Repair Crate Paths',
    +            f'Done.\n\n{result.crates_modified} crate(s) updated, '
    +            f'{result.paths_rewritten} track path(s) fixed.'
    +        )
    ```
  - In `_replace_art()` (line 899):
    ```diff
    -            QMessageBox.warning(self, 'Error', 'Could not write album art to file.')
    +            _ov_alert(self, 'Error', 'Could not write album art to file.')
    ```
  - In `_remove_art()` (line 907):
    ```diff
    -            QMessageBox.warning(self, 'Error', 'Could not remove album art from file.')
    +            _ov_alert(self, 'Error', 'Could not remove album art from file.')
    ```

### 2. Update [dashboard.py](file:///Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort/src/gui/dashboard.py)
* In `_build_welcome()` under the `elif not saved_path.exists():` block (lines 744–774), wrap the returning-user layout elements inside a `content_container = QWidget()` with a fixed width of `440` and middle-elide the library path string, matching the layout structure used in the `else` block:
  ```diff
          elif not saved_path.exists():
              # Returning user whose library path was deleted or moved.
  -            not_found = QLabel('Your previous library could not be found.')
  -            not_found.setStyleSheet('font-size: 14px; color: #f1e3c8;')
  -            not_found.setAlignment(Qt.AlignmentFlag.AlignCenter)
  -            layout.addWidget(not_found)
  -
  -            path_text = QLabel(str(saved_path))
  -            path_text.setWordWrap(True)
  -            path_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
  -            path_text.setStyleSheet('font-size: 12px; color: #7a6a55;')
  -            layout.addWidget(path_text)
  -
  -            btn = QPushButton('Select Music Library…')
  -            btn.setFixedWidth(220)
  -            btn.setMinimumHeight(42)
  -            btn.clicked.connect(self._on_select_library)
  -            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
  +            content_container = QWidget()
  +            content_container.setFixedWidth(440)
  +            cc_layout = QVBoxLayout(content_container)
  +            cc_layout.setContentsMargins(0, 0, 0, 0)
  +            cc_layout.setSpacing(10)
  +            layout.addWidget(content_container, alignment=Qt.AlignmentFlag.AlignCenter)
  +
  +            not_found = QLabel('Your previous library could not be found.')
  +            not_found.setStyleSheet('font-size: 14px; color: #f1e3c8;')
  +            not_found.setAlignment(Qt.AlignmentFlag.AlignCenter)
  +            cc_layout.addWidget(not_found)
  +
  +            path_text = QLabel()
  +            path_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
  +            path_text.setStyleSheet('font-size: 12px; color: #7a6a55;')
  +            fm = QFontMetrics(path_text.font())
  +            elided_path = fm.elidedText(str(saved_path), Qt.TextElideMode.ElideMiddle, 400)
  +            path_text.setText(elided_path)
  +            path_text.setToolTip(str(saved_path))
  +            cc_layout.addWidget(path_text)
  +
  +            btn = QPushButton('Select Music Library…')
  +            btn.setFixedWidth(220)
  +            btn.setMinimumHeight(42)
  +            btn.clicked.connect(self._on_select_library)
  +            cc_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
  ```

---

## Verification Checklist
- Run app: verify all custom dialogs and error alerts in `MainWindow` correctly show the overlay scrim, dim the app, and apply standard `_ov_alert` custom styling.
- Verify welcome screen when library path is missing: the container is 440px wide and the missing path string is middle-elided with a hover tooltip.
- Verify that `QMessageBox` is completely removed from imports and code usages in both files.
