import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import chess
import chess.engine
import chess.polyglot
import copy
import time
import ollama
import threading
import random
import os
from datetime import datetime
from dotenv import load_dotenv
import logging
from functools import lru_cache
import re

# Configuration dictionary for easy customization
CONFIG = {
    "board_colors": {"light": "#f0d9b5", "dark": "#b58863", "selected": "#90EE90", 
                    "legal_move": "#98FB98", "last_move": "#FFD700", "check": "#FF6B6B"},
    "font_sizes": {"piece": 16, "title": 20, "status": 12, "button": 9, "analysis": 9},
    "stockfish": {
        "easy": {"depth": 5, "time": 1.0},
        "medium": {"depth": 10, "time": 2.0},
        "hard": {"depth": 15, "time": 5.0}
    },
    "ollama": {"temperature": 0.3, "top_p": 0.8, "num_predict": 100, "timeout": 30.0},
    "transposition_table_size": 1000,
    "gui": {"min_size": (700, 500), "bg": "#2c3e50", "panel_width": 250},
    "paths": {"openings": "openings.bin"}
}

def setup_logging():
    """Configure logging to file and console."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler('chess_vs_ai.log'),
            logging.StreamHandler()
        ]
    )

class ChessError(Exception):
    """Custom exception for chess-specific errors."""
    pass

class ChessVsAI:
    def __init__(self):
        """Initialize the Chess vs AI application."""
        setup_logging()
        logging.info("Initializing ChessVsAI")
        self.PIECES = {
            'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
            'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'
        }
        self.player_side = 'white'
        self.review_mode = False
        self.current_review_move = 0
        self.ai_thinking = False
        self.board_lock = threading.Lock()
        self.pgn_comments = {}
        self.ai_difficulty = 'medium'  # Default difficulty
        
        # Load environment variables
        load_dotenv()
        self.stockfish_path = os.getenv("STOCKFISH_PATH", r"C:\Users\HP\Desktop\Grok Api Chess Bot\stockfish.exe")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "phi3")
        self.ollama_timeout = float(os.getenv("OLLAMA_TIMEOUT", str(CONFIG["ollama"]["timeout"])))
        
        # Validate environment variables
        if not os.path.exists(self.stockfish_path):
            logging.warning(f"Stockfish path '{self.stockfish_path}' invalid")
            self.stockfish_path = None
        
        # Initialize Stockfish
        self.engine = None
        self.init_stockfish()
        
        # Initialize GUI components
        self.squares = [[None for _ in range(8)] for _ in range(8)]
        self.setup_gui()
        self.reset_game()

    def init_stockfish(self):
        """Initialize Stockfish engine with error handling."""
        try:
            if not self.stockfish_path:
                raise ChessError("Stockfish path not set or invalid")
            self.engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
            self.engine.configure({
                "Threads": min(4, os.cpu_count() or 2),
                "Hash": 256,
                "UCI_LimitStrength": False
            })
            logging.info("Stockfish loaded successfully")
        except Exception as e:
            logging.error(f"Failed to load Stockfish: {e}", exc_info=True)
            self.engine = None
            messagebox.showerror("Stockfish Error", f"Failed to initialize Stockfish: {str(e)}. Falling back to Ollama/random moves.")

    def reset_game(self):
        """Reset the game state to initial position."""
        try:
            with self.board_lock:
                self.chess_board = chess.Board()
                self.move_history = []
                self.board_history = [copy.deepcopy(self.chess_board)]
                self.evaluations = [0.0]
                self.best_moves = [None]
                self.selected_square = None
                self.last_move = None
                self.current_turn = 'white'
                self.game_over = False
                self.review_mode = False
                self.current_review_move = 0
                self.ai_thinking = False
                self.pgn_comments.clear()
            
            self.update_board()
            self.update_status()
            self.update_eval_bar()
            if hasattr(self, 'move_list_text'):
                self.move_list_text.delete(1.0, tk.END)
        except Exception as e:
            logging.error(f"Reset game error: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to reset game")

    def setup_gui(self):
        """Initialize the Tkinter GUI components."""
        try:
            self.root = tk.Tk()
            self.root.title("Chess vs AI with LLM")
            self.root.configure(bg=CONFIG["gui"]["bg"])
            self.root.geometry("900x700")
            self.root.resizable(True, True)
            self.root.minsize(*CONFIG["gui"]["min_size"])

            main_frame = tk.Frame(self.root, bg=CONFIG["gui"]["bg"])
            main_frame.pack(padx=10, pady=10, expand=True, fill='both')

            title_label = tk.Label(
                main_frame, 
                text="♔ Chess vs AI ♚", 
                font=('Arial', CONFIG["font_sizes"]["title"], 'bold'), 
                fg='#ecf0f1', 
                bg=CONFIG["gui"]["bg"]
            )
            title_label.pack(pady=(0, 15))

            content_frame = tk.Frame(main_frame, bg=CONFIG["gui"]["bg"])
            content_frame.pack(expand=True, fill='both')

            self.board_container = tk.Frame(content_frame, bg='#34495e', relief='raised', bd=2)
            self.board_container.pack(side='left', padx=(0, 15), expand=True, fill='both')
            
            self.board_frame = tk.Frame(self.board_container, bg='#34495e')
            self.board_frame.pack(expand=True, fill='both', padx=10, pady=10)

            self.control_panel = tk.Frame(content_frame, bg=CONFIG["gui"]["bg"], width=CONFIG["gui"]["panel_width"])
            self.control_panel.pack(side='right', fill='y')
            self.control_panel.pack_propagate(False)

            self.setup_status_panel()
            self.setup_control_buttons()
            self.setup_analysis_panel()
            self.setup_move_list_panel()
            
            self.create_board()
            
            # Bind keyboard shortcuts
            self.root.bind('<Control-z>', lambda e: self.undo_move())
            self.root.bind('<Control-n>', lambda e: self.new_game())
            self.root.bind('<Control-s>', lambda e: self.switch_side())
            self.root.bind('<Control-p>', lambda e: self.save_pgn())
            self.root.bind('<Control-o>', lambda e: self.load_pgn())
            
            self.root.bind('<Configure>', self.on_window_resize)
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

            if self.player_side == 'black':
                self.root.after(1000, self.ai_move)
        except Exception as e:
            logging.error(f"GUI setup error: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to initialize GUI: {str(e)}")

    def setup_status_panel(self):
        """Setup the status and evaluation panel with a smaller evaluation bar."""
        try:
            status_frame = tk.Frame(self.control_panel, bg=CONFIG["gui"]["bg"])
            status_frame.pack(fill='x', pady=(0, 15))

            self.status_label = tk.Label(
                status_frame, 
                text="Your move", 
                font=('Arial', CONFIG["font_sizes"]["status"], 'bold'), 
                fg='#ecf0f1', 
                bg=CONFIG["gui"]["bg"],
                wraplength=CONFIG["gui"]["panel_width"] - 20
            )
            self.status_label.pack()

            eval_frame = tk.Frame(status_frame, bg=CONFIG["gui"]["bg"])
            eval_frame.pack(pady=(10, 0))

            tk.Label(eval_frame, text="Evaluation", font=('Arial', 9), fg='#bdc3c7', bg=CONFIG["gui"]["bg"]).pack()
            
            self.eval_canvas = tk.Canvas(
                eval_frame, 
                width=20, 
                height=100, 
                bg='#34495e', 
                highlightthickness=1,
                highlightbackground='#bdc3c7'
            )
            self.eval_canvas.pack(pady=5)
            
            self.eval_bar = self.eval_canvas.create_rectangle(4, 50, 16, 50, fill='#bdc3c7', outline='#7f8c8d')
            
            self.eval_label = tk.Label(
                eval_frame, 
                text="0.00", 
                font=('Arial', 8, 'bold'), 
                fg='#ecf0f1', 
                bg=CONFIG["gui"]["bg"]
            )
            self.eval_label.pack()

            # Progress indicator for AI thinking
            self.progress_label = tk.Label(
                status_frame,
                text="",
                font=('Arial', 10),
                fg='#ecf0f1',
                bg=CONFIG["gui"]["bg"]
            )
            self.progress_label.pack()
        except Exception as e:
            logging.error(f"Status panel setup error: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to setup status panel")

    def setup_control_buttons(self):
        """Setup control buttons based on current mode."""
        try:
            if hasattr(self, 'control_frame'):
                self.control_frame.destroy()

            self.control_frame = tk.Frame(self.control_panel, bg=CONFIG["gui"]["bg"])
            self.control_frame.pack(pady=2)

            btn_style = {
                'font': ('Arial', CONFIG["font_sizes"]["button"], 'bold'),
                'bg': '#3498db',
                'fg': 'white',
                'relief': 'flat',
                'padx': 15,
                'pady': 5,
                'width': 15,
                'cursor': 'hand2'
            }

            disabled_style = {
                'bg': '#7f8c8d',
                'fg': '#bdc3c7',
                'state': 'disabled'
            }

            buttons = [
                ("New Game (Ctrl+N)", self.new_game),
                ("Switch Side (Ctrl+S)", self.switch_side),
                ("Undo Move (Ctrl+Z)", self.undo_move),
                ("Resign", self.resign),
                ("Save PGN (Ctrl+P)", self.save_pgn),
                ("Load PGN (Ctrl+O)", self.load_pgn)
            ] if not self.review_mode else [
                ("\u25C0 Previous", self.prev_move),
                ("Next \u25B6", self.next_move),
                ("Add Comment", self.add_comment),
                ("Exit Review", self.exit_review),
                ("New Game (Ctrl+N)", self.new_game),
                ("Save PGN (Ctrl+P)", self.save_pgn),
                ("Load PGN (Ctrl+O)", self.load_pgn)
            ]

            # AI Difficulty Dropdown
            tk.Label(self.control_frame, text="AI Difficulty", font=('Arial', 10, 'bold'), fg='#ecf0f1', bg=CONFIG["gui"]["bg"]).pack(pady=(0, 5))
            self.difficulty_var = tk.StringVar(value=self.ai_difficulty)
            difficulty_menu = ttk.Combobox(self.control_frame, textvariable=self.difficulty_var, values=['easy', 'medium', 'hard'], state='readonly')
            difficulty_menu.pack(pady=1)
            difficulty_menu.bind('<<ComboboxSelected>>', self.set_difficulty)

            for text, command in buttons:
                btn = tk.Button(self.control_frame, text=text, command=command, **btn_style)
                btn.pack(pady=1)
                btn.bind("<Enter>", lambda e, b=btn: b.config(bg='#2980b9') if b['state'] == 'normal' else None)
                btn.bind("<Leave>", lambda e, b=btn: b.config(bg='#3498db') if b['state'] == 'normal' else None)
                # Apply disabled style for Previous/Next buttons when appropriate
                if text == "\u25C0 Previous" and self.current_review_move == 0:
                    btn.config(**disabled_style)
                elif text == "Next \u25B6" and self.current_review_move == len(self.move_history):
                    btn.config(**disabled_style)
        except Exception as e:
            logging.error(f"Control buttons setup error: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to setup control buttons")

    def set_difficulty(self, event):
        """Set AI difficulty based on dropdown selection."""
        try:
            self.ai_difficulty = self.difficulty_var.get()
            logging.info(f"AI difficulty set to {self.ai_difficulty}")
        except Exception as e:
            logging.error(f"Set difficulty error: {e}", exc_info=True)

    def add_comment(self):
        """Add or edit a comment for the current move in review mode."""
        try:
            if not self.review_mode or self.current_review_move == 0:
                messagebox.showinfo("Info", "Select a move to comment on!")
                return

            dialog = tk.Toplevel(self.root)
            dialog.title("Add/Edit Move Comment")
            dialog.geometry("350x250")
            dialog.transient(self.root)
            dialog.grab_set()
            dialog.configure(bg=CONFIG["gui"]["bg"])
            
            # Center the dialog
            x = self.root.winfo_rootx() + (self.root.winfo_width() - 350) // 2
            y = self.root.winfo_rooty() + (self.root.winfo_height() - 250) // 2
            dialog.geometry(f"350x250+{x}+{y}")
            
            move_num = (self.current_review_move + 1) // 2
            color = 'White' if self.current_review_move % 2 == 1 else 'Black'
            move = self.move_history[self.current_review_move - 1]['move']
            prev_board = self.board_history[self.current_review_move - 1]
            try:
                move_text = prev_board.san(move)
            except:
                move_text = move.uci()
            
            tk.Label(dialog, text=f"Comment for Move {move_num} ({color}): {move_text}", 
                     font=('Arial', 12, 'bold'), fg='#ecf0f1', bg=CONFIG["gui"]["bg"], wraplength=300).pack(pady=10)
            
            comment_text = tk.Text(dialog, font=('Arial', 10), height=5, width=40)
            comment_text.pack(pady=5)
            
            if self.current_review_move - 1 in self.pgn_comments:
                comment_text.insert(tk.END, self.pgn_comments[self.current_review_move - 1])
            
            def save():
                comment = comment_text.get("1.0", tk.END).strip()
                if len(comment) > 500:  # Add a reasonable character limit
                    messagebox.showwarning("Warning", "Comment is too long (max 500 characters)!")
                    return
                if comment:
                    self.pgn_comments[self.current_review_move - 1] = comment
                    logging.info(f"Added/Updated comment for move {self.current_review_move}: {comment[:50]}...")
                else:
                    self.pgn_comments.pop(self.current_review_move - 1, None)
                    logging.info(f"Removed comment for move {self.current_review_move}")
                self.update_analysis_text()
                self.update_move_list()
                dialog.destroy()
            
            def cancel():
                dialog.destroy()
            
            tk.Button(dialog, text="Save", command=save, font=('Arial', 10), bg='#3498db', 
                      fg='white', relief='flat', padx=20).pack(pady=5)
            tk.Button(dialog, text="Cancel", command=cancel, font=('Arial', 10), bg='#e74c3c', 
                      fg='white', relief='flat', padx=20).pack(pady=5)
            
            self.root.wait_window(dialog)
        except Exception as e:
            logging.error(f"Add comment error: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to add comment: {str(e)}")

    def prompt_for_comment(self):
        """Prompt for a comment after a move is made, if in review mode."""
        try:
            if self.review_mode and self.current_review_move > 0:
                result = messagebox.askyesno("Comment", "Would you like to add a comment for this move?")
                if result:
                    self.add_comment()
        except Exception as e:
            logging.error(f"Prompt for comment error: {e}", exc_info=True)

    def setup_analysis_panel(self):
        """Setup the analysis text panel."""
        try:
            analysis_frame = tk.Frame(self.control_panel, bg=CONFIG["gui"]["bg"])
            analysis_frame.pack(fill='both', expand=True, pady=(15, 0))

            tk.Label(
                analysis_frame, 
                text="Analysis", 
                font=('Arial', 11, 'bold'), 
                fg='#ecf0f1', 
                bg=CONFIG["gui"]["bg"]
            ).pack()

            text_frame = tk.Frame(analysis_frame, bg='#34495e', relief='sunken', bd=1)
            text_frame.pack(fill='both', expand=True, pady=5)

            self.analysis_text = tk.Text(
                text_frame,
                font=('Arial', CONFIG["font_sizes"]["analysis"]),
                fg='#ecf0f1',
                bg='#34495e',
                wrap='word',
                height=8,
                relief='flat',
                padx=5,
                pady=5
            )
            
            scrollbar = tk.Scrollbar(text_frame, orient='vertical', command=self.analysis_text.yview)
            self.analysis_text.configure(yscrollcommand=scrollbar.set)
            
            self.analysis_text.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
        except Exception as e:
            logging.error(f"Analysis panel setup error: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to setup analysis panel")

    def setup_move_list_panel(self):
        """Setup move list panel for review mode."""
        try:
            move_list_frame = tk.Frame(self.control_panel, bg=CONFIG["gui"]["bg"])
            move_list_frame.pack(fill='x', pady=(10, 0))
            tk.Label(move_list_frame, text="Move List", font=('Arial', 11, 'bold'), fg='#ecf0f1', bg=CONFIG["gui"]["bg"]).pack()
            
            self.move_list_text = tk.Text(
                move_list_frame,
                font=('Arial', CONFIG["font_sizes"]["analysis"]),
                fg='#ecf0f1',
                bg='#34495e',
                wrap='word',
                height=4,
                relief='flat',
                padx=5,
                pady=5
            )
            scrollbar = tk.Scrollbar(move_list_frame, orient='vertical', command=self.move_list_text.yview)
            self.move_list_text.configure(yscrollcommand=scrollbar.set)
            self.move_list_text.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            # Bind click event for move navigation
            self.move_list_text.bind('<Button-1>', self.on_move_list_click)
        except Exception as e:
            logging.error(f"Move list panel setup error: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to setup move list panel")

    def on_move_list_click(self, event):
        """Handle clicks on the move list to navigate to a specific move."""
        try:
            if not self.review_mode:
                return
            
            # Get the index of the clicked position
            index = self.move_list_text.index(f"@{event.x},{event.y}")
            line = int(index.split('.')[0])
            
            # Calculate the move number (each line corresponds to a pair of moves)
            move_pair_index = line - 1  # Lines are 1-based in Tkinter
            move_index = move_pair_index * 2
            
            # Adjust for white or black move
            if self.move_list_text.get(f"{line}.0", f"{line}.end").strip().endswith('...'):
                move_index += 1  # Clicked on black's move
            
            if 0 <= move_index <= len(self.move_history):
                self.current_review_move = move_index
                self.update_board()
                self.update_status()
                self.update_eval_bar()
                self.update_move_list()
                self.setup_control_buttons()
                self.root.after(500, self.prompt_for_comment)
                logging.info(f"Navigated to move {self.current_review_move} via move list click")
        except Exception as e:
            logging.error(f"Move list click error: {e}", exc_info=True)

    def create_board(self):
        """Create the chess board GUI."""
        try:
            for r in range(8):
                for c in range(8):
                    if self.squares[r][c]:
                        self.squares[r][c].destroy()
                    
                    btn = tk.Button(
                        self.board_frame,
                        font=('Arial', CONFIG["font_sizes"]["piece"]),
                        command=lambda x=r, y=c: self.on_click(x, y),
                        relief='flat',
                        bd=1,
                        cursor='hand2'
                    )
                    btn.grid(row=r, column=c, padx=1, pady=1, sticky='nsew')
                    self.squares[r][c] = btn
            
            for i in range(8):
                self.board_frame.grid_rowconfigure(i, weight=1, uniform='chess_rows')
                self.board_frame.grid_columnconfigure(i, weight=1, uniform='chess_cols')
        except Exception as e:
            logging.error(f"Error creating board: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to initialize chess board")

    def on_window_resize(self, event):
        """Handle window resize events."""
        try:
            if event.widget == self.root:
                board_height = self.board_container.winfo_height()
                board_width = self.board_container.winfo_width()
                if board_height > 50 and board_width > 50:
                    new_size = max(12, min(24, int(min(board_height, board_width) / 30)))
                    for r in range(8):
                        for c in range(8):
                            if self.squares[r][c]:
                                self.squares[r][c].config(font=('Arial', new_size))
        except Exception as e:
            logging.error(f"Window resize error: {e}", exc_info=True)

    def on_closing(self):
        """Clean up resources when closing."""
        try:
            if self.engine:
                self.engine.quit()
            self.root.destroy()
        except Exception as e:
            logging.error(f"On closing error: {e}", exc_info=True)

    def get_promotion_piece(self, is_white):
        """Prompt user to select a pawn promotion piece."""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Pawn Promotion")
            dialog.geometry("200x180")
            dialog.transient(self.root)
            dialog.grab_set()
            dialog.configure(bg=CONFIG["gui"]["bg"])
            
            x = self.root.winfo_rootx() + (self.root.winfo_width() - 200) // 2
            y = self.root.winfo_rooty() + (self.root.winfo_height() - 180) // 2
            dialog.geometry(f"200x180+{x}+{y}")
            
            piece_var = tk.StringVar(value='Queen')
            tk.Label(dialog, text="Choose promotion piece:", font=('Arial', 12), fg='#ecf0f1', bg=CONFIG["gui"]["bg"]).pack(pady=10)
            
            for piece in ['Queen', 'Rook', 'Knight', 'Bishop']:
                tk.Radiobutton(dialog, text=piece, variable=piece_var, value=piece, font=('Arial', 10),
                              fg='#ecf0f1', bg=CONFIG["gui"]["bg"], selectcolor='#34495e').pack(anchor='w', padx=20)
            
            def confirm():
                dialog.result = piece_var.get()
                dialog.destroy()
            
            def cancel():
                dialog.result = None
                dialog.destroy()
            
            tk.Button(dialog, text="Confirm", command=confirm, font=('Arial', 10), bg='#3498db', fg='white', relief='flat', padx=20).pack(pady=5)
            tk.Button(dialog, text="Cancel", command=cancel, font=('Arial', 10), bg='#e74c3c', fg='white', relief='flat', padx=20).pack(pady=5)
            
            self.root.wait_window(dialog)
            piece_map = {'Queen': 'q', 'Rook': 'r', 'Knight': 'n', 'Bishop': 'b'}
            return piece_map.get(getattr(dialog, 'result', None), None)
        except Exception as e:
            logging.error(f"Promotion dialog error: {e}", exc_info=True)
            return None

    def make_move(self, move):
        """Make a move on the board."""
        try:
            with self.board_lock:
                if self.game_over or self.review_mode or move not in self.chess_board.legal_moves:
                    logging.warning(f"Invalid move attempt: {move.uci() if move else None}")
                    return False
                
                move_data = {'move': move, 'board': copy.deepcopy(self.chess_board)}
                self.chess_board.push(move)
                self.move_history.append(move_data)
                self.board_history.append(copy.deepcopy(self.chess_board))
                
                self.get_position_evaluation()
                
                self.current_turn = 'black' if self.current_turn == 'white' else 'white'
                self.last_move = (move.from_square, move.to_square)
                return True
        except Exception as e:
            logging.error(f"Make move error: {e}", exc_info=True)
            return False

    def get_position_evaluation(self):
        """Get position evaluation from Stockfish engine."""
        try:
            if not self.engine:
                self.evaluations.append(0.0)
                self.best_moves.append(None)
                return
            
            depth = CONFIG["stockfish"][self.ai_difficulty]["depth"]
            time_limit = CONFIG["stockfish"][self.ai_difficulty]["time"]
            
            eval_info = self.engine.analyse(
                self.chess_board, 
                chess.engine.Limit(depth=depth, time=time_limit)
            )
            
            if eval_info['score'].is_mate():
                eval_score = f"M{eval_info['score'].mate()}"
            else:
                centipawns = eval_info['score'].relative.cp
                eval_score = centipawns / 100.0 if centipawns is not None else 0.0
            
            self.evaluations.append(eval_score)
            pv = eval_info.get('pv', [])
            self.best_moves.append(pv[0] if pv else None)
        except Exception as e:
            logging.error(f"Evaluation error: {e}", exc_info=True)
            self.evaluations.append(0.0)
            self.best_moves.append(None)

    def undo_move(self):
        """Undo the last move(s)."""
        try:
            if not self.move_history or self.review_mode or self.ai_thinking:
                return False
            
            with self.board_lock:
                if not (len(self.move_history) == len(self.board_history) - 1 == len(self.evaluations) == len(self.best_moves)):
                    raise ChessError("Game state lists out of sync")
                
                moves_to_undo = 2 if len(self.move_history) >= 2 else 1
                
                for _ in range(moves_to_undo):
                    if self.move_history:
                        self.move_history.pop()
                        self.board_history.pop()
                        self.evaluations.pop()
                        self.best_moves.pop()
                        self.chess_board.pop()
                
                self.current_turn = 'white' if len(self.move_history) % 2 == 0 else 'black'
                self.game_over = False
                self.last_move = None
            
            self.update_board()
            self.update_status()
            self.update_eval_bar()
            self.update_move_list()
            return True
        except Exception as e:
            logging.error(f"Undo move error: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to undo move: {str(e)}")
            return False

    def resign(self):
        """Resign the game and save PGN."""
        try:
            if not self.game_over and not self.ai_thinking:
                winner = 'Black' if self.player_side == 'white' else 'White'
                self.status_label.config(text=f"You resigned! {winner} wins!")
                self.game_over = True
                self.auto_save_pgn()
                self.enter_review_mode()
        except Exception as e:
            logging.error(f"Resign error: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to resign game")

    def auto_save_pgn(self):
        """Automatically save the game as a PGN file."""
        try:
            if not self.move_history:
                logging.info("No moves to save for PGN")
                return
            
            game = self.create_pgn_game()
            save_dir = os.path.expanduser("~/ChessGames")
            os.makedirs(save_dir, exist_ok=True)
            
            file_path = os.path.join(save_dir, f"chess_game_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pgn")
            file_path = os.path.normpath(file_path)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                print(game, file=f)
            logging.info(f"Game automatically saved to {file_path}")
        except Exception as e:
            logging.error(f"Failed to auto-save PGN: {str(e)}", exc_info=True)

    def create_pgn_game(self):
        """Create a PGN game object from current state."""
        try:
            game = chess.pgn.Game()
            game.headers["Event"] = "Chess vs AI Game"
            game.headers["Site"] = "Local"
            game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
            game.headers["White"] = "Player" if self.player_side == 'white' else "AI"
            game.headers["Black"] = "AI" if self.player_side == 'white' else "Player"
            
            if self.chess_board.is_checkmate():
                game.headers["Result"] = "1-0" if self.current_turn == 'black' else "0-1"
            elif self.chess_board.is_stalemate() or self.chess_board.is_insufficient_material() or \
                 self.chess_board.is_fifty_moves() or self.chess_board.is_repetition():
                game.headers["Result"] = "1/2-1/2"
            elif self.game_over:
                game.headers["Result"] = "0-1" if self.player_side == 'white' else "1-0"
            else:
                game.headers["Result"] = "*"
            
            node = game
            temp_board = chess.Board()
            for i, move_data in enumerate(self.move_history):
                move = move_data['move']
                node = node.add_variation(move)
                if i in self.pgn_comments:
                    node.comment = self.pgn_comments[i]
                temp_board.push(move)
            
            return game
        except Exception as e:
            logging.error(f"Create PGN game error: {e}", exc_info=True)
            return chess.pgn.Game()

    def save_pgn(self):
        """Save the game as a PGN file with user-selected location."""
        try:
            if not self.move_history:
                messagebox.showinfo("Info", "No moves to save!")
                return
            
            game = self.create_pgn_game()
            file_path = filedialog.asksaveasfilename(
                defaultextension=".pgn",
                filetypes=[("PGN files", "*.pgn"), ("All files", "*.*")],
                title="Save PGN File",
                initialfile=f"chess_game_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pgn"
            )
            
            if file_path:
                file_path = os.path.normpath(file_path)
                if not os.path.basename(file_path).replace('.pgn', '').replace('_', '').isalnum():
                    raise ChessError("Invalid file name: use alphanumeric characters")
                with open(file_path, 'w', encoding='utf-8') as f:
                    print(game, file=f)
                messagebox.showinfo("Success", f"Game saved to {file_path}")
        except Exception as e:
            logging.error(f"Failed to save PGN: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"Failed to save PGN: {str(e)}")

    def load_pgn(self):
        """Load a PGN file and enter review mode."""
        try:
            if self.ai_thinking:
                messagebox.showinfo("Wait", "Please wait for AI to finish thinking")
                return

            file_path = filedialog.askopenfilename(
                filetypes=[("PGN files", "*.pgn"), ("All files", "*.*")],
                title="Load PGN File"
            )
            if not file_path:
                return

            file_path = os.path.normpath(file_path)
            with open(file_path, 'r', encoding='utf-8') as f:
                game = chess.pgn.read_game(f)
                if not game:
                    raise ChessError("Invalid or empty PGN file")

            with self.board_lock:
                self.reset_game()
                self.chess_board = game.board()
                self.move_history = []
                self.board_history = [copy.deepcopy(self.chess_board)]
                self.evaluations = [0.0]
                self.best_moves = [None]
                self.pgn_comments = {}

                node = game
                move_number = 0
                while node.variations:
                    move = node.variation(0).move
                    comment = node.variation(0).comment
                    if comment:
                        self.pgn_comments[move_number] = comment
                    move_data = {'move': move, 'board': copy.deepcopy(self.chess_board)}
                    self.chess_board.push(move)
                    self.move_history.append(move_data)
                    self.board_history.append(copy.deepcopy(self.chess_board))
                    self.get_position_evaluation()
                    node = node.variation(0)
                    move_number += 1

                self.game_over = True
                self.player_side = 'white' if game.headers.get("White", "").lower() == "player" else 'black'
                result = game.headers.get("Result", "*")
                status = {
                    "1-0": "White wins!",
                    "0-1": "Black wins!",
                    "1/2-1/2": "Draw!",
                    "*": "Game loaded"
                }.get(result, "Game loaded")
                self.status_label.config(text=status)

            self.enter_review_mode()
            messagebox.showinfo("Success", f"Loaded PGN from {file_path}")
        except Exception as e:
            logging.error(f"Load PGN error: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load PGN: {str(e)}")

    def on_click(self, gui_row, gui_col):
        """Handle square clicks on the board."""
        try:
            if self.game_over or self.review_mode or self.ai_thinking:
                return
            
            if self.player_side == 'black':
                board_row = 7 - gui_row
                board_col = gui_col
            else:
                board_row = gui_row
                board_col = gui_col
            
            square = chess.square(board_col, 7 - board_row)
            logging.info(f"Clicked square: {chess.square_name(square)}")
            
            if (self.current_turn == 'white') != (self.player_side == 'white'):
                return
            
            if self.selected_square is None:
                piece = self.chess_board.piece_at(square)
                if piece and piece.color == (self.current_turn == 'white'):
                    self.selected_square = square
                    logging.info(f"Selected piece: {piece.symbol()} at {chess.square_name(square)}")
                    self.update_board()
            else:
                if square == self.selected_square:
                    self.selected_square = None
                    self.update_board()
                elif (self.chess_board.piece_at(square) and 
                      self.chess_board.piece_at(square).color == (self.current_turn == 'white')):
                    self.selected_square = square
                    logging.info(f"Reselected piece: {self.chess_board.piece_at(square).symbol()} at {chess.square_name(square)}")
                    self.update_board()
                else:
                    self.attempt_move(square)
        except Exception as e:
            logging.error(f"On click error: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to process click")

    def attempt_move(self, target_square):
        """Attempt to make a move to the target square."""
        try:
            move = chess.Move(self.selected_square, target_square)
            
            if (self.chess_board.piece_at(self.selected_square).piece_type == chess.PAWN and
                chess.square_rank(target_square) in [0, 7]):
                promotion = self.get_promotion_piece(self.current_turn == 'white')
                if promotion is None:
                    self.selected_square = None
                    self.update_board()
                    return
                
                if promotion not in 'qrnb':
                    raise ChessError("Invalid promotion piece selected")
                
                move = chess.Move(
                    self.selected_square, 
                    target_square, 
                    promotion=chess.Piece.from_symbol(promotion).piece_type
                )
            
            if move in self.chess_board.legal_moves:
                if self.make_move(move):
                    self.selected_square = None
                    self.update_board()
                    self.update_status()
                    self.update_eval_bar()
                    self.update_move_list()
                    self.check_game_end()
                    
                    if not self.game_over and self.current_turn != self.player_side:
                        self.root.after(500, self.ai_move)
            else:
                messagebox.showinfo("Invalid Move", "That move is not legal!")
                self.squares[7 - chess.square_rank(target_square) if self.player_side == 'white' else chess.square_rank(target_square)][
                    chess.square_file(target_square)].config(bg='#FF6B6B')
                self.root.after(500, self.update_board)
            
            self.selected_square = None
            self.update_board()
        except Exception as e:
            logging.error(f"Attempt move error: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to process move: {str(e)}")

    def check_game_end(self):
        """Check if the game has ended and save PGN."""
        try:
            with self.board_lock:
                if self.chess_board.is_checkmate():
                    winner = 'Black' if self.current_turn == 'white' else 'White'
                    self.status_label.config(text=f"Checkmate! {winner} wins!")
                    self.game_over = True
                    self.auto_save_pgn()
                    self.root.after(1000, self.enter_review_mode)
                elif self.chess_board.is_stalemate():
                    self.status_label.config(text="Draw by stalemate!")
                    self.game_over = True
                    self.auto_save_pgn()
                    self.root.after(1000, self.enter_review_mode)
                elif self.chess_board.is_insufficient_material():
                    self.status_label.config(text="Draw by insufficient material!")
                    self.game_over = True
                    self.auto_save_pgn()
                    self.root.after(1000, self.enter_review_mode)
                elif self.chess_board.is_fifty_moves():
                    self.status_label.config(text="Draw by fifty-move rule!")
                    self.game_over = True
                    self.auto_save_pgn()
                    self.root.after(1000, self.enter_review_mode)
                elif self.chess_board.is_repetition():
                    self.status_label.config(text="Draw by repetition!")
                    self.game_over = True
                    self.auto_save_pgn()
                    self.root.after(1000, self.enter_review_mode)
        except Exception as e:
            logging.error(f"Check game end error: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to check game end")

    def enter_review_mode(self):
        """Enter game review mode."""
        try:
            self.review_mode = True
            self.current_review_move = len(self.move_history)
            self.setup_control_buttons()
            self.update_board()
            self.update_status()
            self.update_eval_bar()
            self.update_move_list()
        except Exception as e:
            logging.error(f"Enter review mode error: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to enter review mode")

    def exit_review(self):
        """Exit review mode."""
        try:
            self.review_mode = False
            self.setup_control_buttons()
            self.update_board()
            self.update_status()
            self.update_eval_bar()
            self.update_move_list()
        except Exception as e:
            logging.error(f"Exit review mode error: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to exit review mode")

    def prev_move(self):
        """Go to previous move in review."""
        try:
            if self.current_review_move > 0:
                self.current_review_move -= 1
                self.update_board()
                self.update_status()
                self.update_eval_bar()
                self.update_move_list()
                self.setup_control_buttons()
                self.root.after(500, self.prompt_for_comment)
        except Exception as e:
            logging.error(f"Previous move error: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to go to previous move")

    def next_move(self):
        """Go to next move in review."""
        try:
            if self.current_review_move < len(self.move_history):
                self.current_review_move += 1
                self.update_board()
                self.update_status()
                self.update_eval_bar()
                self.update_move_list()
                self.setup_control_buttons()
                self.root.after(500, self.prompt_for_comment)
        except Exception as e:
            logging.error(f"Next move error: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to go to next move")

    def update_board(self):
        """Update the visual representation of the board with thread safety."""
        try:
            with self.board_lock:
                if not self.squares or not all(self.squares[r][c] for r in range(8) for c in range(8)):
                    raise ChessError("Invalid squares array")
                
                board_state = self.board_history[self.current_review_move] if self.review_mode else self.chess_board
                
                for r in range(8):
                    for c in range(8):
                        square = chess.square(c, 7-r)
                        gui_r = 7 - chess.square_rank(square) if self.player_side == 'white' else chess.square_rank(square)
                        gui_c = chess.square_file(square)
                        
                        btn = self.squares[gui_r][gui_c]
                        if not btn:
                            continue
                        
                        piece = board_state.piece_at(square)
                        bg_color = CONFIG["board_colors"]["light"] if (gui_r + gui_c) % 2 == 0 else CONFIG["board_colors"]["dark"]
                        
                        if not self.review_mode:
                            if self.selected_square and square == self.selected_square:
                                bg_color = CONFIG["board_colors"]["selected"]
                            elif self.selected_square:
                                legal_moves = [m.to_square for m in self.chess_board.legal_moves 
                                             if m.from_square == self.selected_square]
                                if square in legal_moves:
                                    bg_color = CONFIG["board_colors"]["legal_move"]
                                    btn.config(text='●' if not piece else self.PIECES[piece.symbol()])
                                else:
                                    btn.config(text=self.PIECES.get(piece.symbol() if piece else '', ''))
                            
                            if self.last_move and square in [self.last_move[0], self.last_move[1]]:
                                bg_color = CONFIG["board_colors"]["last_move"]
                            
                            if self.chess_board.is_check():
                                king_square = self.chess_board.king(self.current_turn == 'white')
                                if square == king_square:
                                    bg_color = CONFIG["board_colors"]["check"]
                        else:
                            if self.current_review_move > 0:
                                move = self.move_history[self.current_review_move - 1]['move']
                                if square in [move.from_square, move.to_square]:
                                    bg_color = CONFIG["board_colors"]["last_move"]
                        
                        btn.config(text=self.PIECES.get(piece.symbol() if piece else '', '') if square not in 
                                  [m.to_square for m in self.chess_board.legal_moves if m.from_square == self.selected_square] else '●',
                                  bg=bg_color)
        except Exception as e:
            logging.error(f"Update board error: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to update board")

    def update_eval_bar(self):
        """Update the evaluation bar based on current position."""
        try:
            if not self.evaluations or self.current_review_move == 0:
                self.eval_canvas.coords(self.eval_bar, 4, 50, 16, 50)
                self.eval_label.config(text="0.00")
                return
            
            eval_index = min(self.current_review_move - 1, len(self.evaluations) - 1)
            eval_score = self.evaluations[eval_index]
            
            if eval_score is None:
                self.eval_label.config(text="N/A")
                self.eval_canvas.coords(self.eval_bar, 4, 50, 16, 50)
                return
            
            if isinstance(eval_score, str):
                self.eval_label.config(text=eval_score)
                if eval_score.startswith('M'):
                    self.eval_canvas.coords(self.eval_bar, 4, 10, 16, 50)
                    self.eval_canvas.itemconfig(self.eval_bar, fill='#ffffff')
                else:
                    self.eval_canvas.coords(self.eval_bar, 4, 50, 16, 90)
                    self.eval_canvas.itemconfig(self.eval_bar, fill='#000000')
                return
            
            score = max(min(float(eval_score), 5.0), -5.0)
            bar_height = int((score / 10.0) * 100)
            
            if score >= 0:
                self.eval_canvas.coords(self.eval_bar, 4, 50 - bar_height, 16, 50)
                self.eval_canvas.itemconfig(self.eval_bar, fill='#ffffff')
            else:
                self.eval_canvas.coords(self.eval_bar, 4, 50, 16, 50 - bar_height)
                self.eval_canvas.itemconfig(self.eval_bar, fill='#000000')
            
            self.eval_label.config(text=f"{eval_score:+.2f}" if isinstance(eval_score, (int, float)) else str(eval_score))
        except Exception as e:
            logging.error(f"Update eval bar error: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to update evaluation bar")

    def update_status(self):
        """Update status and analysis text."""
        try:
            if not hasattr(self, 'status_label'):
                return
            
            if self.review_mode:
                self.update_review_status()
            else:
                self.update_game_status()
        except Exception as e:
            logging.error(f"Update status error: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to update status")

    def update_game_status(self):
        """Update status during active game."""
        try:
            if self.game_over:
                return
            
            if self.ai_thinking:
                status = "AI is thinking... ⏳"
                self.progress_label.config(text="Processing...")
            else:
                status = f"{self.current_turn.title()}'s turn"
                self.progress_label.config(text="")
                if self.chess_board.is_check():
                    status += " - CHECK!"
            
            self.status_label.config(text=status)
            self.update_analysis_text()
        except Exception as e:
            logging.error(f"Update game status error: {e}", exc_info=True)

    def update_review_status(self):
        """Update status during review mode."""
        try:
            if self.current_review_move == len(self.move_history):
                status = "Review: Final position"
            elif self.current_review_move == 0:
                status = "Review: Starting position"
            else:
                move_num = (self.current_review_move + 1) // 2
                color = 'White' if self.current_review_move % 2 == 1 else 'Black'
                move = self.move_history[self.current_review_move - 1]['move']
                prev_board = self.board_history[self.current_review_move - 1]
                try:
                    move_text = prev_board.san(move)
                except:
                    move_text = move.uci()
                
                status = f"Review: Move {move_num} ({color}) - {move_text}"
            
            self.status_label.config(text=status)
            self.progress_label.config(text="")
            self.update_analysis_text()
        except Exception as e:
            logging.error(f"Update review status error: {e}", exc_info=True)

    def update_analysis_text(self):
        """Update the analysis text widget."""
        try:
            self.analysis_text.delete(1.0, tk.END)
            
            if self.current_review_move > 0 and self.current_review_move <= len(self.move_history):
                self.show_move_analysis()
            else:
                self.show_move_history()
        except Exception as e:
            logging.error(f"Update analysis text error: {e}", exc_info=True)

    def update_move_list(self):
        """Update the move list panel with visual indication of commented moves."""
        try:
            self.move_list_text.delete(1.0, tk.END)
            self.move_list_text.tag_remove("highlight", "1.0", tk.END)
            self.move_list_text.tag_remove("commented", "1.0", tk.END)
            
            for i in range(0, len(self.move_history), 2):
                move_num = (i + 2) // 2
                white_move = self.move_history[i]['move'] if i < len(self.move_history) else None
                black_move = self.move_history[i + 1]['move'] if i + 1 < len(self.move_history) else None
                board_before = self.board_history[i]
                
                line = f"{move_num}. "
                if white_move:
                    try:
                        line += board_before.san(white_move)
                    except:
                        line += white_move.uci()
                    if i in self.pgn_comments:
                        line += " {*}"
                if black_move:
                    try:
                        line += f" {board_before.san(black_move)}"
                    except:
                        line += f" {black_move.uci()}"
                    if i + 1 in self.pgn_comments:
                        line += " {*}"
                line += "\n"
                self.move_list_text.insert(tk.END, line)
                
                if self.review_mode and i // 2 == (self.current_review_move - 1) // 2:
                    self.move_list_text.tag_add("highlight", f"{i//2 + 1}.0", f"{i//2 + 1}.end")
                    self.move_list_text.tag_configure("highlight", background="#FFD700")
                
                # Highlight moves with comments
                if i in self.pgn_comments:
                    self.move_list_text.tag_add("commented", f"{i//2 + 1}.{len(str(move_num)) + 2}", 
                                              f"{i//2 + 1}.{len(str(move_num)) + 2 + len(board_before.san(white_move))}")
                    self.move_list_text.tag_configure("commented", foreground="#00FF00")
                if i + 1 in self.pgn_comments and black_move:
                    start_pos = len(str(move_num)) + 2 + len(board_before.san(white_move)) + 1
                    self.move_list_text.tag_add("commented", f"{i//2 + 1}.{start_pos}", 
                                              f"{i//2 + 1}.{start_pos + len(board_before.san(black_move))}")
                    self.move_list_text.tag_configure("commented", foreground="#00FF00")
        except Exception as e:
            logging.error(f"Update move list error: {e}", exc_info=True)

    def show_move_analysis(self):
        """Show analysis for the current move in review with enhanced comment and Ollama explanation display."""
        try:
            if self.current_review_move == 0:
                self.analysis_text.insert(tk.END, "Starting position\n")
                return
            
            if self.current_review_move > len(self.move_history):
                return
            
            move = self.move_history[self.current_review_move - 1]['move']
            prev_board = self.board_history[self.current_review_move - 1]
            try:
                move_text = prev_board.san(move)
            except:
                move_text = move.uci()
            
            move_num = (self.current_review_move + 1) // 2
            color = 'White' if self.current_review_move % 2 == 1 else 'Black'
            self.analysis_text.insert(tk.END, f"Move {move_num} ({color}): {move_text}\n\n")
            
            if len(self.evaluations) > self.current_review_move - 1 and self.evaluations[self.current_review_move - 1] is not None:
                curr_eval = self.evaluations[self.current_review_move - 1]
                prev_eval = self.evaluations[self.current_review_move - 2] if self.current_review_move > 1 else 0.0
                
                if isinstance(curr_eval, str) or isinstance(prev_eval, str):
                    self.analysis_text.insert(tk.END, "Mate position reached\n")
                else:
                    eval_change = curr_eval - prev_eval
                    if self.current_review_move % 2 == 0:
                        eval_change = -eval_change
                    
                    self.analysis_text.insert(tk.END, f"Evaluation: {curr_eval:+.2f}\n")
                    
                    if abs(eval_change) > 2.0:
                        self.analysis_text.insert(tk.END, f"⚠️ Blunder! ({eval_change:+.2f})\n")
                    elif abs(eval_change) > 1.0:
                        self.analysis_text.insert(tk.END, f"❌ Mistake ({eval_change:+.2f})\n")
                    elif abs(eval_change) > 0.5:
                        self.analysis_text.insert(tk.END, f"⚡ Inaccuracy ({eval_change:+.2f})\n")
                    elif abs(eval_change) < 0.1:
                        self.analysis_text.insert(tk.END, "✅ Excellent move!\n")
            
            if (len(self.best_moves) > self.current_review_move - 1 and 
                self.best_moves[self.current_review_move - 1] and 
                self.best_moves[self.current_review_move - 1] != move):
                
                best_move = self.best_moves[self.current_review_move - 1]
                try:
                    best_move_text = prev_board.san(best_move)
                    self.analysis_text.insert(tk.END, f"\nBest move was: {best_move_text}\n")
                except:
                    pass

            if self.current_review_move - 1 in self.pgn_comments:
                comment = self.pgn_comments[self.current_review_move - 1]
                tag = "ai_comment" if comment.startswith("AI (Ollama):") else "user_comment"
                self.analysis_text.insert(tk.END, f"\nComment: {comment}\n", tag)
                self.analysis_text.tag_configure("ai_comment", foreground="#00B7EB", font=('Arial', CONFIG["font_sizes"]["analysis"], 'italic'))
                self.analysis_text.tag_configure("user_comment", foreground="#00FF00", font=('Arial', CONFIG["font_sizes"]["analysis"], 'bold'))
            
            # Prompt for user comment after displaying analysis
            self.root.after(500, self.prompt_for_comment)
        except Exception as e:
            logging.error(f"Show move analysis error: {e}", exc_info=True)

    def show_move_history(self):
        """Show recent move history."""
        try:
            self.analysis_text.insert(tk.END, "Recent moves:\n\n")
            start_idx = max(0, len(self.move_history) - 10)
            
            for i in range(start_idx, len(self.move_history)):
                move_data = self.move_history[i]
                move = move_data['move']
                board_before = self.board_history[i]
                
                try:
                    san = board_before.san(move)
                    move_num = (i + 2) // 2
                    
                    if i % 2 == 0:
                        self.analysis_text.insert(tk.END, f"{move_num}. {san}")
                    else:
                        if i == len(self.move_history) - 1:
                            self.analysis_text.insert(tk.END, f" {san}\n")
                        else:
                            self.analysis_text.insert(tk.END, f" {san}\n")
                except Exception as e:
                    logging.error(f"Error generating SAN for move {move.uci()}: {e}", exc_info=True)
                    continue
        except Exception as e:
            logging.error(f"Show move history error: {e}", exc_info=True)

    @lru_cache(maxsize=CONFIG["transposition_table_size"])
    def cached_ollama_move(self, fen):
        """Cached helper for Ollama move generation with strategic explanation."""
        try:
            legal_moves = [move.uci() for move in self.chess_board.legal_moves]
            side = 'White' if self.current_turn == 'white' else 'Black'
            recent_moves = ' '.join(board_before.san(move_data['move']) 
                                  for move_data, board_before in 
                                  zip(self.move_history[-3:], self.board_history[-4:-1]))
            
            prompt = (
                f"You are a chess expert playing as {side}.\n"
                f"Current position (FEN): {fen}\n"
                f"Recent moves: {recent_moves or 'None'}\n"
                f"Legal moves in UCI format: {', '.join(legal_moves) if legal_moves else 'None'}\n"
                f"Your task is to select the best legal move for {side} and provide a 1-2 sentence explanation "
                f"emphasizing strategic goals like piece development, central control, king safety, or preparation for key plans (e.g., castling, attacks).\n"
                f"Respond in the format:\n"
                f"Move: <UCI move>\n"
                f"Explanation: <1-2 sentence strategic explanation>\n"
                f"Example:\n"
                f"Move: e7e5\n"
                f"Explanation: This move develops a piece while also reinforcing control over the center and preparing for kingside castling.\n"
                f"Do NOT include additional text or punctuation outside this format"
            )
            
            if len(self.move_history) < 10:
                if self.current_turn == 'white':
                    prompt += "\nPrioritize opening moves like e4, d4, Nf3, or c4 to control the center and develop pieces."
                else:
                    prompt += "\nPrioritize responses like e5, d5, Nf6, or c5 to counter White's center and prepare development."
            
            uci_pattern = r'^[a-h][1-8][a-h][1-8][qrbn]?$'  # Matches UCI moves, including castling
            
            for attempt in range(3):
                try:
                    response = ollama.generate(
                        model=self.ollama_model,
                        prompt=prompt,
                        options={
                            'temperature': CONFIG["ollama"]["temperature"],
                            'top_p': CONFIG["ollama"]["top_p"],
                            'num_predict': CONFIG["ollama"]["num_predict"],
                            'timeout': self.ollama_timeout
                        }
                    )
                    
                    response_text = response["response"].strip()
                    logging.info(f"Ollama response (attempt {attempt + 1}): {response_text}")
                    
                    # Parse response for move and explanation
                    move_match = re.search(r'Move: ([a-h][1-8][a-h][1-8][qrbn]?)\n', response_text)
                    explanation_match = re.search(r'Explanation: (.+?)(?:\n|$)', response_text, re.DOTALL)
                    
                    if not move_match:
                        logging.warning(f"Ollama attempt {attempt + 1} failed: Invalid response format")
                        continue
                    
                    move_str = move_match.group(1).strip()
                    explanation = explanation_match.group(1).strip() if explanation_match else "No strategic explanation provided."
                    
                    if not re.match(uci_pattern, move_str):
                        logging.warning(f"Ollama attempt {attempt + 1} failed: Invalid UCI format {move_str}")
                        continue
                    
                    move = chess.Move.from_uci(move_str)
                    if move in self.chess_board.legal_moves:
                        logging.info(f"Valid move: {move_str}, Explanation: {explanation}")
                        return move_str, explanation
                    else:
                        logging.warning(f"Ollama attempt {attempt + 1} failed: Move {move_str} not in legal moves")
                
                except Exception as e:
                    logging.error(f"Ollama attempt {attempt + 1} error: {e}", exc_info=True)
                
                if attempt < 2:
                    time.sleep(2 ** attempt)  # Exponential backoff
            
            logging.warning("No valid move found, falling back")
            return None, "No valid move found."
        except Exception as e:
            logging.error(f"Cached Ollama move error: {e}", exc_info=True)
            return None, str(e)

    def get_ollama_move(self):
        """Get move and explanation from Ollama with caching."""
        try:
            with self.board_lock:
                fen = self.chess_board.fen()
                result = self.cached_ollama_move(fen)
                if result and result[0]:
                    move = chess.Move.from_uci(result[0])
                    if move in self.chess_board.legal_moves:
                        # Store explanation as a comment if AI makes this move
                        if result[1] and self.current_turn != self.player_side:
                            self.pgn_comments[len(self.move_history)] = f"AI (Ollama): {result[1]}"
                        return move
                return None
        except Exception as e:
            logging.error(f"Get Ollama move error: {e}", exc_info=True)
            return None

    def get_opening_move(self):
        """Get move from opening book if available."""
        try:
            if os.path.exists(CONFIG["paths"]["openings"]):
                with chess.polyglot.open_reader(CONFIG["paths"]["openings"]) as reader:
                    entry = reader.find(self.chess_board)
                    return entry.move
            return None
        except Exception as e:
            logging.error(f"Opening book error: {e}", exc_info=True)
            return None

    def get_stockfish_move(self):
        """Get move from Stockfish engine."""
        try:
            if not self.engine:
                return None
            
            with self.board_lock:
                time_limit = CONFIG["stockfish"][self.ai_difficulty]["time"]
                depth = CONFIG["stockfish"][self.ai_difficulty]["depth"]
                result = self.engine.play(
                    self.chess_board,
                    chess.engine.Limit(time=time_limit, depth=depth)
                )
                return result.move
        except Exception as e:
            logging.error(f"Stockfish error: {e}", exc_info=True)
            return None

    def get_random_move(self):
        """Get random legal move as last resort."""
        try:
            with self.board_lock:
                legal_moves = list(self.chess_board.legal_moves)
                if legal_moves:
                    return random.choice(legal_moves)
                return None
        except Exception as e:
            logging.error(f"Get random move error: {e}", exc_info=True)
            return None

    def generate_ollama_explanation(self, move):
        """Generate an Ollama explanation for a given move."""
        try:
            with self.board_lock:
                fen = self.chess_board.fen()
                side = 'White' if self.current_turn == 'white' else 'Black'
                recent_moves = ' '.join(board_before.san(move_data['move']) 
                                      for move_data, board_before in 
                                      zip(self.move_history[-3:], self.board_history[-4:-1]))
                try:
                    move_san = self.chess_board.san(move)
                except:
                    move_san = move.uci()
                
                prompt = (
                    f"You are a chess expert analyzing a game as {side}.\n"
                    f"Current position (FEN): {fen}\n"
                    f"Recent moves: {recent_moves or 'None'}\n"
                    f"Move to explain: {move_san} ({move.uci()})\n"
                    f"Provide a 1-2 sentence explanation of why this move is strategically sound, "
                    f"focusing on chess principles like piece development, central control, king safety, or preparation for key plans (e.g., castling, attacks).\n"
                    f"Respond in the format:\n"
                    f"Explanation: <1-2 sentence strategic explanation>\n"
                    f"Example:\n"
                    f"Explanation: This move develops a piece while also reinforcing control over the center and preparing for kingside castling.\n"
                    f"Do NOT include additional text or punctuation outside this format"
                )
                
                response = ollama.generate(
                    model=self.ollama_model,
                    prompt=prompt,
                    options={
                        'temperature': CONFIG["ollama"]["temperature"],
                        'top_p': CONFIG["ollama"]["top_p"],
                        'num_predict': CONFIG["ollama"]["num_predict"],
                        'timeout': self.ollama_timeout
                    }
                )
                
                response_text = response["response"].strip()
                explanation_match = re.search(r'Explanation: (.+?)(?:\n|$)', response_text, re.DOTALL)
                explanation = explanation_match.group(1).strip() if explanation_match else "No strategic explanation provided."
                
                logging.info(f"Explanation for {move.uci()}: {explanation}")
                return explanation
        except Exception as e:
            logging.error(f"Generate Ollama explanation error: {e}", exc_info=True)
            return "Failed to generate explanation."

    def ai_move(self):
        """Handle AI move generation in a separate thread."""
        try:
            if (self.game_over or 
                self.current_turn == self.player_side or 
                self.review_mode or 
                self.ai_thinking):
                return
            
            self.ai_thinking = True
            self.status_label.config(text="AI is thinking... ⏳")
            self.root.config(cursor="wait")
            
            def get_ai_move():
                start_time = time.time()
                move = None
                explanation = None
                
                try:
                    # Try opening book first
                    if len(self.move_history) < 10:
                        move = self.get_opening_move()
                        if move:
                            logging.info(f"Opening move: {move.uci()}")
                    
                    # Try Ollama
                    if not move:
                        result = self.get_ollama_move()
                        if result:
                            move = result
                            logging.info(f"Ollama move: {move.uci()}")
                        else:
                            raise ChessError("Ollama failed to provide valid move")
                
                except Exception as e:
                    logging.error(f"Ollama failed: {e}", exc_info=True)
                    
                    if self.engine:
                        try:
                            move = self.get_stockfish_move()
                            logging.info(f"Stockfish move: {move.uci()}")
                        except Exception as e2:
                            logging.error(f"Stockfish failed: {e2}", exc_info=True)
                            move = self.get_random_move()
                            logging.info(f"Random move: {move.uci() if move else 'None'}")
                    else:
                        move = self.get_random_move()
                        logging.info(f"Random move: {move.uci() if move else 'None'}")
                
                # Generate explanation for non-Ollama moves
                if move and not explanation:
                    explanation = self.generate_ollama_explanation(move)
                
                def execute_move():
                    try:
                        self.ai_thinking = False
                        self.root.config(cursor="")
                        if move and self.make_move(move):
                            if explanation:
                                self.pgn_comments[len(self.move_history) - 1] = f"AI (Ollama): {explanation}"
                            self.update_board()
                            self.update_status()
                            self.update_eval_bar()
                            self.update_move_list()
                            self.check_game_end()
                        
                        logging.info(f"AI move took {time.time() - start_time:.2f} seconds")
                    except Exception as e:
                        logging.error(f"Execute AI move error: {e}", exc_info=True)
                        self.root.config(cursor="")
                        messagebox.showerror("Error", "Failed to execute AI move")
                
                self.root.after(0, execute_move)
            
            threading.Thread(target=get_ai_move, daemon=True).start()
        except Exception as e:
            logging.error(f"AI move error: {e}", exc_info=True)
            self.ai_thinking = False
            self.root.config(cursor="")
            messagebox.showerror("Error", "Failed to process AI move")

    def new_game(self):
        """Start a new game."""
        try:
            if self.ai_thinking:
                messagebox.showinfo("Wait", "Please wait for AI to finish thinking")
                return
                
            self.reset_game()
            self.setup_control_buttons()
            
            if self.player_side == 'black':
                self.root.after(1000, self.ai_move)
        except Exception as e:
            logging.error(f"New game error: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to start new game")

    def switch_side(self):
        """Switch player side (white/black)."""
        try:
            if self.ai_thinking:
                messagebox.showinfo("Wait", "Please wait for AI to finish thinking")
                return
                
            self.player_side = 'black' if self.player_side == 'white' else 'white'
            self.new_game()
        except Exception as e:
            logging.error(f"Switch side error: {e}", exc_info=True)
            messagebox.showerror("Error", "Failed to switch side")

    def run(self):
        """Run the Tkinter application."""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            logging.info("Application interrupted")
        except Exception as e:
            logging.error(f"Application run error: {e}", exc_info=True)
        finally:
            self.on_closing()

def main():
    """Main entry point for the application."""
    try:
        required_modules = ['chess', 'ollama', 'dotenv']
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                logging.error(f"Required module '{module}' not found. Please install it using: pip install {module}")
                return
        
        app = ChessVsAI()
        app.run()
    except Exception as e:
        logging.error(f"Application startup error: {e}", exc_info=True)
        messagebox.showerror("Error", f"Failed to start application: {str(e)}")

if __name__ == "__main__":
    main()