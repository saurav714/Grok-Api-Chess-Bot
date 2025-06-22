import tkinter as tk
from tkinter import ttk, messagebox
import chess
import copy
import time
import ollama
import threading
import random
import os
from dotenv import load_dotenv

class ChessVsAI:
    def __init__(self):
        self.PIECES = {
            'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
            'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'
        }
        self.player_side = 'white'
        self.transposition_table = {}
        self.ai_thinking = False  # Prevent multiple AI moves
        
        # Load environment variables first
        load_dotenv()
        
        # Ollama configuration
        self.ollama_model = os.getenv("OLLAMA_MODEL", "phi3")
        self.ollama_timeout = float(os.getenv("OLLAMA_TIMEOUT", "5.0"))
        
        # Initialize GUI components
        self.squares = [[None for _ in range(8)] for _ in range(8)]
        self.setup_gui()
        self.reset_game()

    def reset_game(self):
        """Reset the game state"""
        self.chess_board = chess.Board()
        self.move_history = []
        self.board_history = [copy.deepcopy(self.chess_board)]
        self.selected_square = None
        self.last_move = None
        self.current_turn = 'white'
        self.game_over = False
        self.ai_thinking = False
        self.transposition_table.clear()
        
        if hasattr(self, 'root'):
            self.update_board()
            self.update_status()

    def setup_gui(self):
        """Initialize the GUI"""
        self.root = tk.Tk()
        self.root.title("Chess vs AI with LLM")
        self.root.configure(bg='#2c3e50')
        self.root.geometry("900x700")
        self.root.resizable(True, True)
        self.root.minsize(700, 500)

        # Main container
        main_frame = tk.Frame(self.root, bg='#2c3e50')
        main_frame.pack(padx=10, pady=10, expand=True, fill='both')

        # Title
        title_label = tk.Label(
            main_frame, 
            text="♔ Chess vs AI ♚", 
            font=('Arial', 20, 'bold'), 
            fg='#ecf0f1', 
            bg='#2c3e50'
        )
        title_label.pack(pady=(0, 15))

        # Content frame
        content_frame = tk.Frame(main_frame, bg='#2c3e50')
        content_frame.pack(expand=True, fill='both')

        # Board container
        self.board_container = tk.Frame(content_frame, bg='#34495e', relief='raised', bd=2)
        self.board_container.pack(side='left', padx=(0, 15), expand=True, fill='both')
        
        self.board_frame = tk.Frame(self.board_container, bg='#34495e')
        self.board_frame.pack(expand=True, fill='both', padx=10, pady=10)

        # Control panel
        self.control_panel = tk.Frame(content_frame, bg='#2c3e50', width=250)
        self.control_panel.pack(side='right', fill='y')
        self.control_panel.pack_propagate(False)

        # Status panel
        self.setup_status_panel()
        self.setup_control_buttons()
        self.setup_analysis_panel()

        # Create the chess board
        self.create_board()
        
        # Bind events
        self.root.bind('<Configure>', self.on_window_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Start AI move if player is black
        if self.player_side == 'black':
            self.root.after(1000, self.ai_move)

    def setup_status_panel(self):
        """Setup the status panel"""
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

    def setup_control_buttons(self):
        """Setup control buttons"""
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

        buttons = [
            ("New Game", self.new_game),
            ("Switch Side", self.switch_side),
            ("Undo Move", self.undo_move),
            ("Resign", self.resign),
            ("Test AI", self.test_ai),
            ("Export Game", self.export_game)
        ]

        for text, command in buttons:
            btn = tk.Button(self.control_frame, text=text, command=command, **btn_style)
            btn.pack(pady=2)
            
            # Add hover effects
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg='#2980b9'))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg='#3498db'))

    def setup_analysis_panel(self):
        """Setup the analysis text panel"""
        analysis_frame = tk.Frame(self.control_panel, bg='#2c3e50')
        analysis_frame.pack(fill='both', expand=True, pady=(15, 0))

        tk.Label(
            analysis_frame, 
            text="Move History", 
            font=('Arial', 11, 'bold'), 
            fg='#ecf0f1', 
            bg='#2c3e50'
        ).pack()

        # Scrollable text widget for move history
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

    def create_board(self):
        """Create the chess board GUI"""
        # Clear existing squares
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

        # Configure grid weights for responsive resizing
        for i in range(8):
            self.board_frame.grid_rowconfigure(i, weight=1, uniform='chess_rows')
            self.board_frame.grid_columnconfigure(i, weight=1, uniform='chess_cols')

    def on_window_resize(self, event):
        """Handle window resize events"""
        if event.widget == self.root:
            board_height = self.board_container.winfo_height()
            if board_height > 50:  # Avoid division by zero
                new_size = max(10, min(24, int(board_height / 30)))
                for r in range(8):
                    for c in range(8):
                        if self.squares[r][c]:
                            self.squares[r][c].config(font=('Arial', new_size))

    def on_closing(self):
        """Clean up resources when closing"""
        self.root.destroy()

    def get_promotion_piece(self, is_white):
        """Get promotion piece from user"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Pawn Promotion")
        dialog.geometry("200x180")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg='#2c3e50')
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))
        
        pieces = ['Queen', 'Rook', 'Knight', 'Bishop']
        piece_var = tk.StringVar(value='Queen')
        
        tk.Label(
            dialog, 
            text="Choose promotion piece:", 
            font=('Arial', 12), 
            fg='#ecf0f1', 
            bg='#2c3e50'
        ).pack(pady=10)
        
        for piece in pieces:
            tk.Radiobutton(
                dialog, 
                text=piece, 
                variable=piece_var, 
                value=piece, 
                font=('Arial', 10),
                fg='#ecf0f1',
                bg='#2c3e50',
                selectcolor='#34495e'
            ).pack(anchor='w', padx=20)
        
        tk.Button(
            dialog, 
            text="Confirm", 
            command=dialog.destroy, 
            font=('Arial', 10),
            bg='#3498db',
            fg='white',
            relief='flat',
            padx=20
        ).pack(pady=10)
        
        self.root.wait_window(dialog)
        
        piece_map = {'Queen': 'q', 'Rook': 'r', 'Knight': 'n', 'Bishop': 'b'}
        return piece_map.get(piece_var.get(), 'q')

    def make_move(self, move):
        """Make a move on the board"""
        if self.game_over or move not in self.chess_board.legal_moves:
            return False
        
        # Store move data
        move_data = {'move': move, 'board': copy.deepcopy(self.chess_board)}
        self.chess_board.push(move)
        self.move_history.append(move_data)
        self.board_history.append(copy.deepcopy(self.chess_board))
        
        # Update game state
        self.current_turn = 'black' if self.current_turn == 'white' else 'white'
        self.last_move = (move.from_square, move.to_square)
        return True

    def undo_move(self):
        """Undo the last move"""
        if not self.move_history or self.ai_thinking:
            return False
        
        # Undo player's move and AI's move if applicable
        moves_to_undo = 2 if len(self.move_history) >= 2 else 1
        
        for _ in range(moves_to_undo):
            if self.move_history:
                self.move_history.pop()
                self.board_history.pop()
                self.chess_board.pop()
        
        self.current_turn = 'white' if len(self.move_history) % 2 == 0 else 'black'
        self.game_over = False
        self.last_move = None
        
        self.update_board()
        self.update_status()
        return True

    def resign(self):
        """Resign the game"""
        if not self.game_over and not self.ai_thinking:
            winner = 'Black' if self.player_side == 'white' else 'White'
            self.status_label.config(text=f"You resigned! {winner} wins!")
            self.game_over = True

    def export_game(self):
        """Export game for review"""
        if not self.move_history:
            messagebox.showinfo("No Game", "No moves to export!")
            return
        
        try:
            from chess_review import save_game_for_review
            filename = save_game_for_review(self.move_history, self.board_history)
            messagebox.showinfo("Game Exported", f"Game saved as: {filename}")
        except ImportError:
            messagebox.showerror("Error", "Chess review module not found!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export game: {e}")

    def on_click(self, gui_row, gui_col):
        """Handle square clicks"""
        if self.game_over or self.ai_thinking:
            return
        
        # Convert GUI coordinates to board coordinates
        if self.player_side == 'black':
            board_row = 7 - gui_row
            board_col = gui_col
        else:
            board_row = gui_row
            board_col = gui_col
        
        square = chess.square(board_col, 7 - board_row)
        
        # Check if it's player's turn
        if (self.current_turn == 'white') != (self.player_side == 'white'):
            return
        
        if self.selected_square is None:
            # Select a piece
            piece = self.chess_board.piece_at(square)
            if piece and piece.color == (self.current_turn == 'white'):
                self.selected_square = square
                self.update_board()
        else:
            # Handle move or selection change
            if square == self.selected_square:
                # Deselect
                self.selected_square = None
                self.update_board()
            elif (self.chess_board.piece_at(square) and 
                  self.chess_board.piece_at(square).color == (self.current_turn == 'white')):
                # Select different piece
                self.selected_square = square
                self.update_board()
            else:
                # Attempt to make a move
                self.attempt_move(square)

    def attempt_move(self, target_square):
        """Attempt to make a move to the target square"""
        move = chess.Move(self.selected_square, target_square)
        
        # Handle pawn promotion
        if (self.chess_board.piece_at(self.selected_square).piece_type == chess.PAWN and
            chess.square_rank(target_square) in [0, 7]):
            promotion = self.get_promotion_piece(self.current_turn == 'white')
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
                self.check_game_end()
                
                # Schedule AI move
                if not self.game_over and self.current_turn != self.player_side:
                    self.root.after(500, self.ai_move)
        else:
            messagebox.showinfo("Invalid Move", "That move is not legal!")
        
        self.selected_square = None
        self.update_board()

    def check_game_end(self):
        """Check if the game has ended"""
        if self.chess_board.is_checkmate():
            winner = 'Black' if self.current_turn == 'white' else 'White'
            self.status_label.config(text=f"Checkmate! {winner} wins!")
            self.game_over = True
        elif self.chess_board.is_stalemate():
            self.status_label.config(text="Draw by stalemate!")
            self.game_over = True
        elif self.chess_board.is_insufficient_material():
            self.status_label.config(text="Draw by insufficient material!")
            self.game_over = True
        elif self.chess_board.is_fifty_moves():
            self.status_label.config(text="Draw by fifty-move rule!")
            self.game_over = True
        elif self.chess_board.is_repetition():
            self.status_label.config(text="Draw by repetition!")
            self.game_over = True

    def update_board(self):
        """Update the visual representation of the board"""
        if not hasattr(self, 'squares') or not self.squares:
            return
        
        for r in range(8):
            for c in range(8):
                square = chess.square(c, 7-r)
                
                # Convert to GUI coordinates
                gui_r = 7 - chess.square_rank(square) if self.player_side == 'white' else chess.square_rank(square)
                gui_c = chess.square_file(square)
                
                btn = self.squares[gui_r][gui_c]
                if not btn:
                    continue
                
                # Get piece for current position
                piece = self.chess_board.piece_at(square)
                
                # Determine background color
                bg_color = '#f0d9b5' if (gui_r + gui_c) % 2 == 0 else '#b58863'
                
                # Highlight selected square and legal moves
                if self.selected_square and square == self.selected_square:
                    bg_color = '#90EE90'
                elif self.selected_square:
                    legal_moves = [m.to_square for m in self.chess_board.legal_moves 
                                 if m.from_square == self.selected_square]
                    if square in legal_moves:
                        bg_color = '#98FB98'
                
                # Highlight last move
                if self.last_move and square in [self.last_move[0], self.last_move[1]]:
                    bg_color = '#FFD700'
                
                # Highlight king in check
                if self.chess_board.is_check():
                    king_square = self.chess_board.king(self.current_turn == 'white')
                    if square == king_square:
                        bg_color = '#FF6B6B'
                
                # Set piece symbol and color
                piece_symbol = self.PIECES.get(piece.symbol() if piece else '', '')
                btn.config(text=piece_symbol, bg=bg_color)

    def update_status(self):
        """Update status and analysis text"""
        if not hasattr(self, 'status_label'):
            return
        
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

    def update_analysis_text(self):
        """Update the analysis text widget with move history"""
        self.analysis_text.delete(1.0, tk.END)
        self.analysis_text.insert(tk.END, "Move History:\n\n")
        
        # Show last 15 moves
        start_idx = max(0, len(self.move_history) - 15)
        
        for i in range(start_idx, len(self.move_history)):
            move_data = self.move_history[i]
            move = move_data['move']
            
            # Get the board state before this move for SAN notation
            board_before = self.board_history[i]
            
            try:
                san = board_before.san(move)
                move_num = (i + 2) // 2  # Move numbering starts at 1
                
                if i % 2 == 0:  # White move
                    self.analysis_text.insert(tk.END, f"{move_num}. {san}")
                else:  # Black move
                    if i == len(self.move_history) - 1:  # Last move
                        self.analysis_text.insert(tk.END, f" {san}\n")
                    else:
                        self.analysis_text.insert(tk.END, f" {san}\n")
                        
            except Exception as e:
                print(f"Error generating SAN for move {move.uci()}: {e}")
                continue

    def ai_move(self):
        """Handle AI move generation"""
        if (self.game_over or 
            self.current_turn == self.player_side or 
            self.ai_thinking):
            return
        
        self.ai_thinking = True
        self.update_status()
        
        def get_ai_move():
            """Get AI move in separate thread"""
            start_time = time.time()
            move = None
            
            try:
                # Try Ollama first
                move = self.get_ollama_move()
                if move:
                    print(f"Ollama move: {move.uci()}")
                else:
                    raise Exception("Ollama failed to provide valid move")
                    
            except Exception as e:
                print(f"Ollama failed: {e}")
                move = self.get_random_move()
            
            # Execute move on main thread
            def execute_move():
                self.ai_thinking = False
                if move and self.make_move(move):
                    self.update_board()
                    self.update_status()
                    self.check_game_end()
                
                print(f"AI move took {time.time() - start_time:.2f} seconds")
            
            self.root.after(0, execute_move)
        
        # Start AI thinking in background thread
        threading.Thread(target=get_ai_move, daemon=True).start()

    def get_ollama_move(self):
        """Get move from Ollama"""
        fen = self.chess_board.fen()
        
        # Check transposition table first
        if fen in self.transposition_table:
            move_str = self.transposition_table[fen]
            try:
                move = chess.Move.from_uci(move_str)
                if move in self.chess_board.legal_moves:
                    return move
            except:
                pass
        
        # Prepare prompt for Ollama
        opening_hints = ""
        if len(self.move_history) < 10:
            if self.current_turn == 'white':
                opening_hints = " Consider opening moves like e4, d4, Nf3, c4."
            else:
                opening_hints = " Consider responses like e5, e6, c5, d5, Nf6."
        
        prompt = (f"Chess position FEN: {fen}\n"
                 f"Generate the best move in UCI format (e.g., e2e4, g1f3).{opening_hints}\n"
                 f"Respond with ONLY the UCI move, nothing else.")
        
        try:
            response = ollama.generate(
                model=self.ollama_model,
                prompt=prompt,
                options={
                    'temperature': 0.7,
                    'top_p': 0.9,
                    'num_predict': 10
                }
            )
            
            move_str = response["response"].strip().lower()
            
            # Clean up the response - extract only UCI move
            import re
            uci_pattern = r'[a-h][1-8][a-h][1-8][qrbn]?'
            match = re.search(uci_pattern, move_str)
            
            if match:
                move_str = match.group()
                move = chess.Move.from_uci(move_str)
                
                if move in self.chess_board.legal_moves:
                    self.transposition_table[fen] = move_str
                    return move
            
            raise ValueError(f"Invalid move from Ollama: {move_str}")
            
        except Exception as e:
            print(f"Ollama error: {e}")
            return None

    def get_random_move(self):
        """Get random legal move as last resort"""
        legal_moves = list(self.chess_board.legal_moves)
        if legal_moves:
            return random.choice(legal_moves)
        return None

    def test_ai(self):
        """Test AI by playing several games"""
        if self.ai_thinking:
            return
            
        def run_test():
            results = []
            for game_num in range(3):
                print(f"Starting test game {game_num + 1}")
                self.reset_game()
                
                moves_played = 0
                max_moves = 100  # Prevent infinite games
                
                while not self.game_over and moves_played < max_moves:
                    if self.current_turn == self.player_side:
                        # Random move for "player"
                        move = random.choice(list(self.chess_board.legal_moves))
                        self.make_move(move)
                    else:
                        # AI move
                        ai_move = None
                        try:
                            ai_move = self.get_ollama_move()
                            if not ai_move:
                                ai_move = self.get_random_move()
                        except:
                            ai_move = self.get_random_move()
                        
                        if ai_move:
                            self.make_move(ai_move)
                    
                    moves_played += 1
                    self.check_game_end()
                
                result = self.chess_board.result()
                results.append(result)
                print(f"Test game {game_num + 1} result: {result}")
            
            # Update UI on main thread
            def show_results():
                wins = results.count('1-0' if self.player_side == 'white' else '0-1')
                losses = results.count('0-1' if self.player_side == 'white' else '1-0')
                draws = results.count('1/2-1/2')
                
                result_text = f"Test Results: {wins}W-{losses}L-{draws}D"
                self.status_label.config(text=result_text)
                print(f"Final test results: {result_text}")
            
            self.root.after(0, show_results)
        
        # Run test in background
        threading.Thread(target=run_test, daemon=True).start()

    def new_game(self):
        """Start a new game"""
        if self.ai_thinking:
            return
            
        self.reset_game()
        self.setup_control_buttons()
        
        # Start AI move if player is black
        if self.player_side == 'black':
            self.root.after(1000, self.ai_move)

    def switch_side(self):
        """Switch player side"""
        if self.ai_thinking:
            return
            
        self.player_side = 'black' if self.player_side == 'white' else 'white'
        self.new_game()

    def run(self):
        """Run the application"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("Application interrupted")
        finally:
            self.on_closing()


def main():
    """Main entry point"""
    try:
        # Check for required dependencies
        required_modules = ['chess', 'ollama', 'dotenv']
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                print(f"Error: Required module '{module}' not found.")
                print(f"Please install it using: pip install {module}")
                return
        
        # Create and run the application
        app = ChessVsAI()
        app.run()
        
    except Exception as e:
        print(f"Application startup error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()