import tkinter as tk
from tkinter import ttk, messagebox
import chess
import chess.svg
from chess_browser_helper import ChessBrowserHelper
import logging
from logging.handlers import RotatingFileHandler
import json
import os
from threading import Thread
import queue
import time
import requests
from tkinterhtml import HtmlFrame
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [Chess Suggester] %(message)s',
    handlers=[
        RotatingFileHandler('chess_suggester.log', maxBytes=10*1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ChessSuggesterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Chess Move Suggester")
        self.root.geometry("1200x800")
        
        self.config = {
            'grok_api_key': os.getenv('GROK_API_KEY', ''),
            'platform': 'lichess',
            'check_interval': 2.0,
            'player_color': 'white'
        }
        
        self.browser_helper = None
        self.board = chess.Board()
        self.running = False
        self.message_queue = queue.Queue()
        
        self.load_config()
        self.create_widgets()
        self.root.after(100, self.process_queue)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        # Main container
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel - Board and Controls
        left_panel = ttk.Frame(main_container)
        main_container.add(left_panel, weight=1)
        
        # Control frame
        control_frame = ttk.LabelFrame(left_panel, text="Controls")
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(control_frame, text="Platform:").grid(row=0, column=0, padx=5, pady=5)
        self.platform_var = tk.StringVar(value=self.config['platform'])
        platform_combo = ttk.Combobox(control_frame, textvariable=self.platform_var,
                                    values=['lichess', 'chess.com'], state='readonly')
        platform_combo.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(control_frame, text="Play as:").grid(row=1, column=0, padx=5, pady=5)
        self.color_var = tk.StringVar(value=self.config['player_color'])
        color_combo = ttk.Combobox(control_frame, textvariable=self.color_var,
                                 values=['white', 'black'], state='readonly')
        color_combo.grid(row=1, column=1, padx=5, pady=5)
        
        self.start_button = ttk.Button(control_frame, text="Start", command=self.start_suggester)
        self.start_button.grid(row=2, column=0, padx=5, pady=5)
        
        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_suggester)
        self.stop_button.grid(row=2, column=1, padx=5, pady=5)
        self.stop_button['state'] = 'disabled'
        
        # Board frame
        board_frame = ttk.LabelFrame(left_panel, text="Current Position")
        board_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.board_html = HtmlFrame(board_frame)
        self.board_html.pack(fill=tk.BOTH, expand=True)
        self.update_board_svg(self.board)
        
        # Right panel - Suggestions and Logs
        right_panel = ttk.Notebook(main_container)
        main_container.add(right_panel, weight=1)
        
        # Suggestions tab
        suggestions_frame = ttk.Frame(right_panel)
        right_panel.add(suggestions_frame, text="Suggestions")
        
        self.suggestions_text = tk.Text(suggestions_frame, wrap=tk.WORD, height=20)
        suggestions_scroll = ttk.Scrollbar(suggestions_frame, command=self.suggestions_text.yview)
        self.suggestions_text.configure(yscrollcommand=suggestions_scroll.set)
        self.suggestions_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        suggestions_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Logs tab
        logs_frame = ttk.Frame(right_panel)
        right_panel.add(logs_frame, text="Logs")
        
        self.log_text = tk.Text(logs_frame, wrap=tk.WORD, height=20)
        log_scroll = ttk.Scrollbar(logs_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def start_suggester(self):
        if not self.config['grok_api_key']:
            messagebox.showerror("Error", "Please set GROK_API_KEY in .env file")
            return
            
        self.running = True
        self.start_button['state'] = 'disabled'
        self.stop_button['state'] = 'normal'
        
        # Initialize browser helper
        self.browser_helper = ChessBrowserHelper(self.platform_var.get())
        if not self.browser_helper.initialize():
            messagebox.showerror("Error", "Failed to initialize browser")
            self.stop_suggester()
            return
            
        Thread(target=self.suggester_loop, daemon=True).start()
        logger.info("Suggester started")

    def stop_suggester(self):
        self.running = False
        if self.browser_helper:
            self.browser_helper.cleanup()
            self.browser_helper = None
        
        self.start_button['state'] = 'normal'
        self.stop_button['state'] = 'disabled'
        logger.info("Suggester stopped")

    def suggester_loop(self):
        last_fen = None
        
        while self.running:
            try:
                current_fen = self.browser_helper.get_current_position()
                if not current_fen:
                    time.sleep(self.config['check_interval'])
                    continue
                
                if current_fen != last_fen:
                    logger.info(f"New position detected: {current_fen}")
                    self.board = chess.Board(current_fen)
                    self.message_queue.put(('board_update', self.board))
                    
                    # Check if it's our turn
                    is_our_turn = (self.board.turn == chess.WHITE and 
                                 self.color_var.get() == 'white') or \
                                (self.board.turn == chess.BLACK and 
                                 self.color_var.get() == 'black')
                    
                    if is_our_turn:
                        move, explanation = self.get_move_suggestion(current_fen)
                        if move:
                            self.message_queue.put(('suggestion', 
                                f"Suggested move: {move}\n\nExplanation: {explanation}\n"))
                    
                    last_fen = current_fen
                
                time.sleep(self.config['check_interval'])
                
            except Exception as e:
                logger.error(f"Error in suggester loop: {e}")
                self.message_queue.put(('error', str(e)))
                time.sleep(self.config['check_interval'])

    def get_move_suggestion(self, fen):
        try:
            headers = {
                "Authorization": f"Bearer {self.config['grok_api_key']}",
                "Content-Type": "application/json"
            }
            
            color = "White" if self.board.turn else "Black"
            prompt = (
                f"Given this chess position (FEN): {fen}\n"
                f"Suggest the best move for {color} and explain why.\n"
                f"Format: Best move in algebraic notation (e.g., e4, Nf3) "
                f"followed by a brief explanation."
            )
            
            payload = {
                "model": "grok-3",
                "prompt": prompt,
                "max_tokens": 200,
                "temperature": 0.7
            }
            
            response = requests.post(
                "https://api.x.ai/v1/grok",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()['choices'][0]['text'].strip()
                # Extract move and explanation
                lines = result.split('\n')
                move = lines[0].split()[-1]
                explanation = '\n'.join(lines[1:]).strip()
                
                # Validate move
                try:
                    chess.Board(fen).parse_san(move)
                    return move, explanation
                except ValueError:
                    logger.warning(f"Invalid move suggested: {move}")
                    return None, "Invalid move suggested"
            else:
                logger.error(f"API error: {response.status_code}")
                return None, f"API error: {response.status_code}"
                
        except Exception as e:
            logger.error(f"Error getting move suggestion: {e}")
            return None, str(e)

    def update_board_svg(self, board):
        try:
            svg = chess.svg.board(board, size=600)
            with open("temp_board.svg", "w") as f:
                f.write(svg)
            self.board_html.set_content(open("temp_board.svg").read())
        except Exception as e:
            logger.error(f"Error updating board display: {e}")

    def process_queue(self):
        try:
            while True:
                message_type, data = self.message_queue.get_nowait()
                
                if message_type == 'board_update':
                    self.update_board_svg(data)
                elif message_type == 'suggestion':
                    self.suggestions_text.insert(tk.END, f"\n{data}")
                    self.suggestions_text.see(tk.END)
                elif message_type == 'error':
                    self.log_text.insert(tk.END, f"ERROR: {data}\n")
                    self.log_text.see(tk.END)
                    
        except queue.Empty:
            pass
        
        if self.running:
            self.root.after(100, self.process_queue)

    def load_config(self):
        try:
            if os.path.exists('chess_suggester_config.json'):
                with open('chess_suggester_config.json', 'r') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
        except Exception as e:
            logger.error(f"Error loading config: {e}")

    def save_config(self):
        try:
            self.config['platform'] = self.platform_var.get()
            self.config['player_color'] = self.color_var.get()
            
            with open('chess_suggester_config.json', 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def on_closing(self):
        self.stop_suggester()
        self.save_config()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = ChessSuggesterGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()