import tkinter as tk
from tkinter import ttk, messagebox
import random
import os
import requests
import re
from dotenv import load_dotenv

load_dotenv()

class ChessVsAI:
    def __init__(self):
        self.PIECES = {
            'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
            'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'
        }
        self.player_side = 'white'
        self.api_provider = os.getenv("API_PROVIDER", "ollama")
        self.reset_game()
        self.setup_gui()

    def reset_game(self):
        self.board = [
            ['r','n','b','q','k','b','n','r'],
            ['p','p','p','p','p','p','p','p'],
            ['.','.','.','.','.','.','.','.'],
            ['.','.','.','.','.','.','.','.'],
            ['.','.','.','.','.','.','.','.'],
            ['.','.','.','.','.','.','.','.'],
            ['P','P','P','P','P','P','P','P'],
            ['R','N','B','Q','K','B','N','R']
        ]
        self.move_history = []
        self.selected_square = None
        self.last_move = None
        self.current_turn = 'white'
        self.white_king_moved = False
        self.black_king_moved = False
        self.white_rook_moved = {'left': False, 'right': False}
        self.black_rook_moved = {'left': False, 'right': False}
        self.en_passant_target = None
        self.game_over = False
        self.check_status = None
        self.fifty_move_counter = 0
        self.position_history = []

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Chess vs AI")
        self.root.configure(bg='#2c3e50')
        self.root.geometry("800x900")
        self.root.resizable(True, True)

        # Main container
        main_frame = tk.Frame(self.root, bg='#2c3e50')
        main_frame.pack(padx=20, pady=20, expand=True, fill='both')

        # Title
        title_label = tk.Label(main_frame, text="♔ Chess vs AI ♚", 
                              font=('Arial', 24, 'bold'), 
                              fg='#ecf0f1', bg='#2c3e50')
        title_label.pack(pady=(0, 20))

        self.board_frame = tk.Frame(main_frame, bg='#34495e')
        self.board_frame.pack(pady=10, expand=True)

        self.status_label = tk.Label(main_frame, text="Your move", 
                                   font=('Arial', 16), 
                                   fg='#ecf0f1', bg='#2c3e50')
        self.status_label.pack(pady=15)

        # Control buttons
        self.control_frame = tk.Frame(main_frame, bg='#2c3e50')
        self.control_frame.pack(pady=10)

        btn_style = {'font': ('Arial', 12), 'bg': '#3498db', 'fg': 'white', 
                    'relief': 'flat', 'padx': 20, 'pady': 5}

        tk.Button(self.control_frame, text="New Game", 
                 command=self.new_game, **btn_style).pack(side='left', padx=5)
        tk.Button(self.control_frame, text="Switch Side", 
                 command=self.switch_side, **btn_style).pack(side='left', padx=5)
        tk.Button(self.control_frame, text="Undo Move", 
                 command=self.undo_move, **btn_style).pack(side='left', padx=5)

        # Move history display
        self.history_label = tk.Label(main_frame, text="Move History: ", 
                                    font=('Arial', 10), 
                                    fg='#bdc3c7', bg='#2c3e50')
        self.history_label.pack(pady=(10, 0))

        self.squares = [[None for _ in range(8)] for _ in range(8)]
        for r in range(8):
            for c in range(8):
                btn = tk.Button(self.board_frame, width=4, height=2,
                               font=('Arial', 20), 
                               command=lambda x=r, y=c: self.on_click(x, y),
                               relief='flat', bd=2)
                btn.grid(row=r, column=c, padx=1, pady=1, sticky='nsew')
                self.squares[r][c] = btn

        for i in range(8):
            self.board_frame.grid_columnconfigure(i, weight=1)
            self.board_frame.grid_rowconfigure(i, weight=1)

        self.update_board()
        if self.player_side == 'black':
            self.root.after(1000, self.ai_move)

    def is_white_piece(self, piece):
        return piece.isupper() and piece != '.'

    def is_black_piece(self, piece):
        return piece.islower() and piece != '.'

    def get_piece_color(self, piece):
        if piece == '.':
            return None
        return 'white' if piece.isupper() else 'black'

    def is_valid_position(self, row, col):
        return 0 <= row < 8 and 0 <= col < 8

    def get_piece_moves(self, row, col, include_king_safety=True):
        """Get all possible moves for a piece at given position"""
        piece = self.board[row][col]
        if piece == '.':
            return []

        piece_type = piece.lower()
        moves = []

        if piece_type == 'p':
            moves = self.get_pawn_moves(row, col)
        elif piece_type == 'r':
            moves = self.get_rook_moves(row, col)
        elif piece_type == 'n':
            moves = self.get_knight_moves(row, col)
        elif piece_type == 'b':
            moves = self.get_bishop_moves(row, col)
        elif piece_type == 'q':
            moves = self.get_queen_moves(row, col)
        elif piece_type == 'k':
            moves = self.get_king_moves(row, col, include_king_safety)

        # Filter out moves that would put own king in check
        if include_king_safety and piece_type != 'k':  # King handles its own safety
            legal_moves = []
            for move in moves:
                if self.is_legal_move(row, col, move[0], move[1]):
                    legal_moves.append(move)
            return legal_moves

        return moves

    def get_pawn_moves(self, row, col):
        moves = []
        piece = self.board[row][col]
        is_white = self.is_white_piece(piece)
        
        # Direction: white moves up (-1), black moves down (+1)
        direction = -1 if is_white else 1
        start_row = 6 if is_white else 1

        # Forward move
        new_row = row + direction
        if self.is_valid_position(new_row, col) and self.board[new_row][col] == '.':
            moves.append((new_row, col))
            
            # Double move from starting position
            if row == start_row and self.board[new_row + direction][col] == '.':
                moves.append((new_row + direction, col))

        # Captures
        for dc in [-1, 1]:
            new_col = col + dc
            if self.is_valid_position(new_row, new_col):
                target = self.board[new_row][new_col]
                if target != '.' and self.get_piece_color(target) != self.get_piece_color(piece):
                    moves.append((new_row, new_col))

        # En passant
        if self.en_passant_target:
            ep_row, ep_col = self.en_passant_target
            if row == ep_row and abs(col - ep_col) == 1:
                if self.is_valid_position(ep_row + direction, ep_col):
                    moves.append((ep_row + direction, ep_col))

        return moves

    def get_rook_moves(self, row, col):
        moves = []
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        
        for dr, dc in directions:
            for i in range(1, 8):
                new_row, new_col = row + dr * i, col + dc * i
                if not self.is_valid_position(new_row, new_col):
                    break
                
                target = self.board[new_row][new_col]
                if target == '.':
                    moves.append((new_row, new_col))
                else:
                    if self.get_piece_color(target) != self.get_piece_color(self.board[row][col]):
                        moves.append((new_row, new_col))
                    break
        
        return moves

    def get_knight_moves(self, row, col):
        moves = []
        knight_moves = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), 
                       (1, -2), (1, 2), (2, -1), (2, 1)]
        
        for dr, dc in knight_moves:
            new_row, new_col = row + dr, col + dc
            if self.is_valid_position(new_row, new_col):
                target = self.board[new_row][new_col]
                if target == '.' or self.get_piece_color(target) != self.get_piece_color(self.board[row][col]):
                    moves.append((new_row, new_col))
        
        return moves

    def get_bishop_moves(self, row, col):
        moves = []
        directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        
        for dr, dc in directions:
            for i in range(1, 8):
                new_row, new_col = row + dr * i, col + dc * i
                if not self.is_valid_position(new_row, new_col):
                    break
                
                target = self.board[new_row][new_col]
                if target == '.':
                    moves.append((new_row, new_col))
                else:
                    if self.get_piece_color(target) != self.get_piece_color(self.board[row][col]):
                        moves.append((new_row, new_col))
                    break
        
        return moves

    def get_queen_moves(self, row, col):
        return self.get_rook_moves(row, col) + self.get_bishop_moves(row, col)

    def get_king_moves(self, row, col, include_king_safety=True):
        moves = []
        king_moves = [(-1, -1), (-1, 0), (-1, 1), (0, -1), 
                     (0, 1), (1, -1), (1, 0), (1, 1)]
        
        piece = self.board[row][col]
        piece_color = self.get_piece_color(piece)
        enemy_color = 'black' if piece_color == 'white' else 'white'
        
        for dr, dc in king_moves:
            new_row, new_col = row + dr, col + dc
            if self.is_valid_position(new_row, new_col):
                target = self.board[new_row][new_col]
                if target == '.' or self.get_piece_color(target) != piece_color:
                    # For king moves, we need to check if the destination is safe
                    if not include_king_safety or not self.is_square_attacked_simple(new_row, new_col, enemy_color):
                        moves.append((new_row, new_col))
        
        # Castling - only check if include_king_safety is True
        if include_king_safety:
            is_white = self.is_white_piece(piece)
            
            if not self.is_in_check_simple(piece_color):
                if is_white and not self.white_king_moved:
                    # Kingside castling
                    if (not self.white_rook_moved['right'] and 
                        self.board[7][5] == '.' and self.board[7][6] == '.' and
                        not self.is_square_attacked_simple(7, 5, 'black') and 
                        not self.is_square_attacked_simple(7, 6, 'black')):
                        moves.append((7, 6))
                    
                    # Queenside castling
                    if (not self.white_rook_moved['left'] and 
                        self.board[7][1] == '.' and self.board[7][2] == '.' and self.board[7][3] == '.' and
                        not self.is_square_attacked_simple(7, 3, 'black') and 
                        not self.is_square_attacked_simple(7, 2, 'black')):
                        moves.append((7, 2))
                
                elif not is_white and not self.black_king_moved:
                    # Kingside castling
                    if (not self.black_rook_moved['right'] and 
                        self.board[0][5] == '.' and self.board[0][6] == '.' and
                        not self.is_square_attacked_simple(0, 5, 'white') and 
                        not self.is_square_attacked_simple(0, 6, 'white')):
                        moves.append((0, 6))
                    
                    # Queenside castling
                    if (not self.black_rook_moved['left'] and 
                        self.board[0][1] == '.' and self.board[0][2] == '.' and self.board[0][3] == '.' and
                        not self.is_square_attacked_simple(0, 3, 'white') and 
                        not self.is_square_attacked_simple(0, 2, 'white')):
                        moves.append((0, 2))
        
        return moves

    def is_square_attacked_simple(self, row, col, by_color):
        """Simple check if a square is attacked - avoids recursion"""
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece != '.' and self.get_piece_color(piece) == by_color:
                    if self.can_piece_attack_square(r, c, row, col):
                        return True
        return False

    def can_piece_attack_square(self, piece_row, piece_col, target_row, target_col):
        """Check if a piece can attack a specific square - no recursion"""
        piece = self.board[piece_row][piece_col]
        piece_type = piece.lower()
        
        row_diff = target_row - piece_row
        col_diff = target_col - piece_col
        
        if piece_type == 'p':
            # Pawn attacks diagonally
            is_white = self.is_white_piece(piece)
            direction = -1 if is_white else 1
            return row_diff == direction and abs(col_diff) == 1
            
        elif piece_type == 'r':
            # Rook attacks in straight lines
            if row_diff == 0 or col_diff == 0:
                return self.is_path_clear(piece_row, piece_col, target_row, target_col)
            
        elif piece_type == 'n':
            # Knight attacks in L-shape
            return (abs(row_diff) == 2 and abs(col_diff) == 1) or (abs(row_diff) == 1 and abs(col_diff) == 2)
            
        elif piece_type == 'b':
            # Bishop attacks diagonally
            if abs(row_diff) == abs(col_diff):
                return self.is_path_clear(piece_row, piece_col, target_row, target_col)
            
        elif piece_type == 'q':
            # Queen attacks like rook + bishop
            if row_diff == 0 or col_diff == 0 or abs(row_diff) == abs(col_diff):
                return self.is_path_clear(piece_row, piece_col, target_row, target_col)
            
        elif piece_type == 'k':
            # King attacks adjacent squares
            return abs(row_diff) <= 1 and abs(col_diff) <= 1 and (row_diff != 0 or col_diff != 0)
        
        return False

    def is_path_clear(self, from_row, from_col, to_row, to_col):
        """Check if path between two squares is clear"""
        row_diff = to_row - from_row
        col_diff = to_col - from_col
        
        # Determine step direction
        row_step = 0 if row_diff == 0 else (1 if row_diff > 0 else -1)
        col_step = 0 if col_diff == 0 else (1 if col_diff > 0 else -1)
        
        # Check each square in the path (excluding start and end)
        current_row, current_col = from_row + row_step, from_col + col_step
        
        while (current_row, current_col) != (to_row, to_col):
            if self.board[current_row][current_col] != '.':
                return False
            current_row += row_step
            current_col += col_step
        
        return True

    def is_in_check_simple(self, color):
        """Simple check detection without recursion"""
        king_pos = self.find_king(color)
        if not king_pos:
            return False
        
        enemy_color = 'black' if color == 'white' else 'white'
        return self.is_square_attacked_simple(king_pos[0], king_pos[1], enemy_color)

    def find_king(self, color):
        """Find the position of the king of given color"""
        king = 'K' if color == 'white' else 'k'
        for r in range(8):
            for c in range(8):
                if self.board[r][c] == king:
                    return (r, c)
        return None

    def is_in_check(self, color):
        """Check if the king of given color is in check"""
        return self.is_in_check_simple(color)

    def is_legal_move(self, from_row, from_col, to_row, to_col):
        """Check if a move is legal (doesn't put own king in check)"""
        # Make temporary move
        original_piece = self.board[to_row][to_col]
        moving_piece = self.board[from_row][from_col]
        
        self.board[to_row][to_col] = moving_piece
        self.board[from_row][from_col] = '.'
        
        # Check if own king is in check after this move
        piece_color = self.get_piece_color(moving_piece)
        in_check = self.is_in_check(piece_color)
        
        # Restore board
        self.board[from_row][from_col] = moving_piece
        self.board[to_row][to_col] = original_piece
        
        return not in_check

    def is_checkmate(self, color):
        """Check if the given color is in checkmate"""
        if not self.is_in_check(color):
            return False
        
        # Check if any legal move exists
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece != '.' and self.get_piece_color(piece) == color:
                    moves = self.get_piece_moves(r, c)
                    if moves:  # If any legal move exists
                        return False
        
        return True

    def is_stalemate(self, color):
        """Check if the given color is in stalemate"""
        if self.is_in_check(color):
            return False
        
        # Check if any legal move exists
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece != '.' and self.get_piece_color(piece) == color:
                    moves = self.get_piece_moves(r, c)
                    if moves:  # If any legal move exists
                        return False
        
        return True

    def is_insufficient_material(self):
        """Check for insufficient material draw"""
        pieces = {'white': [], 'black': []}
        
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece != '.':
                    color = self.get_piece_color(piece)
                    pieces[color].append(piece.lower())
        
        # King vs King
        if len(pieces['white']) == 1 and len(pieces['black']) == 1:
            return True
        
        # King and Bishop/Knight vs King
        for color in ['white', 'black']:
            other = 'black' if color == 'white' else 'white'
            if (len(pieces[color]) == 2 and len(pieces[other]) == 1 and
                ('b' in pieces[color] or 'n' in pieces[color])):
                return True
        
        return False

    def make_move(self, from_row, from_col, to_row, to_col):
        """Execute a move on the board"""
        if self.game_over:
            return False
        
        piece = self.board[from_row][from_col]
        captured_piece = self.board[to_row][to_col]
        
        # Store move for history
        move_data = {
            'from': (from_row, from_col),
            'to': (to_row, to_col),
            'piece': piece,
            'captured': captured_piece,
            'en_passant_target': self.en_passant_target,
            'castling_rights': {
                'white_king_moved': self.white_king_moved,
                'black_king_moved': self.black_king_moved,
                'white_rook_moved': self.white_rook_moved.copy(),
                'black_rook_moved': self.black_rook_moved.copy()
            },
            'fifty_move_counter': self.fifty_move_counter
        }
        
        # Reset en passant
        self.en_passant_target = None
        
        # Handle special moves
        piece_type = piece.lower()
        
        # Pawn moves
        if piece_type == 'p':
            self.fifty_move_counter = 0  # Reset on pawn move
            
            # Double pawn move - set en passant target
            if abs(from_row - to_row) == 2:
                self.en_passant_target = (from_row + (to_row - from_row) // 2, from_col)
            
            # En passant capture
            elif from_col != to_col and captured_piece == '.':
                # Remove the captured pawn
                captured_row = from_row
                self.board[captured_row][to_col] = '.'
                move_data['en_passant_captured'] = self.board[captured_row][to_col]
            
            # Pawn promotion
            elif (to_row == 0 and self.is_white_piece(piece)) or (to_row == 7 and self.is_black_piece(piece)):
                # Auto-promote to queen for now
                piece = 'Q' if self.is_white_piece(piece) else 'q'
                move_data['promotion'] = True
        
        # King moves
        elif piece_type == 'k':
            if self.is_white_piece(piece):
                self.white_king_moved = True
                # Castling
                if from_col == 4 and to_col == 6:  # Kingside
                    self.board[7][5] = self.board[7][7]
                    self.board[7][7] = '.'
                    move_data['castling'] = 'kingside'
                elif from_col == 4 and to_col == 2:  # Queenside
                    self.board[7][3] = self.board[7][0]
                    self.board[7][0] = '.'
                    move_data['castling'] = 'queenside'
            else:
                self.black_king_moved = True
                # Castling
                if from_col == 4 and to_col == 6:  # Kingside
                    self.board[0][5] = self.board[0][7]
                    self.board[0][7] = '.'
                    move_data['castling'] = 'kingside'
                elif from_col == 4 and to_col == 2:  # Queenside
                    self.board[0][3] = self.board[0][0]
                    self.board[0][0] = '.'
                    move_data['castling'] = 'queenside'
        
        # Rook moves (affect castling rights)
        elif piece_type == 'r':
            if self.is_white_piece(piece):
                if from_row == 7 and from_col == 0:
                    self.white_rook_moved['left'] = True
                elif from_row == 7 and from_col == 7:
                    self.white_rook_moved['right'] = True
            else:
                if from_row == 0 and from_col == 0:
                    self.black_rook_moved['left'] = True
                elif from_row == 0 and from_col == 7:
                    self.black_rook_moved['right'] = True
        
        # Update fifty move counter
        if captured_piece != '.' or piece_type == 'p':
            self.fifty_move_counter = 0
        else:
            self.fifty_move_counter += 1
        
        # Make the move
        self.board[to_row][to_col] = piece
        self.board[from_row][from_col] = '.'
        
        # Add to move history
        self.move_history.append(move_data)
        
        # Switch turns
        self.current_turn = 'black' if self.current_turn == 'white' else 'white'
        self.last_move = (from_row, from_col, to_row, to_col)
        
        return True

    def undo_move(self):
        """Undo the last move"""
        if not self.move_history:
            return False
        
        move_data = self.move_history.pop()
        from_row, from_col = move_data['from']
        to_row, to_col = move_data['to']
        
        # Restore piece positions
        self.board[from_row][from_col] = move_data['piece']
        self.board[to_row][to_col] = move_data['captured']
        
        # Restore special move effects
        if 'en_passant_captured' in move_data:
            self.board[from_row][to_col] = move_data['en_passant_captured']
        
        if 'castling' in move_data:
            if move_data['castling'] == 'kingside':
                if self.is_white_piece(move_data['piece']):
                    self.board[7][7] = self.board[7][5]
                    self.board[7][5] = '.'
                else:
                    self.board[0][7] = self.board[0][5]
                    self.board[0][5] = '.'
            elif move_data['castling'] == 'queenside':
                if self.is_white_piece(move_data['piece']):
                    self.board[7][0] = self.board[7][3]
                    self.board[7][3] = '.'
                else:
                    self.board[0][0] = self.board[0][3]
                    self.board[0][3] = '.'
        
        # Restore game state
        self.en_passant_target = move_data['en_passant_target']
        self.white_king_moved = move_data['castling_rights']['white_king_moved']
        self.black_king_moved = move_data['castling_rights']['black_king_moved']
        self.white_rook_moved = move_data['castling_rights']['white_rook_moved']
        self.black_rook_moved = move_data['castling_rights']['black_rook_moved']
        self.fifty_move_counter = move_data['fifty_move_counter']
        
        # Switch turns back
        self.current_turn = 'white' if self.current_turn == 'black' else 'black'
        self.game_over = False
        
        self.update_board()
        self.update_status()
        return True

    def on_click(self, row, col):
        if self.game_over:
            return
        
        if (self.current_turn == 'white') != (self.player_side == 'white'):
            return  # Not player's turn
        
        if self.selected_square is None:
            # Select piece
            piece = self.board[row][col]
            if piece != '.' and self.get_piece_color(piece) == self.current_turn:
                self.selected_square = (row, col)
                self.update_board()
        else:
            from_row, from_col = self.selected_square
            
            if (row, col) == self.selected_square:
                # Deselect
                self.selected_square = None
                self.update_board()
            elif self.board[row][col] != '.' and self.get_piece_color(self.board[row][col]) == self.current_turn:
                # Select different piece
                self.selected_square = (row, col)
                self.update_board()
            else:
                # Try to make move
                legal_moves = self.get_piece_moves(from_row, from_col)
                if (row, col) in legal_moves:
                    self.make_move(from_row, from_col, row, col)
                    self.selected_square = None
                    self.update_board()
                    self.update_status()
                    self.check_game_end()
                    
                    # AI move
                    if not self.game_over and self.current_turn != self.player_side:
                        self.root.after(500, self.ai_move)
                else:
                    self.selected_square = None
                    self.update_board()

    def check_game_end(self):
        """Check for game ending conditions"""
        current_color = self.current_turn
        
        if self.is_checkmate(current_color):
            winner = 'Black' if current_color == 'white' else 'White'
            self.status_label.config(text=f"Checkmate! {winner} wins!")
            self.game_over = True
        elif self.is_stalemate(current_color):
            self.status_label.config(text="Stalemate! Draw!")
            self.game_over = True
        elif self.fifty_move_counter >= 100:  # 50 moves per side
            self.status_label.config(text="Draw by 50-move rule!")
            self.game_over = True
        elif self.is_insufficient_material():
            self.status_label.config(text="Draw by insufficient material!")
            self.game_over = True

    def update_board(self):
        for r in range(8):
            for c in range(8):
                btn = self.squares[r][c]
                piece = self.board[r][c]
                
                # Color scheme
                if (r + c) % 2 == 0:
                    bg_color = '#f0d9b5'  # Light squares
                else:
                    bg_color = '#b58863'  # Dark squares
                
                # Highlight selected square
                if self.selected_square and self.selected_square == (r, c):
                    bg_color = '#yellow'
                
                # Highlight possible moves
                if self.selected_square:
                    from_row, from_col = self.selected_square
                    legal_moves = self.get_piece_moves(from_row, from_col)
                    if (r, c) in legal_moves:
                        bg_color = '#90EE90'  # Light green
                
                # Highlight last move
                if self.last_move:
                    from_r, from_c, to_r, to_c = self.last_move
                    if (r, c) == (from_r, from_c) or (r, c) == (to_r, to_c):
                        bg_color = '#FFD700'  # Gold
                
                # Highlight check
                if self.is_in_check(self.current_turn):
                    king_pos = self.find_king(self.current_turn)
                    if king_pos and (r, c) == king_pos:
                        bg_color = '#FF6B6B'  # Red
                
                btn.config(text=self.PIECES.get(piece, ''), bg=bg_color)

    def update_status(self):
        if self.game_over:
            return
        
        status = f"{self.current_turn.title()}'s turn"
        
        if self.is_in_check(self.current_turn):
            status += " - CHECK!"
        
        self.status_label.config(text=status)
        
        # Update move history
        if self.move_history:
            recent_moves = self.move_history[-5:]  # Show last 5 moves
            history_text = "Recent moves: " + ", ".join([
                f"{self.square_to_notation(move['from'])}-{self.square_to_notation(move['to'])}" 
                for move in recent_moves
            ])
            self.history_label.config(text=history_text)

    def square_to_notation(self, pos):
        """Convert (row, col) to chess notation like 'e4'"""
        row, col = pos
        return chr(ord('a') + col) + str(8 - row)

    def ai_move(self):
        """Make AI move using simple evaluation"""
        if self.game_over or self.current_turn == self.player_side:
            return
        
        # Get all possible moves for AI
        all_moves = []
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece != '.' and self.get_piece_color(piece) == self.current_turn:
                    moves = self.get_piece_moves(r, c)
                    for move in moves:
                        all_moves.append((r, c, move[0], move[1]))
        
        if not all_moves:
            return
        
        # Simple AI: prioritize captures, then random
        best_moves = []
        best_score = -999
        
        for from_r, from_c, to_r, to_c in all_moves:
            score = self.evaluate_move(from_r, from_c, to_r, to_c)
            if score > best_score:
                best_score = score
                best_moves = [(from_r, from_c, to_r, to_c)]
            elif score == best_score:
                best_moves.append((from_r, from_c, to_r, to_c))
        
        # Make the move
        if best_moves:
            from_r, from_c, to_r, to_c = random.choice(best_moves)
            self.make_move(from_r, from_c, to_r, to_c)
            self.update_board()
            self.update_status()
            self.check_game_end()

    def evaluate_move(self, from_r, from_c, to_r, to_c):
        """Simple move evaluation"""
        score = 0
        
        # Piece values
        piece_values = {'p': 1, 'n': 3, 'b': 3, 'r': 5, 'q': 9, 'k': 0}
        
        # Capture value
        captured = self.board[to_r][to_c]
        if captured != '.':
            score += piece_values.get(captured.lower(), 0) * 10
        
        # Center control
        if 2 <= to_r <= 5 and 2 <= to_c <= 5:
            score += 2
        
        # Random factor
        score += random.randint(-1, 1)
        
        return score

    def new_game(self):
        """Start a new game"""
        self.reset_game()
        self.update_board()
        self.update_status()
        
        if self.player_side == 'black':
            self.root.after(1000, self.ai_move)

    def switch_side(self):
        """Switch player side"""
        self.player_side = 'black' if self.player_side == 'white' else 'white'
        self.new_game()

    def run(self):
        """Start the game"""
        self.root.mainloop()


if __name__ == "__main__":
    game = ChessVsAI()
    game.run()