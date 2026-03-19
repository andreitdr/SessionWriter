from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .models import TaggedItem


class TtkScrolledText(ttk.Frame):
    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master)
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("borderwidth", 0)
        self.text = tk.Text(self, **kwargs)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.text.yview)
        self.text.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

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

        ttk.Label(row_frame, text=f"{self.tag_label} ID").grid(row=0, column=0, sticky="w")
        id_entry = ttk.Entry(row_frame, width=30)
        id_entry.grid(row=0, column=1, sticky="w", padx=(6, 8))
        id_entry.insert(0, id_text)

        remove_btn = ttk.Button(row_frame, text="Remove")
        remove_btn.grid(row=0, column=2, sticky="e")

        ttk.Label(row_frame, text="Description").grid(row=1, column=0, sticky="nw", pady=(4, 0))
        body = TtkScrolledText(row_frame, width=90, height=4, wrap=tk.WORD)
        body.grid(row=1, column=1, columnspan=2, sticky="ew", pady=(4, 0))
        if body_text:
            body.insert("1.0", body_text)

        row = {"frame": row_frame, "id": id_entry, "body": body, "remove": remove_btn}
        self.rows.append(row)
        remove_btn.configure(command=lambda r=row: self.remove_row(r))

    def remove_row(self, row: dict[str, object]) -> None:
        frame = row["frame"]
        assert isinstance(frame, ttk.Frame)
        frame.destroy()

        self.rows.remove(row)
        for index, existing in enumerate(self.rows):
            existing_frame = existing["frame"]
            assert isinstance(existing_frame, ttk.Frame)
            existing_frame.grid_configure(row=index)

    def get_items(self) -> list[TaggedItem]:
        items: list[TaggedItem] = []
        for row in self.rows:
            id_entry = row["id"]
            body_widget = row["body"]
            assert isinstance(id_entry, ttk.Entry)
            assert isinstance(body_widget, TtkScrolledText)

            item_id = id_entry.get().strip()
            body_text = body_widget.get("1.0", "end-1c").strip()
            if item_id or body_text:
                items.append(TaggedItem(item_id=item_id, body=body_text))
        return items
