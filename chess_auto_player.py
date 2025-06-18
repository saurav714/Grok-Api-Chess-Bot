import chess
import chess.svg
import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
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
            'grok_api_key': '',
            'platform': 'lichess',  # or 'chess.com'
            'browser': 'chrome',
            'player_color': 'white'
        }
        self.board = chess.Board()
        self.load_config()

    def load_config(self):
        try:
            if os.path.exists('chess_bot_config.json'):
                with open('chess_bot_config.json', 'r') as f:
                    self.config.update(json.load(f))
        except Exception as e:
            logger.error(f"Error loading config: {e}")

    def initialize_browser(self):
        try:
            if self.config['browser'].lower() == 'chrome':
                options = webdriver.ChromeOptions()
                options.add_argument('--start-maximized')
                self.driver = webdriver.Chrome(options=options)
            else:
                options = webdriver.FirefoxOptions()
                options.add_argument('--start-maximized')
                self.driver = webdriver.Firefox(options=options)
            
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
                # Wait for chess board to be present
                board_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.cg-board'))
                )
                # Get FEN from board data attribute
                fen = board_element.get_attribute('data-fen')
                if not fen:
                    # Fallback to piece positions
                    pieces = self.driver.find_elements(By.CSS_SELECTOR, '.cg-board piece')
                    fen = self.construct_fen_from_pieces(pieces)
            else:
                # Chess.com implementation
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
            # Implementation depends on the platform's HTML structure
            # This is a simplified example
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
            for piece_code, fen_char in piece_map.items():
                if piece_code in class_name.lower():
                    return fen_char
            return ''
        except Exception as e:
            logger.error(f"Error extracting piece type: {e}")
            return ''

    def board_to_fen(self, board):
        fen = []
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
            fen.append(rank_fen)
        return '/'.join(fen)

    def get_best_move(self, fen):
        try:
            prompt = (
                f"Given FEN: {fen}, suggest the best move for "
                f"{'White' if self.board.turn else 'Black'} "
                f"in standard algebraic notation (like e4 or Nf3)."
            )
            
            headers = {
                "Authorization": f"Bearer {self.config['grok_api_key']}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "grok-3",
                "prompt": prompt,
                "max_tokens": 50,
                "temperature": 0.7
            }
            
            response = requests.post(
                "https://api.x.ai/v1/grok",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                move = response.json()['choices'][0]['text'].strip()
                return self.validate_move(move)
            else:
                logger.error(f"API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting best move: {e}")
            return None

    def validate_move(self, move_text):
        try:
            # Clean up the move text
            move = move_text.split()[0].strip()
            # Validate the move
            move_obj = self.board.parse_san(move)
            if self.board.is_legal(move_obj):
                return move
            return None
        except Exception as e:
            logger.error(f"Move validation error: {e}")
            return None

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
            actions.move_to_element(to_element)
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
            return
        
        try:
            while True:
                current_fen = self.get_current_position()
                if not current_fen:
                    time.sleep(1)
                    continue
                
                # Update internal board
                self.board = chess.Board(current_fen)
                
                # Check if it's our turn
                if self.board.turn == (self.config['player_color'] == 'white'):
                    best_move = self.get_best_move(current_fen)
                    if best_move:
                        move_obj = self.board.parse_san(best_move)
                        self.play_move(move_obj)
                    
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Runtime error: {e}")
        finally:
            if self.driver:
                self.driver.quit()

class ChessBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Chess Browser Bot")
        self.bot = None
        self.create_widgets()

    def create_widgets(self):
        # Configuration Frame
        config_frame = ttk.LabelFrame(self.root, text="Configuration")
        config_frame.pack(padx=10, pady=5, fill="x")

        # API Key
        ttk.Label(config_frame, text="Grok API Key:").grid(row=0, column=0, padx=5, pady=5)
        self.api_key_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.api_key_var, show="*").grid(row=0, column=1, padx=5, pady=5)

        # Platform Selection
        ttk.Label(config_frame, text="Platform:").grid(row=1, column=0, padx=5, pady=5)
        self.platform_var = tk.StringVar(value="lichess")
        ttk.Radiobutton(config_frame, text="Lichess", variable=self.platform_var, value="lichess").grid(row=1, column=1)
        ttk.Radiobutton(config_frame, text="Chess.com", variable=self.platform_var, value="chess.com").grid(row=1, column=2)

        # Color Selection
        ttk.Label(config_frame, text="Play as:").grid(row=2, column=0, padx=5, pady=5)
        self.color_var = tk.StringVar(value="white")
        ttk.Radiobutton(config_frame, text="White", variable=self.color_var, value="white").grid(row=2, column=1)
        ttk.Radiobutton(config_frame, text="Black", variable=self.color_var, value="black").grid(row=2, column=2)

        # Control Buttons
        control_frame = ttk.Frame(self.root)
        control_frame.pack(pady=10)
        ttk.Button(control_frame, text="Start Bot", command=self.start_bot).pack(side="left", padx=5)
        ttk.Button(control_frame, text="Stop Bot", command=self.stop_bot).pack(side="left", padx=5)

        # Status
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var).pack(pady=5)

    def start_bot(self):
        try:
            config = {
                'grok_api_key': self.api_key_var.get(),
                'platform': self.platform_var.get(),
                'player_color': self.color_var.get()
            }
            
            with open('chess_bot_config.json', 'w') as f:
                json.dump(config, f)
            
            self.bot = ChessBrowserBot()
            self.status_var.set("Bot started")
            self.bot.run()
            
        except Exception as e:
            self.status_var.set(f"Error: {e}")
            messagebox.showerror("Error", str(e))

    def stop_bot(self):
        if self.bot and self.bot.driver:
            self.bot.driver.quit()
            self.bot = None
            self.status_var.set("Bot stopped")

def main():
    root = tk.Tk()
    app = ChessBotGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()