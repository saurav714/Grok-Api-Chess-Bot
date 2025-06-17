# chess_game_reviewer.py
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
        RotatingFileHandler('chess_bot.log', maxBytes=10*1024*1024, backupCount=5),
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
        self.stockfish = Stockfish(path='stockfish')  # Adjust path to Stockfish binary
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
                if message_type == 'analysis_update':
                    self.analysis_text.delete(1.0, tk.END)
                    self.analysis_text.insert(tk.END, data)
                    self.analysis_text.see(tk.END)
                elif message_type == 'error':
                    self.analysis_text.insert(tk.END, f"Error: {data}\n")
                    self.analysis_text.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)
    
    def clear_analysis(self):
        self.analysis_text.delete(1.0, tk.END)
    
    def load_config(self):
        try:
            if os.path.exists('chess_bot_config.json'):
                with open('chess_bot_config.json', 'r') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
                    logger.info("Configuration loaded")
        except Exception as e:
            logger.error(f"Error loading config: {e}")
    
    def save_config(self):
        try:
            self.config['grok_api_key'] = self.api_key_var.get()
            self.config['pgn_directory'] = self.pgn_dir_var.get()
            with open('chess_bot_config.json', 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Configuration saved")
            messagebox.showinfo("Configuration", "Configuration saved successfully!")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            messagebox.showerror("Configuration", f"Error saving configuration: {e}")

def main():
    root = tk.Tk()
    app = ChessGameReviewerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    try:
        logger.info("Reviewer application started")
        main()
    except KeyboardInterrupt:
        logger.info("Reviewer stopped by user")
        print("Reviewer stopped.")
    except Exception as e:
        logger.error(f"Reviewer error: {e}")
        print(f"Reviewer error: {e}")
# End of chess_game_reviewer.py