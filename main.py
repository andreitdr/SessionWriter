import sys
import tkinter as tk
from session_writer.app import SessionWriterApp

if __name__ == "__main__":
    try:
        print("Starting Session Sheet Writer application...", flush=True)
        root = tk.Tk()
        print("Tk window created", flush=True)
        
        app = SessionWriterApp(root)
        print("App initialized successfully", flush=True)
        
        # Bring window to foreground on macOS
        root.lift()
        root.attributes('-topmost', True)
        root.after_idle(root.attributes, '-topmost', False)
        print("Window brought to foreground, starting mainloop...", flush=True)
        
        root.mainloop()
    except Exception as e:
        import traceback
        print(f"ERROR: Failed to start application: {e}", file=sys.stderr, flush=True)
        traceback.print_exc()
        sys.exit(1)


