import os

new_code = """
# ── macOS PARITY IMPLEMENTATION ────────────────────────────

    def _load_apps_manifest_and_autostart(self):
        import json
        manifest_path = "Applications/apps_manifest.json"
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r") as f:
                    apps = json.load(f)
                self._apps_manifest_cache = dict(apps)
                
                # AUTOSTART
                autostart_entries = [
                    (name, dat) for name, dat in apps.items()
                    if dat.get("autostart") is True and dat.get("entry_point")
                ]
                autostart_entries.sort(
                    key=lambda kv: (int(kv[1].get("autostart_order", 99)), kv[0].lower())
                )
                for ord_idx, (name, dat) in enumerate(autostart_entries):
                    delay = int(dat.get("autostart_delay_ms", 700 + 600 * ord_idx))
                    QTimer.singleShot(delay, (lambda nm: lambda: self._autostart_one(nm))(name))
            except Exception as e:
                print(f"[Boot Error] Failed to load apps manifest: {e}")

    def _toggle_spotlight(self):
        if hasattr(self, '_spotlight'):
            if self._spotlight.isVisible():
                self._spotlight.hide()
            else:
                self._spotlight.setGeometry(self.width() // 2 - 300, self.height() // 2 - 150, 600, 300)
                self._spotlight.show()
                self._spotlight.search_bar.setFocus()
                self._spotlight.search_bar.clear()
                self._spotlight._update_list()

    def _toggle_launchpad(self):
        if hasattr(self, '_launchpad'):
            if self._launchpad.isVisible():
                self._launchpad.hide()
            else:
                self._launchpad.setGeometry(0, 0, self.width(), self.height())
                self._launchpad.show()

    def _build_top_menu_bar(self):
        bar = QWidget()
        bar.setFixedHeight(26)
        bar.setStyleSheet("background-color: rgba(26, 27, 38, 0.95); border-bottom: 1px solid #414868;")
        
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(15)
        
        lbl_apple = QLabel("🧜‍♀️ SIFTA")
        lbl_apple.setStyleSheet("color: #bb9af7; font-weight: bold; font-family: -apple-system, BlinkMacSystemFont, sans-serif;")
        layout.addWidget(lbl_apple)
        
        file_menu = QLabel("File")
        file_menu.setStyleSheet("color: #a9b1d6;")
        layout.addWidget(file_menu)
        
        edit_menu = QLabel("Edit")
        edit_menu.setStyleSheet("color: #a9b1d6;")
        layout.addWidget(edit_menu)

        layout.addStretch(1)

        self._relay_indicator = QLabel("● Relay: …")
        self._relay_indicator.setStyleSheet("color: #565f89; font-size: 11px;")
        layout.addWidget(self._relay_indicator)

        self._relay_timer = QTimer(self)
        self._relay_timer.timeout.connect(self._update_relay_indicator)
        self._relay_timer.start(2000)
        
        return bar

    def _build_dock(self):
        bar = QWidget()
        bar.setFixedHeight(80)
        bar.setStyleSheet("background: transparent;")
        
        main_h = QHBoxLayout(bar)
        main_h.setContentsMargins(0, 0, 0, 15)
        main_h.addStretch()
        
        dock_frame = QFrame()
        dock_frame.setStyleSheet(\"\"\"
            QFrame {
                background-color: rgba(26, 27, 38, 0.85);
                border: 1px solid #414868;
                border-radius: 16px;
            }
        \"\"\")
        
        dock_layout = QHBoxLayout(dock_frame)
        dock_layout.setContentsMargins(15, 10, 15, 10)
        dock_layout.setSpacing(15)
        
        def make_dock_btn(emoji, name, callback):
            btn = QPushButton(emoji)
            btn.setFixedSize(50, 50)
            btn.setToolTip(name)
            btn.setStyleSheet(\"\"\"
                QPushButton {
                    background-color: #24283b;
                    font-size: 28px;
                    border-radius: 12px;
                    border: 1px solid #414868;
                }
                QPushButton:hover {
                    background-color: #bb9af7;
                    border: 1px solid #9d7cd8;
                }
            \"\"\")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(callback)
            dock_layout.addWidget(btn)
        
        make_dock_btn("🚀", "Launchpad", self._toggle_launchpad)
        make_dock_btn("🔍", "Spotlight", self._toggle_spotlight)
        make_dock_btn("📁", "Finder", lambda: self.spawn_native_widget("File Manager", "Applications/sifta_file_manager_widget.py", "FileManagerWidget"))
        make_dock_btn("🌐", "Safari", lambda: self.spawn_native_widget("Swarm Browser", "Applications/sifta_swarm_browser.py", "SwarmBrowserWidget"))
        make_dock_btn("💬", "Messages", self.open_swarm_chat)
        make_dock_btn("👩‍💻", "Terminal", lambda: self._launch_app("Terminal", "Applications/sifta_terminal.py", "SiftaTerminalApp", 700, 450))
        make_dock_btn("⚙️", "Settings", lambda: self.spawn_native_widget("Settings", "Applications/sifta_system_settings.py", "SystemSettingsWidget"))
        
        main_h.addWidget(dock_frame)
        main_h.addStretch()
        return bar


class LaunchpadWidget(QWidget):
    def __init__(self, desktop):
        super().__init__(desktop)
        self.desktop = desktop
        self.setStyleSheet("background-color: rgba(10, 10, 15, 0.90);")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)
        
        search = QLineEdit()
        search.setPlaceholderText("Search Apps...")
        search.setStyleSheet("background: rgba(36, 40, 59, 0.8); color: white; padding: 10px; font-size: 18px; border-radius: 8px;")
        search.textChanged.connect(self._filter_apps)
        layout.addWidget(search, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(40)
        
        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(40)
        
        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.grid_container)
        scroll.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(scroll)
        
        self._app_buttons = []
        self._populate_grid()
        
    def _populate_grid(self):
        apps = self.desktop._apps_manifest_cache
        sorted_apps = sorted(apps.keys())
        
        row, col = 0, 0
        for name in sorted_apps:
            dat = apps[name]
            btn = QPushButton("📦\\n" + name)
            btn.setFixedSize(120, 120)
            btn.setStyleSheet(\"\"\"
                QPushButton { background: transparent; color: #a9b1d6; font-size: 14px; font-weight: bold; border: none; }
                QPushButton:hover { background: rgba(187, 154, 247, 0.3); border-radius: 16px; }
            \"\"\")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            def make_launcher(n, d):
                def launch():
                    self.hide()
                    self.desktop._launch_app(n, d.get("entry_point"), d.get("widget_class", ""), 920, 640)
                return launch
                
            btn.clicked.connect(make_launcher(name, dat))
            self.grid_layout.addWidget(btn, row, col)
            self._app_buttons.append((name, btn))
            
            col += 1
            if col > 6:
                col = 0
                row += 1

    def _filter_apps(self, text):
        t = text.lower()
        for name, btn in self._app_buttons:
            btn.setVisible(t in name.lower())

    def mousePressEvent(self, event):
        self.hide()


class SpotlightWidget(QWidget):
    def __init__(self, desktop):
        super().__init__(desktop)
        self.desktop = desktop
        self.setStyleSheet("background-color: rgba(26, 27, 38, 0.95); border-radius: 12px; border: 1px solid #414868;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Spotlight Search...")
        self.search_bar.setStyleSheet("background: transparent; color: white; padding: 15px; font-size: 24px; border: none;")
        self.search_bar.textChanged.connect(self._update_list)
        self.search_bar.returnPressed.connect(self._launch_selected)
        layout.addWidget(self.search_bar)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(\"\"\"
            QListWidget { background: transparent; border-top: 1px solid #414868; font-size: 16px; color: #a9b1d6; }
            QListWidget::item { padding: 10px; }
            QListWidget::item:selected { background: #bb9af7; color: #1a1b26; }
        \"\"\")
        layout.addWidget(self.list_widget)

    def _update_list(self):
        self.list_widget.clear()
        t = self.search_bar.text().lower()
        if not t:
            return
        
        apps = self.desktop._apps_manifest_cache
        for name in sorted(apps.keys()):
            if t in name.lower():
                self.list_widget.addItem(name)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _launch_selected(self):
        item = self.list_widget.currentItem()
        if item:
            name = item.text()
            dat = self.desktop._apps_manifest_cache.get(name)
            if dat:
                self.desktop._launch_app(name, dat.get("entry_point"), dat.get("widget_class", ""), 920, 640)
        self.hide()
        
    def focusOutEvent(self, event):
        self.hide()
        super().focusOutEvent(event)

"""

with open(".simulation_publicpush_sandbox/sifta_os_desktop.py", "a") as f:
    f.write(new_code)

print("Patch 2 appended.")
