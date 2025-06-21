import tkinter as tk
from tkinter import ttk, messagebox
import random
import copy
import time
import zlib

class ChessVsAI:
    def __init__(self):
        self.PIECES = {
            'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
            'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'
        }
        self.player_side = 'white'
        self.transposition_table = {}  # New: For storing previously evaluated positions
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
        self.fifty_move_counter = 0
        self.position_history = {}
        self.update_position_history()
        self.transposition_table.clear()

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Chess vs AI")
        self.root.configure(bg='#2c3e50')
        self.root.geometry("500x600")
        self.root.resizable(True, True)
        self.root.minsize(400, 400)

        main_frame = tk.Frame(self.root, bg='#2c3e50')
        main_frame.pack(padx=10, pady=10, expand=True, fill='both')

        title_label = tk.Label(main_frame, text="♔ Chess vs AI ♚", 
                              font=('Arial', 18, 'bold'), 
                              fg='#ecf0f1', bg='#2c3e50')
        title_label.pack(pady=(0, 10))

        self.board_container = tk.Frame(main_frame, bg='#34495e')
        self.board_container.pack(pady=5, expand=True, fill='both')
        
        self.board_frame = tk.Frame(self.board_container, bg='#34495e')
        self.board_frame.pack(expand=True, fill='both')
        
        self.status_label = tk.Label(main_frame, text="Your move", 
                                   font=('Arial', 12), 
                                   fg='#ecf0f1', bg='#2c3e50')
        self.status_label.pack(pady=5)

        self.control_frame = tk.Frame(main_frame, bg='#2c3e50')
        self.control_frame.pack(pady=5)

        btn_style = {'font': ('Arial', 8), 'bg': '#3498db', 'fg': 'white', 
                    'relief': 'flat', 'padx': 10, 'pady': 3}

        tk.Button(self.control_frame, text="New Game", 
                 command=self.new_game, **btn_style).pack(side='left', padx=3)
        tk.Button(self.control_frame, text="Switch Side", 
                 command=self.switch_side, **btn_style).pack(side='left', padx=3)
        tk.Button(self.control_frame, text="Undo Move", 
                 command=self.undo_move, **btn_style).pack(side='left', padx=3)

        self.history_label = tk.Label(main_frame, text="Move History: ", 
                                    font=('Arial', 8), 
                                    fg='#bdc3c7', bg='#2c3e50')
        self.history_label.pack(pady=(5, 0))

        self.squares = [[None for _ in range(8)] for _ in range(8)]
        self.create_board()
        
        self.root.bind('<Configure>', self.on_window_resize)

        self.update_board()
        if self.player_side == 'black':
            self.root.after(500, self.ai_move)

    def create_board(self):
        for r in range(8):
            for c in range(8):
                if self.squares[r][c]:
                    self.squares[r][c].destroy()
                
                btn = tk.Button(
                    self.board_frame,
                    font=('Arial', 14),
                    command=lambda x=r, y=c: self.on_click(x, y),
                    relief='flat', 
                    bd=1
                )
                btn.grid(row=r, column=c, padx=1, pady=1, sticky='nsew')
                self.squares[r][c] = btn

        for i in range(8):
            self.board_frame.grid_rowconfigure(i, weight=1, uniform='chess_rows')
            self.board_frame.grid_columnconfigure(i, weight=1, uniform='chess_cols')

    def on_window_resize(self, event):
        board_height = self.board_container.winfo_height()
        if board_height > 0:
            new_size = max(8, min(20, int(board_height / 25)))
            for r in range(8):
                for c in range(8):
                    self.squares[r][c].config(font=('Arial', new_size))

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

        if include_king_safety and piece_type != 'k':
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
        direction = -1 if is_white else 1
        start_row = 6 if is_white else 1

        new_row = row + direction
        if self.is_valid_position(new_row, col) and self.board[new_row][col] == '.':
            moves.append((new_row, col))
            if row == start_row and self.is_valid_position(new_row + direction, col) and self.board[new_row + direction][col] == '.':
                moves.append((new_row + direction, col))

        for dc in [-1, 1]:
            new_col = col + dc
            if self.is_valid_position(new_row, new_col):
                target = self.board[new_row][new_col]
                if target != '.' and self.get_piece_color(target) != self.get_piece_color(piece):
                    moves.append((new_row, new_col))
                elif (new_row, new_col) == self.en_passant_target:
                    moves.append((new_row, new_col))

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
                    if not include_king_safety or not self.is_square_attacked(new_row, new_col, enemy_color):
                        moves.append((new_row, new_col))
        
        if include_king_safety and not self.is_in_check(piece_color):
            is_white = self.is_white_piece(piece)
            if is_white and not self.white_king_moved:
                if (not self.white_rook_moved['right'] and 
                    self.board[7][5] == '.' and self.board[7][6] == '.' and
                    not self.is_square_attacked(7, 5, 'black') and 
                    not self.is_square_attacked(7, 6, 'black')):
                    moves.append((7, 6))
                if (not self.white_rook_moved['left'] and 
                    self.board[7][1] == '.' and self.board[7][2] == '.' and self.board[7][3] == '.' and
                    not self.is_square_attacked(7, 2, 'black') and 
                    not self.is_square_attacked(7, 3, 'black')):
                    moves.append((7, 2))
            elif not is_white and not self.black_king_moved:
                if (not self.black_rook_moved['right'] and 
                    self.board[0][5] == '.' and self.board[0][6] == '.' and
                    not self.is_square_attacked(0, 5, 'white') and 
                    not self.is_square_attacked(0, 6, 'white')):
                    moves.append((0, 6))
                if (not self.black_rook_moved['left'] and 
                    self.board[0][1] == '.' and self.board[0][2] == '.' and self.board[0][3] == '.' and
                    not self.is_square_attacked(0, 2, 'white') and 
                    not self.is_square_attacked(0, 3, 'white')):
                    moves.append((0, 2))
        
        return moves

    def is_square_attacked(self, row, col, by_color):
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece != '.' and self.get_piece_color(piece) == by_color:
                    if self.can_piece_attack_square(r, c, row, col):
                        return True
        return False

    def can_piece_attack_square(self, piece_row, piece_col, target_row, target_col):
        piece = self.board[piece_row][piece_col]
        piece_type = piece.lower()
        
        row_diff = target_row - piece_row
        col_diff = target_col - piece_col
        
        if piece_type == 'p':
            is_white = self.is_white_piece(piece)
            direction = -1 if is_white else 1
            return row_diff == direction and abs(col_diff) == 1
            
        elif piece_type == 'r':
            if row_diff == 0 or col_diff == 0:
                return self.is_path_clear(piece_row, piece_col, target_row, target_col)
            
        elif piece_type == 'n':
            return (abs(row_diff) == 2 and abs(col_diff) == 1) or (abs(row_diff) == 1 and abs(col_diff) == 2)
            
        elif piece_type == 'b':
            if abs(row_diff) == abs(col_diff):
                return self.is_path_clear(piece_row, piece_col, target_row, target_col)
            
        elif piece_type == 'q':
            if row_diff == 0 or col_diff == 0 or abs(row_diff) == abs(col_diff):
                return self.is_path_clear(piece_row, piece_col, target_row, target_col)
            
        elif piece_type == 'k':
            return abs(row_diff) <= 1 and abs(col_diff) <= 1 and (row_diff != 0 or col_diff != 0)
        
        return False

    def is_path_clear(self, from_row, from_col, to_row, to_col):
        row_diff = to_row - from_row
        col_diff = to_col - from_col
        
        row_step = 0 if row_diff == 0 else (1 if row_diff > 0 else -1)
        col_step = 0 if col_diff == 0 else (1 if col_diff > 0 else -1)
        
        current_row, current_col = from_row + row_step, from_col + col_step
        
        while (current_row, current_col) != (to_row, to_col):
            if self.board[current_row][current_col] != '.':
                return False
            current_row += row_step
            current_col += col_step
        
        return True

    def is_in_check(self, color):
        king_pos = self.find_king(color)
        if not king_pos:
            return False
        enemy_color = 'black' if color == 'white' else 'white'
        return self.is_square_attacked(king_pos[0], king_pos[1], enemy_color)

    def find_king(self, color):
        king = 'K' if color == 'white' else 'k'
        for r in range(8):
            for c in range(8):
                if self.board[r][c] == king:
                    return (r, c)
        return None

    def is_legal_move(self, from_row, from_col, to_row, to_col):
        if not self.is_valid_position(from_row, from_col) or not self.is_valid_position(to_row, to_col):
            return False
        piece = self.board[from_row][from_col]
        if piece == '.' or self.get_piece_color(piece) != self.current_turn:
            return False
        original_piece = self.board[to_row][to_col]
        moving_piece = self.board[from_row][from_col]
        
        self.board[to_row][to_col] = moving_piece
        self.board[from_row][from_col] = '.'
        
        in_check = self.is_in_check(self.current_turn)
        
        self.board[from_row][from_col] = moving_piece
        self.board[to_row][to_col] = original_piece
        
        return not in_check

    def is_checkmate(self, color):
        if not self.is_in_check(color):
            return False
        
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece != '.' and self.get_piece_color(piece) == color:
                    moves = self.get_piece_moves(r, c)
                    if moves:
                        return False
        
        return True

    def is_stalemate(self, color):
        if self.is_in_check(color):
            return False
        
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece != '.' and self.get_piece_color(piece) == color:
                    moves = self.get_piece_moves(r, c)
                    if moves:
                        return False
        
        return True

    def is_insufficient_material(self):
        pieces = {'white': [], 'black': []}
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece != '.':
                    color = self.get_piece_color(piece)
                    pieces[color].append(piece.lower())
        
        white_count = len(pieces['white'])
        black_count = len(pieces['black'])
        
        if white_count <= 2 and black_count <= 2:
            if white_count == 1 and black_count == 1:  # King vs King
                return True
            for color in ['white', 'black']:
                other = 'black' if color == 'white' else 'white'
                if len(pieces[color]) == 2:
                    piece = [p for p in pieces[color] if p != 'k'][0]
                    if piece in ['b', 'n']:  # King + Bishop/Knight vs King
                        return len(pieces[other]) == 1
                    elif piece in ['b', 'n'] and len(pieces[other]) == 2:  # King + Bishop/Knight vs King + Bishop/Knight
                        other_piece = [p for p in pieces[other] if p != 'k'][0]
                        if other_piece in ['b', 'n']:
                            if piece == 'b' and other_piece == 'b':
                                # Check if bishops are on same color squares
                                white_bishop_pos = [(r,c) for r in range(8) for c in range(8) if self.board[r][c].lower() == 'b' and self.get_piece_color(self.board[r][c]) == color][0]
                                black_bishop_pos = [(r,c) for r in range(8) for c in range(8) if self.board[r][c].lower() == 'b' and self.get_piece_color(self.board[r][c]) == other][0]
                                return (white_bishop_pos[0] + white_bishop_pos[1]) % 2 == (black_bishop_pos[0] + black_bishop_pos[1]) % 2
                            return True
        return False

    def is_threefold_repetition(self):
        position_key = self.get_position_key()
        return self.position_history.get(position_key, 0) >= 3

    def get_position_key(self):
        board_str = ''.join(''.join(row) for row in self.board)
        castling = f"{self.white_king_moved}{self.black_king_moved}{self.white_rook_moved['left']}{self.white_rook_moved['right']}{self.black_rook_moved['left']}{self.black_rook_moved['right']}"
        ep = str(self.en_passant_target)
        return f"{board_str}|{castling}|{ep}|{self.current_turn}"

    def update_position_history(self):
        position_key = self.get_position_key()
        self.position_history[position_key] = self.position_history.get(position_key, 0) + 1

    def get_promotion_piece(self, is_white):
        dialog = tk.Toplevel(self.root)
        dialog.title("Pawn Promotion")
        dialog.transient(self.root)
        dialog.grab_set()
        
        pieces = ['Queen', 'Knight', 'Rook', 'Bishop']  # Reordered for better UX
        piece_var = tk.StringVar(value='Queen')
        
        tk.Label(dialog, text="Choose promotion piece:", font=('Arial', 10)).pack(pady=5)
        for piece in pieces:
            tk.Radiobutton(dialog, text=piece, variable=piece_var, value=piece, font=('Arial', 8)).pack(anchor='w', padx=15)
        tk.Button(dialog, text="Confirm", command=dialog.destroy, font=('Arial', 8)).pack(pady=5)
        
        self.root.wait_window(dialog)
        
        piece_map = {'Queen': 'Q', 'Rook': 'R', 'Bishop': 'B', 'Knight': 'N'}
        selected = piece_map[piece_var.get()]
        return selected if is_white else selected.lower()

    def make_move(self, from_row, from_col, to_row, to_col):
        if self.game_over or not self.is_legal_move(from_row, from_col, to_row, to_col):
            return False
        
        piece = self.board[from_row][from_col]
        captured_piece = self.board[to_row][to_col]
        
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
            'fifty_move_counter': self.fifty_move_counter,
            'position_history': self.position_history.copy()
        }
        
        self.en_passant_target = None
        
        piece_type = piece.lower()
        
        if piece_type == 'p':
            self.fifty_move_counter = 0
            if abs(from_row - to_row) == 2:
                self.en_passant_target = (from_row + (to_row - from_row) // 2, from_col)
            elif from_col != to_col and captured_piece == '.' and (to_row, to_col) == self.en_passant_target:
                captured_row = from_row
                self.board[captured_row][to_col] = '.'
                move_data['en_passant_captured'] = 'P' if self.current_turn == 'black' else 'p'
            elif (to_row == 0 and self.is_white_piece(piece)) or (to_row == 7 and self.is_black_piece(piece)):
                if self.current_turn == self.player_side:
                    piece = self.get_promotion_piece(self.is_white_piece(piece))
                else:
                    piece = 'Q' if self.is_white_piece(piece) else 'q'
                move_data['promotion'] = piece
        
        elif piece_type == 'k':
            if self.is_white_piece(piece):
                self.white_king_moved = True
                if from_col == 4 and to_col == 6:
                    self.board[7][5] = self.board[7][7]
                    self.board[7][7] = '.'
                    move_data['castling'] = 'kingside'
                elif from_col == 4 and to_col == 2:
                    self.board[7][3] = self.board[7][0]
                    self.board[7][0] = '.'
                    move_data['castling'] = 'queenside'
            else:
                self.black_king_moved = True
                if from_col == 4 and to_col == 6:
                    self.board[0][5] = self.board[0][7]
                    self.board[0][7] = '.'
                    move_data['castling'] = 'kingside'
                elif from_col == 4 and to_col == 2:
                    self.board[0][3] = self.board[0][0]
                    self.board[0][0] = '.'
                    move_data['castling'] = 'queenside'
        
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
        
        if captured_piece != '.' or piece_type == 'p':
            self.fifty_move_counter = 0
        else:
            self.fifty_move_counter += 1
        
        self.board[to_row][to_col] = piece
        self.board[from_row][from_col] = '.'
        
        self.move_history.append(move_data)
        self.update_position_history()
        
        self.current_turn = 'black' if self.current_turn == 'white' else 'white'
        self.last_move = (from_row, from_col, to_row, to_col)
        
        return True

    def undo_move(self):
        if not self.move_history:
            return False
        
        move_data = self.move_history.pop()
        from_row, from_col = move_data['from']
        to_row, to_col = move_data['to']
        
        self.board[from_row][from_col] = move_data['piece']
        self.board[to_row][to_col] = move_data['captured']
        
        if 'en_passant_captured' in move_data:
            if self.is_white_piece(move_data['piece']):
                self.board[to_row+1][to_col] = 'p'
            else:
                self.board[to_row-1][to_col] = 'P'
        
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
        
        if 'promotion' in move_data:
            if self.is_white_piece(move_data['piece']):
                self.board[from_row][from_col] = 'P'
            else:
                self.board[from_row][from_col] = 'p'
        
        self.en_passant_target = move_data['en_passant_target']
        self.position_history = move_data['position_history']
        self.white_king_moved = move_data['castling_rights']['white_king_moved']
        self.black_king_moved = move_data['castling_rights']['black_king_moved']
        self.white_rook_moved = move_data['castling_rights']['white_rook_moved']
        self.black_rook_moved = move_data['castling_rights']['black_rook_moved']
        self.fifty_move_counter = move_data['fifty_move_counter']
        
        self.current_turn = 'white' if self.current_turn == 'black' else 'black'
        self.game_over = False
        
        self.update_board()
        self.update_status()
        return True

    def on_click(self, gui_row, gui_col):
        if self.game_over:
            return
        
        if self.player_side == 'black':
            board_row = 7 - gui_row
            board_col = gui_col
        else:
            board_row = gui_row
            board_col = gui_col
        
        if (self.current_turn == 'white') != (self.player_side == 'white'):
            return
        
        if self.selected_square is None:
            piece = self.board[board_row][board_col]
            if piece != '.' and self.get_piece_color(piece) == self.current_turn:
                self.selected_square = (board_row, board_col)
                self.update_board()
            else:
                self.selected_square = None
                self.update_board()
        else:
            from_row, from_col = self.selected_square
            if (board_row, board_col) == self.selected_square:
                self.selected_square = None
                self.update_board()
            elif self.board[board_row][board_col] != '.' and self.get_piece_color(self.board[board_row][board_col]) == self.current_turn:
                self.selected_square = (board_row, board_col)
                self.update_board()
            else:
                legal_moves = self.get_piece_moves(from_row, from_col)
                if (board_row, board_col) in legal_moves:
                    if self.make_move(from_row, from_col, board_row, board_col):
                        self.selected_square = None
                        self.update_board()
                        self.update_status()
                        self.check_game_end()
                        if not self.game_over and self.current_turn != self.player_side:
                            self.root.after(500, self.ai_move)
                    else:
                        messagebox.showerror("Invalid Move", "That move is not legal!")
                self.selected_square = None
                self.update_board()

    def check_game_end(self):
        current_color = self.current_turn
        if self.is_checkmate(current_color):
            winner = 'Black' if current_color == 'white' else 'White'
            self.status_label.config(text=f"Checkmate! {winner} wins!")
            self.game_over = True
        elif self.is_stalemate(current_color):
            self.status_label.config(text="Stalemate! Draw!")
            self.game_over = True
        elif self.fifty_move_counter >= 100:
            self.status_label.config(text="Draw by 50-move rule!")
            self.game_over = True
        elif self.is_insufficient_material():
            self.status_label.config(text="Draw by insufficient material!")
            self.game_over = True
        elif self.is_threefold_repetition():
            self.status_label.config(text="Draw by threefold repetition!")
            self.game_over = True

    def update_board(self):
        for gui_r in range(8):
            for gui_c in range(8):
                if self.player_side == 'black':
                    board_r = 7 - gui_r
                    board_c = gui_c
                else:
                    board_r = gui_r
                    board_c = gui_c
                
                btn = self.squares[gui_r][gui_c]
                piece = self.board[board_r][board_c]
                bg_color = '#f0d9b5' if (gui_r + gui_c) % 2 == 0 else '#b58863'
                
                if self.selected_square:
                    selected_r, selected_c = self.selected_square
                    if (board_r, board_c) == (selected_r, selected_c):
                        bg_color = '#FFFF00'
                    
                    legal_moves = self.get_piece_moves(selected_r, selected_c)
                    if (board_r, board_c) in legal_moves:
                        bg_color = '#90EE90'
                
                if self.last_move:
                    from_r, from_c, to_r, to_c = self.last_move
                    if (board_r, board_c) in [(from_r, from_c), (to_r, to_c)]:
                        bg_color = '#FFD700'
                
                if self.is_in_check(self.current_turn):
                    king_pos = self.find_king(self.current_turn)
                    if king_pos and (board_r, board_c) == king_pos:
                        bg_color = '#FF6B6B'
                
                btn.config(text=self.PIECES.get(piece, ''), bg=bg_color)

    def update_status(self):
        if self.game_over:
            return
        status = f"{self.current_turn.title()}'s turn"
        if self.is_in_check(self.current_turn):
            status += " - CHECK!"
        self.status_label.config(text=status)
        
        if self.move_history:
            recent_moves = self.move_history[-5:]
            history_text = "Recent moves: " + ", ".join([
                f"{self.square_to_notation(move['from'])}-{self.square_to_notation(move['to'])}" 
                for move in recent_moves
            ])
            self.history_label.config(text=history_text)

    def square_to_notation(self, pos):
        row, col = pos
        return chr(ord('a') + col) + str(8 - row)

    def ai_move(self):
        if self.game_over or self.current_turn == self.player_side:
            return
        start_time = time.time()
        move = self.minimax(3, self.current_turn, -float('inf'), float('inf'))[1]
        if time.time() - start_time > 2:
            print("AI move took", time.time() - start_time, "seconds")
        if move:
            from_r, from_c, to_r, to_c = move
            self.make_move(from_r, from_c, to_r, to_c)
            self.update_board()
            self.update_status()
            self.check_game_end()

    def minimax(self, depth, color, alpha, beta):
        position_key = zlib.crc32(self.get_position_key().encode())
        if position_key in self.transposition_table:
            tt_entry = self.transposition_table[position_key]
            if tt_entry['depth'] >= depth:
                return tt_entry['score'], tt_entry['best_move']
        
        if depth == 0 or self.is_checkmate(color) or self.is_stalemate(color) or self.is_insufficient_material() or self.is_threefold_repetition():
            score = self.evaluate_board()
            return score, None
        
        moves = self.get_all_moves(color)
        # Order moves: captures first, then checks, then others
        moves = self.order_moves(moves)
        
        best_move = None
        if color == self.current_turn:
            max_eval = -float('inf')
            for move in moves:
                from_r, from_c, to_r, to_c = move
                original_piece = self.board[to_r][to_c]
                moving_piece = self.board[from_r][from_c]
                
                self.board[to_r][to_c] = moving_piece
                self.board[from_r][from_c] = '.'
                self.current_turn = 'black' if color == 'white' else 'white'
                
                eval_score, _ = self.minimax(depth - 1, self.current_turn, alpha, beta)
                
                self.current_turn = color
                self.board[from_r][from_c] = moving_piece
                self.board[to_r][to_c] = original_piece
                
                if eval_score > max_eval:
                    max_eval = eval_score
                    best_move = move
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break
            
            self.transposition_table[position_key] = {
                'score': max_eval,
                'best_move': best_move,
                'depth': depth
            }
            return max_eval, best_move
        else:
            min_eval = float('inf')
            for move in moves:
                from_r, from_c, to_r, to_c = move
                original_piece = self.board[to_r][to_c]
                moving_piece = self.board[from_r][from_c]
                
                self.board[to_r][to_c] = moving_piece
                self.board[from_r][from_c] = '.'
                self.current_turn = 'black' if color == 'white' else 'white'
                
                eval_score, _ = self.minimax(depth - 1, self.current_turn, alpha, beta)
                
                self.current_turn = color
                self.board[from_r][from_c] = moving_piece
                self.board[to_r][to_c] = original_piece
                
                if eval_score < min_eval:
                    min_eval = eval_score
                    best_move = move
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break
            
            self.transposition_table[position_key] = {
                'score': min_eval,
                'best_move': best_move,
                'depth': depth
            }
            return min_eval, best_move

    def order_moves(self, moves):
        piece_values = {'p': 1, 'n': 3, 'b': 3, 'r': 5, 'q': 9, 'k': 200}
        ordered_moves = []
        
        for move in moves:
            from_r, from_c, to_r, to_c = move
            score = 0
            
            # Prioritize captures
            if self.board[to_r][to_c] != '.':
                captured_value = piece_values.get(self.board[to_r][to_c].lower(), 0)
                moving_value = piece_values.get(self.board[from_r][from_c].lower(), 0)
                score += 10 * captured_value - moving_value  # MVV-LVA (Most Valuable Victim - Least Valuable Attacker)
            
            # Prioritize checks
            original_piece = self.board[to_r][to_c]
            moving_piece = self.board[from_r][from_c]
            self.board[to_r][to_c] = moving_piece
            self.board[from_r][from_c] = '.'
            opponent_color = 'black' if self.current_turn == 'white' else 'white'
            if self.is_in_check(opponent_color):
                score += 50
            self.board[from_r][from_c] = moving_piece
            self.board[to_r][to_c] = original_piece
            
            # Prioritize pawn promotions
            if self.board[from_r][from_c].lower() == 'p' and (to_r == 0 or to_r == 7):
                score += 100
            
            ordered_moves.append((move, score))
        
        ordered_moves.sort(key=lambda x: x[1], reverse=True)
        return [move[0] for move in ordered_moves]

    def evaluate_board(self):
        piece_values = {'p': 100, 'n': 320, 'b': 330, 'r': 500, 'q': 900, 'k': 20000}
        
        # Piece-square tables for better positional evaluation
        pawn_table = [
            0,  0,  0,  0,  0,  0,  0,  0,
            50, 50, 50, 50, 50, 50, 50, 50,
            10, 10, 20, 30, 30, 20, 10, 10,
            5,  5, 10, 25, 25, 10,  5,  5,
            0,  0,  0, 20, 20,  0,  0,  0,
            5, -5,-10,  0,  0,-10, -5,  5,
            5, 10, 10,-20,-20, 10, 10,  5,
            0,  0,  0,  0,  0,  0,  0,  0
        ]
        
        knight_table = [
            -50,-40,-30,-30,-30,-30,-40,-50,
            -40,-20,  0,  0,  0,  0,-20,-40,
            -30,  0, 10, 15, 15, 10,  0,-30,
            -30,  5, 15, 20, 20, 15,  5,-30,
            -30,  0, 15, 20, 20, 15,  0,-30,
            -30,  5, 10, 15, 15, 10,  5,-30,
            -40,-20,  0,  5,  5,  0,-20,-40,
            -50,-40,-30,-30,-30,-30,-40,-50
        ]
        
        bishop_table = [
            -20,-10,-10,-10,-10,-10,-10,-20,
            -10,  0,  0,  0,  0,  0,  0,-10,
            -10,  0,  5, 10, 10,  5,  0,-10,
            -10,  5,  5, 10, 10,  5,  5,-10,
            -10,  0, 10, 10, 10, 10,  0,-10,
            -10, 10, 10,  5,  5, 10, 10,-10,
            -10,  5,  0,  0,  0,  0,  5,-10,
            -20,-10,-10,-10,-10,-10,-10,-20
        ]
        
        score = 0
        
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece != '.':
                    value = piece_values.get(piece.lower(), 0)
                    idx = r * 8 + c
                    if piece.lower() == 'p':
                        pos_bonus = pawn_table[idx] if self.is_white_piece(piece) else pawn_table[(7-r)*8+c]
                    elif piece.lower() == 'n':
                        pos_bonus = knight_table[idx] if self.is_white_piece(piece) else knight_table[(7-r)*8+c]
                    elif piece.lower() == 'b':
                        pos_bonus = bishop_table[idx] if self.is_white_piece(piece) else bishop_table[(7-r)*8+c]
                    else:
                        pos_bonus = 0
                        
                    if self.is_white_piece(piece):
                        score += value + pos_bonus
                    else:
                        score -= value + pos_bonus
        
        # Mobility bonus
        white_moves = len(self.get_all_moves('white'))
        black_moves = len(self.get_all_moves('black'))
        score += (white_moves - black_moves) * 5
        
        # King safety
        white_king = self.find_king('white')
        black_king = self.find_king('black')
        if white_king:
            r, c = white_king
            # Penalize king on open files
            if not any(self.board[i][c] == 'P' for i in range(r)):
                score -= 20
            # Penalize king in center in opening/middlegame
            if len(self.move_history) < 20 and c in [3, 4]:
                score -= 15
        if black_king:
            r, c = black_king
            if not any(self.board[i][c] == 'p' for i in range(r+1, 8)):
                score += 20
            if len(self.move_history) < 20 and c in [3, 4]:
                score += 15
        
        # Pawn structure
        for c in range(8):
            white_pawns = sum(1 for r in range(8) if self.board[r][c] == 'P')
            black_pawns = sum(1 for r in range(8) if self.board[r][c] == 'p')
            # Penalize doubled pawns
            if white_pawns > 1:
                score -= 10 * (white_pawns - 1)
            if black_pawns > 1:
                score += 10 * (black_pawns - 1)
        
        # Terminal conditions
        if self.is_checkmate('white'):
            score -= 1000000
        elif self.is_checkmate('black'):
            score += 1000000
        elif self.is_in_check('white'):
            score -= 50
        elif self.is_in_check('black'):
            score += 50
        
        return score

    def get_all_moves(self, color):
        moves = []
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece != '.' and self.get_piece_color(piece) == color:
                    piece_moves = self.get_piece_moves(r, c)
                    for move in piece_moves:
                        moves.append((r, c, move[0], move[1]))
        return moves

    def new_game(self):
        self.reset_game()
        self.update_board()
        self.update_status()
        if self.player_side == 'black':
            self.root.after(500, self.ai_move)

    def switch_side(self):
        self.player_side = 'black' if self.player_side == 'white' else 'white'
        self.new_game()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    game = ChessVsAI()
    game.run()