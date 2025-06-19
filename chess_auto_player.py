import chess
import chess.svg
import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import logging
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from PIL import Image
import io
import base64
from threading import Thread
import queue
from tkinterhtml import HtmlFrame
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [Chess Bot] %(message)s',
    handlers=[
        logging.FileHandler('chess_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ChessBrowserBot:
    def __init__(self):
        self.driver = None
        self.config = {
            'platform': 'lichess',  # or 'chess.com'
            'browser': 'chrome',
            'player_color': 'white'
        }
        self.board = chess.Board()
        self.grok_api_key = os.getenv('GROK_API_KEY')
        self.load_config()
        self.message_queue = queue.Queue()

    def load_config(self):
        try:
            if os.path.exists('chess_bot_config.json'):
                with open('chess_bot_config.json', 'r') as f:
                    saved_config = json.load(f)
                    # Only load non-sensitive settings
                    for key in ['platform', 'browser', 'player_color']:
                        if key in saved_config:
                            self.config[key] = saved_config[key]
        except Exception as e:
            logger.error(f"Error loading config: {e}")

    def initialize_browser(self):
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--start-maximized')
            options.add_experimental_option('excludeSwitches', ['enable-automation'])
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            
            # Navigate to chess platform
            if self.config['platform'] == 'lichess':
                self.driver.get('https://lichess.org/')
            else:
                self.driver.get('https://chess.com/play/online')
            
            logger.info(f"Browser initialized for {self.config['platform']}")
            return True
        except Exception as e:
            logger.error(f"Browser initialization error: {e}")
            return False

    def get_current_position(self):
        try:
            if self.config['platform'] == 'lichess':
                board_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.cg-board'))
                )
                fen = board_element.get_attribute('data-fen')
                if not fen:
                    pieces = self.driver.find_elements(By.CSS_SELECTOR, '.cg-board piece')
                    fen = self.construct_fen_from_pieces(pieces)
            else:
                board_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.board'))
                )
                pieces = self.driver.find_elements(By.CSS_SELECTOR, '.piece')
                fen = self.construct_fen_from_pieces(pieces)

            return fen
        except Exception as e:
            logger.error(f"Error getting position: {e}")
            return None

    def construct_fen_from_pieces(self, pieces):
        board = [['' for _ in range(8)] for _ in range(8)]
        
        for piece in pieces:
            try:
                class_name = piece.get_attribute('class')
                coords = self.extract_coordinates(class_name)
                piece_type = self.extract_piece_type(class_name)
                if coords and piece_type:
                    x, y = coords
                    board[y][x] = piece_type
            except Exception as e:
                logger.error(f"Error processing piece: {e}")

        return self.board_to_fen(board)

    def extract_coordinates(self, class_name):
        try:
            if 'square-' in class_name:
                square = class_name.split('square-')[1].split()[0]
                file = ord(square[0]) - ord('a')
                rank = 8 - int(square[1])
                return file, rank
            return None
        except Exception as e:
            logger.error(f"Error extracting coordinates: {e}")
            return None

    def extract_piece_type(self, class_name):
        piece_map = {
            'wp': 'P', 'wr': 'R', 'wn': 'N', 'wb': 'B', 'wq': 'Q', 'wk': 'K',
            'bp': 'p', 'br': 'r', 'bn': 'n', 'bb': 'b', 'bq': 'q', 'bk': 'k'
        }
        try:
            class_name = class_name.lower()
            for piece_code, fen_char in piece_map.items():
                if piece_code in class_name:
                    return fen_char
            return ''
        except Exception as e:
            logger.error(f"Error extracting piece type: {e}")
            return ''

    def board_to_fen(self, board):
        try:
            fen_rows = []
            for rank in board:
                empty = 0
                rank_fen = ''
                for square in rank:
                    if square == '':
                        empty += 1
                    else:
                        if empty > 0:
                            rank_fen += str(empty)
                            empty = 0
                        rank_fen += square
                if empty > 0:
                    rank_fen += str(empty)
                fen_rows.append(rank_fen)
            
            fen = '/'.join(fen_rows)
            return f"{fen} w KQkq - 0 1"  # Add default state
        except Exception as e:
            logger.error(f"Error constructing FEN: {e}")
            return chess.STARTING_FEN

    def get_best_move(self, fen):
        try:
            if not self.grok_api_key:
                logger.error("Grok API key not found in environment")
                return None, "API key not found"

            headers = {
                "Authorization": f"Bearer {self.grok_api_key}",
                "Content-Type": "application/json"
            }
            
            prompt = (
                f"Given FEN: {fen}, suggest the best move for "
                f"{'White' if self.board.turn else 'Black'} "
                f"in standard algebraic notation (like e4 or Nf3) "
                f"and explain why in a brief sentence."
            )
            
            payload = {
                "model": "grok-3",
                "prompt": prompt,
                "max_tokens": 100,
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
                # Try to extract move and explanation
                parts = result.split('\n', 1)
                move = parts[0].split()[-1].strip()
                explanation = parts[1].strip() if len(parts) > 1 else ""
                
                if self.validate_move(move):
                    return move, explanation
                return None, "Invalid move suggested"
            else:
                logger.error(f"API error: {response.status_code}")
                return None, f"API error: {response.status_code}"
                
        except Exception as e:
            logger.error(f"Error getting best move: {e}")
            return None, str(e)

    def validate_move(self, move_text):
        try:
            move = move_text.split()[0].strip()
            move_obj = self.board.parse_san(move)
            return self.board.is_legal(move_obj)
        except Exception:
            return False

    def play_move(self, move):
        try:
            # Convert move to coordinates
            from_square = chess.square_name(move.from_square)
            to_square = chess.square_name(move.to_square)
            
            # Find source and destination elements
            if self.config['platform'] == 'lichess':
                from_selector = f".square-{from_square}"
                to_selector = f".square-{to_square}"
            else:
                from_selector = f"[data-square='{from_square}']"
                to_selector = f"[data-square='{to_square}']"
            
            from_element = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, from_selector))
            )
            to_element = self.driver.find_element(By.CSS_SELECTOR, to_selector)
            
            # Execute move
            actions = ActionChains(self.driver)
            actions.move_to_element(from_element)
            actions.click_and_hold()
            time.sleep(0.2)  # Small delay for more natural movement
            actions.move_to_element(to_element)
            time.sleep(0.1)
            actions.release()
            actions.perform()
            
            # Update internal board
            self.board.push(move)
            logger.info(f"Move played: {move}")
            return True
            
        except Exception as e:
            logger.error(f"Error playing move: {e}")
            return False

    def run(self):
        if not self.initialize_browser():
            self.message_queue.put(('error', "Failed to initialize browser"))
            return
        
        try:
            while True:
                current_fen = self.get_current_position()
                if not current_fen:
                    time.sleep(1)
                    continue
                
                # Update internal board
                self.board = chess.Board(current_fen)
                self.message_queue.put(('board_update', self.board))
                
                # Check if it's our turn
                if self.board.turn == (self.config['player_color'] == 'white'):
                    move, explanation = self.get_best_move(current_fen)
                    if move:
                        self.message_queue.put(('suggestion', f"Suggested: {move}\n{explanation}"))
                        move_obj = self.board.parse_san(move)
                        if self.play_move(move_obj):
                            self.message_queue.put(('info', f"Played move: {move}"))
                    
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Runtime error: {e}")
            self.message_queue.put(('error', str(e)))
        finally:
            if self.driver:
                self.driver.quit()

class ChessBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Chess Browser Bot")
        self.root.geometry("1000x600")
        self.bot = None
        self.create_widgets()

    def create_widgets(self):
        # Main container
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel - Configuration and Board
        left_panel = ttk.Frame(main_container)
        main_container.add(left_panel, weight=1)
        
        # Configuration Frame
        config_frame = ttk.LabelFrame(left_panel, text="Configuration")
        config_frame.pack(fill="x", padx=5, pady=5)

        # API Key Status
        ttk.Label(config_frame, text="Grok API Key:").grid(row=0, column=0, padx=5, pady=5)
        api_key_status = "Set" if os.getenv('GROK_API_KEY') else "Not Set"
        ttk.Label(config_frame, text=api_key_status).grid(row=0, column=1, padx=5, pady=5)

        # Platform Selection
        ttk.Label(config_frame, text="Platform:").grid(row=1, column=0, padx=5, pady=5)
        self.platform_var = tk.StringVar(value="lichess")
        ttk.Radiobutton(config_frame, text="Lichess", variable=self.platform_var, 
                       value="lichess").grid(row=1, column=1)
        ttk.Radiobutton(config_frame, text="Chess.com", variable=self.platform_var,
                       value="chess.com").grid(row=1, column=2)

        # Color Selection
        ttk.Label(config_frame, text="Play as:").grid(row=2, column=0, padx=5, pady=5)
        self.color_var = tk.StringVar(value="white")
        ttk.Radiobutton(config_frame, text="White", variable=self.color_var,
                       value="white").grid(row=2, column=1)
        ttk.Radiobutton(config_frame, text="Black", variable=self.color_var,
                       value="black").grid(row=2, column=2)

        # Board Display
        board_frame = ttk.LabelFrame(left_panel, text="Current Position")
        board_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.board_html = HtmlFrame(board_frame)
        self.board_html.pack(fill=tk.BOTH, expand=True)
        self.update_board_svg(chess.Board())

        # Right panel - Controls and Output
        right_panel = ttk.Frame(main_container)
        main_container.add(right_panel, weight=1)
        
        # Control Buttons
        control_frame = ttk.LabelFrame(right_panel, text="Controls")
        control_frame.pack(fill="x", padx=5, pady=5)
        self.start_button = ttk.Button(control_frame, text="Start Bot", 
                                     command=self.start_bot)
        self.start_button.pack(side="left", padx=5, pady=5)
        self.stop_button = ttk.Button(control_frame, text="Stop Bot",
                                    command=self.stop_bot, state='disabled')
        self.stop_button.pack(side="left", padx=5, pady=5)

        # Status and Output
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
            logger.error(f"Error updating board display: {e}")

    def start_bot(self):
        if not os.getenv('GROK_API_KEY'):
            messagebox.showerror("Error", "Please set GROK_API_KEY in .env file")
            return

        try:
            config = {
                'platform': self.platform_var.get(),
                'player_color': self.color_var.get()
            }
            
            with open('chess_bot_config.json', 'w') as f:
                json.dump(config, f)
            
            self.bot = ChessBrowserBot()
            self.start_button['state'] = 'disabled'
            self.stop_button['state'] = 'normal'
            self.log_message("Bot started")
            
            Thread(target=self.run_bot_with_queue, daemon=True).start()
            
        except Exception as e:
            self.log_message(f"Error: {e}")
            messagebox.showerror("Error", str(e))

    def run_bot_with_queue(self):
        try:
            self.bot.run()
            while True:
                try:
                    msg_type, msg = self.bot.message_queue.get_nowait()
                    self.root.after(0, self.handle_message, msg_type, msg)
                except queue.Empty:
                    time.sleep(0.1)
        except Exception as e:
            self.root.after(0, self.log_message, f"Bot error: {e}")

    def handle_message(self, msg_type, msg):
        if msg_type == 'board_update':
            self.update_board_svg(msg)
        elif msg_type in ['suggestion', 'info', 'error']:
            self.log_message(msg)

    def stop_bot(self):
        if self.bot:
            if self.bot.driver:
                self.bot.driver.quit()
            self.bot = None
            self.start_button['state'] = 'normal'
            self.stop_button['state'] = 'disabled'
            self.log_message("Bot stopped")

    def log_message(self, message):
        self.output_text.insert(tk.END, f"{message}\n")
        self.output_text.see(tk.END)

    def on_closing(self):
        self.stop_bot()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = ChessBotGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()