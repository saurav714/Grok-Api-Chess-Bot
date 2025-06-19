import tkinter as tk
from tkinter import ttk, messagebox
import chess.svg
from threading import Thread
import queue
import os
import json
from .chess_bot import ChessBot
from tkinterhtml import HtmlFrame

class ChessBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Chess Bot")
        self.root.geometry("1000x600")
        
        self.config = {
            'platform': 'lichess',
            'player_color': 'white'
        }
        
        self.bot = None
        self.load_config()
        self.setup_gui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def setup_gui(self):
        # Main container
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel
        left_panel = ttk.Frame(main_container)
        main_container.add(left_panel, weight=1)
        
        # Configuration
        config_frame = ttk.LabelFrame(left_panel, text="Configuration")
        config_frame.pack(fill="x", padx=5, pady=5)
        
        # Platform selection
        ttk.Label(config_frame, text="Platform:").grid(row=0, column=0, padx=5, pady=5)
        self.platform_var = tk.StringVar(value=self.config['platform'])
        ttk.Radiobutton(config_frame, text="Lichess", variable=self.platform_var,
                       value="lichess").grid(row=0, column=1)
        ttk.Radiobutton(config_frame, text="Chess.com", variable=self.platform_var,
                       value="chess.com").grid(row=0, column=2)
        
        # Color selection
        ttk.Label(config_frame, text="Play as:").grid(row=1, column=0, padx=5, pady=5)
        self.color_var = tk.StringVar(value=self.config['player_color'])
        ttk.Radiobutton(config_frame, text="White", variable=self.color_var,
                       value="white").grid(row=1, column=1)
        ttk.Radiobutton(config_frame, text="Black", variable=self.color_var,
                       value="black").grid(row=1, column=2)
        
        # Board display
        board_frame = ttk.LabelFrame(left_panel, text="Current Position")
        board_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.board_html = HtmlFrame(board_frame)
        self.board_html.pack(fill=tk.BOTH, expand=True)
        self.update_board_svg(chess.Board())
        
        # Right panel
        right_panel = ttk.Frame(main_container)
        main_container.add(right_panel, weight=1)
        
        # Controls
        control_frame = ttk.LabelFrame(right_panel, text="Controls")
        control_frame.pack(fill="x", padx=5, pady=5)
        
        self.start_button = ttk.Button(control_frame, text="Start Bot",
                                     command=self.start_bot)
        self.start_button.pack(side="left", padx=5, pady=5)
        
        self.stop_button = ttk.Button(control_frame, text="Stop Bot",
                                    command=self.stop_bot, state='disabled')
        self.stop_button.pack(side="left", padx=5, pady=5)
        
        # Output
        output_frame = ttk.LabelFrame(right_panel, text="Output")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.output_text = tk.Text(output_frame, height=20, width=40)
        scrollbar = ttk.Scrollbar(output_frame, command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=scrollbar.set)
        self.output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def update_board_svg(self, board):
        try:
            svg = chess.svg.board(board, size=400)
            with open("temp_board.svg", "w") as f:
                f.write(svg)
            self.board_html.set_content(open("temp_board.svg").read())
        except Exception as e:
            self.log_message(f"Error updating board: {e}")

    def start_bot(self):
        if not os.getenv('GROK_API_KEY'):
            messagebox.showerror("Error", "Please set GROK_API_KEY in .env file")
            return

        try:
            self.config['platform'] = self.platform_var.get()
            self.config['player_color'] = self.color_var.get()
            self.save_config()
            
            self.bot = ChessBot(self.config)
            self.start_button['state'] = 'disabled'
            self.stop_button['state'] = 'normal'
            self.log_message("Bot started")
            
            Thread(target=self.run_bot, daemon=True).start()
            self.root.after(100, self.process_bot_messages)
            
        except Exception as e:
            self.log_message(f"Error: {e}")
            messagebox.showerror("Error", str(e))

    def run_bot(self):
        try:
            self.bot.start()
        except Exception as e:
            self.root.after(0, self.log_message, f"Bot error: {e}")

    def process_bot_messages(self):
        try:
            while True:
                msg_type, msg = self.bot.message_queue.get_nowait()
                
                if msg_type == 'board_update':
                    self.update_board_svg(msg)
                elif msg_type in ['suggestion', 'info', 'error']:
                    self.log_message(msg)
                    
        except queue.Empty:
            pass
        
        if self.bot and self.bot.running:
            self.root.after(100, self.process_bot_messages)

    def stop_bot(self):
        if self.bot:
            self.bot.running = False
            self.bot = None
            self.start_button['state'] = 'normal'
            self.stop_button['state'] = 'disabled'
            self.log_message("Bot stopped")

    def log_message(self, message):
        self.output_text.insert(tk.END, f"{message}\n")
        self.output_text.see(tk.END)

    def load_config(self):
        try:
            if os.path.exists('chess_bot_config.json'):
                with open('chess_bot_config.json', 'r') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
        except Exception as e:
            self.log_message(f"Error loading config: {e}")

    def save_config(self):
        try:
            with open('chess_bot_config.json', 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            self.log_message(f"Error saving config: {e}")

    def on_closing(self):
        self.stop_bot()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = ChessBotGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()