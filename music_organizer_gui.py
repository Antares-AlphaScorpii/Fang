from pathlib import Path
import json
import os
import sys
import urllib.parse
import urllib.request

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from music_organizer import (
    analyze_music,
    apply_operations,
)


APP_NAME = "Fang"
APP_ORG = "Antares-AlphaScorpii"

CONFIG_DIR = os.path.expanduser(
    "~/Library/Application Support/Fang"
)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


# ------------------------------------------------------------
# Settings
# ------------------------------------------------------------

DEFAULT_SETTINGS = {
    "appearance": "system",
    "acoustid_api_key": "",
}


def load_settings():
    settings = DEFAULT_SETTINGS.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)

        if isinstance(saved, dict):
            settings.update(saved)

    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    return settings


def save_settings(settings):
    os.makedirs(CONFIG_DIR, exist_ok=True)

    temp_file = CONFIG_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

    os.replace(temp_file, CONFIG_FILE)


# ------------------------------------------------------------
# Appearance
# ------------------------------------------------------------

def get_system_theme():
    try:
        import subprocess

        result = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True,
            text=True,
            timeout=2,
        )

        if result.returncode == 0:
            if result.stdout.strip().lower() == "dark":
                return "dark"

    except Exception:
        pass

    return "light"


# ------------------------------------------------------------
# Scorpius logo
# ------------------------------------------------------------

class ScorpiusLogo(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(58, 58)
        self.setMaximumSize(58, 58)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect())
        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(QColor("#8B6FB8"))
        painter.drawRoundedRect(rect, 16, 16)

        points = [
            QPointF(14, 13),
            QPointF(25, 18),
            QPointF(34, 25),
            QPointF(42, 32),
            QPointF(40, 42),
            QPointF(31, 48),
            QPointF(21, 45),
            QPointF(14, 37),
            QPointF(11, 28),
        ]

        pen = QPen(QColor("#F4EFFF"), 1.6)
        painter.setPen(pen)

        for a, b in zip(points, points[1:]):
            painter.drawLine(a, b)

        painter.setPen(Qt.PenStyle.NoPen)

        for index, point in enumerate(points):
            radius = 3.5 if index == 2 else 2.4

            if index == 2:
                painter.setBrush(QColor("#FFD76A"))
            else:
                painter.setBrush(QColor("#FFFFFF"))

            painter.drawEllipse(
                int(point.x() - radius),
                int(point.y() - radius),
                int(radius * 2),
                int(radius * 2),
            )

        painter.end()


# ------------------------------------------------------------
# Reusable UI helpers
# ------------------------------------------------------------

class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")


def make_title(text):
    label = QLabel(text)
    label.setObjectName("PageTitle")
    return label


def make_subtitle(text):
    label = QLabel(text)
    label.setObjectName("PageSubtitle")
    label.setWordWrap(True)
    return label


def make_section_title(text):
    label = QLabel(text)
    label.setObjectName("SectionTitle")
    return label


# ------------------------------------------------------------
# Settings page
# ------------------------------------------------------------

class SettingsPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window

        self.system_radio = QRadioButton("System")
        self.light_radio = QRadioButton("Light")
        self.dark_radio = QRadioButton("Dark")

        self.api_key = QLineEdit()
        self.api_key.setEchoMode(
            QLineEdit.EchoMode.Password
        )
        self.api_key.setPlaceholderText(
            "Enter your AcoustID application API key"
        )
        self.api_key.setMinimumHeight(42)

        self.test_button = QPushButton("Test Key")
        self.save_button = QPushButton("Save Settings")

        self.status_label = QLabel(
            "AcoustID is not configured yet."
        )
        self.status_label.setObjectName("StatusText")
        self.status_label.setWordWrap(True)

        self.build_ui()
        self.load_from_settings()

    def build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setWidget(self._build_content())

        outer.addWidget(scroll)

    def _build_content(self):
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(32, 28, 32, 32)
        root.setSpacing(20)

        root.addWidget(
            make_title("Settings")
        )

        root.addWidget(
            make_subtitle(
                "Customize Fang and connect optional music identification."
            )
        )

        # --------------------------------------------------------
        # Appearance
        # --------------------------------------------------------

        appearance_card = Card()
        appearance_layout = QVBoxLayout(appearance_card)
        appearance_layout.setContentsMargins(24, 22, 24, 22)
        appearance_layout.setSpacing(12)

        appearance_layout.addWidget(
            make_section_title("Appearance")
        )

        appearance_description = QLabel(
            "Choose how Fang should look. System follows your macOS appearance."
        )
        appearance_description.setWordWrap(True)
        appearance_layout.addWidget(
            appearance_description
        )

        radio_layout = QHBoxLayout()
        radio_layout.setSpacing(18)

        radio_layout.addWidget(self.system_radio)
        radio_layout.addWidget(self.light_radio)
        radio_layout.addWidget(self.dark_radio)
        radio_layout.addStretch()

        appearance_layout.addLayout(radio_layout)

        self.system_radio.toggled.connect(
            self.appearance_changed
        )
        self.light_radio.toggled.connect(
            self.appearance_changed
        )
        self.dark_radio.toggled.connect(
            self.appearance_changed
        )

        root.addWidget(appearance_card)

        # --------------------------------------------------------
        # AcoustID
        # --------------------------------------------------------

        acoustid_card = Card()
        acoustid_layout = QVBoxLayout(acoustid_card)
        acoustid_layout.setContentsMargins(24, 22, 24, 22)
        acoustid_layout.setSpacing(12)

        acoustid_layout.addWidget(
            make_section_title("Music Identification")
        )

        acoustid_description = QLabel(
            "Fang can use AcoustID to identify audio files by their "
            "audio fingerprint. This is optional."
        )
        acoustid_description.setWordWrap(True)
        acoustid_layout.addWidget(
            acoustid_description
        )

        key_row = QHBoxLayout()
        key_row.setSpacing(10)

        key_row.addWidget(self.api_key, 1)
        key_row.addWidget(self.test_button)

        acoustid_layout.addLayout(key_row)

        status_container = QWidget()
        status_container.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        status_container.setMinimumHeight(28)
        status_layout = QVBoxLayout(status_container)
        status_layout.setContentsMargins(0, 4, 0, 0)
        status_layout.addWidget(self.status_label)

        acoustid_layout.addWidget(status_container)

        self.test_button.clicked.connect(
            self.test_acoustid_key
        )

        root.addWidget(acoustid_card)

        # --------------------------------------------------------
        # About Fang
        # --------------------------------------------------------

        about_card = Card()
        about_layout = QVBoxLayout(about_card)
        about_layout.setContentsMargins(24, 22, 24, 22)
        about_layout.setSpacing(8)

        about_layout.addWidget(
            make_section_title("About Fang")
        )

        about_name = QLabel("Fang")
        about_name.setStyleSheet(
            "font-size: 20px; font-weight: 700;"
        )
        about_layout.addWidget(about_name)

        about_subtitle = QLabel("Music Organizer")
        about_subtitle.setStyleSheet(
            "font-size: 13px; font-weight: 600;"
        )
        about_layout.addWidget(about_subtitle)

        about_text = QLabel(
            "Fang helps turn messy music folders into a clean, "
            "organized library using the metadata already stored "
            "in your audio files. It can organize music into "
            "Artist, Album and Track folders and can use AcoustID "
            "to help identify files when their metadata is incomplete.\n\n"
            "Fang is designed around safety. Scanning and reviewing "
            "never changes your files. Suggested moves and renames "
            "are shown first, and changes are only made when you "
            "explicitly approve them."
        )
        about_text.setWordWrap(True)
        about_text.setMinimumHeight(105)
        about_text.setStyleSheet(
            "font-size: 12px;"
        )
        about_layout.addWidget(about_text)

        root.addWidget(about_card)

        root.addSpacing(4)

        save_row = QHBoxLayout()
        save_row.addStretch()
        save_row.addWidget(self.save_button)

        self.save_button.clicked.connect(
            self.save
        )

        root.addLayout(save_row)
        root.addSpacing(12)

        return content

    def load_from_settings(self):
        settings = self.window.settings

        appearance = settings.get(
            "appearance",
            "system"
        )

        self.system_radio.setChecked(
            appearance == "system"
        )

        self.light_radio.setChecked(
            appearance == "light"
        )

        self.dark_radio.setChecked(
            appearance == "dark"
        )

        self.api_key.setText(
            settings.get("acoustid_api_key", "")
        )

    def appearance_changed(self):
        if not self.isVisible():
            return

        if self.system_radio.isChecked():
            appearance = "system"
        elif self.light_radio.isChecked():
            appearance = "light"
        else:
            appearance = "dark"

        self.window.settings["appearance"] = appearance
        save_settings(self.window.settings)
        self.window.update_theme()

    def save(self):
        if self.system_radio.isChecked():
            appearance = "system"
        elif self.light_radio.isChecked():
            appearance = "light"
        else:
            appearance = "dark"

        self.window.settings["appearance"] = appearance
        self.window.settings["acoustid_api_key"] = (
            self.api_key.text().strip()
        )

        save_settings(self.window.settings)

        self.status_label.setText(
            "Settings saved."
        )

    def test_acoustid_key(self):
        key = self.api_key.text().strip()

        if not key:
            self.status_label.setText(
                "Enter an AcoustID application API key first."
            )
            return

        self.test_button.setEnabled(False)
        self.status_label.setText(
            "Testing AcoustID key..."
        )

        QApplication.processEvents()

        try:
            import os
            import subprocess

            music_dir = os.path.expanduser("~/Music")
            audio_file = None

            for root, dirs, files in os.walk(music_dir):
                for filename in files:
                    if filename.lower().endswith(
                        (".mp3", ".flac", ".m4a", ".wav", ".ogg", ".opus")
                    ):
                        audio_file = os.path.join(root, filename)
                        break
                if audio_file:
                    break

            if not audio_file:
                raise RuntimeError(
                    "No supported audio file was found in ~/Music."
                )

            result = subprocess.run(
                ["fpcalc", audio_file],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )

            duration = None
            fingerprint = None

            for line in result.stdout.splitlines():
                if line.startswith("DURATION="):
                    duration = line.split("=", 1)[1].strip()
                elif line.startswith("FINGERPRINT="):
                    fingerprint = line.split("=", 1)[1].strip()

            if not duration or not fingerprint:
                raise RuntimeError(
                    "fpcalc did not return a valid fingerprint."
                )

            params = {
                "format": "json",
                "client": key,
                "duration": duration,
                "fingerprint": fingerprint,
            }

            url = (
                "https://api.acoustid.org/v2/lookup?"
                + urllib.parse.urlencode(params)
            )

            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Fang/1.0"
                },
            )

            with urllib.request.urlopen(
                request,
                timeout=10,
            ) as response:
                data = json.loads(
                    response.read().decode("utf-8")
                )

            if data.get("status") == "ok":
                self.status_label.setText(
                    "✓ AcoustID connection works. "
                    "Your application key was accepted."
                )
            else:
                error = data.get(
                    "error",
                    {}
                )

                message = error.get(
                    "message",
                    "AcoustID returned an error."
                )

                self.status_label.setText(
                    f"AcoustID responded: {message}"
                )

        except Exception as exc:
            self.status_label.setText(
                f"Could not contact AcoustID: {exc}"
            )

        finally:
            self.test_button.setEnabled(True)


# ------------------------------------------------------------
# Organize page
# ------------------------------------------------------------

class OrganizePage(QWidget):
    def __init__(self, window):
        super().__init__()

        self.window = window
        self.source_folder = ""
        self.output_folder = ""
        self.operations = []

        self.build_ui()

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 32)
        root.setSpacing(20)

        header = QHBoxLayout()

        title_area = QVBoxLayout()
        title_area.setSpacing(4)

        title_area.addWidget(
            make_title("Organize Music")
        )

        title_area.addWidget(
            make_subtitle(
                "Scan your music, review Fang's suggestions, "
                "then apply only the changes you approve."
            )
        )

        header.addLayout(title_area, 1)

        self.review_badge = QLabel("REVIEW MODE")
        self.review_badge.setObjectName("Badge")
        self.review_badge.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        header.addWidget(
            self.review_badge,
            0,
            Qt.AlignmentFlag.AlignTop
        )

        root.addLayout(header)

        folders_card = Card()
        folders_layout = QVBoxLayout(folders_card)
        folders_layout.setContentsMargins(24, 22, 24, 22)
        folders_layout.setSpacing(12)

        folders_layout.addWidget(
            make_section_title("Folders")
        )

        self.source_label = QLabel(
            "Source: No folder selected"
        )

        self.output_label = QLabel(
            "Destination: No folder selected"
        )

        folders_layout.addWidget(
            self.source_label
        )

        folders_layout.addWidget(
            self.output_label
        )

        folder_buttons = QHBoxLayout()

        self.source_button = QPushButton(
            "Choose Music Folder"
        )

        self.output_button = QPushButton(
            "Choose Destination"
        )

        folder_buttons.addWidget(
            self.source_button
        )
        folder_buttons.addWidget(
            self.output_button
        )
        folder_buttons.addStretch()

        folders_layout.addLayout(folder_buttons)

        root.addWidget(folders_card)

        actions_card = Card()
        actions_layout = QVBoxLayout(actions_card)
        actions_layout.setContentsMargins(24, 22, 24, 22)
        actions_layout.setSpacing(12)

        actions_layout.addWidget(
            make_section_title("Actions")
        )

        action_row = QHBoxLayout()

        self.scan_button = QPushButton(
            "Scan & Analyze"
        )
        self.scan_button.setObjectName(
            "PrimaryButton"
        )

        self.review_button = QPushButton(
            "Open Review"
        )

        self.review_button.setEnabled(False)

        action_row.addWidget(
            self.scan_button
        )
        action_row.addWidget(
            self.review_button
        )
        action_row.addStretch()

        actions_layout.addLayout(action_row)

        self.summary_label = QLabel(
            "Nothing scanned yet."
        )

        self.summary_label.setObjectName(
            "StatusText"
        )

        actions_layout.addWidget(
            self.summary_label
        )

        root.addWidget(actions_card)

        root.addStretch()

        self.source_button.clicked.connect(
            self.choose_source
        )

        self.output_button.clicked.connect(
            self.choose_output
        )

        self.scan_button.clicked.connect(
            self.scan
        )

        self.review_button.clicked.connect(
            self.open_review
        )

    def choose_source(self):
        from PyQt6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(
            self,
            "Choose Music Folder",
            os.path.expanduser("~/Music"),
        )

        if folder:
            self.source_folder = folder
            self.source_label.setText(
                f"Source: {folder}"
            )

    def choose_output(self):
        from PyQt6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(
            self,
            "Choose Destination",
            os.path.expanduser("~/Music"),
        )

        if folder:
            self.output_folder = folder
            self.output_label.setText(
                f"Destination: {folder}"
            )

    def scan(self):
        if not self.source_folder:
            QMessageBox.warning(
                self,
                "Source Required",
                "Choose a music folder first.",
            )
            return

        if not self.output_folder:
            QMessageBox.warning(
                self,
                "Destination Required",
                "Choose a destination folder first.",
            )
            return

        self.scan_button.setEnabled(False)
        self.summary_label.setText(
            "Scanning and analyzing..."
        )

        QApplication.processEvents()

        try:
            self.operations = analyze_music(
                self.source_folder,
                self.output_folder,
                acoustid_api_key=self.window.settings.get(
                    "acoustid_api_key",
                    "",
                ),
            )

            total = len(self.operations)

            keep = sum(
                1
                for op in self.operations
                if op.get("status") == "keep"
            )

            rename = sum(
                1
                for op in self.operations
                if op.get("status") == "rename"
            )

            review = sum(
                1
                for op in self.operations
                if op.get("status") == "review"
            )

            self.summary_label.setText(
                f"{total} files scanned  •  "
                f"{keep} keep  •  "
                f"{rename} rename  •  "
                f"{review} needs review"
            )

            self.review_button.setEnabled(
                bool(self.operations)
            )

            if self.operations:
                self.window.review_page.load_operations(
                    self.operations
                )

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Scan Failed",
                str(exc),
            )

        finally:
            self.scan_button.setEnabled(True)

    def open_review(self):
        self.window.tabs.setCurrentWidget(
            self.window.review_page
        )


# ------------------------------------------------------------
# Review page
# ------------------------------------------------------------

class ReviewPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.operations = []
        self.selected_sources = set()
        self.filtered_operations = []

        self.build_ui()

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    def operation_key(self, operation):
        return str(operation.get("source"))

    def metadata_value(self, metadata, key):
        if not metadata:
            return None

        value = metadata.get(key)

        if isinstance(value, list):
            value = value[0] if value else None

        if value is None:
            return None

        value = str(value).strip()

        return value or None

    def display_artist(self, operation):
        metadata = operation.get("metadata", {})

        return (
            self.metadata_value(metadata, "album_artist")
            or self.metadata_value(metadata, "artist")
            or "Unknown Artist"
        )

    def display_album(self, operation):
        return (
            self.metadata_value(
                operation.get("metadata", {}),
                "album",
            )
            or "Unknown Album"
        )

    def display_title(self, operation):
        return (
            self.metadata_value(
                operation.get("metadata", {}),
                "title",
            )
            or Path(operation.get("source", "")).stem
            or "Unknown Track"
        )

    def status_text(self, operation):
        status = operation.get("status")

        if status == "keep":
            return "KEEP"

        if status == "rename":
            return "RENAME"

        if status == "review":
            return "REVIEW"

        if status == "problem":
            return "PROBLEM"

        return str(status or "REVIEW").upper()

    def status_style(self, operation):
        status = operation.get("status")

        if status == "keep":
            return (
                "background:#E9DDF7;"
                "color:#4C3566;"
            )

        if status == "rename":
            return (
                "background:#E7D1FA;"
                "color:#5E2390;"
            )

        if status == "review":
            return (
                "background:#F0DDFB;"
                "color:#67258C;"
            )

        if status == "problem":
            return (
                "background:#F9DCEB;"
                "color:#8A174B;"
            )

        return (
            "background:#F0DDFB;"
            "color:#67258C;"
        )

    def safe_filename(self, name):
        name = str(name or "").strip()

        for char in '/:*?"<>|':
            name = name.replace(char, "-")

        name = name.rstrip(". ")

        return name or "Untitled"

    def artwork_for_file(self, file_path):
        try:
            from mutagen import File

            audio = File(str(file_path))

            if audio is None:
                return None

            pictures = getattr(audio, "pictures", None)

            if pictures:
                return pictures[0].data

            if hasattr(audio, "tags") and audio.tags:
                covr = audio.tags.get("covr")

                if covr:
                    return bytes(covr[0])

                apic = audio.tags.getall("APIC")

                if apic:
                    return apic[0].data

        except Exception:
            pass

        return None

    def make_artwork(self, file_path):
        label = QLabel()

        label.setObjectName("ReviewArtwork")
        label.setFixedSize(92, 92)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label.setStyleSheet("""
            QLabel#ReviewArtwork {
                background: #EEE6FA;
                border: 1px solid #D8C9ED;
                border-radius: 12px;
            }
        """)

        data = self.artwork_for_file(file_path)

        if data:
            pixmap = QPixmap()

            if pixmap.loadFromData(data):
                label.setPixmap(
                    pixmap.scaled(
                        92,
                        92,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

                return label

        label.setText("♪")
        label.setFont(QFont("Arial", 30))

        return label

    def metadata_html(self, operation):
        metadata = operation.get("metadata", {})

        artist = self.metadata_value(metadata, "artist")
        album_artist = self.metadata_value(
            metadata,
            "album_artist",
        )
        album = self.metadata_value(metadata, "album")
        title = self.metadata_value(metadata, "title")

        values = [
            ("Artist", artist),
            ("Album Artist", album_artist),
            ("Album", album),
            ("Title", title),
        ]

        palette = self.palette()

        text_color = palette.color(
            palette.ColorRole.Text
        ).name()

        secondary_color = palette.color(
            palette.ColorRole.PlaceholderText
        ).name()

        parts = []

        for label, value in values:
            value = value or "Missing"

            parts.append(
                f"""
                <div style="margin-bottom:4px;">
                    <span style="color:{secondary_color};">
                        {label}:
                    </span>
                    <span style="color:{text_color}; font-weight:600;">
                        {value}
                    </span>
                </div>
                """
            )

        return "".join(parts)

    def destination_text(self, operation):
        target = Path(operation.get("target"))

        return str(target)

    def is_changed(self, operation):
        source = Path(operation.get("source"))
        target = Path(operation.get("target"))

        try:
            return source.resolve() != target.resolve()
        except Exception:
            return source != target

    def selected_operations(self):
        return [
            operation
            for operation in self.operations
            if self.operation_key(operation)
            in self.selected_sources
        ]

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------

    def build_ui(self):
        root = QVBoxLayout(self)

        root.setContentsMargins(28, 26, 28, 24)
        root.setSpacing(16)

        # Header
        header = QHBoxLayout()
        header.setSpacing(12)

        title = QLabel("Review Changes")
        title.setObjectName("PageTitle")

        subtitle = QLabel(
            "Review Fang's proposed organization before applying anything."
        )
        subtitle.setObjectName("PageSubtitle")

        title_column = QVBoxLayout()
        title_column.setSpacing(3)

        title_column.addWidget(title)
        title_column.addWidget(subtitle)

        header.addLayout(title_column)
        header.addStretch()

        self.count_badge = QLabel("0 FILES")
        self.count_badge.setObjectName("ReviewCountBadge")
        self.count_badge.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.count_badge.setMinimumWidth(82)

        header.addWidget(self.count_badge)

        root.addLayout(header)

        # Search / sort / grouping
        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.search_box = QLineEdit()

        self.search_box.setPlaceholderText(
            "Search artist, album, title, or filename..."
        )

        self.search_box.setClearButtonEnabled(True)
        self.search_box.setMinimumHeight(38)

        self.sort_combo = QComboBox()

        self.sort_combo.addItems([
            "Artist",
            "Album",
            "Title",
            "File Name",
            "Status",
        ])

        self.sort_combo.setMinimumHeight(38)

        self.group_combo = QComboBox()

        self.group_combo.addItems([
            "No Grouping",
            "Artist",
            "Album",
            "Artist + Album",
        ])

        self.group_combo.setMinimumHeight(38)

        controls.addWidget(self.search_box, 3)
        controls.addWidget(self.sort_combo, 1)
        controls.addWidget(self.group_combo, 1)

        root.addLayout(controls)

        # Selection controls
        selection_bar = QHBoxLayout()
        selection_bar.setSpacing(8)

        self.select_all_button = QPushButton("Select All")
        self.deselect_all_button = QPushButton("Deselect All")
        self.rename_button = QPushButton("Rename Selected")
        self.keep_button = QPushButton("Keep Selected")

        for button in (
            self.select_all_button,
            self.deselect_all_button,
            self.rename_button,
            self.keep_button,
        ):
            button.setMinimumHeight(34)

        selection_bar.addWidget(self.select_all_button)
        selection_bar.addWidget(self.deselect_all_button)
        selection_bar.addStretch()
        selection_bar.addWidget(self.rename_button)
        selection_bar.addWidget(self.keep_button)

        root.addLayout(selection_bar)

        # Scroll area
        self.scroll_area = QScrollArea()

        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(
            QFrame.Shape.NoFrame
        )
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.list_widget = QWidget()

        self.list_layout = QVBoxLayout(
            self.list_widget
        )

        self.list_layout.setContentsMargins(
            2,
            2,
            8,
            2,
        )

        self.list_layout.setSpacing(10)

        self.scroll_area.setWidget(
            self.list_widget
        )

        root.addWidget(
            self.scroll_area,
            1,
        )

        # Bottom action bar
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        self.summary = QLabel(
            "No files to review."
        )

        self.summary.setObjectName(
            "ReviewSummary"
        )

        self.apply_button = QPushButton(
            "Apply Selected Changes"
        )

        self.apply_button.setObjectName(
            "PrimaryButton"
        )

        self.apply_button.setMinimumHeight(42)
        self.apply_button.setMinimumWidth(210)

        bottom.addWidget(self.summary)
        bottom.addStretch()
        bottom.addWidget(self.apply_button)

        root.addLayout(bottom)

        # Signals
        self.search_box.textChanged.connect(
            self.refresh_list
        )

        self.sort_combo.currentTextChanged.connect(
            self.refresh_list
        )

        self.group_combo.currentTextChanged.connect(
            self.refresh_list
        )

        self.select_all_button.clicked.connect(
            self.select_all
        )

        self.deselect_all_button.clicked.connect(
            self.deselect_all
        )

        self.rename_button.clicked.connect(
            self.rename_selected
        )

        self.keep_button.clicked.connect(
            self.keep_selected
        )

        self.apply_button.clicked.connect(
            self.apply_selected
        )

    # --------------------------------------------------------
    # Loading / filtering
    # --------------------------------------------------------

    def load_operations(
        self,
        operations,
        reset_selection=True,
    ):
        self.operations = list(operations)

        if reset_selection:
            self.selected_sources = {
                self.operation_key(operation)
                for operation in self.operations
            }

        self.refresh_list()

    def filtered_items(self):
        query = (
            self.search_box.text()
            .strip()
            .lower()
        )

        operations = []

        for operation in self.operations:
            if not query:
                operations.append(operation)
                continue

            metadata = operation.get(
                "metadata",
                {},
            )

            searchable = [
                self.metadata_value(
                    metadata,
                    "artist",
                ),
                self.metadata_value(
                    metadata,
                    "album_artist",
                ),
                self.metadata_value(
                    metadata,
                    "album",
                ),
                self.metadata_value(
                    metadata,
                    "title",
                ),
                Path(
                    operation.get(
                        "source",
                        "",
                    )
                ).name,
                Path(
                    operation.get(
                        "target",
                        "",
                    )
                ).name,
            ]

            searchable_text = " ".join(
                value.lower()
                for value in searchable
                if value
            )

            if query in searchable_text:
                operations.append(operation)

        sort_mode = self.sort_combo.currentText()

        if sort_mode == "Artist":
            operations.sort(
                key=lambda op:
                self.display_artist(op).lower()
            )

        elif sort_mode == "Album":
            operations.sort(
                key=lambda op:
                self.display_album(op).lower()
            )

        elif sort_mode == "Title":
            operations.sort(
                key=lambda op:
                self.display_title(op).lower()
            )

        elif sort_mode == "File Name":
            operations.sort(
                key=lambda op:
                Path(
                    op.get(
                        "source",
                        "",
                    )
                ).name.lower()
            )

        elif sort_mode == "Status":
            operations.sort(
                key=lambda op:
                self.status_text(op).lower()
            )

        return operations

    # --------------------------------------------------------
    # Card
    # --------------------------------------------------------

    def make_card(self, operation):
        source = Path(
            operation.get("source")
        )

        target = Path(
            operation.get("target")
        )

        card = QFrame()

        card.setObjectName(
            "ReviewRow"
        )

        card.setFrameShape(
            QFrame.Shape.StyledPanel
        )

        outer = QHBoxLayout(card)

        outer.setContentsMargins(
            14,
            14,
            14,
            14,
        )

        outer.setSpacing(14)

        checkbox = QCheckBox()

        checkbox.setChecked(
            self.operation_key(operation)
            in self.selected_sources
        )

        checkbox.setToolTip(
            "Select this operation"
        )

        def checkbox_changed(state):
            key = self.operation_key(
                operation
            )

            if (
                state
                == Qt.CheckState.Checked.value
            ):
                self.selected_sources.add(
                    key
                )
            else:
                self.selected_sources.discard(
                    key
                )

            self.update_summary()

        checkbox.stateChanged.connect(
            checkbox_changed
        )

        outer.addWidget(
            checkbox,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        artwork = self.make_artwork(
            source
        )

        outer.addWidget(
            artwork,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        middle = QVBoxLayout()
        middle.setSpacing(7)

        # Title and status
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        title_label = QLabel(
            self.display_title(
                operation
            )
        )

        title_label.setObjectName(
            "ReviewTitle"
        )

        title_label.setWordWrap(True)

        status = QLabel(
            self.status_text(
                operation
            )
        )

        status.setStyleSheet(
            "QLabel {"
            "padding:4px 9px;"
            "border-radius:9px;"
            "font-size:10px;"
            "font-weight:700;"
            + self.status_style(
                operation
            )
            + "}"
        )

        status.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        title_row.addWidget(
            title_label,
            1,
        )

        title_row.addWidget(
            status,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        middle.addLayout(
            title_row
        )

        # Artist / album
        artist_album = QLabel(
            f"{self.display_artist(operation)}"
            f"  •  "
            f"{self.display_album(operation)}"
        )

        artist_album.setObjectName(
            "ReviewArtistAlbum"
        )

        artist_album.setWordWrap(True)

        middle.addWidget(
            artist_album
        )

        # Clean destination section
        location_frame = QFrame()

        location_frame.setObjectName(
            "ReviewLocation"
        )

        location_layout = QVBoxLayout(
            location_frame
        )

        location_layout.setContentsMargins(
            11,
            9,
            11,
            9,
        )

        location_layout.setSpacing(4)

        destination_label = QLabel(
            "ORGANIZE TO"
        )

        destination_label.setObjectName(
            "ReviewSectionLabel"
        )

        location_layout.addWidget(
            destination_label
        )

        destination = QLabel(
            str(target)
        )

        destination.setObjectName(
            "ReviewTarget"
        )

        destination.setWordWrap(True)

        location_layout.addWidget(
            destination
        )

        if source.name != target.name:
            original = QLabel(
                f"Original filename: {source.name}"
            )

            original.setObjectName(
                "ReviewOriginal"
            )

            original.setWordWrap(True)

            location_layout.addWidget(
                original
            )

        middle.addWidget(
            location_frame
        )

        # Metadata
        metadata_frame = QFrame()

        metadata_frame.setObjectName(
            "ReviewMetadata"
        )

        metadata_layout = QVBoxLayout(
            metadata_frame
        )

        metadata_layout.setContentsMargins(
            11,
            9,
            11,
            9,
        )

        metadata_layout.setSpacing(3)

        metadata_header = QLabel(
            "CURRENT METADATA"
        )

        metadata_header.setObjectName(
            "ReviewSectionLabel"
        )

        metadata_layout.addWidget(
            metadata_header
        )

        metadata_label = QLabel()

        metadata_label.setText(
            self.metadata_html(
                operation
            )
        )

        metadata_label.setTextFormat(
            Qt.TextFormat.RichText
        )

        metadata_label.setWordWrap(True)

        metadata_layout.addWidget(
            metadata_label
        )

        metadata_note = QLabel(
            "Used for organization only. "
            "Fang does not change the embedded tags."
        )

        metadata_note.setObjectName(
            "ReviewMetadataNote"
        )

        metadata_note.setWordWrap(True)

        metadata_layout.addWidget(
            metadata_note
        )

        middle.addWidget(
            metadata_frame
        )

        reason = operation.get(
            "reason"
        )

        if reason:
            reason_label = QLabel(
                f"Why: {reason}"
            )

            reason_label.setObjectName(
                "ReviewReason"
            )

            reason_label.setWordWrap(True)

            middle.addWidget(
                reason_label
            )

        outer.addLayout(
            middle,
            1,
        )

        skip_button = QPushButton(
            "Skip"
        )

        skip_button.setObjectName(
            "ReviewSkipButton"
        )

        skip_button.setFixedWidth(
            58
        )

        skip_button.setToolTip(
            "Remove this file from the review list without changing it."
        )

        skip_button.clicked.connect(
            lambda:
            self.skip_operation(
                operation
            )
        )

        outer.addWidget(
            skip_button,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        return card

    def make_group_header(self, text):
        label = QLabel(text)

        label.setObjectName(
            "ReviewGroupHeader"
        )

        return label

    # --------------------------------------------------------
    # Refresh
    # --------------------------------------------------------

    def clear_list(self):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    def refresh_list(self):
        self.clear_list()

        operations = self.filtered_items()

        self.filtered_operations = operations

        if not operations:
            empty = QLabel(
                "No files match your current search or filter."
                if self.operations
                else
                "There are no files waiting for review."
            )

            empty.setObjectName(
                "ReviewEmpty"
            )

            empty.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            empty.setMinimumHeight(
                160
            )

            self.list_layout.addWidget(
                empty
            )

            self.update_summary()

            return

        grouping = (
            self.group_combo.currentText()
        )

        if grouping == "No Grouping":
            for operation in operations:
                self.list_layout.addWidget(
                    self.make_card(
                        operation
                    )
                )

        else:
            groups = {}

            for operation in operations:
                artist = self.display_artist(
                    operation
                )

                album = self.display_album(
                    operation
                )

                if grouping == "Artist":
                    group_name = artist

                elif grouping == "Album":
                    group_name = album

                else:
                    group_name = (
                        f"{artist}  •  {album}"
                    )

                groups.setdefault(
                    group_name,
                    []
                ).append(operation)

            for group_name, group_operations in groups.items():
                self.list_layout.addWidget(
                    self.make_group_header(
                        group_name
                    )
                )

                for operation in group_operations:
                    self.list_layout.addWidget(
                        self.make_card(
                            operation
                        )
                    )

        self.list_layout.addStretch()

        self.update_summary()

    # --------------------------------------------------------
    # Selection
    # --------------------------------------------------------

    def select_all(self):
        for operation in self.filtered_operations:
            self.selected_sources.add(
                self.operation_key(
                    operation
                )
            )

        self.refresh_list()

    def deselect_all(self):
        for operation in self.filtered_operations:
            self.selected_sources.discard(
                self.operation_key(
                    operation
                )
            )

        self.refresh_list()

    # --------------------------------------------------------
    # Review actions
    # --------------------------------------------------------

    def rename_selected(self):
        selected = self.selected_operations()

        if not selected:
            QMessageBox.information(
                self,
                "Nothing Selected",
                "Select at least one file first.",
            )
            return

        changed = 0

        for operation in selected:
            title = self.display_title(
                operation
            )

            source = Path(
                operation.get("source")
            )

            target = Path(
                operation.get("target")
            )

            safe_title = self.safe_filename(
                title
            )

            new_target = (
                target.parent
                / (
                    safe_title
                    + source.suffix
                )
            )

            operation["target"] = new_target
            operation["action"] = "rename"
            operation["status"] = "rename"
            operation["reason"] = (
                "The filename was set to the track title."
            )

            changed += 1

        self.refresh_list()

        QMessageBox.information(
            self,
            "Rename Updated",
            f"{changed} selected file(s) now use "
            "the track title as the proposed filename.",
        )

    def keep_selected(self):
        selected = self.selected_operations()

        if not selected:
            QMessageBox.information(
                self,
                "Nothing Selected",
                "Select at least one file first.",
            )
            return

        for operation in selected:
            source = Path(
                operation.get("source")
            )

            operation["target"] = source
            operation["action"] = "keep"
            operation["status"] = "keep"
            operation["reason"] = (
                "You chose to keep this file where it is."
            )

        self.refresh_list()

    def skip_operation(self, operation):
        key = self.operation_key(
            operation
        )

        self.operations = [
            item
            for item in self.operations
            if self.operation_key(item)
            != key
        ]

        self.selected_sources.discard(
            key
        )

        self.refresh_list()

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    def update_summary(self):
        total = len(
            self.operations
        )

        selected = self.selected_operations()

        selected_changes = sum(
            1
            for operation in selected
            if self.is_changed(
                operation
            )
            and operation.get(
                "status"
            ) != "keep"
        )

        selected_actionable = sum(
            1
            for operation in selected
            if operation.get(
                "status"
            ) != "keep"
            and self.is_changed(
                operation
            )
        )

        attention = sum(
            1
            for operation in self.operations
            if operation.get(
                "status"
            ) in (
                "review",
                "problem",
            )
        )

        if total == 0:
            self.count_badge.setText(
                "0 FILES"
            )

            self.summary.setText(
                "No files to review."
            )

            self.apply_button.setEnabled(
                False
            )

            return

        self.count_badge.setText(
            f"{total} FILE"
            if total == 1
            else f"{total} FILES"
        )

        self.summary.setText(
            f"{len(selected)} selected  •  "
            f"{selected_changes} changes selected  •  "
            f"{attention} need attention"
        )

        self.apply_button.setEnabled(
            selected_actionable > 0
        )

    # --------------------------------------------------------
    # Apply
    # --------------------------------------------------------

    def apply_selected(self):
        selected = self.selected_operations()

        selected_operations = [
            operation
            for operation in selected
            if operation.get(
                "status"
            ) != "keep"
            and self.is_changed(
                operation
            )
        ]

        if not selected_operations:
            QMessageBox.information(
                self,
                "Nothing to Apply",
                "There are no selected changes to apply.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Apply Changes?",
            f"Fang is ready to apply "
            f"{len(selected_operations)} file operation(s).\n\n"
            "Files that are not selected will be untouched.",
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            results = apply_operations(
                selected_operations
            )

            successful_results = [
                result
                for result in results
                if result.get(
                    "success"
                )
            ]

            failed_results = [
                result
                for result in results
                if not result.get(
                    "success"
                )
            ]

            successful_keys = {
                self.operation_key(
                    result
                )
                for result in successful_results
            }

            self.operations = [
                operation
                for operation in self.operations
                if self.operation_key(
                    operation
                )
                not in successful_keys
            ]

            self.selected_sources.difference_update(
                successful_keys
            )

            if failed_results:
                error_lines = []

                for result in failed_results[:5]:
                    source = Path(
                        result.get(
                            "source"
                        )
                    ).name

                    error = (
                        result.get(
                            "error"
                        )
                        or
                        "Unknown error"
                    )

                    error_lines.append(
                        f"• {source}: {error}"
                    )

                details = "\n".join(
                    error_lines
                )

                if len(
                    failed_results
                ) > 5:
                    details += (
                        f"\n• ...and "
                        f"{len(failed_results) - 5} more"
                    )

                QMessageBox.warning(
                    self,
                    "Changes Partially Applied",
                    f"{len(successful_results)} operation(s) "
                    f"succeeded and "
                    f"{len(failed_results)} failed.\n\n"
                    "The failed files were kept in Review so "
                    "you can try again.\n\n"
                    f"{details}",
                )

            else:
                QMessageBox.information(
                    self,
                    "Changes Applied",
                    f"Fang successfully applied "
                    f"{len(successful_results)} "
                    f"operation(s).",
                )

            self.refresh_list()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Apply Failed",
                str(exc),
            )

# ------------------------------------------------------------
# Main window
# ------------------------------------------------------------

class FangWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.settings = load_settings()
        self.last_system_theme = None

        self.setWindowTitle("Fang")
        self.resize(1100, 760)
        self.setMinimumSize(900, 650)

        self.build_ui()
        self.update_theme()

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(
            self.check_system_theme
        )
        self.theme_timer.start(1000)

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            0, 0, 0, 0
        )
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("Header")

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(
            24, 18, 24, 18
        )
        header_layout.setSpacing(14)

        header_layout.addWidget(
            ScorpiusLogo()
        )

        title_layout = QVBoxLayout()
        title_layout.setSpacing(0)

        fang_label = QLabel("Fang")
        fang_label.setObjectName(
            "AppTitle"
        )

        subtitle = QLabel(
            "Music Organizer"
        )
        subtitle.setObjectName(
            "AppSubtitle"
        )

        title_layout.addWidget(
            fang_label
        )
        title_layout.addWidget(
            subtitle
        )

        header_layout.addLayout(
            title_layout
        )

        header_layout.addStretch()

        root.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.organize_page = OrganizePage(
            self
        )

        self.review_page = ReviewPage(
            self
        )

        self.settings_page = SettingsPage(
            self
        )

        self.tabs.addTab(
            self.organize_page,
            "Organize"
        )

        self.tabs.addTab(
            self.review_page,
            "Review"
        )

        self.tabs.addTab(
            self.settings_page,
            "Settings"
        )

        root.addWidget(
            self.tabs,
            1
        )

    def check_system_theme(self):
        if self.settings.get(
            "appearance"
        ) != "system":
            return

        theme = get_system_theme()

        if theme != self.last_system_theme:
            self.last_system_theme = theme
            self.update_theme()

    def update_theme(self):
        appearance = self.settings.get(
            "appearance",
            "system"
        )

        if appearance == "system":
            theme = get_system_theme()
        else:
            theme = appearance

        self.last_system_theme = theme

        if theme == "dark":
            self.apply_dark_style()
        else:
            self.apply_light_style()

    def apply_light_style(self):
        self.setStyleSheet("""
            QWidget {
                background: #F5F2F8;
                color: #29252F;
                font-family: "Helvetica Neue";
            }

            QFrame#Header {
                background: #FFFFFF;
                border-bottom: 1px solid #E4DFEA;
            }

            QFrame#Card {
                background: #FFFFFF;
                border: 1px solid #E4DFEA;
                border-radius: 14px;
            }

            QFrame#ReviewRow {
                background: #FFFFFF;
                border: 1px solid #E4DFEA;
                border-radius: 10px;
            }

            QLabel#AppTitle {
                font-size: 22px;
                font-weight: 700;
                color: #28232E;
            }

            QLabel#AppSubtitle {
                font-size: 12px;
                color: #766D7F;
            }

            QLabel#PageTitle {
                font-size: 28px;
                font-weight: 700;
                color: #28232E;
            }

            QLabel#PageSubtitle {
                font-size: 14px;
                color: #766D7F;
            }

            QLabel#SectionTitle {
                font-size: 16px;
                font-weight: 700;
                color: #38313F;
            }

            QLabel#StatusText {
                color: #766D7F;
            }

            QLabel#ReviewSource {
                font-weight: 600;
                color: #342D3A;
            }

            QLabel#ReviewTarget {
                color: #645B6C;
            }

            QLabel#ReviewReason {
                font-size: 11px;
                color: #8A8190;
            }

            QLabel#ReviewStatus {
                font-size: 10px;
                font-weight: 700;
                color: #8063A5;
            }

            QLabel#Badge {
                background: #EEE7F8;
                color: #7657A0;
                border-radius: 9px;
                padding: 7px 12px;
                font-size: 10px;
                font-weight: 700;
            }

            QTabWidget::pane {
                border: none;
            }

            QTabBar::tab {
                padding: 12px 20px;
                color: #766D7F;
                background: transparent;
            }

            QTabBar::tab:selected {
                color: #7657A0;
                font-weight: 700;
                border-bottom: 2px solid #8B6FB8;
            }

            QPushButton {
                background: #ECE7F1;
                color: #332C3A;
                border: 1px solid #DDD5E4;
                border-radius: 9px;
                padding: 9px 15px;
                font-weight: 600;
            }

            QPushButton:hover {
                background: #E3DCEA;
            }

            QPushButton:disabled {
                color: #AAA3AF;
                background: #F0EDF2;
            }

            QPushButton#PrimaryButton {
                background: #8062A5;
                color: white;
                border: none;
            }

            QPushButton#PrimaryButton:hover {
                background: #715495;
            }

            QLineEdit {
                background: #FFFFFF;
                border: 1px solid #D8D0DF;
                border-radius: 8px;
                padding: 9px;
                color: #29252F;
            }

            QLineEdit:focus {
                border: 1px solid #8B6FB8;
            }

            QRadioButton,
            QCheckBox {
                spacing: 8px;
            }

            QScrollArea {
                background: transparent;
                border: none;
            }

            QScrollArea > QWidget > QWidget {
                background: transparent;
            }

            QAbstractScrollArea {
                background: transparent;
                border: none;
            }

            QAbstractScrollArea > QWidget {
                background: transparent;
            }

            QRadioButton,
            QCheckBox,
            QLabel {
                background: transparent;
            }
        """)

    def apply_dark_style(self):
        self.setStyleSheet("""
            QWidget {
                background: #17141B;
                color: #F1EDF4;
                font-family: "Helvetica Neue";
            }

            QFrame#Header {
                background: #201C25;
                border-bottom: 1px solid #332D38;
            }

            QFrame#Card {
                background: #211D26;
                border: 1px solid #342E39;
                border-radius: 14px;
            }

            QFrame#ReviewRow {
                background: #211D26;
                border: 1px solid #342E39;
                border-radius: 10px;
            }

            QLabel#AppTitle {
                font-size: 22px;
                font-weight: 700;
                color: #F4EFF7;
            }

            QLabel#AppSubtitle {
                font-size: 12px;
                color: #AAA0B1;
            }

            QLabel#PageTitle {
                font-size: 28px;
                font-weight: 700;
                color: #F4EFF7;
            }

            QLabel#PageSubtitle {
                font-size: 14px;
                color: #AAA0B1;
            }

            QLabel#SectionTitle {
                font-size: 16px;
                font-weight: 700;
                color: #E9E1ED;
            }

            QLabel#StatusText {
                color: #AAA0B1;
            }

            QLabel#ReviewSource {
                font-weight: 600;
                color: #F0EAF3;
            }

            QLabel#ReviewTarget {
                color: #C0B6C5;
            }

            QLabel#ReviewReason {
                font-size: 11px;
                color: #958A9A;
            }

            QLabel#ReviewStatus {
                font-size: 10px;
                font-weight: 700;
                color: #B79BD3;
            }

            QLabel#Badge {
                background: #382D47;
                color: #C8AEE4;
                border-radius: 9px;
                padding: 7px 12px;
                font-size: 10px;
                font-weight: 700;
            }

            QTabWidget::pane {
                border: none;
            }

            QTabBar::tab {
                padding: 12px 20px;
                color: #A89EAE;
                background: transparent;
            }

            QTabBar::tab:selected {
                color: #C5A8DF;
                font-weight: 700;
                border-bottom: 2px solid #A681C8;
            }

            QPushButton {
                background: #302A35;
                color: #EDE6F0;
                border: 1px solid #443A49;
                border-radius: 9px;
                padding: 9px 15px;
                font-weight: 600;
            }

            QPushButton:hover {
                background: #39313F;
            }

            QPushButton:disabled {
                color: #766E7B;
                background: #29242D;
            }

            QPushButton#PrimaryButton {
                background: #8062A5;
                color: white;
                border: none;
            }

            QPushButton#PrimaryButton:hover {
                background: #9272B9;
            }

            QLineEdit {
                background: #18151C;
                border: 1px solid #443A49;
                border-radius: 8px;
                padding: 9px;
                color: #F1EDF4;
            }

            QLineEdit:focus {
                border: 1px solid #A681C8;
            }

            QRadioButton,
            QCheckBox {
                spacing: 8px;
            }

            QScrollArea {
                background: transparent;
                border: none;
            }

            QScrollArea > QWidget > QWidget {
                background: transparent;
            }

            QAbstractScrollArea {
                background: transparent;
                border: none;
            }

            QAbstractScrollArea > QWidget {
                background: transparent;
            }

            QRadioButton,
            QCheckBox,
            QLabel {
                background: transparent;
            }
        """)

    def closeEvent(self, event):
        save_settings(
            self.settings
        )

        event.accept()


def main():
    app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    app.setFont(
        QFont("Helvetica Neue", 13)
    )

    window = FangWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
