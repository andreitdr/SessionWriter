from __future__ import annotations

import json
import sys
import tkinter as tk
from datetime import datetime
import platform
from pathlib import Path
import shutil
from tkinter import filedialog, messagebox, ttk

from .content_builder import build_content
from .io_utils import now_start_string
from .models import SessionFormData
from .validation import session_filename, validate_form
from .widgets import TaggedItemsEditor, TtkScrolledText


class SessionWriterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Session Sheet Writer")
        self.root.geometry("1100x900")

        self.base_dir = Path(__file__).resolve().parent.parent
        # When frozen (PyInstaller), use the exe's directory; otherwise the project root
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
        else:
            exe_dir = self.base_dir
        self._temp_dir = exe_dir / "temp"
        self._temp_dir.mkdir(exist_ok=True)
        self._config_path = self._temp_dir / ".sessionwriter.json"

        self.default_output_dir = Path(".").resolve()

        self.initials_var = tk.StringVar(value="")
        self.sequence_var = tk.StringVar(value="A")
        self.start_var = tk.StringVar(value=now_start_string())
        self.duration_var = tk.StringVar(value="normal")
        self.multiplier_var = tk.StringVar(value="1")
        self.setup_var = tk.StringVar(value="20")
        self.test_var = tk.StringVar(value="50")
        self.bug_var = tk.StringVar(value="30")
        self.charter_pct_var = tk.StringVar(value="85")
        self.opportunity_pct_var = tk.StringVar(value="15")
        saved_output_dir = self._load_config().get("output_dir", "")
        self.output_dir_var = tk.StringVar(
            value=saved_output_dir if saved_output_dir else str(self.default_output_dir)
        )

        self.datafiles: list[tuple[str, str, str]] = []  # (original_name, full_path, dest_name)
        self._pct_updating = False  # guard against recursive trace calls

        self.charter_pct_var.trace_add("write", lambda *_: self._on_charter_pct_changed())
        self.opportunity_pct_var.trace_add("write", lambda *_: self._on_opportunity_pct_changed())

        self._build_ui()
        self._restore_draft()

        # Auto-save draft every 30 seconds and on close
        self._schedule_autosave()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        """Main UI layout orchestrator."""
        content = self._setup_scrollable_canvas()
        
        # Build form sections in order
        self._build_file_info_section(content, row=0)
        self._build_version_env_section(content, row=1)
        self._build_charter_section(content, row=2)
        self._build_tester_section(content, row=3)
        self._build_breakdown_section(content, row=4)
        self._build_datafiles_section(content, row=5)
        self._build_notes_section(content, row=6)
        self.bugs_editor = TaggedItemsEditor(content, title="Bugs", tag_label="BUG")
        self.bugs_editor.grid(row=7, column=0, sticky="ew", pady=(0, 10))
        self.issues_editor = TaggedItemsEditor(content, title="Issues", tag_label="ISSUE")
        self.issues_editor.grid(row=8, column=0, sticky="ew", pady=(0, 10))
        self._build_buttons(content, row=9)
        
        content.columnconfigure(0, weight=1)
        self.root.update_idletasks()  # Force layout computation
        self.canvas.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _setup_scrollable_canvas(self) -> ttk.Frame:
        """Set up scrollable canvas and return content frame."""
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(outer, highlightthickness=0)
        vscroll = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)

        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Use ttk.Frame for cross-platform theme compatibility
        content = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=content, anchor="nw")

        def on_content_configure(_: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event: tk.Event) -> None:
            canvas.itemconfigure(canvas_window, width=event.width)

        content.bind("<Configure>", on_content_configure)
        canvas.bind("<Configure>", on_canvas_configure)
        
        # Cross-platform mouse wheel scrolling
        def _scroll_delta(event: tk.Event) -> int:
            """Return scroll direction: negative = up, positive = down."""
            if event.num == 4:
                return -1
            if event.num == 5:
                return 1
            if getattr(event, "delta", 0):
                if platform.system() == "Windows":
                    return int(-1 * (event.delta / 120))
                return int(-1 * event.delta)
            return 0

        def _find_text_widget(event: tk.Event) -> tk.Text | None:
            """Walk up from the widget under the cursor to find a tk.Text."""
            widget = event.widget
            # event.widget can be a string path if the real widget was destroyed
            if isinstance(widget, str):
                return None
            while widget is not None:
                if isinstance(widget, tk.Text):
                    return widget
                widget = getattr(widget, "master", None)
            return None

        def on_mousewheel(event: tk.Event) -> None:
            delta = _scroll_delta(event)
            if delta == 0:
                return

            text_w = _find_text_widget(event)
            if text_w is not None:
                top, bottom = text_w.yview()
                can_scroll = not (top <= 0.0 and bottom >= 1.0)  # content overflows
                at_top = top <= 0.0
                at_bottom = bottom >= 1.0
                # If there is scrollable content and we are not at the boundary
                # in the scroll direction, let the Text widget handle it.
                if can_scroll:
                    if delta < 0 and not at_top:
                        text_w.yview_scroll(delta, "units")
                        return
                    if delta > 0 and not at_bottom:
                        text_w.yview_scroll(delta, "units")
                        return

            # Fall through: scroll the main canvas
            canvas.yview_scroll(delta, "units")

        self.root.bind_all("<MouseWheel>", on_mousewheel)
        if platform.system() == "Linux":
            self.root.bind_all("<Button-4>", on_mousewheel)
            self.root.bind_all("<Button-5>", on_mousewheel)
        
        # Store references for later
        self.canvas = canvas
        self.canvas_window = canvas_window
        self.content = content
        
        return content

    def _build_file_info_section(self, parent: tk.Misc, row: int) -> None:
        """Build File Info section."""
        frame = ttk.LabelFrame(parent, text="File Info", padding=10)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Tester initials (3 chars)").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.initials_var, width=10).grid(row=0, column=1, sticky="w", padx=(8, 0))

        ttk.Label(frame, text="Sequence letter").grid(row=0, column=2, sticky="w", padx=(20, 0))
        ttk.Entry(frame, textvariable=self.sequence_var, width=5).grid(row=0, column=3, sticky="w", padx=(8, 0))

        ttk.Label(frame, text="Start (m/d/yy h:mmam|pm)").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=self.start_var, width=28).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        ttk.Label(frame, text="Output folder").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=self.output_dir_var).grid(
            row=2, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=(8, 0)
        )
        ttk.Button(frame, text="Browse", command=self._choose_output_dir).grid(row=2, column=3, sticky="e", pady=(8, 0))

    def _build_charter_section(self, parent: tk.Misc, row: int) -> None:
        """Build Charter section with mission and areas."""
        frame = ttk.LabelFrame(parent, text="Charter", padding=10)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Mission description").grid(row=0, column=0, sticky="nw")
        self.charter_text = TtkScrolledText(frame, width=100, height=5, wrap=tk.WORD)
        self.charter_text.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(frame, text="Areas (one per line)").grid(row=1, column=0, sticky="nw", pady=(8, 0))
        self.areas_text = TtkScrolledText(frame, width=100, height=8, wrap=tk.WORD)
        self.areas_text.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

    def _build_version_env_section(self, parent: tk.Misc, row: int) -> None:
        """Build Version & Environment section at the top of the page."""
        frame = ttk.LabelFrame(parent, text="Version & Environment", padding=10)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        frame.columnconfigure(0, weight=1)

        # --- Versions ---
        ver_header = ttk.Frame(frame)
        ver_header.grid(row=0, column=0, sticky="w")
        ttk.Label(ver_header, text="Versions").grid(row=0, column=0, sticky="w")
        ttk.Button(ver_header, text="Add Version", command=self._add_version_row).grid(row=0, column=1, padx=(12, 0))

        self.version_rows_frame = ttk.Frame(frame)
        self.version_rows_frame.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        self.version_rows: list[dict[str, object]] = []
        self._add_version_row()  # start with one row

        # --- Environments ---
        env_header = ttk.Frame(frame)
        env_header.grid(row=2, column=0, sticky="w")
        ttk.Label(env_header, text="Environments").grid(row=0, column=0, sticky="w")
        ttk.Button(env_header, text="Add Environment", command=self._add_env_row).grid(row=0, column=1, padx=(12, 0))

        self.env_rows_frame = ttk.Frame(frame)
        self.env_rows_frame.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        self.env_rows: list[dict[str, object]] = []
        self._add_env_row()  # start with one row

    def _add_version_row(self) -> None:
        row_frame = ttk.Frame(self.version_rows_frame)
        row_frame.grid(row=len(self.version_rows), column=0, sticky="ew", pady=2)
        entry = ttk.Entry(row_frame, width=50)
        entry.grid(row=0, column=0, sticky="w")
        remove_btn = ttk.Button(row_frame, text="Remove")
        remove_btn.grid(row=0, column=1, padx=(8, 0))
        row = {"frame": row_frame, "entry": entry, "remove": remove_btn}
        self.version_rows.append(row)
        remove_btn.configure(command=lambda r=row: self._remove_version_row(r))

    def _remove_version_row(self, row: dict[str, object]) -> None:
        if len(self.version_rows) <= 1:
            return  # keep at least one row
        frame = row["frame"]
        assert isinstance(frame, ttk.Frame)
        frame.destroy()
        self.version_rows.remove(row)
        for idx, r in enumerate(self.version_rows):
            f = r["frame"]
            assert isinstance(f, ttk.Frame)
            f.grid_configure(row=idx)

    def _add_env_row(self) -> None:
        row_frame = ttk.Frame(self.env_rows_frame)
        row_frame.grid(row=len(self.env_rows), column=0, sticky="ew", pady=2)
        combo = ttk.Combobox(row_frame, values=("VM", "CN", "LOCAL_HW"), width=20)
        combo.grid(row=0, column=0, sticky="w")
        remove_btn = ttk.Button(row_frame, text="Remove")
        remove_btn.grid(row=0, column=1, padx=(8, 0))
        row = {"frame": row_frame, "combo": combo, "remove": remove_btn}
        self.env_rows.append(row)
        remove_btn.configure(command=lambda r=row: self._remove_env_row(r))

    def _remove_env_row(self, row: dict[str, object]) -> None:
        if len(self.env_rows) <= 1:
            return  # keep at least one row
        frame = row["frame"]
        assert isinstance(frame, ttk.Frame)
        frame.destroy()
        self.env_rows.remove(row)
        for idx, r in enumerate(self.env_rows):
            f = r["frame"]
            assert isinstance(f, ttk.Frame)
            f.grid_configure(row=idx)

    def _get_versions(self) -> list[str]:
        results: list[str] = []
        for row in self.version_rows:
            entry = row["entry"]
            assert isinstance(entry, ttk.Entry)
            val = entry.get().strip()
            if val:
                results.append(val)
        return results

    def _get_environments(self) -> list[str]:
        results: list[str] = []
        for row in self.env_rows:
            combo = row["combo"]
            assert isinstance(combo, ttk.Combobox)
            val = combo.get().strip()
            if val:
                results.append(val)
        return results

    def _build_tester_section(self, parent: tk.Misc, row: int) -> None:
        """Build Tester section."""
        frame = ttk.LabelFrame(parent, text="Tester", padding=10)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        frame.columnconfigure(1, weight=1)
        
        ttk.Label(frame, text="Tester names (one per line)").grid(row=0, column=0, sticky="nw")
        self.tester_text = TtkScrolledText(frame, width=100, height=4, wrap=tk.WORD)
        self.tester_text.grid(row=0, column=1, sticky="ew", padx=(8, 0))

    def _build_breakdown_section(self, parent: tk.Misc, row: int) -> None:
        """Build Task Breakdown section."""
        frame = ttk.LabelFrame(parent, text="Task Breakdown", padding=10)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(frame, text="Duration").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            frame, textvariable=self.duration_var, values=("short", "normal", "long"), state="readonly", width=10
        ).grid(row=0, column=1, sticky="w", padx=(8, 20))

        ttk.Label(frame, text="Multiplier").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(frame, from_=1, to=20, textvariable=self.multiplier_var, width=6).grid(row=0, column=3, sticky="w", padx=(8, 20))

        ttk.Label(frame, text="Session setup %").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Spinbox(frame, from_=0, to=100, textvariable=self.setup_var, width=6).grid(row=1, column=1, sticky="w", padx=(8, 20), pady=(8, 0))

        ttk.Label(frame, text="Test design/execution %").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Spinbox(frame, from_=0, to=100, textvariable=self.test_var, width=6).grid(row=1, column=3, sticky="w", padx=(8, 20), pady=(8, 0))

        ttk.Label(frame, text="Bug investigation/reporting %").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Spinbox(frame, from_=0, to=100, textvariable=self.bug_var, width=6).grid(row=2, column=1, sticky="w", padx=(8, 20), pady=(8, 0))

        ttk.Label(frame, text="Charter %").grid(row=2, column=2, sticky="w", pady=(8, 0))
        ttk.Spinbox(frame, from_=0, to=100, textvariable=self.charter_pct_var, width=6).grid(row=2, column=3, sticky="w", padx=(8, 20), pady=(8, 0))

        ttk.Label(frame, text="Opportunity %").grid(row=2, column=4, sticky="w", pady=(8, 0))
        ttk.Spinbox(frame, from_=0, to=100, textvariable=self.opportunity_pct_var, width=6).grid(row=2, column=5, sticky="w", padx=(8, 0), pady=(8, 0))

    # --- auto-calc charter / opportunity ---
    def _on_charter_pct_changed(self) -> None:
        if self._pct_updating:
            return
        try:
            val = int(self.charter_pct_var.get())
        except ValueError:
            return
        if 0 <= val <= 100:
            self._pct_updating = True
            self.opportunity_pct_var.set(str(100 - val))
            self._pct_updating = False

    def _on_opportunity_pct_changed(self) -> None:
        if self._pct_updating:
            return
        try:
            val = int(self.opportunity_pct_var.get())
        except ValueError:
            return
        if 0 <= val <= 100:
            self._pct_updating = True
            self.charter_pct_var.set(str(100 - val))
            self._pct_updating = False

    def _build_datafiles_section(self, parent: tk.Misc, row: int) -> None:
        """Build Data Files section with a treeview list."""
        frame = ttk.LabelFrame(parent, text="Data Files", padding=10)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        frame.columnconfigure(0, weight=1)

        # Top bar: buttons + file count
        top_bar = ttk.Frame(frame)
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.columnconfigure(1, weight=1)

        ttk.Button(top_bar, text="\u2795  Add Files", command=self._choose_datafiles).grid(row=0, column=0)
        self.datafile_count_label = ttk.Label(top_bar, text="0 files", foreground="grey")
        self.datafile_count_label.grid(row=0, column=1, sticky="e")

        # Column headers
        header_frame = ttk.Frame(frame)
        header_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        header_frame.columnconfigure(0, weight=2)
        header_frame.columnconfigure(1, weight=0)
        header_frame.columnconfigure(2, weight=2)
        header_frame.columnconfigure(3, weight=3)
        ttk.Label(header_frame, text="Dest Name", font=("TkDefaultFont", 9, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header_frame, text="Ext", font=("TkDefaultFont", 9, "bold")).grid(row=0, column=1, sticky="w")
        ttk.Label(header_frame, text="Original Name", font=("TkDefaultFont", 9, "bold")).grid(row=0, column=2, sticky="w", padx=(8, 0))
        ttk.Label(header_frame, text="Location", font=("TkDefaultFont", 9, "bold")).grid(row=0, column=3, sticky="w", padx=(8, 0))

        # Scrollable rows container
        df_canvas = tk.Canvas(frame, height=130, highlightthickness=0)
        df_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=df_canvas.yview)
        df_canvas.configure(yscrollcommand=df_scroll.set)
        df_canvas.grid(row=2, column=0, sticky="ew", pady=(2, 0))
        df_scroll.grid(row=2, column=1, sticky="ns", pady=(2, 0))

        self.datafiles_rows_frame = ttk.Frame(df_canvas)
        self._df_canvas = df_canvas
        self._df_canvas_window = df_canvas.create_window((0, 0), window=self.datafiles_rows_frame, anchor="nw")

        self.datafiles_rows_frame.bind("<Configure>", lambda _: df_canvas.configure(scrollregion=df_canvas.bbox("all")))
        df_canvas.bind("<Configure>", lambda e: df_canvas.itemconfigure(self._df_canvas_window, width=e.width))

        self.datafiles_rows_frame.columnconfigure(0, weight=2)
        self.datafiles_rows_frame.columnconfigure(1, weight=0)
        self.datafiles_rows_frame.columnconfigure(2, weight=2)
        self.datafiles_rows_frame.columnconfigure(3, weight=3)
        self.datafiles_rows_frame.columnconfigure(4, weight=0)
        self.datafile_row_widgets: list[dict[str, object]] = []

    def _build_notes_section(self, parent: tk.Misc, row: int) -> None:
        """Build Test Notes section."""
        frame = ttk.LabelFrame(parent, text="Test Notes", padding=10)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        frame.columnconfigure(0, weight=1)
        
        self.notes_text = TtkScrolledText(frame, width=100, height=6, wrap=tk.WORD)
        self.notes_text.grid(row=0, column=0, sticky="ew")

    def _build_buttons(self, parent: tk.Misc, row: int) -> None:
        """Build action buttons."""
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="e", pady=(8, 4))
        ttk.Button(frame, text="Preview", command=self.preview).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(frame, text="Save .ses", command=self.save).grid(row=0, column=1)

    # ---- config persistence ------------------------------------------------
    def _load_config(self) -> dict:
        """Load persisted settings from disk."""
        try:
            return json.loads(self._config_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _save_config(self, **updates: object) -> None:
        """Merge *updates* into the config file and write it back."""
        cfg = self._load_config()
        cfg.update(updates)
        try:
            self._config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        except OSError:
            pass  # non-critical

    # ---- draft persistence -------------------------------------------------
    def _collect_draft(self) -> dict:
        """Snapshot every form field into a JSON-serialisable dict."""
        self._sync_datafile_dest_names()

        # version rows
        versions: list[str] = []
        for row in self.version_rows:
            entry = row["entry"]
            assert isinstance(entry, ttk.Entry)
            versions.append(entry.get())

        # environment rows
        environments: list[str] = []
        for row in self.env_rows:
            combo = row["combo"]
            assert isinstance(combo, ttk.Combobox)
            environments.append(combo.get())

        # bugs
        bugs: list[str] = []
        for row in self.bugs_editor.rows:
            body = row["body"]
            assert isinstance(body, TtkScrolledText)
            bugs.append(body.get("1.0", "end-1c"))

        # issues
        issues: list[str] = []
        for row in self.issues_editor.rows:
            body = row["body"]
            assert isinstance(body, TtkScrolledText)
            issues.append(body.get("1.0", "end-1c"))

        return {
            "initials": self.initials_var.get(),
            "sequence": self.sequence_var.get(),
            "start": self.start_var.get(),
            "duration": self.duration_var.get(),
            "multiplier": self.multiplier_var.get(),
            "setup_pct": self.setup_var.get(),
            "test_pct": self.test_var.get(),
            "bug_pct": self.bug_var.get(),
            "charter_pct": self.charter_pct_var.get(),
            "opportunity_pct": self.opportunity_pct_var.get(),
            "output_dir": self.output_dir_var.get(),
            "charter": self.charter_text.get("1.0", "end-1c"),
            "areas": self.areas_text.get("1.0", "end-1c"),
            "testers": self.tester_text.get("1.0", "end-1c"),
            "notes": self.notes_text.get("1.0", "end-1c"),
            "versions": versions,
            "environments": environments,
            "datafiles": [
                {"name": n, "path": p, "dest": d}
                for n, p, d in self.datafiles
            ],
            "bugs": bugs,
            "issues": issues,
        }

    def _restore_draft(self) -> None:
        """Populate widgets from saved draft, if any."""
        cfg = self._load_config()
        draft: dict | None = cfg.get("draft")
        if not draft:
            return

        # Simple StringVar fields
        for key, var in [
            ("initials", self.initials_var),
            ("sequence", self.sequence_var),
            ("start", self.start_var),
            ("duration", self.duration_var),
            ("multiplier", self.multiplier_var),
            ("setup_pct", self.setup_var),
            ("test_pct", self.test_var),
            ("bug_pct", self.bug_var),
            ("charter_pct", self.charter_pct_var),
            ("opportunity_pct", self.opportunity_pct_var),
            ("output_dir", self.output_dir_var),
        ]:
            if key in draft:
                var.set(draft[key])

        # Text widgets
        for key, widget in [
            ("charter", self.charter_text),
            ("areas", self.areas_text),
            ("testers", self.tester_text),
            ("notes", self.notes_text),
        ]:
            if draft.get(key):
                widget.delete("1.0", tk.END)
                widget.insert("1.0", draft[key])

        # Version rows
        saved_versions = draft.get("versions", [])
        if saved_versions:
            # First row already exists — fill it
            first_entry = self.version_rows[0]["entry"]
            assert isinstance(first_entry, ttk.Entry)
            first_entry.insert(0, saved_versions[0])
            for v in saved_versions[1:]:
                self._add_version_row()
                entry = self.version_rows[-1]["entry"]
                assert isinstance(entry, ttk.Entry)
                entry.insert(0, v)

        # Environment rows
        saved_envs = draft.get("environments", [])
        if saved_envs:
            first_combo = self.env_rows[0]["combo"]
            assert isinstance(first_combo, ttk.Combobox)
            first_combo.set(saved_envs[0])
            for e in saved_envs[1:]:
                self._add_env_row()
                combo = self.env_rows[-1]["combo"]
                assert isinstance(combo, ttk.Combobox)
                combo.set(e)

        # Data files
        saved_df = draft.get("datafiles", [])
        for df in saved_df:
            name = df.get("name", "")
            path = df.get("path", "")
            dest = df.get("dest", "")
            if name:
                self.datafiles.append((name, path, dest))
        if saved_df:
            self._refresh_datafiles_listbox()

        # Bugs
        for body_text in draft.get("bugs", []):
            self.bugs_editor.add_row(body_text=body_text)

        # Issues
        for body_text in draft.get("issues", []):
            self.issues_editor.add_row(body_text=body_text)

    def _save_draft(self) -> None:
        """Persist the current form state as a draft."""
        self._save_config(draft=self._collect_draft())

    def _clear_draft(self) -> None:
        """Remove the draft from the config file."""
        cfg = self._load_config()
        cfg.pop("draft", None)
        try:
            self._config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _schedule_autosave(self) -> None:
        """Auto-save draft every 30 seconds."""
        self._save_draft()
        self._autosave_id = self.root.after(30_000, self._schedule_autosave)

    def _on_close(self) -> None:
        """Save draft and close app."""
        self._save_draft()
        self.root.destroy()

    def _choose_output_dir(self) -> None:
        """Open directory chooser and update output directory path."""
        chosen = filedialog.askdirectory(initialdir=self.output_dir_var.get() or str(self.default_output_dir))
        if chosen:
            self.output_dir_var.set(chosen)
            self._save_config(output_dir=chosen)

    def _refresh_datafiles_listbox(self) -> None:
        """Refresh datafiles row display."""
        # Destroy existing row widgets
        for row_w in self.datafile_row_widgets:
            for widget in (row_w["entry"], row_w["ext_label"], row_w["name_label"], row_w["path_label"], row_w["remove_btn"]):
                assert isinstance(widget, tk.Widget)
                widget.destroy()
        self.datafile_row_widgets.clear()

        for idx, (name, full_path, dest_name) in enumerate(self.datafiles):
            display_path = str(Path(full_path).parent) if full_path != name else ""
            stem = Path(name).stem
            ext = Path(name).suffix  # e.g. ".png"

            entry_var = tk.StringVar(value=dest_name)
            entry = ttk.Entry(self.datafiles_rows_frame, textvariable=entry_var)
            entry.grid(row=idx, column=0, sticky="ew", pady=1, padx=(0, 4))
            # Show placeholder (stem only) when empty
            if not dest_name:
                entry.insert(0, stem)
                entry.configure(foreground="grey")

                def _on_focus_in(e: tk.Event, _entry: ttk.Entry = entry, _stem: str = stem) -> None:
                    if _entry.get() == _stem and str(_entry.cget("foreground")) == "grey":
                        _entry.delete(0, tk.END)
                        _entry.configure(foreground="")

                def _on_focus_out(e: tk.Event, _entry: ttk.Entry = entry, _stem: str = stem, _idx: int = idx) -> None:
                    val = _entry.get().strip()
                    if not val or val == _stem:
                        _entry.delete(0, tk.END)
                        _entry.insert(0, _stem)
                        _entry.configure(foreground="grey")
                        self.datafiles[_idx] = (self.datafiles[_idx][0], self.datafiles[_idx][1], "")
                    else:
                        self.datafiles[_idx] = (self.datafiles[_idx][0], self.datafiles[_idx][1], val)

                entry.bind("<FocusIn>", _on_focus_in)
                entry.bind("<FocusOut>", _on_focus_out)
            else:
                def _on_change_focus_out(e: tk.Event, _entry: ttk.Entry = entry, _stem: str = stem, _idx: int = idx) -> None:
                    val = _entry.get().strip()
                    if not val or val == _stem:
                        _entry.delete(0, tk.END)
                        _entry.insert(0, _stem)
                        _entry.configure(foreground="grey")
                        self.datafiles[_idx] = (self.datafiles[_idx][0], self.datafiles[_idx][1], "")
                    else:
                        self.datafiles[_idx] = (self.datafiles[_idx][0], self.datafiles[_idx][1], val)

                entry.bind("<FocusOut>", _on_change_focus_out)

            # Show the extension as a non-editable label next to the entry
            ext_label = ttk.Label(self.datafiles_rows_frame, text=ext, foreground="grey")
            ext_label.grid(row=idx, column=1, sticky="w", pady=1)

            name_label = ttk.Label(self.datafiles_rows_frame, text=name)
            name_label.grid(row=idx, column=2, sticky="w", pady=1, padx=(8, 4))

            path_label = ttk.Label(self.datafiles_rows_frame, text=display_path, foreground="grey")
            path_label.grid(row=idx, column=3, sticky="w", pady=1, padx=(8, 4))

            remove_btn = ttk.Button(self.datafiles_rows_frame, text="\u2716", width=3,
                                    command=lambda i=idx: self._remove_datafile_at(i))
            remove_btn.grid(row=idx, column=4, sticky="e", pady=1, padx=(4, 0))

            self.datafile_row_widgets.append({
                "entry": entry, "ext_label": ext_label, "name_label": name_label,
                "path_label": path_label, "remove_btn": remove_btn,
            })

        count = len(self.datafiles)
        self.datafile_count_label.configure(text=f"{count} file{'s' if count != 1 else ''}")

    def _choose_datafiles(self) -> None:
        """Open file chooser and add selected files to datafiles list."""
        paths = filedialog.askopenfilenames(initialdir=str(self.base_dir))
        if not paths:
            return
        for raw in paths:
            name = Path(raw).name
            if name and not any(n == name for n, p, d in self.datafiles):
                self.datafiles.append((name, raw, ""))
        self._refresh_datafiles_listbox()

    def _remove_datafile_at(self, index: int) -> None:
        """Remove a single datafile by index and refresh."""
        if 0 <= index < len(self.datafiles):
            self.datafiles.pop(index)
        self._refresh_datafiles_listbox()

    def _remove_selected_datafiles(self) -> None:
        """Remove selected (focused) datafile from list."""
        # With the row-based UI, remove the last focused entry's row
        # or simply do nothing if nothing is focused — the per-row ✖ button handles removal
        pass

    def _selected_areas(self) -> list[str]:
        """Extract area names from text widget (one per line)."""
        raw = self.areas_text.get("1.0", "end-1c")
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def _testers(self) -> list[str]:
        """Extract tester names from text widget (one per line)."""
        raw = self.tester_text.get("1.0", "end-1c")
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def _sync_datafile_dest_names(self) -> None:
        """Read current entry values back into self.datafiles."""
        for idx, row_w in enumerate(self.datafile_row_widgets):
            entry = row_w["entry"]
            assert isinstance(entry, ttk.Entry)
            val = entry.get().strip()
            orig_name, full_path, _ = self.datafiles[idx]
            stem = Path(orig_name).stem
            # If the value matches the placeholder (stem shown in grey), treat as empty
            if val == stem and str(entry.cget("foreground")) == "grey":
                val = ""
            self.datafiles[idx] = (orig_name, full_path, val)

    def _build_form_data(self) -> SessionFormData:
        """Collect all form inputs into a data object."""
        self._sync_datafile_dest_names()
        return SessionFormData(
            initials=self.initials_var.get(),
            sequence=self.sequence_var.get(),
            start=self.start_var.get(),
            charter_description=self.charter_text.get("1.0", "end-1c"),
            selected_areas=self._selected_areas(),
            versions=self._get_versions(),
            environments=self._get_environments(),
            testers=self._testers(),
            duration=self.duration_var.get(),
            multiplier=self.multiplier_var.get(),
            setup_pct=self.setup_var.get(),
            test_pct=self.test_var.get(),
            bug_pct=self.bug_var.get(),
            charter_pct=self.charter_pct_var.get(),
            opportunity_pct=self.opportunity_pct_var.get(),
            datafiles=[
                (dest + Path(name).suffix) if dest else name
                for name, _, dest in self.datafiles
            ],
            notes=self.notes_text.get("1.0", "end-1c"),
            bugs=self.bugs_editor.get_items(),
            issues=self.issues_editor.get_items(),
        )

    def preview(self) -> None:
        """Show a preview window with the generated session file content."""
        data = self._build_form_data()
        errors = validate_form(data)
        if errors:
            messagebox.showerror("Validation errors", "\n".join(f"- {err}" for err in errors))
            return

        preview_window = tk.Toplevel(self.root)
        preview_window.title(session_filename(data))
        preview_window.geometry("900x700")
        text = TtkScrolledText(preview_window, wrap=tk.NONE)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert("1.0", build_content(data))
        text.configure(state=tk.DISABLED)

    def save(self) -> None:
        """Validate form, create date folders, copy data files, and write .ses file."""
        data = self._build_form_data()
        errors = validate_form(data)
        if errors:
            messagebox.showerror("Validation errors", "\n".join(f"- {err}" for err in errors))
            return

        date_str = datetime.now().strftime("%Y-%m-%d")
        output_root = Path(self.output_dir_var.get().strip() or str(self.default_output_dir))
        approved_dir = output_root / date_str / "approved"
        datafiles_dir = output_root / date_str / "dataFiles"

        default_name = session_filename(data)
        approved_dir.mkdir(parents=True, exist_ok=True)

        path = filedialog.asksaveasfilename(
            title="Save session file",
            initialdir=str(approved_dir),
            initialfile=default_name,
            defaultextension=".ses",
            filetypes=[("Session files", "*.ses"), ("All files", "*.*")],
        )
        if not path:
            return

        target = Path(path)

        if self.datafiles:
            datafiles_dir.mkdir(parents=True, exist_ok=True)
            for orig_name, original_path, dest_name in self.datafiles:
                ext = Path(orig_name).suffix
                copy_name = (dest_name + ext) if dest_name else orig_name
                if original_path and Path(original_path).is_file():
                    try:
                        shutil.copy2(original_path, datafiles_dir / copy_name)
                    except Exception as e:
                        print(f"Failed to copy datafile {copy_name}: {e}")

        target.write_text(build_content(data), encoding="utf-8")
        self._clear_draft()
        self._save_config(output_dir=self.output_dir_var.get().strip())
        messagebox.showinfo("Saved", f"Session file written to:\n{target}")
