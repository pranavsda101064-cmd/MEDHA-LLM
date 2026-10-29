"""Qt Studio: generate, inspect, evaluate, and play a lesson offline."""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import replace
from pathlib import Path
from typing import cast

from PySide6.QtCore import Qt, QThread, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import config
from medha.core.schema import LanguageCode
from medha.library.models import LibraryFilter, LibraryLesson
from medha.library.repository import LessonLibrary
from medha.render.playback import ChunkedPlayback, LessonPlayback
from medha.render.timeline import CheckpointTiming
from medha.render.widget import BoardWidget

from .service import StudioOptions, StudioResult
from .workers import GenerateWorker, OpenWorker, VoiceTestWorker

logger = logging.getLogger(__name__)

SUBJECTS = ("math", "physics", "chemistry", "electronics", "ai", "general")
DIFFICULTIES = ("beginner", "intermediate", "advanced")
LANGUAGES = tuple((name, code) for code, name in config.LANGUAGE_NAMES.items())

STYLE = """
QMainWindow, QWidget { background: #0b1110; color: #e7efe9; }
QLabel#brand { font-size: 20px; font-weight: 700; letter-spacing: 2px; }
QLabel#subtitle { color: #7f968c; font-size: 11px; }
QLabel#meta { color: #a8bdb3; }
QLabel#quality { color: #a8bdb3; }
QLabel#hint { color: #e4c07a; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QListWidget, QPlainTextEdit {
    background: #111b18; border: 1px solid #263a33; border-radius: 6px;
    padding: 6px; selection-background-color: #2f6f5e;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #4f9d84;
}
QListWidget { min-height: 64px; }
QPushButton {
    background: #182622; border: 1px solid #2d493f; border-radius: 6px;
    padding: 7px 11px; color: #dfece5;
}
QPushButton:hover { background: #21362f; border-color: #4f9d84; }
QPushButton:disabled { color: #60736b; border-color: #1b2924; }
QPushButton#primary { background: #2f6f5e; border-color: #4f9d84; font-weight: 700; }
QPushButton#primary:hover { background: #3b8772; }
QSlider::groove:horizontal { background: #1a2924; height: 5px; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #71c8aa; width: 13px; margin: -5px 0; border-radius: 6px;
}
QFrame#panel { background: #0e1714; border: 1px solid #1d2d27; border-radius: 9px; }
QDialog { background: #0e1714; }
QTabWidget::pane { border: 0; }
QTabBar::tab {
    background: #111b18; border: 1px solid #263a33; padding: 7px 13px;
    margin-right: 3px; border-radius: 6px;
}
QTabBar::tab:selected { background: #2f6f5e; border-color: #4f9d84; }
"""


def _normalize_answer(value: str) -> str:
    cleaned = re.sub(r"[^\w\s+\-*/^=.]", " ", value.casefold())
    return " ".join(cleaned.split())


def _friendly_error(message: str) -> str:
    lowered = message.lower()
    if any(
        marker in lowered
        for marker in (
            "out of memory",
            "bad allocation",
            "paging file",
            "tokenizers.pyd",
            "0xc0000409",
        )
    ):
        return (
            "Medha ran out of memory while loading the local models.\n\n"
            "Try closing other apps, unchecking Rerank, removing the material "
            "from the Material list if it is already indexed, or enabling the "
            "Windows pagefile. Then restart Medha."
        )
    return message


def _answer_matches(answer: str, expected: str) -> bool:
    given = _normalize_answer(answer)
    if not given:
        return False
    variants = re.split(r"[;,.]|\bbecause\b", expected.casefold())
    for raw in [expected.casefold(), *variants]:
        wanted = _normalize_answer(raw)
        if not wanted:
            continue
        if wanted == given:
            return True
        if len(given) >= 3 and (given in wanted or wanted in given):
            return True
        wanted_tokens = set(wanted.split())
        given_tokens = set(given.split())
        if len(wanted_tokens) > 2:
            overlap = len(wanted_tokens & given_tokens) / len(wanted_tokens)
            if overlap >= 0.7:
                return True
    return False


class CheckpointDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        library: LessonLibrary | None,
        lesson_id: str,
        checkpoint: CheckpointTiming,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Checkpoint")
        self.resize(590, 390)
        self.library = library
        self.lesson_id = lesson_id
        self.checkpoint = checkpoint
        self._hint_index = 0
        self._revealed = False
        self.submissions = 0
        self.correct_submissions = 0

        layout = QVBoxLayout(self)
        label = QLabel(f"CHECKPOINT  ·  {checkpoint.step_id}")
        label.setObjectName("subtitle")
        layout.addWidget(label)
        question = QLabel(checkpoint.question)
        question.setWordWrap(True)
        question.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(question)
        self.answer = QLineEdit()
        self.answer.setPlaceholderText("Type your answer")
        layout.addWidget(self.answer)
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        self.hint = QLabel("")
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        layout.addStretch(1)

        buttons = QHBoxLayout()
        self.hint_button = QPushButton("Hint")
        self.reveal_button = QPushButton("Show answer")
        self.submit_button = QPushButton("Submit")
        self.submit_button.setObjectName("primary")
        self.continue_button = QPushButton("Continue")
        buttons.addWidget(self.hint_button)
        buttons.addWidget(self.reveal_button)
        buttons.addStretch(1)
        buttons.addWidget(self.submit_button)
        buttons.addWidget(self.continue_button)
        layout.addLayout(buttons)

        self.hint_button.clicked.connect(self._show_hint)
        self.reveal_button.clicked.connect(self._show_answer)
        self.submit_button.clicked.connect(self._submit)
        self.continue_button.clicked.connect(self.accept)
        self.answer.returnPressed.connect(self._submit)
        self.answer.setFocus()

    def _show_hint(self) -> None:
        if not self.checkpoint.hints:
            self.hint.setText("No hint for this checkpoint. Trust the lesson.")
            return
        index = min(self._hint_index, len(self.checkpoint.hints) - 1)
        self.hint.setText(f"Hint {index + 1}: {self.checkpoint.hints[index]}")
        self._hint_index = min(self._hint_index + 1, len(self.checkpoint.hints))

    def _show_answer(self) -> None:
        self._revealed = True
        self.result_label.setText(f"Expected: {self.checkpoint.expected}")

    def _submit(self) -> None:
        answer = self.answer.text().strip()
        if not answer:
            self.result_label.setText("Write an answer first.")
            return
        correct = _answer_matches(answer, self.checkpoint.expected)
        self.submissions += 1
        if correct:
            self.correct_submissions += 1
            self.result_label.setText("Correct. Keep going.")
            self.result_label.setStyleSheet("color: #71c8aa;")
        else:
            self.result_label.setText("Not quite. Try again, use a hint, or show the answer.")
            self.result_label.setStyleSheet("color: #e4c07a;")
        if self.library is not None:
            try:
                self.library.record_checkpoint(
                    self.lesson_id,
                    self.checkpoint.step_id,
                    self.checkpoint.question,
                    answer,
                    correct=correct,
                )
            except Exception as exc:
                self.hint.setText(f"Could not save this attempt: {exc}")
        if self._revealed and not correct:
            self.hint.setText(f"Expected: {self.checkpoint.expected}")


class StudioWindow(QMainWindow):
    def __init__(self, *, tts: bool = True) -> None:
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} Studio")
        self.resize(1380, 860)
        self.setMinimumSize(1020, 680)
        self.setStyleSheet(STYLE)
        self._library_error: str | None = None
        self._settings: dict[str, object] = {}
        self.library: LessonLibrary | None = None
        try:
            self.library = LessonLibrary()
            self._settings = self.library.get_settings()
        except Exception as exc:
            self._library_error = str(exc)
        saved_tts = self._settings.get("tts")
        self._tts = bool(saved_tts) if tts and isinstance(saved_tts, bool) else tts
        self._voice = str(self._settings.get("voice", config.KOKORO_VOICE))
        saved_speed = self._settings.get("speed")
        self._speed = (
            float(saved_speed)
            if isinstance(saved_speed, (int, float))
            and not isinstance(saved_speed, bool)
            else config.KOKORO_SPEED
        )
        self._playback: LessonPlayback | ChunkedPlayback | None = None
        self._result: StudioResult | None = None
        self._thread: QThread | None = None
        self._worker: GenerateWorker | OpenWorker | None = None
        self._voice_thread: QThread | None = None
        self._voice_worker: VoiceTestWorker | None = None
        self._closing = False
        self._updating_slider = False
        self._library_lessons: dict[str, LibraryLesson] = {}
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._build_ui()
        self._restore_form()
        self._start_library()
        if self._tts:
            self._warm_tts()

    def _warm_tts(self) -> None:
        def load() -> None:
            try:
                from medha.tts.kokoro import KokoroEngine

                KokoroEngine(voice=self._voice, speed=self._speed).warmup()
            except Exception:
                logger.exception("Kokoro warmup failed; first speech may be slower")

        threading.Thread(target=load, name="kokoro-warmup", daemon=True).start()

    # --- construction -------------------------------------------------
    def _build_ui(self) -> None:
        split = QSplitter(Qt.Orientation.Horizontal, self)
        split.setChildrenCollapsible(False)
        split.addWidget(self._build_panel())
        split.addWidget(self._build_board())
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([410, 970])
        self.setCentralWidget(split)
        self.statusBar().showMessage("Ready. Write a topic, then Generate.")

    def _build_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMinimumWidth(370)
        panel.setMaximumWidth(460)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        brand = QLabel("MEDHA STUDIO")
        brand.setObjectName("brand")
        subtitle = QLabel("offline blackboard lesson director")
        subtitle.setObjectName("subtitle")
        layout.addWidget(brand)
        layout.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_create_tab(), "Create")
        self.tabs.addTab(self._build_library_tab(), "Library")
        self.tabs.addTab(self._build_settings_tab(), "Settings")
        layout.addWidget(self.tabs, 1)
        return panel

    def _build_create_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(2, 10, 2, 2)
        layout.setSpacing(9)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(7)
        self.topic = QLineEdit("Newton's second law")
        self.topic.setPlaceholderText("What should the lesson teach?")
        self.subject = QComboBox()
        self.subject.addItems(SUBJECTS)
        self.subject.setCurrentText("physics")
        self.difficulty = QComboBox()
        self.difficulty.addItems(DIFFICULTIES)
        self.difficulty.setCurrentText("beginner")
        self.language = QComboBox()
        for name, code in LANGUAGES:
            self.language.addItem(name, code)
        self.steps = QSpinBox()
        self.steps.setRange(1, config.LESSON_MAX_STEPS)
        self.steps.setValue(config.LESSON_DEFAULT_STEPS)
        self.audience = QLineEdit(config.LESSON_DEFAULT_AUDIENCE)
        form.addRow("Topic", self.topic)
        form.addRow("Subject", self.subject)
        form.addRow("Level", self.difficulty)
        form.addRow("Language", self.language)
        form.addRow("Steps", self.steps)
        form.addRow("Audience", self.audience)
        layout.addLayout(form)

        rag_row = QHBoxLayout()
        self.use_rag = QCheckBox("Use indexed material")
        self.use_rag.setChecked(True)
        self.use_rerank = QCheckBox("Rerank")
        self.use_rerank.setChecked(True)
        self.use_ocr = QCheckBox("OCR scans")
        rag_row.addWidget(self.use_rag)
        rag_row.addWidget(self.use_rerank)
        rag_row.addWidget(self.use_ocr)
        layout.addLayout(rag_row)

        self.rag_query = QLineEdit()
        self.rag_query.setPlaceholderText("Optional retrieval query (defaults to topic)")
        layout.addWidget(self.rag_query)

        layout.addWidget(QLabel("Material"))
        self.material_list = QListWidget()
        self.material_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(self.material_list)
        material_row = QHBoxLayout()
        self.add_material = QPushButton("Add file")
        self.remove_material = QPushButton("Remove")
        material_row.addWidget(self.add_material)
        material_row.addWidget(self.remove_material)
        layout.addLayout(material_row)

        self.generate_button = QPushButton("Generate lesson")
        self.generate_button.setObjectName("primary")
        layout.addWidget(self.generate_button)
        actions = QHBoxLayout()
        self.open_button = QPushButton("Open")
        self.eval_button = QPushButton("Evaluate")
        self.folder_button = QPushButton("Folder")
        actions.addWidget(self.open_button)
        actions.addWidget(self.eval_button)
        actions.addWidget(self.folder_button)
        layout.addLayout(actions)

        self.meta_label = QLabel("No lesson loaded.")
        self.meta_label.setObjectName("meta")
        self.meta_label.setWordWrap(True)
        layout.addWidget(self.meta_label)
        self.quality_label = QLabel("")
        self.quality_label.setObjectName("quality")
        self.quality_label.setWordWrap(True)
        layout.addWidget(self.quality_label)
        self.narration_label = QLabel("")
        self.narration_label.setObjectName("hint")
        self.narration_label.setWordWrap(True)
        layout.addWidget(self.narration_label)
        self._update_narration_label()
        layout.addStretch(1)

        self.generate_button.clicked.connect(self._generate)
        self.open_button.clicked.connect(self._open)
        self.eval_button.clicked.connect(self._evaluate_dialog)
        self.folder_button.clicked.connect(self._open_folder)
        self.add_material.clicked.connect(self._add_material)
        self.remove_material.clicked.connect(self._remove_material)
        return tab

    def _build_library_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(2, 10, 2, 2)
        layout.setSpacing(9)

        self.library_search = QLineEdit()
        self.library_search.setPlaceholderText("Search titles or lesson IDs")
        layout.addWidget(self.library_search)
        filters = QHBoxLayout()
        self.library_subject = QComboBox()
        self.library_subject.addItem("all subjects", None)
        for subject in SUBJECTS:
            self.library_subject.addItem(subject, subject)
        self.library_language = QComboBox()
        self.library_language.addItem("all languages", None)
        for name, code in LANGUAGES:
            self.library_language.addItem(name, code)
        self.library_favorites = QCheckBox("Favorites only")
        filters.addWidget(self.library_subject, 1)
        filters.addWidget(self.library_language, 1)
        layout.addLayout(filters)
        layout.addWidget(self.library_favorites)

        self.library_list = QListWidget()
        self.library_list.setMinimumHeight(180)
        self.library_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        layout.addWidget(self.library_list, 1)
        self.library_detail = QLabel("Indexed lessons appear here.")
        self.library_detail.setObjectName("meta")
        self.library_detail.setWordWrap(True)
        layout.addWidget(self.library_detail)

        buttons = QHBoxLayout()
        self.library_open = QPushButton("Open")
        self.library_open.setObjectName("primary")
        self.library_favorite_button = QPushButton("Favorite")
        self.library_delete = QPushButton("Delete")
        buttons.addWidget(self.library_open)
        buttons.addWidget(self.library_favorite_button)
        buttons.addWidget(self.library_delete)
        layout.addLayout(buttons)
        scan_row = QHBoxLayout()
        self.library_refresh = QPushButton("Refresh")
        self.library_scan = QPushButton("Scan folder")
        scan_row.addWidget(self.library_refresh)
        scan_row.addWidget(self.library_scan)
        layout.addLayout(scan_row)

        self.library_stats = QLabel("")
        self.library_stats.setObjectName("subtitle")
        self.library_stats.setWordWrap(True)
        layout.addWidget(self.library_stats)

        self.library_search.textChanged.connect(self._refresh_library)
        self.library_subject.currentIndexChanged.connect(self._refresh_library)
        self.library_language.currentIndexChanged.connect(self._refresh_library)
        self.library_favorites.toggled.connect(self._refresh_library)
        self.library_list.itemDoubleClicked.connect(self._library_open_item)
        self.library_list.currentItemChanged.connect(self._library_selection_changed)
        self.library_open.clicked.connect(self._library_open_selected)
        self.library_favorite_button.clicked.connect(self._library_toggle_favorite)
        self.library_delete.clicked.connect(self._library_delete_selected)
        self.library_refresh.clicked.connect(self._refresh_library)
        self.library_scan.clicked.connect(self._library_scan)
        return tab

    def _build_settings_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(2, 10, 2, 2)
        layout.setSpacing(10)

        self.tts_toggle = QCheckBox("Narrate lessons with Kokoro")
        self.tts_toggle.setChecked(self._tts)
        layout.addWidget(self.tts_toggle)
        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        self.voice = QLineEdit(self._voice)
        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.5, 1.5)
        self.speed.setSingleStep(0.05)
        self.speed.setDecimals(2)
        self.speed.setValue(self._speed)
        form.addRow("Kokoro voice", self.voice)
        form.addRow("Speech speed", self.speed)
        layout.addLayout(form)

        settings_row = QHBoxLayout()
        self.save_settings = QPushButton("Save settings")
        self.test_voice = QPushButton("Test voice")
        settings_row.addWidget(self.save_settings, 1)
        settings_row.addWidget(self.test_voice, 1)
        layout.addLayout(settings_row)
        note = QLabel(
            "Stored locally in data/medha.db. Lesson JSON files remain the source of truth."
        )
        note.setObjectName("subtitle")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.database_label = QLabel(f"Library database: {config.DB_PATH}")
        self.database_label.setObjectName("subtitle")
        self.database_label.setWordWrap(True)
        layout.addWidget(self.database_label)
        layout.addStretch(1)

        self.tts_toggle.toggled.connect(self._set_tts)
        self.save_settings.clicked.connect(self._save_settings)
        self.test_voice.clicked.connect(self._test_voice)
        return tab

    def _build_board(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 8)
        layout.setSpacing(6)
        self.board_window = BoardWidget(frame_factory=self._render_board, parent=frame)
        self.board_view = self.board_window
        layout.addWidget(self.board_view, 1)

        transport = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")
        self.stop_button = QPushButton("Stop")
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setMinimumWidth(112)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1)
        self.slider.setEnabled(False)
        transport.addWidget(self.play_button)
        transport.addWidget(self.pause_button)
        transport.addWidget(self.stop_button)
        transport.addWidget(self.slider, 1)
        transport.addWidget(self.time_label)
        layout.addLayout(transport)

        self.play_button.clicked.connect(self._play)
        self.pause_button.clicked.connect(self._pause)
        self.stop_button.clicked.connect(self._stop)
        self.slider.sliderPressed.connect(self._slider_pressed)
        self.slider.sliderReleased.connect(self._slider_released)
        self._set_transport(False)
        return frame

    # --- library ------------------------------------------------------
    def _start_library(self) -> None:
        if self.library is None:
            self.library_list.clear()
            self.library_detail.setText(
                f"Library unavailable: {self._library_error or 'unknown error'}"
            )
            self.library_stats.setText("")
            return
        try:
            report = self.library.index_directory()
            if report.errors:
                self.statusBar().showMessage(
                    f"Library scanned with {len(report.errors)} error(s)", 8000
                )
        except Exception as exc:
            self._library_error = str(exc)
            self.statusBar().showMessage(f"Library scan failed: {exc}", 8000)
        self._refresh_library()

    def _selected_library_id(self) -> str | None:
        item = self.library_list.currentItem()
        if item is None:
            return None
        raw = item.data(Qt.ItemDataRole.UserRole)
        return str(raw) if raw else None

    def _set_library_selection(self, lesson_id: str) -> None:
        for index in range(self.library_list.count()):
            item = self.library_list.item(index)
            if str(item.data(Qt.ItemDataRole.UserRole)) == lesson_id:
                self.library_list.setCurrentRow(index)
                return

    def _refresh_library(self, *_args: object) -> None:
        if self.library is None:
            return
        selected = self._selected_library_id()
        subject = self.library_subject.currentData()
        language = self.library_language.currentData()
        filters = LibraryFilter(
            query=self.library_search.text().strip() or None,
            subject=str(subject) if subject else None,
            language=str(language) if language else None,
            favorite=True if self.library_favorites.isChecked() else None,
            limit=500,
        )
        try:
            lessons = self.library.list_lessons(filters)
            stats = self.library.statistics()
        except Exception as exc:
            self.library_detail.setText(f"Library error: {exc}")
            return
        self._library_lessons = {lesson.lesson_id: lesson for lesson in lessons}
        self.library_list.clear()
        for lesson in lessons:
            star = "★" if lesson.favorite else "·"
            item = QListWidgetItem(
                f"{star} {lesson.title}\n"
                f"{lesson.subject} · {lesson.difficulty} · {lesson.language}"
                f" · {lesson.steps} steps · {lesson.score}/100"
            )
            item.setData(Qt.ItemDataRole.UserRole, lesson.lesson_id)
            item.setToolTip(lesson.path)
            self.library_list.addItem(item)
        if selected is not None:
            self._set_library_selection(selected)
        minutes = stats.total_duration_ms / 60000
        self.library_stats.setText(
            f"{stats.lessons} lesson(s) · {stats.favorites} favorite(s) · "
            f"{minutes:.1f} min · {stats.checkpoint_attempts} checkpoint attempt(s)"
        )
        if not lessons:
            self.library_detail.setText("No lessons match this filter.")
        elif self.library_list.currentItem() is None:
            self.library_list.setCurrentRow(0)
        self._library_selection_changed()

    def _library_selection_changed(self) -> None:
        lesson_id = self._selected_library_id()
        lesson = self._library_lessons.get(lesson_id or "")
        if lesson is None:
            self.library_detail.setText("Select a lesson to open or manage it.")
            return
        try:
            summary = self.library.checkpoint_summary(lesson.lesson_id) if self.library else None
        except Exception:
            summary = None
        detail = (
            f"{lesson.score}/100 · {lesson.language} · "
            f"{lesson.actions} actions · {lesson.path}"
        )
        if summary is not None and summary.attempts:
            detail += (
                f"\nCheckpoints: {summary.correct}/{summary.attempts} correct"
                f" ({summary.accuracy * 100:.0f}%)"
            )
        self.library_detail.setText(detail)

    def _library_open_item(self, item: QListWidgetItem) -> None:
        raw = item.data(Qt.ItemDataRole.UserRole)
        if raw:
            self._open_library_lesson(str(raw))

    def _library_open_selected(self) -> None:
        lesson_id = self._selected_library_id()
        if lesson_id is None:
            QMessageBox.information(self, "No lesson", "Select a lesson first.")
            return
        self._open_library_lesson(lesson_id)

    def _open_library_lesson(self, lesson_id: str) -> None:
        lesson = self._library_lessons.get(lesson_id)
        if lesson is None:
            return
        path = Path(lesson.path)
        if not path.exists():
            QMessageBox.warning(self, "Missing file", f"Lesson file not found:\n{path}")
            return
        self.load_path(path, tts=self._tts)

    def _library_toggle_favorite(self) -> None:
        if self.library is None:
            return
        lesson_id = self._selected_library_id()
        lesson = self._library_lessons.get(lesson_id or "")
        if lesson is None:
            QMessageBox.information(self, "No lesson", "Select a lesson first.")
            return
        try:
            self.library.set_favorite(lesson.lesson_id, not lesson.favorite)
        except Exception as exc:
            QMessageBox.warning(self, "Library", str(exc))
            return
        self._refresh_library()
        self._set_library_selection(lesson.lesson_id)

    def _library_delete_selected(self) -> None:
        if self.library is None:
            return
        lesson_id = self._selected_library_id()
        lesson = self._library_lessons.get(lesson_id or "")
        if lesson is None:
            QMessageBox.information(self, "No lesson", "Select a lesson first.")
            return
        answer = QMessageBox.question(
            self,
            "Delete lesson",
            f"Delete '{lesson.title}' from the library and remove its JSON file?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.library.delete_lesson(lesson.lesson_id, delete_file=True)
        except Exception as exc:
            QMessageBox.warning(self, "Library", str(exc))
            return
        self._refresh_library()

    def _library_scan(self) -> None:
        if self.library is None or self._thread is not None:
            return
        try:
            report = self.library.index_directory()
        except Exception as exc:
            QMessageBox.warning(self, "Library", str(exc))
            return
        self._refresh_library()
        self.statusBar().showMessage(
            f"Library scan: {report.indexed} indexed, {report.skipped} skipped", 8000
        )

    # --- rendering ----------------------------------------------------
    def _render_board(self, board: object, _elapsed: float) -> None:
        from medha.render.scene import Board

        assert isinstance(board, Board)
        if self._playback is not None:
            self._playback.render(board)
            return
        if not board.items:
            board.add_text(
                "Medha",
                at=(0.07, 0.09),
                size=0.115,
                color="chalk",
                width_px=4.2,
            )
            board.add_text(
                "offline blackboard teacher",
                at=(0.072, 0.225),
                size=0.030,
                color="diagram",
                width_px=2.4,
            )
            board.add_polyline([(0.07, 0.205), (0.34, 0.205)], color="math", width_px=2.0)
            board.add_text(
                "Write a topic, then Generate.",
                at=(0.07, 0.36),
                size=0.032,
                color="chalk",
                width_px=2.5,
                max_width=0.55,
            )

    @property
    def playback(self) -> LessonPlayback | ChunkedPlayback | None:
        return self._playback

    def show_result(self, result: StudioResult) -> None:
        self._apply_result(result)

    def _on_partial(self, playback: object) -> None:
        assert isinstance(playback, ChunkedPlayback)
        first = self._playback is not playback
        if first:
            if self._playback is not None:
                self._playback.stop()
            self._playback = playback
            self._result = None
            self._timer.stop()
            self.slider.setRange(0, max(1, playback.duration_ms))
            self.slider.setValue(0)
            self._set_transport(True)
            self.statusBar().showMessage(
                "First step ready. Press Play while the rest prepares."
            )
        self.slider.setRange(0, max(1, playback.duration_ms))
        self._update_time()
        self.board_window.update()

    def seek_ms(self, position_ms: int) -> None:
        if self._playback is None:
            return
        self._playback.seek(position_ms)
        self._update_time()
        self.board_window.update()

    def _apply_result(self, result: StudioResult) -> None:
        same_playback = self._playback is result.playback
        if not same_playback and self._playback is not None:
            self._playback.stop()
        self._result = result
        self._playback = result.playback
        if not same_playback:
            self._timer.stop()
        lesson = result.lesson
        actions = sum(len(step.board) for step in lesson.steps)
        report = result.report
        narration = "narration on" if self._tts else "narration off"
        self.meta_label.setText(
            f"{lesson.title}\n"
            f"{lesson.subject} / {lesson.difficulty} / {lesson.language}"
            f" / {len(lesson.steps)} steps / {actions} actions"
            f" / {result.playback.duration_ms / 1000:.1f}s / {narration}\n"
            f"{result.path if result.path is not None else lesson.lesson_id}"
        )
        self.quality_label.setText(
            f"Quality {report.score}/100"
            f"  ({report.errors} error, {report.warnings} warning)"
        )
        self.quality_label.setToolTip("\n".join(result.warnings))
        self.slider.setRange(0, max(1, result.playback.duration_ms))
        if not same_playback:
            self.slider.setValue(0)
        self.slider.setEnabled(True)
        self._set_transport(True)
        self._update_time()
        self.board_window.update()
        self.statusBar().showMessage(
            f"Ready: {lesson.lesson_id} (quality {report.score}/100, {narration})"
        )

    def _set_transport(self, enabled: bool) -> None:
        self.play_button.setEnabled(enabled)
        self.pause_button.setEnabled(enabled)
        self.stop_button.setEnabled(enabled)

    def _update_time(self) -> None:
        duration = self._playback.duration_ms if self._playback is not None else 0
        position = self._playback.position_ms() if self._playback is not None else 0
        self.time_label.setText(f"{_fmt(position)} / {_fmt(duration)}")
        if not self._updating_slider and self._playback is not None:
            self._updating_slider = True
            self.slider.setValue(position)
            self._updating_slider = False

    # --- playback -----------------------------------------------------
    def _play(self) -> None:
        if self._playback is None:
            return
        self._playback.start()
        self._timer.start()
        self.board_window.update()

    def _pause(self) -> None:
        if self._playback is None:
            return
        self._playback.pause()
        self._timer.stop()
        self._update_time()
        self.board_window.update()

    def _stop(self) -> None:
        if self._playback is None:
            return
        self._playback.stop()
        self._timer.stop()
        self.slider.setValue(0)
        self._update_time()
        self.board_window.update()

    def _tick(self) -> None:
        if self._playback is None:
            return
        checkpoint = self._playback.take_checkpoint()
        if checkpoint is not None:
            self._pause()
            self._run_checkpoint(checkpoint)
            if self._playback is not None and not self._playback.is_finished():
                self._play()
            return
        if self._playback.is_finished():
            self._playback.pause()
            self._timer.stop()
        self._update_time()
        self.board_window.update()

    def _run_checkpoint(self, checkpoint: CheckpointTiming) -> None:
        if self._result is not None:
            lesson_id = self._result.lesson.lesson_id
        elif self._playback is not None:
            lesson_id = self._playback.prepared.lesson.lesson_id
        else:
            lesson_id = ""
        dialog = CheckpointDialog(self, self.library, lesson_id, checkpoint)
        dialog.exec()
        self._refresh_library()
        if dialog.correct_submissions:
            self.statusBar().showMessage(
                f"Checkpoint complete: {dialog.correct_submissions}"
                f"/{dialog.submissions} correct",
                8000,
            )

    def _slider_pressed(self) -> None:
        self._updating_slider = True

    def _slider_released(self) -> None:
        self._updating_slider = False
        if self._playback is not None:
            self._playback.seek(self.slider.value())
            self._update_time()
            self.board_window.update()

    # --- actions ------------------------------------------------------
    def _add_material(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add lesson material",
            str(config.UPLOAD_DIR),
            "Documents (*.pdf *.pptx)",
        )
        for raw in paths:
            path = Path(raw)
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(str(path))
            self.material_list.addItem(item)

    def _remove_material(self) -> None:
        row = self.material_list.currentRow()
        if row >= 0:
            self.material_list.takeItem(row)

    def _materials(self) -> tuple[Path, ...]:
        paths: list[Path] = []
        for index in range(self.material_list.count()):
            item = self.material_list.item(index)
            raw = item.data(Qt.ItemDataRole.UserRole)
            if raw:
                paths.append(Path(str(raw)))
        return tuple(paths)

    def _options(self) -> StudioOptions:
        raw_language = self.language.currentData()
        language = (
            cast(LanguageCode, raw_language)
            if raw_language in config.SUPPORTED_LANGUAGES
            else "en"
        )
        return StudioOptions(
            topic=self.topic.text().strip(),
            subject=self.subject.currentText(),
            difficulty=self.difficulty.currentText(),
            language=language,
            audience=self.audience.text().strip() or config.LESSON_DEFAULT_AUDIENCE,
            steps=self.steps.value(),
            rag_query=self.rag_query.text().strip() or None,
            use_rag=self.use_rag.isChecked(),
            use_rerank=self.use_rerank.isChecked(),
            materials=self._materials(),
            ocr=True if self.use_ocr.isChecked() else None,
            tts=self._tts,
            voice=self.voice.text().strip() or config.KOKORO_VOICE,
            speed=float(self.speed.value()),
        )

    def _generate(self) -> None:
        if self._thread is not None:
            return
        options = self._options()
        if not options.topic:
            QMessageBox.warning(self, "Topic needed", "Enter a lesson topic first.")
            return
        if len(options.topic) < 3:
            QMessageBox.warning(
                self,
                "Topic too short",
                "Use a topic with at least 3 characters.",
            )
            return
        self._stop()
        self._set_busy(True)
        self._start_worker(GenerateWorker(options))

    def _open(self) -> None:
        if self._thread is not None:
            return
        start = config.LESSON_CONTENT_DIR if config.LESSON_CONTENT_DIR.exists() else config.ROOT
        path, _ = QFileDialog.getOpenFileName(
            self, "Open lesson", str(start), "Lessons (*.json)"
        )
        if path:
            self.load_path(Path(path), tts=self._tts)

    def load_path(self, path: Path, *, tts: bool | None = None) -> None:
        if self._thread is not None:
            return
        options = self._options()
        if tts is not None:
            options = replace(options, tts=tts)
        self._stop()
        self._set_busy(True)
        self._start_worker(OpenWorker(path, options))

    def _start_worker(self, worker: GenerateWorker | OpenWorker) -> None:
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.status.connect(self._status)
        worker.partial.connect(self._on_partial)
        worker.finished.connect(self._on_result)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._worker_finished)
        self._thread = thread
        self._worker = worker
        thread.start()

    def _status(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _on_result(self, result: object) -> None:
        assert isinstance(result, StudioResult)
        self._apply_result(result)
        if self.library is not None and result.path is not None:
            try:
                self.library.upsert_lesson(
                    result.lesson,
                    result.path,
                    score=result.report.score,
                    duration_ms=result.playback.duration_ms,
                )
                self._refresh_library()
                self._set_library_selection(result.lesson.lesson_id)
            except Exception as exc:
                self.statusBar().showMessage(f"Lesson saved; index failed: {exc}", 10000)
        if result.tts_error:
            self.statusBar().showMessage(
                f"Ready without speech: {result.tts_error}", 12000
            )
        elif result.playback.audio_error:
            self.statusBar().showMessage(
                f"Audio output unavailable: {result.playback.audio_error}", 12000
            )

    def _on_failed(self, message: str) -> None:
        self.statusBar().showMessage("Generation failed", 12000)
        QMessageBox.critical(self, "Medha Studio", _friendly_error(message))

    def _worker_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._set_busy(False)
        if self._closing:
            self._closing = False
            self.close()

    def _set_busy(self, busy: bool) -> None:
        for widget in (
            self.generate_button,
            self.open_button,
            self.eval_button,
            self.add_material,
            self.remove_material,
            self.library_open,
            self.library_favorite_button,
            self.library_delete,
            self.library_refresh,
            self.library_scan,
            self.test_voice,
        ):
            widget.setEnabled(not busy)
        if busy:
            self.statusBar().showMessage("Working...")

    def _evaluate_dialog(self) -> None:
        if self._result is None:
            QMessageBox.information(self, "No lesson", "Generate or open a lesson first.")
            return
        report = self._result.report
        text = report.format_text()
        if self._result.warnings:
            text += "\n\nGeneration warnings\n" + "\n".join(
                f"- {warning}" for warning in self._result.warnings
            )
        dialog = QDialog(self)
        dialog.setWindowTitle("Lesson quality")
        dialog.resize(720, 520)
        layout = QVBoxLayout(dialog)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setPlainText(text)
        layout.addWidget(view)
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def _open_folder(self) -> None:
        path = (
            self._result.path.parent
            if self._result is not None and self._result.path is not None
            else config.LESSON_CONTENT_DIR
        )
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # --- settings -----------------------------------------------------
    def _restore_form(self) -> None:
        subject = self._settings.get("subject")
        if isinstance(subject, str) and subject in SUBJECTS:
            self.subject.setCurrentText(subject)
        difficulty = self._settings.get("difficulty")
        if isinstance(difficulty, str) and difficulty in DIFFICULTIES:
            self.difficulty.setCurrentText(difficulty)
        language = self._settings.get("language")
        if isinstance(language, str) and language in config.LANGUAGE_NAMES:
            index = self.language.findData(language)
            if index >= 0:
                self.language.setCurrentIndex(index)
        steps = self._settings.get("steps")
        if isinstance(steps, int):
            self.steps.setValue(max(1, min(config.LESSON_MAX_STEPS, steps)))
        audience = self._settings.get("audience")
        if isinstance(audience, str) and audience.strip():
            self.audience.setText(audience)
        self.use_rag.setChecked(bool(self._settings.get("use_rag", True)))
        self.use_rerank.setChecked(bool(self._settings.get("use_rerank", True)))
        self.use_ocr.setChecked(bool(self._settings.get("use_ocr", False)))
        self.tts_toggle.setChecked(self._tts)

    def _update_narration_label(self) -> None:
        if not hasattr(self, "narration_label"):
            return
        state = "ON" if self._tts else "OFF"
        self.narration_label.setText(
            f"Narration: {state}"
            + ("" if self._tts else " - enable it in Settings to hear lessons")
        )

    def _set_tts(self, checked: bool) -> None:
        self._tts = bool(checked)
        self._update_narration_label()
        self._save_settings()
        if checked:
            if self._result is not None:
                self.statusBar().showMessage(
                    "Narration enabled. Reopen or regenerate this lesson to hear it.",
                    12000,
                )
            else:
                self.statusBar().showMessage(
                    "Narration enabled. The voice loads on the next lesson.",
                    8000,
                )
        else:
            self.statusBar().showMessage(
                "Narration disabled for future lessons.", 8000
            )

    def _test_voice(self) -> None:
        if self._voice_thread is not None:
            return
        voice = self.voice.text().strip() or config.KOKORO_VOICE
        speed = float(self.speed.value())
        self.test_voice.setEnabled(False)
        self.statusBar().showMessage("Loading voice for a test...")
        thread = QThread(self)
        worker = VoiceTestWorker(voice, speed)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._voice_ok)
        worker.failed.connect(self._voice_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._voice_finished)
        self._voice_thread = thread
        self._voice_worker = worker
        thread.start()

    def _voice_ok(self, message: str) -> None:
        self.statusBar().showMessage(message, 8000)

    def _voice_failed(self, message: str) -> None:
        self.statusBar().showMessage("Voice test failed", 12000)
        QMessageBox.warning(self, "Voice test failed", _friendly_error(message))

    def _voice_finished(self) -> None:
        self._voice_thread = None
        self._voice_worker = None
        if hasattr(self, "test_voice"):
            self.test_voice.setEnabled(True)

    def _save_settings(self, *_args: object) -> None:
        if self.library is None:
            self.statusBar().showMessage("Library unavailable; settings not saved.", 8000)
            return
        values = {
            "tts": self.tts_toggle.isChecked(),
            "voice": self.voice.text().strip() or config.KOKORO_VOICE,
            "speed": round(float(self.speed.value()), 2),
            "use_rag": self.use_rag.isChecked(),
            "use_rerank": self.use_rerank.isChecked(),
            "use_ocr": self.use_ocr.isChecked(),
            "subject": self.subject.currentText(),
            "difficulty": self.difficulty.currentText(),
            "language": self.language.currentData() or "en",
            "steps": self.steps.value(),
            "audience": self.audience.text().strip(),
        }
        try:
            self.library.set_settings(values)
        except Exception as exc:
            self.statusBar().showMessage(f"Settings not saved: {exc}", 8000)
            return
        self._settings = values
        self.statusBar().showMessage("Settings saved.", 5000)

    # --- lifecycle ----------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:
        if self._thread is not None:
            self._closing = True
            self.statusBar().showMessage("Finishing the current job before closing...")
            event.ignore()
            return
        self._save_settings()
        self._timer.stop()
        if self._playback is not None:
            self._playback.stop()
        event.accept()


def _fmt(milliseconds: int) -> str:
    seconds = max(0, milliseconds) // 1000
    return f"{seconds // 60:02d}:{seconds % 60:02d}"
