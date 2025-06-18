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
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import requests
import numpy as np
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [Reviewer] %(message)s',
    handlers=[
        RotatingFileHandler('chess_reviewer.log', maxBytes=10*1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ChessAnalysis:
    def __init__(self):
        self.evaluations = []
        self.positions = []
        self.comments = []
        self.best_moves = []
        self.player_moves = []
        self.accuracy = 0.0
        self.blunders = []
        self.mistakes = []
        self.brilliant_moves = []

class ChessGameReviewerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Enhanced Chess Game Reviewer")
        self.root.geometry("1200x800")
        self.config = {
            'grok_api_key': '',
            'pgn_directory': os.path.expanduser("~/Downloads"),
            'stockfish_depth': 20,
            'analysis_threshold': 3.0,
            'brilliant_threshold': 0.5,
            'mistake_threshold': 1.5
        }
        self.setup_stockfish()
        self.load_config()
        self.create_widgets()
        self.message_queue = queue.Queue()
        self.pgn_game = None
        self.platform = None
        self.current_move = 0
        self.move_nodes = []
        self.analysis = ChessAnalysis()
        self.analysis_running = False
        self.root.after(100, self.process_queue)
        
    def setup_stockfish(self):
        try:
            self.stockfish = Stockfish(path='stockfish')
            self.stockfish.set_depth(self.config['stockfish_depth'])
            self.stockfish.set_skill_level(20)
            logger.info("Stockfish engine initialized")
        except Exception as e:
            logger.error(f"Error initializing Stockfish: {e}")
            messagebox.showerror("Error", f"Failed to initialize Stockfish engine: {e}")
            self.stockfish = None

    def create_widgets(self):
        self.create_menu()
        
        # Main container with paned window
        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel for board and controls
        left_panel = ttk.Frame(self.paned)
        self.paned.add(left_panel, weight=1)
        
        # Board frame
        board_frame = ttk.LabelFrame(left_panel, text="Chess Board")
        board_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.board_html = HtmlFrame(board_frame)
        self.board_html.pack(fill=tk.BOTH, expand=True)
        self.update_board_svg(chess.Board())
        
        # Navigation controls
        nav_frame = ttk.Frame(left_panel)
        nav_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(nav_frame, text="<<", command=self.first_move).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_frame, text="<", command=self.prev_move).pack(side=tk.LEFT, padx=2)
        self.move_var = tk.StringVar(value="Move: 0/0")
        ttk.Label(nav_frame, textvariable=self.move_var).pack(side=tk.LEFT, padx=10)
        ttk.Button(nav_frame, text=">", command=self.next_move).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_frame, text=">>", command=self.last_move).pack(side=tk.LEFT, padx=2)
        
        # Right panel with notebook
        right_panel = ttk.Notebook(self.paned)
        self.paned.add(right_panel, weight=1)
        
        # Game details tab
        game_frame = ttk.Frame(right_panel)
        right_panel.add(game_frame, text="Game Details")
        
        self.game_text = tk.Text(game_frame, height=15, width=40)
        game_scroll = ttk.Scrollbar(game_frame, command=self.game_text.yview)
        self.game_text.configure(yscrollcommand=game_scroll.set)
        self.game_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        game_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Analysis tab
        analysis_frame = ttk.Frame(right_panel)
        right_panel.add(analysis_frame, text="Analysis")
        
        # Analysis controls
        control_frame = ttk.Frame(analysis_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(control_frame, text="Start Analysis", command=self.start_analysis).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Stop Analysis", command=self.stop_analysis).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Export Analysis", command=self.export_analysis).pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(analysis_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(fill=tk.X, padx=5, pady=5)
        
        # Analysis text
        self.analysis_text = tk.Text(analysis_frame, height=20, width=40)
        analysis_scroll = ttk.Scrollbar(analysis_frame, command=self.analysis_text.yview)
        self.analysis_text.configure(yscrollcommand=analysis_scroll.set)
        self.analysis_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        analysis_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Evaluation graph tab
        graph_frame = ttk.Frame(right_panel)
        right_panel.add(graph_frame, text="Evaluation Graph")
        
        self.figure, self.ax = plt.subplots(figsize=(6, 4))
        self.canvas = FigureCanvasTkAgg(self.figure, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Load PGN", command=self.select_pgn_file)
        file_menu.add_command(label="Load Latest", command=self.load_latest_pgn)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        config_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Configuration", menu=config_menu)
        config_menu.add_command(label="Settings", command=self.show_settings)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

    def show_settings(self):
        settings = tk.Toplevel(self.root)
        settings.title("Settings")
        settings.geometry("400x300")
        
        ttk.Label(settings, text="Grok API Key:").pack(padx=5, pady=5)
        api_key = ttk.Entry(settings, show="*")
        api_key.insert(0, self.config['grok_api_key'])
        api_key.pack(padx=5, pady=5)
        
        ttk.Label(settings, text="Stockfish Depth:").pack(padx=5, pady=5)
        depth = ttk.Entry(settings)
        depth.insert(0, str(self.config['stockfish_depth']))
        depth.pack(padx=5, pady=5)
        
        ttk.Button(settings, text="Save", command=lambda: self.save_settings(
            api_key.get(), int(depth.get())
        )).pack(pady=10)

    def save_settings(self, api_key, depth):
        self.config['grok_api_key'] = api_key
        self.config['stockfish_depth'] = depth
        self.stockfish.set_depth(depth)
        self.save_config()
        
    def show_about(self):
        messagebox.showinfo(
            "About",
            "Enhanced Chess Game Reviewer\n\n"
            "A tool for analyzing chess games using both Stockfish and Grok AI.\n"
            "Version 2.0"
        )

    def start_analysis(self):
        if not self.pgn_game:
            messagebox.showwarning("Warning", "Please load a PGN file first")
            return
        
        if self.analysis_running:
            messagebox.showinfo("Info", "Analysis is already running")
            return
        
        self.analysis_running = True
        self.progress_var.set(0)
        Thread(target=self.analyze_game, daemon=True).start()

    def stop_analysis(self):
        self.analysis_running = False
        
    def analyze_game(self):
        try:
            self.analysis = ChessAnalysis()
            board = chess.Board()
            node = self.pgn_game
            total_moves = sum(1 for _ in node.mainline())
            moves_analyzed = 0
            
            while node.variations and self.analysis_running:
                move = node.variations[0].move
                san_move = board.san(move)
                fen_before = board.fen()
                
                # Stockfish analysis
                self.stockfish.set_fen_position(fen_before)
                eval_before = self.stockfish.get_evaluation()
                best_move = self.stockfish.get_best_move()
                
                # Grok analysis if API key is available
                grok_analysis = ""
                if self.config['grok_api_key']:
                    grok_analysis = self.get_grok_analysis(fen_before)
                
                # Store position data
                self.analysis.positions.append(fen_before)
                self.analysis.evaluations.append(eval_before['value'] / 100.0)
                self.analysis.best_moves.append(best_move)
                self.analysis.player_moves.append(move.uci())
                
                # Make the move
                board.push(move)
                
                # Calculate position change
                self.stockfish.set_fen_position(board.fen())
                eval_after = self.stockfish.get_evaluation()
                eval_diff = abs(eval_after['value'] - eval_before['value']) / 100.0
                
                # Categorize move
                comment = self.categorize_move(eval_diff, move.uci(), best_move)
                self.analysis.comments.append(comment)
                
                if grok_analysis:
                    comment += f"\nGrok: {grok_analysis}"
                
                # Update progress
                moves_analyzed += 1
                progress = (moves_analyzed / total_moves) * 100
                self.message_queue.put(('progress', progress))
                self.message_queue.put(('analysis_update', f"Move {moves_analyzed}: {san_move}\n{comment}\n"))
                
                node = node.variations[0]
            
            # Calculate final statistics
            self.calculate_statistics()
            self.update_evaluation_graph()
            self.message_queue.put(('analysis_complete', None))
            
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            self.message_queue.put(('error', str(e)))
        finally:
            self.analysis_running = False

    def get_grok_analysis(self, fen):
        try:
            headers = {
                "Authorization": f"Bearer {self.config['grok_api_key']}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "grok-3",
                "prompt": f"Analyze this chess position (FEN): {fen}\nProvide a brief tactical assessment.",
                "max_tokens": 100
            }
            response = requests.post(
                "https://api.x.ai/v1/grok",
                headers=headers,
                json=payload,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()['choices'][0]['text'].strip()
            return ""
        except Exception as e:
            logger.error(f"Grok API error: {e}")
            return ""

    def categorize_move(self, eval_diff, player_move, best_move):
        if eval_diff > self.config['analysis_threshold']:
            self.analysis.blunders.append(player_move)
            return f"Blunder (-{eval_diff:.2f})"
        elif eval_diff > self.config['mistake_threshold']:
            self.analysis.mistakes.append(player_move)
            return f"Mistake (-{eval_diff:.2f})"
        elif eval_diff < self.config['brilliant_threshold'] and player_move == best_move:
            self.analysis.brilliant_moves.append(player_move)
            return "Brilliant move!"
        return f"Normal move ({eval_diff:+.2f})"

    def calculate_statistics(self):
        total_moves = len(self.analysis.player_moves)
        if total_moves == 0:
            return
        
        perfect_moves = sum(1 for p, b in zip(self.analysis.player_moves, self.analysis.best_moves) if p == b)
        self.analysis.accuracy = (perfect_moves / total_moves) * 100
        
        summary = f"\nGame Statistics\n===============\n"
        summary += f"Accuracy: {self.analysis.accuracy:.1f}%\n"
        summary += f"Brilliant moves: {len(self.analysis.brilliant_moves)}\n"
        summary += f"Mistakes: {len(self.analysis.mistakes)}\n"
        summary += f"Blunders: {len(self.analysis.blunders)}\n"
        
        self.message_queue.put(('analysis_update', summary))

    def update_evaluation_graph(self):
        self.ax.clear()
        moves = range(len(self.analysis.evaluations))
        evals = self.analysis.evaluations
        
        self.ax.plot(moves, evals, 'b-', label='Position Evaluation')
        self.ax.axhline(y=0, color='k', linestyle='-', alpha=0.3)
        self.ax.set_xlabel('Move Number')
        self.ax.set_ylabel('Evaluation (pawns)')
        self.ax.set_title('Position Evaluation Over Time')
        self.ax.grid(True, alpha=0.3)
        self.ax.legend()
        
        self.canvas.draw()

    def export_analysis(self):
        if not hasattr(self, 'analysis') or not self.analysis.evaluations:
            messagebox.showwarning("Warning", "No analysis data to export")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=f"chess_analysis_{timestamp}.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write("Chess Game Analysis Report\n")
                    f.write("=========================\n\n")
                    
                    # Game details
                    f.write("Game Details:\n")
                    for key, value in self.pgn_game.headers.items():
                        f.write(f"{key}: {value}\n")
                    f.write("\n")
                    
                    # Move by move analysis
                    f.write("Move Analysis:\n")
                    for i, (eval, comment) in enumerate(zip(self.analysis.evaluations, self.analysis.comments)):
                        f.write(f"Move {i+1}: Evaluation: {eval:+.2f} - {comment}\n")
                    
                    # Statistics
                    f.write("\nStatistics:\n")
                    f.write(f"Accuracy: {self.analysis.accuracy:.1f}%\n")
                    f.write(f"Brilliant moves: {len(self.analysis.brilliant_moves)}\n")
                    f.write(f"Mistakes: {len(self.analysis.mistakes)}\n")
                    f.write(f"Blunders: {len(self.analysis.blunders)}\n")
                
                messagebox.showinfo("Success", "Analysis exported successfully")
                
            except Exception as e:
                logger.error(f"Export error: {e}")
                messagebox.showerror("Error", f"Failed to export analysis: {e}")

    # ... (rest of the existing methods remain the same)

def main():
    root = tk.Tk()
    app = ChessGameReviewerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    try:
        logger.info("Enhanced Chess Game Reviewer started")
        main()
    except Exception as e:
        logger.error(f"Application error: {e}")
        messagebox.showerror("Error", f"Application error: {e}")