import chess
import chess.svg
import cv2
import numpy as np
import pyautogui
import requests
import time
from mss import mss
from PIL import Image
import logging
from logging.handlers import RotatingFileHandler
import tkinter as tk
from tkinter import ttk, messagebox
import os
import json
from threading import Thread
import queue
from tkinterhtml import HtmlFrame

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [Auto-Player] %(message)s',
    handlers=[
        RotatingFileHandler('chess_bot.log', maxBytes=10*1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ChessBoardDetector:
    def __init__(self, platform="lichess"):
        self.piece_templates = {}
        self.board_corners = None
        self.square_size = 80
        self.platform = platform
        self.load_piece_templates()
    
    def load_piece_templates(self):
        template_dir = f"piece_templates_{self.platform.lower()}"
        if not os.path.exists(template_dir):
            logger.warning(f"Template directory {template_dir} not found. Creating empty templates.")
            os.makedirs(template_dir, exist_ok=True)
            return
        
        piece_names = ['wp', 'wr', 'wn', 'wb', 'wq', 'wk', 'bp', 'br', 'bn', 'bb', 'bq', 'bk']
        for piece in piece_names:
            template_path = os.path.join(template_dir, f"{piece}.png")
            if os.path.exists(template_path):
                template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
                if template is not None:
                    self.piece_templates[piece] = template
                    logger.info(f"Loaded template for {piece}")
                else:
                    logger.warning(f"Failed to load template: {template_path}")
            else:
                logger.warning(f"Template not found: {template_path}")
    
    def detect_board_corners(self, image, min_area=10000):
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_MEAN_C, 
                                         cv2.THRESH_BINARY, 11, 2)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            board_candidates = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > min_area:
                    epsilon = 0.02 * cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, epsilon, True)
                    if len(approx) == 4:
                        x, y, w, h = cv2.boundingRect(approx)
                        aspect_ratio = float(w) / h
                        if 0.8 <= aspect_ratio <= 1.2:
                            board_candidates.append((area, approx))
            
            if board_candidates:
                _, corners = max(board_candidates, key=lambda x: x[0])
                corners = corners.reshape(4, 2)
                ordered_corners = self.order_corners(corners)
                self.board_corners = ordered_corners
                self.calculate_square_size(ordered_corners)
                logger.info(f"Board detected with corners: {ordered_corners}")
                return ordered_corners
            else:
                logger.warning("No board detected")
                return None
                
        except Exception as e:
            logger.error(f"Error detecting board corners: {e}")
            return None
    
    def order_corners(self, corners):
        centroid = np.mean(corners, axis=0)
        angles = np.arctan2(corners[:, 1] - centroid[1], corners[:, 0] - centroid[0])
        sorted_indices = np.argsort(angles)
        ordered = corners[sorted_indices]
        sums = np.sum(ordered, axis=1)
        top_left_idx = np.argmin(sums)
        ordered = np.roll(ordered, -top_left_idx, axis=0)
        return ordered
    
    def calculate_square_size(self, corners):
        try:
            width = np.linalg.norm(corners[1] - corners[0])
            height = np.linalg.norm(corners[3] - corners[0])
            self.square_size = int((width + height) / 16)
            logger.info(f"Calculated square size: {self.square_size}")
        except Exception as e:
            logger.error(f"Error calculating square size: {e}")
            self.square_size = 80
    
    def extract_square(self, image, file_idx, rank_idx):
        try:
            if self.board_corners is None:
                logger.error("Board corners not detected")
                return None
            
            corners = self.board_corners
            x_ratio = file_idx / 8.0
            y_ratio = rank_idx / 8.0
            top_left = corners[0] + x_ratio * (corners[1] - corners[0]) + y_ratio * (corners[3] - corners[0])
            top_right = corners[0] + (x_ratio + 1/8) * (corners[1] - corners[0]) + y_ratio * (corners[3] - corners[0])
            bottom_left = corners[0] + x_ratio * (corners[1] - corners[0]) + (y_ratio + 1/8) * (corners[3] - corners[0])
            bottom_right = corners[0] + (x_ratio + 1/8) * (corners[1] - corners[0]) + (y_ratio + 1/8) * (corners[3] - corners[0])
            
            square_corners = np.array([top_left, top_right, bottom_right, bottom_left], dtype=np.float32)
            dst_size = 64
            dst_corners = np.array([[0, 0], [dst_size, 0], [dst_size, dst_size], [0, dst_size]], dtype=np.float32)
            transform_matrix = cv2.getPerspectiveTransform(square_corners, dst_corners)
            square = cv2.warpPerspective(image, transform_matrix, (dst_size, dst_size))
            return square
            
        except Exception as e:
            logger.error(f"Error extracting square at {file_idx}, {rank_idx}: {e}")
            return None
    
    def identify_piece(self, square_image):
        if square_image is None or len(self.piece_templates) == 0:
            logger.warning("No templates or invalid square")
            return '.'
        
        try:
            gray_square = cv2.cvtColor(square_image, cv2.COLOR_BGR2GRAY) if len(square_image.shape) == 3 else square_image
            best_match = '.'
            best_score = 0.8
            
            for piece_name, template in self.piece_templates.items():
                template_resized = cv2.resize(template, (gray_square.shape[1], gray_square.shape[0]))
                result = cv2.matchTemplate(gray_square, template_resized, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                if max_val > best_score:
                    best_score = max_val
                    best_match = self.piece_name_to_fen(piece_name)
                    logger.debug(f"Piece {piece_name} matched with score {max_val}")
            
            if best_match == '.':
                logger.debug("No piece matched; empty square")
            return best_match
            
        except Exception as e:
            logger.error(f"Error identifying piece: {e}")
            return '.'
    
    def piece_name_to_fen(self, piece_name):
        mapping = {
            'wp': 'P', 'wr': 'R', 'wn': 'N', 'wb': 'B', 'wq': 'Q', 'wk': 'K',
            'bp': 'p', 'br': 'r', 'bn': 'n', 'bb': 'b', 'bq': 'q', 'bk': 'k'
        }
        return mapping.get(piece_name, '.')
    
    def detect_board_to_fen(self, image):
        try:
            if self.board_corners is None:
                self.detect_board_corners(image)
            
            if self.board_corners is None:
                logger.error("Could not detect board")
                return chess.Board().fen()
            
            fen_rows = []
            for rank in range(8):
                row_pieces = []
                for file in range(8):
                    square = self.extract_square(image, file, rank)
                    piece = self.identify_piece(square)
                    row_pieces.append(piece)
                
                fen_row = ''
                empty_count = 0
                for piece in row_pieces:
                    if piece == '.':
                        empty_count += 1
                    else:
                        if empty_count > 0:
                            fen_row += str(empty_count)
                            empty_count = 0
                        fen_row += piece
                if empty_count > 0:
                    fen_row += str(empty_count)
                fen_rows.append(fen_row)
            
            fen_position = '/'.join(fen_rows)
            fen_string = f"{fen_position} w KQkq - 0 1"
            
            try:
                chess.Board(fen_string)
                logger.info(f"Generated FEN: {fen_string}")
                return fen_string
            except ValueError as e:
                logger.error(f"Invalid FEN generated: {fen_string}, error: {e}")
                return chess.Board().fen()
                
        except Exception as e:
            logger.error(f"Error in detect_board_to_fen: {e}")
            return chess.Board().fen()

class ChessAutoPlayerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Chess Auto Player")
        self.root.geometry("1000x600")
        self.platform = "lichess"
        self.detector = ChessBoardDetector(self.platform)
        self.board = chess.Board()
        self.running = False
        self.auto_play = False
        self.config = {
            'grok_api_key': '',
            'screen_region': (100, 100, 800, 800),
            'check_interval': 2,
            'player_color': chess.WHITE,
            'platform': 'lichess'
        }
        self.load_config()
        self.create_widgets()
        self.message_queue = queue.Queue()
        self.root.after(100, self.process_queue)
    
    def create_widgets(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text="Configuration")
        self.create_config_tab(config_frame)
        monitor_frame = ttk.Frame(notebook)
        notebook.add(monitor_frame, text="Monitoring")
        self.create_monitor_tab(monitor_frame)
        logs_frame = ttk.Frame(notebook)
        notebook.add(logs_frame, text="Logs")
        self.create_logs_tab(logs_frame)
    
    def create_config_tab(self, parent):
        api_frame = ttk.LabelFrame(parent, text="API Configuration")
        api_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(api_frame, text="Grok API Key:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.api_key_var = tk.StringVar(value=self.config['grok_api_key'])
        api_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, width=50, show='*')
        api_entry.grid(row=0, column=1, padx=5, pady=5)
        
        region_frame = ttk.LabelFrame(parent, text="Screen Region")
        region_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(region_frame, text="X:").grid(row=0, column=0, padx=5, pady=5)
        self.x_var = tk.StringVar(value=str(self.config['screen_region'][0]))
        ttk.Entry(region_frame, textvariable=self.x_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(region_frame, text="Y:").grid(row=0, column=2, padx=5, pady=5)
        self.y_var = tk.StringVar(value=str(self.config['screen_region'][1]))
        ttk.Entry(region_frame, textvariable=self.y_var, width=10).grid(row=0, column=3, padx=5, pady=5)
        ttk.Label(region_frame, text="Width:").grid(row=1, column=0, padx=5, pady=5)
        self.width_var = tk.StringVar(value=str(self.config['screen_region'][2]))
        ttk.Entry(region_frame, textvariable=self.width_var, width=10).grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(region_frame, text="Height:").grid(row=1, column=2, padx=5, pady=5)
        self.height_var = tk.StringVar(value=str(self.config['screen_region'][3]))
        ttk.Entry(region_frame, textvariable=self.height_var, width=10).grid(row=1, column=3, padx=5, pady=5)
        ttk.Button(region_frame, text="Select Region", command=self.select_region).grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(region_frame, text="Test Detection", command=self.test_detection).grid(row=2, column=2, columnspan=2, pady=10)
        
        bot_frame = ttk.LabelFrame(parent, text="Bot Configuration")
        bot_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(bot_frame, text="Check Interval (seconds):").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.interval_var = tk.StringVar(value=str(self.config['check_interval']))
        ttk.Entry(bot_frame, textvariable=self.interval_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(bot_frame, text="Player Color:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.color_var = tk.StringVar(value="White" if self.config['player_color'] == chess.WHITE else "Black")
        color_combo = ttk.Combobox(bot_frame, textvariable=self.color_var, values=["White", "Black"], state="readonly")
        color_combo.grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(bot_frame, text="Platform:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.platform_var = tk.StringVar(value=self.config['platform'].capitalize())
        platform_combo = ttk.Combobox(bot_frame, textvariable=self.platform_var, values=["Lichess", "Chess.com"], state="readonly")
        platform_combo.grid(row=2, column=1, padx=5, pady=5)
        
        template_frame = ttk.LabelFrame(parent, text="Piece Templates")
        template_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(template_frame, text="Load Templates", command=self.load_templates).pack(side='left', padx=5, pady=5)
        ttk.Button(template_frame, text="Create Templates", command=self.create_templates).pack(side='left', padx=5, pady=5)
        
        ttk.Button(parent, text="Save Configuration", command=self.save_config).pack(pady=10)
    
    def create_monitor_tab(self, parent):
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill='x', padx=5, pady=5)
        self.start_button = ttk.Button(control_frame, text="Start Auto-Player", command=self.start_player)
        self.start_button.pack(side='left', padx=5)
        self.stop_button = ttk.Button(control_frame, text="Stop Auto-Player", command=self.stop_player, state='disabled')
        self.stop_button.pack(side='left', padx=5)
        self.auto_play_var = tk.BooleanVar()
        ttk.Checkbutton(control_frame, text="Auto Play", variable=self.auto_play_var).pack(side='left', padx=5)
        
        status_frame = ttk.LabelFrame(parent, text="Status")
        status_frame.pack(fill='x', padx=5, pady=5)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status_frame, textvariable=self.status_var).pack(padx=5, pady=5)
        
        content_frame = ttk.Frame(parent)
        content_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        board_frame = ttk.LabelFrame(content_frame, text="Board")
        board_frame.pack(side='left', fill='both', expand=True, padx=5)
        self.board_html = HtmlFrame(board_frame)
        self.board_html.pack(fill='both', expand=True)
        self.update_board_svg(self.board)
        
        position_frame = ttk.LabelFrame(content_frame, text="Current Position")
        position_frame.pack(side='right', fill='both', expand=True, padx=5)
        self.position_text = tk.Text(position_frame, height=15, width=30)
        position_scrollbar = ttk.Scrollbar(position_frame, orient='vertical', command=self.position_text.yview)
        self.position_text.configure(yscrollcommand=position_scrollbar.set)
        self.position_text.pack(side='left', fill='both', expand=True)
        position_scrollbar.pack(side='right', fill='y')
    
    def create_logs_tab(self, parent):
        self.log_text = tk.Text(parent, height=25, width=80)
        log_scrollbar = ttk.Scrollbar(parent, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        self.log_text.pack(side='left', fill='both', expand=True)
        log_scrollbar.pack(side='right', fill='y')
        ttk.Button(parent, text="Clear Logs", command=self.clear_logs).pack(pady=5)
    
    def select_region(self):
        messagebox.showinfo("Select Region", "Click OK, then drag to select the chessboard region.")
        # TODO: Implement interactive region selection
    
    def test_detection(self):
        try:
            region = self.get_screen_region()
            screenshot = self.capture_screenshot(region)
            fen = self.detector.detect_board_to_fen(screenshot)
            if self.detector.board_corners is not None:
                messagebox.showinfo("Detection Test", f"Board detected! FEN: {fen}")
            else:
                messagebox.showwarning("Detection Test", "Could not detect board.")
        except Exception as e:
            logger.error(f"Detection test error: {e}")
            messagebox.showerror("Detection Test", f"Error: {e}")
    
    def load_templates(self):
        self.detector = ChessBoardDetector(self.platform_var.get().lower())
        messagebox.showinfo("Templates", f"Loaded {len(self.detector.piece_templates)} piece templates for {self.platform_var.get()}")
    
    def create_templates(self):
        messagebox.showinfo("Create Templates", 
                            "To create templates:\n"
                            "1. Take screenshots of individual pieces\n"
                            "2. Save them in 'piece_templates_{platform}' directory\n"
                            "3. Name them: wp.png, wr.png, wn.png, wb.png, wq.png, wk.png, bp.png, br.png, bn.png, bb.png, bq.png, bk.png")
    
    def get_screen_region(self):
        try:
            return (
                int(self.x_var.get()),
                int(self.y_var.get()),
                int(self.width_var.get()),
                int(self.height_var.get())
            )
        except ValueError as e:
            logger.error(f"Invalid screen region values: {e}")
            return self.config['screen_region']
    
    def capture_screenshot(self, region):
        try:
            with mss() as sct:
                monitor = {"top": region[1], "left": region[0], "width": region[2], "height": region[3]}
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.error(f"Screenshot capture error: {e}")
            return None
    
    def start_player(self):
        if not self.config['grok_api_key']:
            messagebox.showerror("Error", "Please enter a valid Grok API key")
            return
        self.running = True
        self.auto_play = self.auto_play_var.get()
        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.status_var.set("Running...")
        logger.info("Auto-Player started")
        Thread(target=self.player_loop, daemon=True).start()
    
    def stop_player(self):
        self.running = False
        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
        self.status_var.set("Stopped")
        logger.info("Auto-Player stopped")
    
    def player_loop(self):
        last_fen = None
        while self.running:
            try:
                region = self.get_screen_region()
                screenshot = self.capture_screenshot(region)
                if screenshot is None:
                    continue
                fen = self.detector.detect_board_to_fen(screenshot)
                
                if fen != last_fen:
                    logger.info(f"New position detected: {fen}")
                    self.board = chess.Board(fen)
                    self.message_queue.put(('position_update', self.board.unicode()))
                    self.message_queue.put(('board_update', self.board))
                    
                    if self.board.turn == self.config['player_color']:
                        move, explanation = self.get_best_move(fen)
                        if move:
                            self.message_queue.put(('move_suggestion', move))
                            self.message_queue.put(('explanation', explanation))
                            if self.auto_play:
                                move_obj = self.board.parse_san(move)
                                self.play_move(move_obj)
                    
                    last_fen = fen
                
                time.sleep(self.config['check_interval'])
                
            except Exception as e:
                logger.error(f"Error in player loop: {e}")
                self.message_queue.put(('error', str(e)))
    
    def get_best_move(self, fen):
        try:
            prompt = (
                f"Given FEN: {fen}, suggest the best move for {'White' if self.board.turn == chess.WHITE else 'Black'} "
                f"and explain why in a concise manner."
            )
            headers = {"Authorization": f"Bearer {self.config['grok_api_key']}", "Content-Type": "application/json"}
            payload = {"model": "grok-3", "prompt": prompt, "max_tokens": 200}
            
            start_time = time.time()
            response = requests.post("https://api.x.ai/v1/grok", headers=headers, json=payload)
            response.raise_for_status()
            response_text = response.json().get("choices", [{}])[0].get("text", "")
            logger.info f"Grok API response took {time.time() - start_time:.1f} seconds")
            
            # Parse response
            move_match = re.search(r"Best move: (\w+)", response_text, re.IGNORECASE)
            move = move_match.group(1) if move_match else None
            explanation = response_text.split("Explanation:")[-1].strip() if "Explanation:" in response_text else response_text
            
            if move and self.board.is_legal(self.board.parse_san(move)):
                logger.info(f"Grok suggested move: {move}")
                return move, explanation
            else:
                logger.warning(f"Invalid or no move suggested by Grok: {response_text}")
                return None, "No valid move suggested."
                
        except Exception as e:
            logger.error(f"Grok API error: {e}")
            self.message_queue.put(('error', f"Error: {e}"))
            return None, f"Error: {e}"
    
    def play_move(self, move):
        try:
            from_square = move.from_square
            to_square = move.to_square
            files = 'abcdefgh'
            from_file, from_rank = files[chess.square_file(from_square)], 8 - chess.square_rank(from_square)
            to_file, to_rank = files[chess.square_file(to_square)], 8 - chess.square_rank(to_square)
            
            if self.config['player_color'] == chess.BLACK:
                from_file, from_rank = files[7 - chess.square_file(from_square)], chess.square_rank(from_square) + 1
                to_file, to_rank = files[7 - chess.square_file(to_square)], chess.square_rank(to_square) + 1
            
            region = self.get_screen_region()
            square_size = self.detector.square_size
            
            x1 = region[0] + (files.index(from_file) * square_size) + (square_size // 2)
            y1 = region[1] + ((from_rank - 1) * square_size) + (square_size // 2)
            x2 = region[0] + (files.index(to_file) * square_size) + (square_size // 2)
            y2 = region[1] + ((to_rank - 1) * square_size) + (square_size // 2)
            
            logger.debug(f"Moving mouse from ({x1}, {y1}) to ({x2}, {y2}) for {move.uci()}")
            pyautogui.moveTo(x1, y1)
            pyautogui.mouseDown()
            pyautogui.moveTo(x2, y2)
            pyautogui.mouseUp()
            logger.info(f"Played move via mouse: {move.uci()}")
            self.message_queue.put(('move_played', f"Played: {move.uci()}"))
            self.board.push(move)
            self.message_queue.put(('board_update', self.board))
            
        except Exception as e:
            logger.error(f"Error playing move {move.uci()}: {e}")
            self.message_queue.put(('error', f"Move error: {e}"))
    
    def update_board_svg(self, board):
        try:
            svg = chess.svg.board(board, size=400)
            with open("temp_board.svg", "w") as f:
                f.write(svg)
            self.board_html.set_content(open("temp_board.svg").read())
            logger.debug("Updated SVG board")
        except Exception as e:
            logger.error(f"Error updating SVG board: {e}")
    
    def process_queue(self):
        try:
            while True:
                message_type, data = self.message_queue.get_nowait()
                if message_type == 'position_update':
                    self.position_text.delete(1.0, tk.END)
                    self.position_text.insert(tk.END, data)
                elif message_type == 'board_update':
                    self.update_board_svg(data)
                elif message_type == 'move_suggestion':
                    self.log_text.insert(tk.END, f"Suggested move: {data}\n")
                    self.log_text.see(tk.END)
                elif message_type == 'explanation':
                    self.log_text.insert(tk.END, f"Explanation: {data}\n")
                    self.log_text.see(tk.END)
                elif message_type == 'move_played':
                    self.log_text.insert(tk.END, f"{data}\n")
                    self.log_text.see(tk.END)
                elif message_type == 'error':
                    self.log_text.insert(tk.END, f"Error: {data}\n")
                    self.log_text.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)
    
    def clear_logs(self):
        self.log_text.delete(1.0, tk.END)
    
    def load_config(self):
        try:
            if os.path.exists('chess_config.json'):
                with open('chess_config.json', 'r') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
                    logger.info("Configuration loaded")
            except Exception as e:
                logger.error(f"Error loading config: {e}")
    
    def save_config(self):
        try:
            self.config['grok_api_key'] = self.api_key_var.get()
            self.config['screen_region'] = self.get_screen_region()
            self.config['check_interval'] = float(self.interval_var.get())
            self.config['player_color'] = chess.WHITE if self.color_var.get() == "White" else chess.BLACK
            self.config['platform'] = self.platform_var.get().lower()
            with open('chess_config.json', 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Configuration saved")
            messagebox.showinfo("Configuration", "Success")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            messagebox.showerror("Configuration", f"Error: {e}")

def main():
    root = tk.Tk()
    app = ChessAutoPlayerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    try:
        pyautogui.FAILSAFE = True
        logger.info("Auto-Player started")
        main()
    except KeyboardInterrupt:
        logger.info("Auto-Player stopped by user")
        print("Auto-Player stopped")
    except Exception as e:
        logger.error(f"Auto-Player error: {e}")
        print(f"Auto-Player error: {e}")
```

#### 3. `chess_game_reviewer.py`
Uses Stockfish for PGN analysis, `chess.svg` for move navigation.

<xaiArtifact artifact_id="72fafe29-0b16-4ddc-90e5-f29f025c00da" artifact_version_id="f808a14a-7198-45d7-8c0f-b605cef95268" title="Chess Game Reviewer" contentType="text/python">
```python
import chess
import chess.pgn
import chess.svg
import os
import time
import logging
from logging.handlers import RotatingFileHandler
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
from threading import Thread
import queue
from stockfish import Stockfish
from tkinterhtml import HtmlFrame

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [Reviewer] %(message)s',
    handlers=[
        RotatingFileHandler('chess_log.txt', maxBytes=1024*1024*10, backupCount=10),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ChessGameReviewerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Chess Game Reviewer")
        self.root.geometry("1000x600")
        self.config = {
            'grok_api_key': '',
            'pgn_directory': os.path.expanduser("~/Downloads")
        }
        self.stockfish = Stockfish(path='./stockfish')  # Adjust path to Stockfish binary
        self.stockfish.set_depth(20)
        self.load_config()
        self.create_widgets()
        self.message_queue = queue.Queue()
        self.pgn_game = None
        self.platform = None
        self.current_move = 0
        self.move_nodes = []
        self.root.after(100, self.process_queue)
    
    def create_widgets(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text="Configuration")
        self.create_config_tab(config_frame)
        game_frame = ttk.Frame(notebook)
        notebook.add(game_frame, text="Game Details")
        self.create_game_tab(game_frame)
        analysis_frame = ttk.Frame(notebook)
        notebook.add(analysis_frame, text="Analysis")
        self.create_analysis_tab(analysis_frame)
    
    def create_config_tab(self, parent):
        api_frame = ttk.LabelFrame(parent, text="API Configuration")
        api_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(api_frame, text="Grok API Key (optional):").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.api_key_var = tk.StringVar(value=self.config['grok_api_key'])
        api_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, width=50, show='*')
        api_entry.grid(row=0, column=1, padx=5, pady=5)
        
        pgn_frame = ttk.LabelFrame(parent, text="PGN Directory")
        pgn_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(pgn_frame, text="Directory:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.pgn_dir_var = tk.StringVar(value=self.config['pgn_directory'])
        ttk.Entry(pgn_frame, textvariable=self.pgn_dir_var, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(pgn_frame, text="Browse", command=self.browse_pgn_directory).grid(row=0, column=2, padx=5, pady=5)
        
        ttk.Button(parent, text="Save Configuration", command=self.save_config).pack(pady=10)
    
    def create_game_tab(self, parent):
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(control_frame, text="Load Latest PGN", command=self.load_latest_pgn).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Select PGN File", command=self.select_pgn_file).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Analyze Game", command=self.start_analysis).pack(side='left', padx=5)
        
        status_frame = ttk.LabelFrame(parent, text="Status")
        status_frame.pack(fill='x', padx=5, pady=5)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status_frame, textvariable=self.status_var).pack(padx=5, pady=5)
        
        content_frame = ttk.Frame(parent)
        content_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        board_frame = ttk.LabelFrame(content_frame, text="Board")
        board_frame.pack(side='left', fill='both', expand=True, padx=5)
        self.board_html = HtmlFrame(board_frame)
        self.board_html.pack(fill='both', expand=True)
        self.update_board_svg(chess.Board())
        
        nav_frame = ttk.Frame(board_frame)
        nav_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(nav_frame, text="<<", command=self.first_move).pack(side='left', padx=2)
        ttk.Button(nav_frame, text="<", command=self.prev_move).pack(side='left', padx=2)
        ttk.Button(nav_frame, text=">", command=self.next_move).pack(side='left', padx=2)
        ttk.Button(nav_frame, text=">>", command=self.last_move).pack(side='left', padx=2)
        
        game_frame = ttk.LabelFrame(content_frame, text="Game Details")
        game_frame.pack(side='right', fill='both', expand=True, padx=5)
        self.game_text = tk.Text(game_frame, height=15, width=30)
        game_scrollbar = ttk.Scrollbar(game_frame, orient='vertical', command=self.game_text.yview)
        self.game_text.configure(yscrollcommand=game_scrollbar.set)
        self.game_text.pack(side='left', fill='both', expand=True)
        game_scrollbar.pack(side='right', fill='y')
    
    def create_analysis_tab(self, parent):
        self.analysis_text = tk.Text(parent, height=25, width=80)
        analysis_scrollbar = ttk.Scrollbar(parent, orient='vertical', command=self.analysis_text.yview)
        self.analysis_text.configure(yscrollcommand=analysis_scrollbar.set)
        self.analysis_text.pack(side='left', fill='both', expand=True)
        analysis_scrollbar.pack(side='right', fill='y')
        ttk.Button(parent, text="Clear Analysis", command=self.clear_analysis).pack(pady=5)
    
    def browse_pgn_directory(self):
        directory = filedialog.askdirectory(initialdir=self.config['pgn_directory'])
        if directory:
            self.pgn_dir_var.set(directory)
            logger.info(f"PGN directory set to: {directory}")
    
    def load_latest_pgn(self):
        try:
            self.status_var.set("Searching for PGN...")
            pgn_dir = self.pgn_dir_var.get()
            if not os.path.exists(pgn_dir):
                logger.error(f"PGN directory does not exist: {pgn_dir}")
                messagebox.showerror("Error", f"PGN directory not found: {pgn_dir}")
                self.status_var.set("Ready")
                return
            
            pgn_files = [
                f for f in os.listdir(pgn_dir)
                if f.endswith('.pgn') and ('lichess_' in f.lower() or 'chess_com_' in f.lower())
            ]
            if not pgn_files:
                logger.warning("No Lichess or Chess.com PGN files found in directory")
                messagebox.showwarning("Warning", "No Lichess or Chess.com PGN files found")
                self.status_var.set("Ready")
                return
            
            latest_pgn = max(
                pgn_files,
                key=lambda f: os.path.getmtime(os.path.join(pgn_dir, f))
            )
            pgn_path = os.path.join(pgn_dir, latest_pgn)
            self.load_pgn(pgn_path)
            self.status_var.set(f"Loaded: {latest_pgn}")
            
        except Exception as e:
            logger.error(f"Error loading latest PGN: {e}")
            messagebox.showerror("Error", f"Error loading PGN: {e}")
            self.status_var.set("Ready")
    
    def select_pgn_file(self):
        try:
            pgn_file = filedialog.askopenfilename(
                initialdir=self.pgn_dir_var.get(),
                filetypes=[("PGN files", "*.pgn")]
            )
            if pgn_file:
                self.load_pgn(pgn_file)
                self.status_var.set(f"Loaded: {os.path.basename(pgn_file)}")
        except Exception as e:
            logger.error(f"Error selecting PGN file: {e}")
            messagebox.showerror("Error", f"Error selecting PGN: {e}")
            self.status_var.set("Ready")
    
    def load_pgn(self, pgn_path):
        try:
            with open(pgn_path, 'r', encoding='utf-8') as pgn_file:
                self.pgn_game = chess.pgn.read_game(pgn_file)
            if not self.pgn_game:
                logger.error("Invalid or empty PGN file")
                messagebox.showerror("Error", "Invalid or empty PGN file")
                return
            
            # Detect platform
            headers = self.pgn_game.headers
            site = headers.get('Site', '').lower()
            if 'lichess' in site or 'lichess' in os.path.basename(pgn_path).lower():
                self.platform = "Lichess"
            elif 'chess.com' in site or 'chess_com' in os.path.basename(pgn_path).lower():
                self.platform = "Chess.com"
            else:
                self.platform = "Unknown"
            logger.info(f"Detected platform: {self.platform}")
            
            # Collect moves
            self.move_nodes = []
            node = self.pgn_game
            self.move_nodes.append(node.board())
            while node.variations:
                node = node.variations[0]
                self.move_nodes.append(node.board())
            
            # Display game details
            moves = []
            node = self.pgn_game
            while node.variations:
                move = node.variations[0].move
                moves.append(node.board().san(move))
                node = node.variations[0]
            
            game_text = f"Platform: {self.platform}\n"
            game_text += f"White: {headers.get('White', 'Unknown')}\n"
            game_text += f"Black: {headers.get('Black', 'Unknown')}\n"
            game_text += f"Result: {headers.get('Result', '*')}\n"
            game_text += f"Date: {headers.get('Date', 'Unknown')}\n"
            game_text += f"Site: {headers.get('Site', 'Unknown')}\n"
            game_text += f"Event: {headers.get('Event', 'Unknown')}\n\n"
            game_text += "Moves:\n"
            for i, move in enumerate(moves, 1):
                if i % 2 == 1:
                    game_text += f"{(i+1)//2}. {move} "
                else:
                    game_text += f"{move}\n"
            
            self.game_text.delete(1.0, tk.END)
            self.game_text.insert(tk.END, game_text)
            self.current_move = 0
            self.update_board_svg(self.move_nodes[0])
            logger.info(f"Loaded PGN from {pgn_path}")
            messagebox.showinfo("Success", f"Loaded PGN: {os.path.basename(pgn_path)} ({self.platform})")
            
        except Exception as e:
            logger.error(f"Error loading PGN {pgn_path}: {e}")
            messagebox.showerror("Error", f"Error loading PGN: {e}")
    
    def first_move(self):
        self.current_move = 0
        self.update_board_svg(self.move_nodes[self.current_move])
    
    def prev_move(self):
        if self.current_move > 0:
            self.current_move -= 1
            self.update_board_svg(self.move_nodes[self.current_move])
    
    def next_move(self):
        if self.current_move < len(self.move_nodes) - 1:
            self.current_move += 1
            self.update_board_svg(self.move_nodes[self.current_move])
    
    def last_move(self):
        self.current_move = len(self.move_nodes) - 1
        self.update_board_svg(self.move_nodes[self.current_move])
    
    def start_analysis(self):
        if not self.pgn_game:
            logger.warning("No PGN loaded for analysis")
            messagebox.showwarning("Warning", "Please load a PGN file first")
            return
        
        self.status_var.set("Analyzing...")
        Thread(target=self.analyze_game, daemon=True).start()
    
    def analyze_game(self):
        try:
            analysis = "Game Analysis\n============\n"
            board = chess.Board()
            node = self.pgn_game
            move_number = 1
            blunders = []
            brilliant_moves = []
            
            while node.variations:
                move = node.variations[0].move
                san_move = board.san(move)
                fen_before = board.fen()
                self.stockfish.set_fen_position(fen_before)
                eval_before = self.stockfish.get_evaluation().get('value', 0) / 100.0
                best_move = self.stockfish.get_best_move()
                
                board.push(move)
                fen_after = board.fen()
                self.stockfish.set_fen_position(fen_after)
                eval_after = self.stockfish.get_evaluation().get('value', 0) / 100.0
                
                centipawn_loss = abs(eval_before - eval_after) if board.turn == chess.BLACK else abs(eval_after - eval_before)
                
                if centipawn_loss > 3.0:
                    blunders.append((move_number, san_move, centipawn_loss, best_move))
                    analysis += f"Move {move_number}: {san_move} (Blunder, -{centipawn_loss:.2f} cp)\n"
                    analysis += f"  Suggested: {board.san(board.parse_uci(best_move))}\n"
                elif centipawn_loss < 0.5 and best_move == move.uci():
                    brilliant_moves.append((move_number, san_move))
                    analysis += f"Move {move_number}: {san_move} (Brilliant!)\n"
                else:
                    analysis += f"Move {move_number}: {san_move} ({eval_after:+.2f} cp)\n"
                
                node = node.variations[0]
                move_number += 1 if board.turn == chess.WHITE else move_number
            
            analysis += "\nSummary\n=======\n"
            analysis += f"Blunders: {len(blunders)}\n"
            for move_num, move, loss, best in blunders:
                analysis += f"  Move {move_num}: {move} (-{loss:.2f} cp, suggested: {board.san(board.parse_uci(best))})\n"
            analysis += f"Brilliant Moves: {len(brilliant_moves)}\n"
            for move_num, move in brilliant_moves:
                analysis += f"  Move {move_num}: {move}\n"
            
            self.message_queue.put(('analysis_update', analysis))
            self.status_var.set("Analysis Complete")
            logger.info("Game analysis completed")
            
        except Exception as e:
            logger.error(f"Error analyzing game: {e}")
            self.message_queue.put(('error', f"Analysis error: {e}"))
            self.status_var.set("Ready")
    
    def