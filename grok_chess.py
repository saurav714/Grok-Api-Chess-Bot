import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import chess
import chess.engine
import chess.pgn
import copy
import time
import ollama
import threading
import random
import os
from datetime import datetime
from dotenv import load_dotenv
import traceback
from collections import OrderedDict

class ChessVsAI:
    def __init__(self):
        self.PIECES = {
            'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
            'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'
        }
        self.player_side = 'white'
        self.transposition_table = OrderedDict()
        self.transposition_table_max_size = 1000
        self.review_mode = False
        self.current_review_move = 0
        self.ai_thinking = False
        self.board_lock = threading.Lock()
        self.pgn_comments = {}  # Store PGN comments
        
        # Load environment variables
        load_dotenv()
        
        # Stockfish configuration
        self.stockfish_path = os.getenv("STOCKFISH_PATH", r"C:\Users\HP\Desktop\Grok Api Chess Bot\stockfish.exe")
        self.engine = None
        self.init_stockfish()
        
        # Ollama configuration
        self.ollama_model = os.getenv("OLLAMA_MODEL", "phi3")
        self.ollama_timeout = float(os.getenv("OLLAMA_TIMEOUT", "30.0"))
        
        # Initialize GUI components
        self.squares = [[None for _ in range(8)] for _ in range(8)]
        self.setup_gui()
        self.reset_game()

    def init_stockfish(self):
        """Initialize Stockfish engine with error handling"""
        try:
            if not os.path.exists(self.stockfish_path):
                print(f"Stockfish not found at '{self.stockfish_path}'")
                self.engine = None
                messagebox.showerror("Stockfish Error", f"Stockfish executable not found at '{self.stockfish_path}'. Please set STOCKFISH_PATH in .env file.")
                return
            self.engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
            self.engine.configure({
                "Threads": min(4, os.cpu_count() or 2),
                "Hash": 256,
                "UCI_LimitStrength": False
            })
            print("Stockfish loaded successfully.")
        except Exception as e:
            print(f"Failed to load Stockfish: {e}")
            traceback.print_exc()
            self.engine = None
            messagebox.showerror("Stockfish Error", "Failed to initialize Stockfish. AI will use Ollama or random moves.")

    def reset_game(self):
        """Reset the game state"""
        try:
            with self.board_lock:
                self.chess_board = chess.Board()
                self.move_history = []
                self.board_history = [copy.deepcopy(self.chess_board)]
                self.evaluations = []
                self.best_moves = []
                self.selected_square = None
                self.last_move = None
                self.current_turn = 'white'
                self.game_over = False
                self.review_mode = False
                self.current_review_move = 0
                self.ai_thinking = False
                self.transposition_table.clear()
                self.pgn_comments = {}
            
            if hasattr(self, 'root'):
                self.update_board()
                self.update_status()
                self.update_eval_bar()
        except Exception as e:
            print(f"Reset game error: {e}")
            traceback.print_exc()

    def setup_gui(self):
        """Initialize the GUI"""
        try:
            self.root = tk.Tk()
            self.root.title("Chess vs AI with LLM")
            self.root.configure(bg='#2c3e50')
            self.root.geometry("900x700")
            self.root.resizable(True, True)
            self.root.minsize(700, 500)

            main_frame = tk.Frame(self.root, bg='#2c3e50')
            main_frame.pack(padx=10, pady=10, expand=True, fill='both')

            title_label = tk.Label(
                main_frame, 
                text="♔ Chess vs AI ♚", 
                font=('Arial', 20, 'bold'), 
                fg='#ecf0f1', 
                bg='#2c3e50'
            )
            title_label.pack(pady=(0, 15))

            content_frame = tk.Frame(main_frame, bg='#2c3e50')
            content_frame.pack(expand=True, fill='both')

            self.board_container = tk.Frame(content_frame, bg='#34495e', relief='raised', bd=2)
            self.board_container.pack(side='left', padx=(0, 15), expand=True, fill='both')
            
            self.board_frame = tk.Frame(self.board_container, bg='#34495e')
            self.board_frame.pack(expand=True, fill='both', padx=10, pady=10)

            self.control_panel = tk.Frame(content_frame, bg='#2c3e50', width=250)
            self.control_panel.pack(side='right', fill='y')
            self.control_panel.pack_propagate(False)

            self.setup_status_panel()
            self.setup_control_buttons()
            self.setup_analysis_panel()

            self.debug_panel = tk.Frame(self.control_panel, bg='#2c3e50')
            self.debug_panel.pack(fill='x', pady=(10, 0))
            tk.Label(self.debug_panel, text="Ollama Debug", font=('Arial', 11, 'bold'), fg='#ecf0f1', bg='#2c3e50').pack()
            self.debug_text = tk.Text(
                self.debug_panel,
                font=('Arial', 9),
                fg='#ecf0f1',
                bg='#34495e',
                wrap='word',
                height=4,
                relief='flat',
                padx=5,
                pady=5
            )
            scrollbar = tk.Scrollbar(self.debug_panel, orient='vertical', command=self.debug_text.yview)
            self.debug_text.configure(yscrollcommand=scrollbar.set)
            self.debug_text.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            self.create_board()
            
            self.root.bind('<Configure>', self.on_window_resize)
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

            if self.player_side == 'black':
                self.root.after(1000, self.ai_move)
        except Exception as e:
            print(f"GUI setup error: {e}")
            traceback.print_exc()
            messagebox.showerror("Error", "Failed to initialize GUI")

    def setup_status_panel(self):
        """Setup the status and evaluation panel"""
        try:
            status_frame = tk.Frame(self.control_panel, bg='#2c3e50')
            status_frame.pack(fill='x', pady=(0, 15))

            self.status_label = tk.Label(
                status_frame, 
                text="Your move", 
                font=('Arial', 12, 'bold'), 
                fg='#ecf0f1', 
                bg='#2c3e50',
                wraplength=230
            )
            self.status_label.pack()

            eval_frame = tk.Frame(status_frame, bg='#2c3e50')
            eval_frame.pack(pady=(10, 0))

            tk.Label(eval_frame, text="Evaluation", font=('Arial', 10), fg='#bdc3c7', bg='#2c3e50').pack()
            
            self.eval_canvas = tk.Canvas(
                eval_frame, 
                width=30, 
                height=150, 
                bg='#34495e', 
                highlightthickness=1,
                highlightbackground='#bdc3c7'
            )
            self.eval_canvas.pack(pady=5)
            
            self.eval_bar = self.eval_canvas.create_rectangle(5, 75, 25, 75, fill='#bdc3c7', outline='#7f8c8d')
            
            self.eval_label = tk.Label(
                eval_frame, 
                text="0.00", 
                font=('Arial', 10, 'bold'), 
                fg='#ecf0f1', 
                bg='#2c3e50'
            )
            self.eval_label.pack()
        except Exception as e:
            print(f"Status panel setup error: {e}")
            traceback.print_exc()
            messagebox.showerror("Error", "Failed to setup status panel")

    def setup_control_buttons(self):
        """Setup control buttons based on current mode"""
        try:
            if hasattr(self, 'control_frame'):
                self.control_frame.destroy()

            self.control_frame = tk.Frame(self.control_panel, bg='#2c3e50')
            self.control_frame.pack(pady=10)

            btn_style = {
                'font': ('Arial', 9, 'bold'),
                'bg': '#3498db',
                'fg': 'white',
                'relief': 'flat',
                'padx': 15,
                'pady': 5,
                'width': 15,
                'cursor': 'hand2'
            }

            if not self.review_mode:
                buttons = [
                    ("New Game", self.new_game),
                    ("Switch Side", self.switch_side),
                    ("Undo Move", self.undo_move),
                    ("Resign", self.resign),
                    ("Save PGN", self.save_pgn),
                    ("Load PGN", self.load_pgn)
                ]
            else:
                buttons = [
                    ("\u25C0 Previous", self.prev_move),
                    ("Next \u25B6", self.next_move),
                    ("Exit Review", self.exit_review),
                    ("New Game", self.new_game),
                    ("Save PGN", self.save_pgn),
                    ("Load PGN", self.load_pgn)
                ]

            for text, command in buttons:
                btn = tk.Button(self.control_frame, text=text, command=command, **btn_style)
                btn.pack(pady=2)
                btn.bind("<Enter>", lambda e, b=btn: b.config(bg='#2980b9'))
                btn.bind("<Leave>", lambda e, b=btn: b.config(bg='#3498db'))
        except Exception as e:
            print(f"Control buttons setup error: {e}")
            traceback.print_exc()
            messagebox.showerror("Error", "Failed to setup control buttons")

    def setup_analysis_panel(self):
        """Setup the analysis text panel"""
        try:
            analysis_frame = tk.Frame(self.control_panel, bg='#2c3e50')
            analysis_frame.pack(fill='both', expand=True, pady=(15, 0))

            tk.Label(
                analysis_frame, 
                text="Analysis", 
                font=('Arial', 11, 'bold'), 
                fg='#ecf0f1', 
                bg='#2c3e50'
            ).pack()

            text_frame = tk.Frame(analysis_frame, bg='#34495e', relief='sunken', bd=1)
            text_frame.pack(fill='both', expand=True, pady=5)

            self.analysis_text = tk.Text(
                text_frame,
                font=('Arial', 9),
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
            print(f"Analysis panel setup error: {e}")
            traceback.print_exc()
            messagebox.showerror("Error", "Failed to setup analysis panel")

    def create_board(self):
        """Create the chess board GUI"""
        try:
            for r in range(8):
                for c in range(8):
                    if self.squares[r][c]:
                        self.squares[r][c].destroy()
                    
                    btn = tk.Button(
                        self.board_frame,
                        font=('Arial', 16),
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
            print(f"Error creating board: {e}")
            traceback.print_exc()
            messagebox.showerror("Error", "Failed to initialize chess board")

    def on_window_resize(self, event):
        """Handle window resize events"""
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
            print(f"Window resize error: {e}")
            traceback.print_exc()

    def on_closing(self):
        """Clean up resources when closing"""
        try:
            if self.engine:
                self.engine.quit()
            self.root.destroy()
        except:
            pass

    def get_promotion_piece(self, is_white):
        """Get promotion piece from user"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Pawn Promotion")
            dialog.geometry("200x180")
            dialog.transient(self.root)
            dialog.grab_set()
            dialog.configure(bg='#2c3e50')
            
            x = self.root.winfo_rootx() + (self.root.winfo_width() - 200) // 2
            y = self.root.winfo_rooty() + (self.root.winfo_height() - 180) // 2
            dialog.geometry(f"200x180+{x}+{y}")
            
            piece_var = tk.StringVar(value='Queen')
            tk.Label(dialog, text="Choose promotion piece:", font=('Arial', 12), fg='#ecf0f1', bg='#2c3e50').pack(pady=10)
            
            for piece in ['Queen', 'Rook', 'Knight', 'Bishop']:
                tk.Radiobutton(dialog, text=piece, variable=piece_var, value=piece, font=('Arial', 10),
                              fg='#ecf0f1', bg='#2c3e50', selectcolor='#34495e').pack(anchor='w', padx=20)
            
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
            print(f"Promotion dialog error: {e}")
            traceback.print_exc()
            return None

    def make_move(self, move):
        """Make a move on the board"""
        try:
            with self.board_lock:
                if self.game_over or self.review_mode or move not in self.chess_board.legal_moves:
                    print(f"Invalid move attempt: {move.uci() if move else None}")
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
            print(f"Make move error: {e}")
            traceback.print_exc()
            return False

    def get_position_evaluation(self):
        """Get position evaluation from engine"""
        try:
            if self.engine:
                eval_info = self.engine.analyse(
                    self.chess_board, 
                    chess.engine.Limit(depth=15, time=2.0)
                )
                
                if eval_info['score'].is_mate():
                    eval_score = f"M{eval_info['score'].mate()}"
                else:
                    centipawns = eval_info['score'].relative.cp
                    eval_score = centipawns / 100.0 if centipawns is not None else 0.0
                
                self.evaluations.append(eval_score)
                pv = eval_info.get('pv', [])
                self.best_moves.append(pv[0] if pv else None)
            else:
                self.evaluations.append(0.0)
                self.best_moves.append(None)
        except Exception as e:
            print(f"Evaluation error: {e}")
            traceback.print_exc()
            self.evaluations.append(0.0)
            self.best_moves.append(None)

    def undo_move(self):
        """Undo the last move"""
        try:
            if not self.move_history or self.review_mode or self.ai_thinking:
                return False
            
            with self.board_lock:
                if not (len(self.move_history) == len(self.board_history) - 1 == len(self.evaluations) == len(self.best_moves)):
                    print("Error: Game state lists out of sync")
                    self.reset_game()
                    return False
                
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
            return True
        except Exception as e:
            print(f"Undo move error: {e}")
            traceback.print_exc()
            return False

    def resign(self):
        """Resign the game and save PGN"""
        try:
            if not self.game_over and not self.ai_thinking:
                winner = 'Black' if self.player_side == 'white' else 'White'
                self.status_label.config(text=f"You resigned! {winner} wins!")
                self.game_over = True
                self.auto_save_pgn()
                self.enter_review_mode()
        except Exception as e:
            print(f"Resign error: {e}")
            traceback.print_exc()

    def auto_save_pgn(self):
        """Automatically save the game as a PGN file"""
        try:
            if not self.move_history:
                print("No moves to save for PGN")
                return
            
            game = chess.pgn.Game()
            game.headers["Event"] = "Chess vs AI Game"
            game.headers["Site"] = "Local"
            game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
            game.headers["White"] = "Player" if self.player_side == 'white' else "AI"
            game.headers["Black"] = "AI" if self.player_side == 'white' else "Player"
            
            if self.chess_board.is_checkmate():
                game.headers["Result"] = "1-0" if self.current_turn == 'black' else "0-1"
            elif self.chess_board.is_stalemate() or self.chess_board.is_insufficient_material() or self.chess_board.is_fifty_moves() or self.chess_board.is_repetition():
                game.headers["Result"] = "1/2-1/2"
            elif self.game_over:
                game.headers["Result"] = "0-1" if self.player_side == 'white' else "1-0"
            else:
                game.headers["Result"] = "*"
            
            node = game
            temp_board = chess.Board()
            for move_data in self.move_history:
                move = move_data['move']
                node = node.add_variation(move)
                temp_board.push(move)
            
            save_dir = os.path.expanduser("~/ChessGames")
            try:
                os.makedirs(save_dir, exist_ok=True)
            except Exception as e:
                print(f"Failed to create directory {save_dir}: {e}")
                traceback.print_exc()
                return
            
            file_path = os.path.join(save_dir, f"chess_game_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pgn")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                print(game, file=f)
            print(f"Game automatically saved to {file_path}")
        except Exception as e:
            print(f"Failed to auto-save PGN: {str(e)}")
            traceback.print_exc()

    def save_pgn(self):
        """Save the game as a PGN file with user-selected location"""
        try:
            if not self.move_history:
                messagebox.showinfo("Info", "No moves to save!")
                return
            
            game = chess.pgn.Game()
            game.headers["Event"] = "Chess vs AI Game"
            game.headers["Site"] = "Local"
            game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
            game.headers["White"] = "Player" if self.player_side == 'white' else "AI"
            game.headers["Black"] = "AI" if self.player_side == 'white' else "Player"
            
            if self.chess_board.is_checkmate():
                game.headers["Result"] = "1-0" if self.current_turn == 'black' else "0-1"
            elif self.chess_board.is_stalemate() or self.chess_board.is_insufficient_material() or self.chess_board.is_fifty_moves() or self.chess_board.is_repetition():
                game.headers["Result"] = "1/2-1/2"
            elif self.game_over:
                game.headers["Result"] = "0-1" if self.player_side == 'white' else "1-0"
            else:
                game.headers["Result"] = "*"
            
            node = game
            temp_board = chess.Board()
            for move_data in self.move_history:
                move = move_data['move']
                node = node.add_variation(move)
                temp_board.push(move)
            
            file_path = filedialog.asksaveasfilename(
                defaultextension=".pgn",
                filetypes=[("PGN files", "*.pgn"), ("All files", "*.*")],
                title="Save PGN File",
                initialfile=f"chess_game_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pgn"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    print(game, file=f)
                messagebox.showinfo("Success", f"Game saved to {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save PGN: {str(e)}")
            traceback.print_exc()

    def load_pgn(self):
        """Load a PGN file and enter review mode"""
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

            with open(file_path, 'r', encoding='utf-8') as f:
                game = chess.pgn.read_game(f)
                if not game:
                    messagebox.showerror("Error", "Invalid or empty PGN file")
                    return

            # Reset game state
            with self.board_lock:
                self.reset_game()
                self.chess_board = game.board()
                self.move_history = []
                self.board_history = [copy.deepcopy(self.chess_board)]
                self.evaluations = [0.0]
                self.best_moves = [None]
                self.pgn_comments = {}

                # Replay moves and compute evaluations
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

                # Set game result and headers
                self.game_over = True
                self.player_side = 'white' if game.headers.get("White", "").lower() == "player" else 'black'
                result = game.headers.get("Result", "*")
                if result == "1-0":
                    status = "White wins!"
                elif result == "0-1":
                    status = "Black wins!"
                elif result == "1/2-1/2":
                    status = "Draw!"
                else:
                    status = "Game loaded"
                self.status_label.config(text=status)

            # Enter review mode
            self.enter_review_mode()
            messagebox.showinfo("Success", f"Loaded PGN from {file_path}")
        except Exception as e:
            print(f"Load PGN error: {e}")
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load PGN: {str(e)}")

    def on_click(self, gui_row, gui_col):
        """Handle square clicks"""
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
            print(f"Clicked square: {chess.square_name(square)}")
            
            if (self.current_turn == 'white') != (self.player_side == 'white'):
                return
            
            if self.selected_square is None:
                piece = self.chess_board.piece_at(square)
                if piece and piece.color == (self.current_turn == 'white'):
                    self.selected_square = square
                    print(f"Selected piece: {piece.symbol()} at {chess.square_name(square)}")
                    self.update_board()
            else:
                if square == self.selected_square:
                    self.selected_square = None
                    self.update_board()
                elif (self.chess_board.piece_at(square) and 
                      self.chess_board.piece_at(square).color == (self.current_turn == 'white')):
                    self.selected_square = square
                    print(f"Reselected piece: {self.chess_board.piece_at(square).symbol()} at {chess.square_name(square)}")
                    self.update_board()
                else:
                    self.attempt_move(square)
        except Exception as e:
            print(f"On click error: {e}")
            traceback.print_exc()

    def attempt_move(self, target_square):
        """Attempt to make a move to the target square"""
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
                    messagebox.showerror("Error", "Invalid promotion piece selected")
                    self.selected_square = None
                    self.update_board()
                    return
                
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
                    self.check_game_end()
                    
                    if not self.game_over and self.current_turn != self.player_side:
                        self.root.after(500, self.ai_move)
            else:
                messagebox.showinfo("Invalid Move", "That move is not legal!")
            
            self.selected_square = None
            self.update_board()
        except Exception as e:
            print(f"Attempt move error: {e}")
            traceback.print_exc()
            messagebox.showerror("Error", "Failed to process move")

    def check_game_end(self):
        """Check if the game has ended and save PGN"""
        try:
            with self.board_lock:
                if self.chess_board.is_checkmate():
                    winner = 'Black' if self.current_turn == 'white' else 'White'
                    self.status_label.config(text=f"发行Checkmate! {winner} wins!")
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
            print(f"Check game end error: {e}")
            traceback.print_exc()

    def enter_review_mode(self):
        """Enter game review mode"""
        try:
            self.review_mode = True
            self.current_review_move = len(self.move_history)
            self.setup_control_buttons()
            self.update_board()
            self.update_status()
            self.update_eval_bar()
        except Exception as e:
            print(f"Enter review mode error: {e}")
            traceback.print_exc()

    def exit_review(self):
        """Exit review mode"""
        try:
            self.review_mode = False
            self.setup_control_buttons()
            self.update_board()
            self.update_status()
            self.update_eval_bar()
        except Exception as e:
            print(f"Exit review mode error: {e}")
            traceback.print_exc()

    def prev_move(self):
        """Go to previous move in review"""
        try:
            if self.current_review_move > 0:
                self.current_review_move -= 1
                self.update_board()
                self.update_status()
                self.update_eval_bar()
            self.control_frame.winfo_children()[0].config(state='disabled' if self.current_review_move == 0 else 'normal')
        except Exception as e:
            print(f"Previous move error: {e}")
            traceback.print_exc()

    def next_move(self):
        """Go to next move in review"""
        try:
            if self.current_review_move < len(self.move_history):
                self.current_review_move += 1
                self.update_board()
                self.update_status()
                self.update_eval_bar()
            self.control_frame.winfo_children()[1].config(state='disabled' if self.current_review_move == len(self.move_history) else 'normal')
        except Exception as e:
            print(f"Next move error: {e}")
            traceback.print_exc()

    def update_board(self):
        """Update the visual representation of the board"""
        try:
            if not self.squares or not all(self.squares[r][c] for r in range(8) for c in range(8)):
                print("Error: Invalid squares array")
                return
            
            for r in range(8):
                for c in range(8):
                    square = chess.square(c, 7-r)
                    
                    gui_r = 7 - chess.square_rank(square) if self.player_side == 'white' else chess.square_rank(square)
                    gui_c = chess.square_file(square)
                    
                    btn = self.squares[gui_r][gui_c]
                    if not btn:
                        continue
                    
                    with self.board_lock:
                        if self.review_mode and self.current_review_move < len(self.board_history):
                            board_state = self.board_history[self.current_review_move]
                            piece = board_state.piece_at(square)
                        else:
                            piece = self.chess_board.piece_at(square)
                    
                    bg_color = '#f0d9b5' if (gui_r + gui_c) % 2 == 0 else '#b58863'
                    
                    if not self.review_mode:
                        if self.selected_square and square == self.selected_square:
                            bg_color = '#90EE90'
                        elif self.selected_square:
                            legal_moves = [m.to_square for m in self.chess_board.legal_moves 
                                          if m.from_square == self.selected_square]
                            if square in legal_moves:
                                bg_color = '#98FB98'
                        
                        if self.last_move and square in [self.last_move[0], self.last_move[1]]:
                            bg_color = '#FFD700'
                        
                        if self.chess_board.is_check():
                            king_square = self.chess_board.king(self.current_turn == 'white')
                            if square == king_square:
                                bg_color = '#FF6B6B'
                    else:
                        if self.current_review_move > 0:
                            move = self.move_history[self.current_review_move - 1]['move']
                            if square in [move.from_square, move.to_square]:
                                bg_color = '#FFD700'
                    
                    piece_symbol = self.PIECES.get(piece.symbol() if piece else '', '')
                    btn.config(text=piece_symbol, bg=bg_color)
        except Exception as e:
            print(f"Update board error: {e}")
            traceback.print_exc()

    def update_eval_bar(self):
        """Update the evaluation bar"""
        try:
            if not self.evaluations or self.current_review_move == 0:
                self.eval_canvas.coords(self.eval_bar, 5, 75, 25, 75)
                self.eval_label.config(text="0.00")
                return
            
            eval_index = min(self.current_review_move - 1, len(self.evaluations) - 1)
            eval_score = self.evaluations[eval_index]
            
            if eval_score is None:
                self.eval_label.config(text="N/A")
                self.eval_canvas.coords(self.eval_bar, 5, 75, 25, 75)
                return
            
            if isinstance(eval_score, str):
                self.eval_label.config(text=eval_score)
                if eval_score.startswith('M'):
                    self.eval_canvas.coords(self.eval_bar, 5, 10, 25, 75)
                    self.eval_canvas.itemconfig(self.eval_bar, fill='#ffffff')
                else:
                    self.eval_canvas.coords(self.eval_bar, 5, 75, 25, 140)
                    self.eval_canvas.itemconfig(self.eval_bar, fill='#000000')
                return
            
            score = max(min(float(eval_score), 5.0), -5.0)
            bar_height = int((score / 10.0) * 150)
            
            if score >= 0:
                self.eval_canvas.coords(self.eval_bar, 5, 75 - bar_height, 25, 75)
                self.eval_canvas.itemconfig(self.eval_bar, fill='#ffffff')
            else:
                self.eval_canvas.coords(self.eval_bar, 5, 75, 25, 75 - bar_height)
                self.eval_canvas.itemconfig(self.eval_bar, fill='#000000')
            
            self.eval_label.config(text=f"{eval_score:+.2f}" if isinstance(eval_score, (int, float)) else str(eval_score))
        except Exception as e:
            print(f"Update eval bar error: {e}")
            traceback.print_exc()

    def update_status(self):
        """Update status and analysis text"""
        try:
            if not hasattr(self, 'status_label'):
                return
            
            if self.review_mode:
                self.update_review_status()
            else:
                self.update_game_status()
        except Exception as e:
            print(f"Update status error: {e}")
            traceback.print_exc()

    def update_review_status(self):
        """Update status during review mode"""
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
            self.update_analysis_text()
        except Exception as e:
            print(f"Update review status error: {e}")
            traceback.print_exc()

    def update_game_status(self):
        """Update status during active game"""
        try:
            if self.game_over:
                return
            
            if self.ai_thinking:
                status = "AI is thinking..."
            else:
                status = f"{self.current_turn.title()}'s turn"
                if self.chess_board.is_check():
                    status += " - CHECK!"
            
            self.status_label.config(text=status)
            self.update_analysis_text()
        except Exception as e:
            print(f"Update game status error: {e}")
            traceback.print_exc()

    def update_analysis_text(self):
        """Update the analysis text widget"""
        try:
            self.analysis_text.delete(1.0, tk.END)
            
            if self.current_review_move > 0 and self.current_review_move <= len(self.move_history):
                self.show_move_analysis()
            else:
                self.show_move_history()
        except Exception as e:
            print(f"Update analysis text error: {e}")
            traceback.print_exc()

    def show_move_analysis(self):
        """Show analysis for the current move in review"""
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
            
            self.analysis_text.insert(tk.END, f"Move: {move_text}\n\n")
            
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
                self.analysis_text.insert(tk.END, f"\nComment: {self.pgn_comments[self.current_review_move - 1]}\n")
        except Exception as e:
            print(f"Show move analysis error: {e}")
            traceback.print_exc()

    def show_move_history(self):
        """Show recent move history"""
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
                    print(f"Error generating SAN for move {move.uci()}: {e}")
                    traceback.print_exc()
                    continue
        except Exception as e:
            print(f"Show move history error: {e}")
            traceback.print_exc()

    def ai_move(self):
        """Handle AI move generation"""
        try:
            if (self.game_over or 
                self.current_turn == self.player_side or 
                self.review_mode or 
                self.ai_thinking):
                return
            
            self.ai_thinking = True
            self.update_status()
            
            def get_ai_move():
                start_time = time.time()
                move = None
                
                try:
                    move = self.get_ollama_move(max_retries=3)
                    if move:
                        print(f"Ollama move: {move.uci()}")
                        self.debug_text.delete(1.0, tk.END)
                        self.debug_text.insert(tk.END, f"Ollama move: {move.uci()}\n")
                    else:
                        raise Exception("Ollama failed to provide valid move")
                except Exception as e:
                    print(f"Ollama failed: {e}")
                    traceback.print_exc()
                    self.debug_text.delete(1.0, tk.END)
                    self.debug_text.insert(tk.END, f"Ollama error: {str(e)}\nFalling back to Stockfish/random\n")
                    
                    if self.engine:
                        try:
                            move = self.get_stockfish-move()
                            print(f"Stockfish move: {move.uci()}")
                            self.debug_text.insert(tk.END, f"Stockfish move: {move.uci()}\n")
                        except Exception as e2:
                            print(f"Stockfish failed: {e2}")
                            traceback.print_exc()
                            self.debug_text.insert(tk.END, f"Stockfish error: {str(e2)}\nFalling back to random\n")
                            move = self.get_random_move()
                    else:
                        move = self.get_random_move()
                        self.debug_text.insert(tk.END, f"Random move: {move.uci() if move else 'None'}\n")
                
                def execute_move():
                    try:
                        self.ai_thinking = False
                        if move and self.make_move(move):
                            self.update_board()
                            self.update_status()
                            self.update_eval_bar()
                            self.check_game_end()
                        
                        print(f"AI move took {time.time() - start_time:.2f} seconds")
                    except Exception as e:
                        print(f"Execute AI move error: {e}")
                        traceback.print_exc()
                
                self.root.after(0, execute_move)
            
            threading.Thread(target=get_ai_move, daemon=True).start()
        except Exception as e:
            print(f"AI move error: {e}")
            traceback.print_exc()

    def get_ollama_move(self, max_retries=3):
        """Get move from Ollama with improved prompt for phi3"""
        try:
            with self.board_lock:
                fen = self.chess_board.fen()
                
                if fen in self.transposition_table:
                    move_str = self.transposition_table[fen]
                    try:
                        move = chess.Move.from_uci(move_str)
                        if move in self.chess_board.legal_moves:
                            self.debug_text.delete(1.0, tk.END)
                            self.debug_text.insert(tk.END, f"Transposition hit: {move_str}\n")
                            return move
                    except:
                        self.debug_text.delete(1.0, tk.END)
                        self.debug_text.insert(tk.END, f"Transposition failed: {move_str}\n")
                
                legal_moves = [move.uci() for move in self.chess_board.legal_moves]
                side = 'White' if self.current_turn == 'white' else 'Black'
                
                prompt = (
                    f"You are playing chess as {side}.\n"
                    f"Current position (FEN): {fen}\n"
                    f"Legal moves in UCI format: {', '.join(legal_moves) if legal_moves else 'None'}\n"
                    f"Your task is to select the best legal move for {side}.\n"
                    f"Respond with ONLY the UCI move (e.g., e2e4, g1f3, e7e8q for promotion).\n"
                    f"Do NOT include any other text, explanations, or punctuation.\n"
                    f"Ensure the move is from the list of legal moves provided."
                )
                
                if len(self.move_history) < 10:
                    if self.current_turn == 'white':
                        prompt += "\nConsider common opening moves like e4, d4, Nf3, c4."
                    else:
                        prompt += "\nConsider common responses like e5, e6, c5, d5, Nf6."
                
                import re
                uci_pattern = r'^[a-h][1-8][a-h][1-8][qrbn]?$'  # Stricter regex
                
                for attempt in range(max_retries):
                    try:
                        response = ollama.generate(
                            model=self.ollama_model,
                            prompt=prompt,
                            options={
                                'temperature': 0.3,
                                'top_p': 0.8,
                                'num_predict': 8,
                                'timeout': self.ollama_timeout
                            }
                        )
                        
                        move_str = response["response"].strip().lower()
                        self.debug_text.delete(1.0, tk.END)
                        self.debug_text.insert(tk.END, f"Attempt {attempt + 1}: {move_str}\n")
                        
                        if not re.match(uci_pattern, move_str):
                            self.debug_text.insert(tk.END, f"Invalid UCI format: {move_str}\n")
                            print(f"Ollama attempt {attempt + 1} failed: Invalid UCI format {move_str}")
                            continue
                        
                        try:
                            move = chess.Move.from_uci(move_str)
                            if move in self.chess_board.legal_moves:
                                self.transposition_table[fen] = move_str
                                if len(self.transposition_table) > self.transposition_table_max_size:
                                    self.transposition_table.popitem(last=False)
                                self.debug_text.insert(tk.END, f"Valid move: {move_str}\n")
                                return move
                            else:
                                self.debug_text.insert(tk.END, f"Move not legal: {move_str}\n")
                                print(f"Ollama attempt {attempt + 1} failed: Move {move_str} not in legal moves")
                        except ValueError as e:
                            self.debug_text.insert(tk.END, f"Invalid move parsing: {str(e)}\n")
                            print(f"Ollama attempt {attempt + 1} failed: {str(e)}")
                        
                    except Exception as e:
                        print(f"Ollama attempt {attempt + 1} error: {e}")
                        traceback.print_exc()
                        self.debug_text.insert(tk.END, f"Error: {str(e)}\n")
                    
                    if attempt < max_retries - 1:
                        time.sleep(1)
                
                self.debug_text.insert(tk.END, "No valid move found, falling back\n")
                return None
        except Exception as e:
            print(f"Get Ollama move error: {e}")
            traceback.print_exc()
            return None

    def get_stockfish_move(self):
        """Get move from Stockfish"""
        try:
            if not self.engine:
                return None
            
            with self.board_lock:
                time_limit = 3.0 if len(self.move_history) < 20 else 5.0
                result = self.engine.play(
                    self.chess_board,
                    chess.engine.Limit(time=time_limit, depth=15)
                )
                return result.move
        except Exception as e:
            print(f"Stockfish error: {e}")
            traceback.print_exc()
            return None

    def get_random_move(self):
        """Get random legal move as last resort"""
        try:
            with self.board_lock:
                legal_moves = list(self.chess_board.legal_moves)
                if legal_moves:
                    return random.choice(legal_moves)
                return None
        except Exception as e:
            print(f"Get random move error: {e}")
            traceback.print_exc()
            return None

    def new_game(self):
        """Start a new game"""
        try:
            if self.ai_thinking:
                messagebox.showinfo("Wait", "Please wait for AI to finish thinking")
                return
                
            self.reset_game()
            self.setup_control_buttons()
            
            if self.player_side == 'black':
                self.root.after(1000, self.ai_move)
        except Exception as e:
            print(f"New game error: {e}")
            traceback.print_exc()

    def switch_side(self):
        """Switch player side"""
        try:
            if self.ai_thinking:
                messagebox.showinfo("Wait", "Please wait for AI to finish thinking")
                return
                
            self.player_side = 'black' if self.player_side == 'white' else 'white'
            self.new_game()
        except Exception as e:
            print(f"Switch side error: {e}")
            traceback.print_exc()

    def run(self):
        """Run the application"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("Application interrupted")
        except Exception as e:
            print(f"Application run error: {e}")
            traceback.print_exc()
        finally:
            self.on_closing()

def main():
    try:
        required_modules = ['chess', 'ollama', 'dotenv']
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                print(f"Error: Required module '{module}' not found.")
                print(f"Please install it using: pip install {module}")
                return
        
        app = ChessVsAI()
        app.run()
        
    except Exception as e:
        print(f"Application startup error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()