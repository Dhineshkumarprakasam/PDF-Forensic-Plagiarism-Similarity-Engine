"""PDF-FPSE desktop app. Run: python app.py"""
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

import engine

INK, PAPER, TEAL, RUST, MOSS, MIST = "#16263A", "#F4F6F8", "#1F7A8C", "#B8452F", "#6B8F3A", "#DDE3E9"
VERDICT_TAG = {"Copied": RUST, "Needs": "#B7791F", "No": MOSS}

ctk.set_appearance_mode("light")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PDF-FPSE · Similarity Checker")
        self.geometry("1150x760")
        self.minsize(700, 540)
        self.configure(fg_color=PAPER)
        self.q = queue.Queue()
        self.folder = tk.StringVar()
        self.out = tk.StringVar()
        self.prompt = tk.StringVar()
        self.result = None
        self._toolbar_wrapped = None
        self._build()
        self.after(100, self._poll)

    def _row(self, parent, label, var, cmd, row):
        ctk.CTkLabel(
            parent, text=label, text_color=INK, font=("Segoe UI", 13, "bold"),
            width=180, anchor="w",
        ).grid(row=row, column=0, padx=(24, 8), pady=10)
        ctk.CTkEntry(
            parent, textvariable=var, height=38, border_color=MIST,
            fg_color="white", text_color=INK, font=("Segoe UI", 12),
        ).grid(row=row, column=1, sticky="ew", pady=10)
        ctk.CTkButton(
            parent, text="Browse", width=100, height=38, fg_color="white",
            text_color=TEAL, border_width=1, border_color=TEAL,
            hover_color=MIST, font=("Segoe UI", 12, "bold"), command=cmd,
        ).grid(row=row, column=2, padx=20, pady=10)

    def _build(self):
        head = ctk.CTkFrame(self, fg_color=INK, corner_radius=0, height=92)
        head.pack(fill="x")
        ctk.CTkLabel(
            head, text="Assignment Similarity Checker", text_color="white",
            font=("Georgia", 24, "bold"),
        ).pack(anchor="w", padx=32, pady=(14, 0))
        subtitle = ctk.CTkLabel(
            head,
            text="Compares every pair of student PDFs for copied text and reused screenshots.",
            text_color="#B9C7D6", font=("Segoe UI", 13), wraplength=1050,
            justify="left",
        )
        subtitle.pack(anchor="w", padx=34, pady=(2, 12))
        head.bind("<Configure>", lambda event: subtitle.configure(wraplength=max(260, event.width - 68)))

        card = ctk.CTkFrame(
            self, fg_color="white", corner_radius=12, border_width=1,
            border_color="#E2E8F0",
        )
        card.pack(fill="x", padx=28, pady=(20, 12))
        card.columnconfigure(1, weight=1)
        self._row(card, "Student PDFs folder", self.folder, lambda: self._pick(self.folder, True), 0)
        self._row(card, "Save reports to", self.out, lambda: self._pick(self.out, True), 1)
        self._row(card, "Question paper PDF (optional)", self.prompt, lambda: self._pick(self.prompt, False), 2)

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=28, pady=4)
        self.btn = ctk.CTkButton(
            bar, text="Check for Similarity", height=42, width=195,
            fg_color=TEAL, hover_color="#16596A", font=("Segoe UI", 14, "bold"),
            command=self.start, corner_radius=8,
        )
        self.btn.grid(row=0, column=0, sticky="w")
        self.open_btn = ctk.CTkButton(
            bar, text="Open Reports Folder", height=42, fg_color="white",
            text_color=TEAL, border_width=1, border_color=TEAL,
            hover_color=MIST, state="disabled", command=self.open_out,
            font=("Segoe UI", 13, "bold"), corner_radius=8,
        )
        self.open_btn.grid(row=0, column=1, padx=12, sticky="w")
        self.status = ctk.CTkLabel(
            bar, text="Choose a folder to begin.", text_color="#5A6B7C",
            font=("Segoe UI", 13),
        )
        self.status.grid(row=0, column=2, padx=14, sticky="w")
        bar.columnconfigure(2, weight=1)
        bar.bind("<Configure>", self._resize_toolbar)

        self.prog = ctk.CTkProgressBar(
            self, height=10, progress_color=TEAL, fg_color=MIST, corner_radius=5,
        )
        self.prog.set(0)
        self.prog.pack(fill="x", padx=28, pady=(12, 10))

        self.summary = ctk.CTkLabel(
            self, text="", text_color=INK, font=("Segoe UI", 14, "bold"),
            anchor="w",
        )
        self.summary.pack(fill="x", padx=30, pady=(4, 6))
        self.bind("<Configure>", self._resize_summary)

        wrap = ctk.CTkFrame(
            self, fg_color="white", corner_radius=12, border_width=1,
            border_color="#E2E8F0",
        )
        wrap.pack(fill="both", expand=True, padx=28, pady=(2, 24))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "T.Treeview", rowheight=32, font=("Segoe UI", 11), background="white",
            fieldbackground="white", foreground=INK, borderwidth=0,
        )
        style.configure(
            "T.Treeview.Heading", font=("Segoe UI", 11, "bold"), background=MIST,
            foreground=INK, relief="flat",
        )

        columns = (
            "PDF_1", "PDF_2", "Q_Value", "Longest_Match_Words", "Shared_Words",
            "Image_Match_Percent", "Trigger_Type", "Verdict",
        )
        headings = (
            "PDF 1", "PDF 2", "q-value", "Longest match (words)", "Shared words",
            "Image match %", "Evidence", "Verdict",
        )
        self.tree = ttk.Treeview(wrap, columns=columns, show="headings", style="T.Treeview")
        self._column_weights = (0.15, 0.15, 0.10, 0.16, 0.12, 0.13, 0.10, 0.09)
        self._column_min_widths = (90, 90, 75, 100, 85, 95, 75, 85)
        for column, heading, minimum in zip(columns, headings, self._column_min_widths):
            self.tree.heading(column, text=heading)
            self.tree.column(column, width=minimum, minwidth=minimum, anchor="w", stretch=True)
        for tag, color in VERDICT_TAG.items():
            self.tree.tag_configure(tag, foreground=color)

        y_scroll = ttk.Scrollbar(wrap, command=self.tree.yview)
        x_scroll = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        y_scroll.pack(side="right", fill="y")
        x_scroll.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree.bind("<Configure>", self._resize_columns)
        self.tree.bind("<Double-1>", self._detail)

    def _resize_toolbar(self, event):
        wrapped = event.width < 880
        self.status.configure(wraplength=max(220, event.width - (24 if wrapped else 450)))
        if wrapped == self._toolbar_wrapped:
            return
        self._toolbar_wrapped = wrapped
        if wrapped:
            self.status.grid_configure(row=1, column=0, columnspan=3, padx=4, pady=(8, 0), sticky="w")
        else:
            self.status.grid_configure(row=0, column=2, columnspan=1, padx=14, pady=0, sticky="w")

    def _resize_columns(self, event):
        width = max(1, event.width - 24)
        for column, weight, minimum in zip(
            self.tree["columns"], self._column_weights, self._column_min_widths,
        ):
            self.tree.column(column, width=max(minimum, int(width * weight)))

    def _resize_summary(self, event):
        self.summary.configure(wraplength=max(320, event.width - 60))

    def _pick(self, var, is_dir):
        if is_dir:
            path = filedialog.askdirectory()
        else:
            path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if path:
            var.set(path)
            if var is self.folder and not self.out.get():
                self.out.set(os.path.join(path, "fpse_reports"))

    def start(self):
        if not os.path.isdir(self.folder.get()):
            return messagebox.showwarning(
                "Folder needed", "Choose the folder that holds the student PDFs.",
            )
        self.btn.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        self.tree.delete(*self.tree.get_children())
        self.summary.configure(text="")
        out = self.out.get() or os.path.join(self.folder.get(), "fpse_reports")
        self.out.set(out)
        folder, prompt = self.folder.get(), self.prompt.get() or None

        def work():
            try:
                result = engine.run(
                    folder, out, prompt,
                    lambda fraction, message: self.q.put(("p", fraction, message)),
                )
                self.q.put(("done", result))
            except Exception as error:
                self.q.put(("err", str(error)))

        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                message = self.q.get_nowait()
                if message[0] == "p":
                    self.prog.set(message[1])
                    self.status.configure(text=message[2])
                elif message[0] == "err":
                    self.btn.configure(state="normal")
                    self.status.configure(text="Could not finish.")
                    messagebox.showerror("Check failed", message[1])
                else:
                    self._show(message[1])
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _show(self, result):
        self.result = result
        self.btn.configure(state="normal")
        self.open_btn.configure(state="normal")
        self.status.configure(text="Reports saved. Double-click a row for the evidence.")
        if result["solo"]:
            summary = (
                "Only 2 PDFs: no class comparison is possible. Review matching text and "
                "pictures manually."
            )
        else:
            summary = (
                f"{result['docs']} PDFs, {result['pairs']} pairs tested. "
                f"{result['flagged']} pair(s) marked Copied."
            )
            if result["warn"]:
                summary += f" {result['warn']}"
        if result["skipped"]:
            summary += f" Could not read: {', '.join(result['skipped'])}."
        self.summary.configure(text=summary)
        for row in result["rows"]:
            values = [
                f"{row[column]:.2e}" if column == "Q_Value" and row[column] != "" else row[column]
                for column in self.tree["columns"]
            ]
            self.tree.insert("", "end", values=values, tags=(row["Verdict"].split()[0],))

    def _detail(self, _event):
        selection = self.tree.selection()
        if not selection:
            return
        values = self.tree.item(selection[0], "values")
        row = next(
            (
                item for item in self.result["rows"]
                if item["PDF_1"] == values[0] and item["PDF_2"] == values[1]
            ),
            None,
        )
        if not row:
            return

        win = ctk.CTkToplevel(self)
        win.title(f"Evidence Analysis · {row['PDF_1']} vs {row['PDF_2']}")
        win.geometry("800x620")
        win.minsize(480, 400)
        win.configure(fg_color=PAPER)

        header = ctk.CTkFrame(
            win, fg_color="white", corner_radius=0, height=64,
            border_width=1, border_color="#E2E8F0",
        )
        header.pack(fill="x")
        title = ctk.CTkLabel(
            header, text=f"Comparison: {row['PDF_1']} & {row['PDF_2']}",
            text_color=INK, font=("Segoe UI", 15, "bold"),
            wraplength=760, justify="left",
        )
        title.pack(anchor="w", padx=20, pady=(8, 0))
        ctk.CTkLabel(
            header, text=f"Verdict: {row['Verdict']}  |  Evidence: {row['Trigger_Type'] or 'None'}",
            text_color="#5A6B7C", font=("Segoe UI", 12),
        ).pack(anchor="w", padx=20, pady=(0, 8))
        header.bind("<Configure>", lambda event: title.configure(wraplength=max(260, event.width - 40)))

        content = ctk.CTkFrame(win, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=16)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)

        table = ctk.CTkFrame(
            content, fg_color="white", corner_radius=10, border_width=1,
            border_color="#E2E8F0",
        )
        table.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        metrics = [
            ("Verdict", row["Verdict"]),
            ("Evidence", row["Trigger_Type"] or "None"),
        ]
        for key in engine.MATRIX_COLS:
            if key in ("PDF_1", "PDF_2", "Verdict", "Trigger_Type"):
                continue
            value = row[key]
            if key in ("Q_Value", "Text_P_Value") and value != "":
                value = f"{value:.2e}"
            metrics.append((key.replace("_", " "), str(value)))

        for index, (label, value) in enumerate(metrics):
            background = "#F8FAFC" if index % 2 else "white"
            metric_row = ctk.CTkFrame(table, fg_color=background, corner_radius=0, height=32)
            metric_row.pack(fill="x", padx=1, pady=1)
            metric_row.pack_propagate(False)
            ctk.CTkLabel(
                metric_row, text=label, text_color="#5A6B7C",
                font=("Segoe UI", 11, "bold"), anchor="w",
            ).pack(side="left", padx=16, fill="y")
            ctk.CTkLabel(
                metric_row, text=value, text_color=INK,
                font=("Segoe UI", 11), anchor="w",
            ).pack(side="right", padx=16, fill="y")

        passage = ctk.CTkFrame(
            content, fg_color="white", corner_radius=10, border_width=1,
            border_color="#E2E8F0",
        )
        passage.grid(row=1, column=0, sticky="nsew")
        passage.rowconfigure(1, weight=1)
        passage.columnconfigure(0, weight=1)
        ctk.CTkLabel(
            passage, text="Longest matching text found:",
            text_color=INK, font=("Segoe UI", 13, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))
        box = ctk.CTkTextbox(
            passage, wrap="word", font=("Consolas", 12), fg_color="#F8FAFC",
            text_color=INK, border_width=1, border_color="#E2E8F0", corner_radius=6,
        )
        box.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        box.insert("1.0", row["_passage"] or "(No matching text passage found.)")
        box.configure(state="disabled")

    def open_out(self):
        path = self.out.get()
        if sys.platform.startswith("win"):
            os.startfile(path)
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])


if __name__ == "__main__":
    App().mainloop()
