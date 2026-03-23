from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .models import TaggedItem


class TtkScrolledText(ttk.Frame):
    """Scrolled text widget with an overlay expand indicator when content overflows."""

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master)
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("borderwidth", 0)

        self._collapsed_height: int | None = kwargs.get("height")
        self._expandable = self._collapsed_height is not None

        # --- main text + scrollbar ---
        self.text = tk.Text(self, **kwargs)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.text.yview)
        self.text.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        if self._expandable:
            # Overlay expand pill – placed on top of the text widget
            self._pill = tk.Label(
                self.text,
                text=" ↗ Expand ",
                cursor="hand2",
                fg="#ffffff",
                bg="#5a5a5a",
                font=("TkDefaultFont", 8),
                padx=6,
                pady=2,
                relief="flat",
                bd=0,
            )
            self._pill_visible = False
            self._pill.bind("<Button-1>", lambda _: self._open_popup())
            self._pill.bind("<Enter>", lambda _: self._pill.configure(bg="#3a7cf7"))
            self._pill.bind("<Leave>", lambda _: self._pill.configure(bg="#5a5a5a"))

            # monitor content and scroll changes
            self.text.bind("<<Modified>>", self._on_modified, add=True)
            self.text.bind("<Configure>", lambda _: self.after(20, self._check_overflow), add=True)
            self.text.bind("<KeyRelease>", lambda _: self.after(20, self._check_overflow), add=True)

    # ---- overflow detection ------------------------------------------------
    def _on_modified(self, _event: tk.Event | None = None) -> None:
        self.text.edit_modified(False)
        self.after(20, self._check_overflow)

    def _check_overflow(self) -> None:
        if not self._expandable:
            return
        self.text.update_idletasks()
        top, bottom = self.text.yview()
        overflows = not (top <= 0.0 and bottom >= 1.0)
        if overflows and not self._pill_visible:
            self._pill.place(relx=1.0, rely=1.0, anchor="se", x=-4, y=-4)
            self._pill.lift()
            self._pill_visible = True
        elif not overflows and self._pill_visible:
            self._pill.place_forget()
            self._pill_visible = False

    # ---- popup editor ------------------------------------------------------
    def _open_popup(self) -> None:
        popup = tk.Toplevel(self.winfo_toplevel())
        popup.title("Expanded Editor")
        popup.geometry("850x550")
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        popup.configure(bg="#f5f5f5")

        # header
        header = tk.Frame(popup, bg="#f5f5f5")
        header.pack(fill=tk.X, padx=16, pady=(14, 0))
        tk.Label(
            header, text="Expanded Editor", font=("TkDefaultFont", 11, "bold"),
            bg="#f5f5f5", anchor="w",
        ).pack(side=tk.LEFT)

        # text area with border frame
        text_border = tk.Frame(popup, bg="#cccccc", bd=0)
        text_border.pack(fill=tk.BOTH, expand=True, padx=16, pady=(10, 0))

        inner = tk.Frame(text_border, bg="white")
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        text = tk.Text(
            inner,
            wrap=self.text.cget("wrap"),
            highlightthickness=0,
            borderwidth=0,
            font=self.text.cget("font"),
            padx=6,
            pady=6,
        )
        scroll = ttk.Scrollbar(inner, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # copy current content
        content = self.text.get("1.0", "end-1c")
        if content:
            text.insert("1.0", content)
        text.focus_set()

        # footer
        footer = tk.Frame(popup, bg="#f5f5f5")
        footer.pack(fill=tk.X, padx=16, pady=12)

        def _on_close() -> None:
            new_content = text.get("1.0", "end-1c")
            self.text.delete("1.0", tk.END)
            if new_content:
                self.text.insert("1.0", new_content)
            popup.destroy()
            self.after(20, self._check_overflow)

        ttk.Button(footer, text="Done", command=_on_close).pack(side=tk.RIGHT)
        popup.protocol("WM_DELETE_WINDOW", _on_close)
        popup.bind("<Escape>", lambda _: _on_close())

    def get(self, *args, **kwargs) -> str:
        return self.text.get(*args, **kwargs)

    def insert(self, *args, **kwargs) -> None:
        self.text.insert(*args, **kwargs)

    def configure(self, **kwargs) -> None:
        self.text.configure(**kwargs)

    def delete(self, *args, **kwargs) -> None:
        self.text.delete(*args, **kwargs)
        
    def bind(self, *args, **kwargs):
        return self.text.bind(*args, **kwargs)


class TaggedItemsEditor(ttk.LabelFrame):
    def __init__(self, parent: tk.Misc, title: str, tag_label: str) -> None:
        super().__init__(parent, text=title, padding=10)
        self.tag_label = tag_label
        self.rows: list[dict[str, object]] = []

        controls = ttk.Frame(self)
        controls.grid(row=0, column=0, sticky="w")
        ttk.Button(controls, text=f"Add {tag_label}", command=self.add_row).grid(row=0, column=0, sticky="w")

        self.rows_container = ttk.Frame(self)
        self.rows_container.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.columnconfigure(0, weight=1)

    def add_row(self, id_text: str = "", body_text: str = "") -> None:
        row_frame = ttk.Frame(self.rows_container)
        row_frame.grid(row=len(self.rows), column=0, sticky="ew", pady=4)
        row_frame.columnconfigure(1, weight=1)

        next_id = len(self.rows) + 1
        id_label = ttk.Label(row_frame, text=f"{self.tag_label}-{next_id}", width=12)
        id_label.grid(row=0, column=0, sticky="w")

        remove_btn = ttk.Button(row_frame, text="Remove")
        remove_btn.grid(row=0, column=2, sticky="e")

        ttk.Label(row_frame, text="Description").grid(row=1, column=0, sticky="nw", pady=(4, 0))
        body = TtkScrolledText(row_frame, width=90, height=4, wrap=tk.WORD)
        body.grid(row=1, column=1, columnspan=2, sticky="ew", pady=(4, 0))
        if body_text:
            body.insert("1.0", body_text)

        row = {"frame": row_frame, "id_label": id_label, "body": body, "remove": remove_btn}
        self.rows.append(row)
        remove_btn.configure(command=lambda r=row: self.remove_row(r))

    def remove_row(self, row: dict[str, object]) -> None:
        frame = row["frame"]
        assert isinstance(frame, ttk.Frame)
        frame.destroy()

        self.rows.remove(row)
        self._renumber_rows()

    def _renumber_rows(self) -> None:
        """Re-grid rows and update their auto-assigned IDs."""
        for index, existing in enumerate(self.rows):
            existing_frame = existing["frame"]
            assert isinstance(existing_frame, ttk.Frame)
            existing_frame.grid_configure(row=index)
            id_label = existing["id_label"]
            assert isinstance(id_label, ttk.Label)
            id_label.configure(text=f"{self.tag_label}-{index + 1}")

    def get_items(self) -> list[TaggedItem]:
        items: list[TaggedItem] = []
        for index, row in enumerate(self.rows):
            body_widget = row["body"]
            assert isinstance(body_widget, TtkScrolledText)

            item_id = str(index + 1)
            body_text = body_widget.get("1.0", "end-1c").strip()
            if body_text:
                items.append(TaggedItem(item_id=item_id, body=body_text))
        return items
