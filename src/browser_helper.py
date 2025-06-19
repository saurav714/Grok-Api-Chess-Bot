from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import chess
import logging
import time

logger = logging.getLogger(__name__)

class ChessPlatform:
    def __init__(self, name, url, board_selector):
        self.name = name
        self.url = url
        self.board_selector = board_selector
        
    @property
    def piece_selector(self):
        return '.piece' if self.name == 'chess.com' else '.cg-board piece'

    def get_move_selectors(self, from_square, to_square):
        if self.name == 'lichess':
            return f".square-{from_square}", f".square-{to_square}"
        return f"[data-square='{from_square}']", f"[data-square='{to_square}']"

PLATFORMS = {
    'lichess': ChessPlatform('lichess', 'https://lichess.org', '.cg-board'),
    'chess.com': ChessPlatform('chess.com', 'https://chess.com/play/online', '.board')
}

class BrowserHelper:
    def __init__(self, platform_name='lichess'):
        self.platform = PLATFORMS[platform_name]
        self.driver = None
        self.board_element = None
        
    def initialize(self):
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--start-maximized')
            options.add_experimental_option('excludeSwitches', ['enable-automation'])
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            
            self.driver.get(self.platform.url)
            return self.wait_for_board()
        except Exception as e:
            logger.error(f"Browser initialization error: {e}")
            return False
            
    def wait_for_board(self):
        try:
            self.board_element = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.platform.board_selector))
            )
            return True
        except Exception as e:
            logger.error(f"Error waiting for board: {e}")
            return False

    def get_position(self):
        try:
            if self.platform.name == 'lichess':
                fen = self.board_element.get_attribute('data-fen')
                if fen:
                    return self.validate_fen(fen)
            
            pieces = self.driver.find_elements(By.CSS_SELECTOR, self.platform.piece_selector)
            return self.construct_fen(pieces)
        except Exception as e:
            logger.error(f"Error getting position: {e}")
            return None
            
    def construct_fen(self, pieces):
        board = [['' for _ in range(8)] for _ in range(8)]
        
        for piece in pieces:
            try:
                class_name = piece.get_attribute('class')
                coords = self.get_piece_coordinates(class_name)
                piece_type = self.get_piece_type(class_name)
                if coords and piece_type:
                    x, y = coords
                    board[y][x] = piece_type
            except Exception as e:
                logger.error(f"Error processing piece: {e}")
                
        return self.board_array_to_fen(board)

    def get_piece_coordinates(self, class_name):
        try:
            if 'square-' in class_name:
                square = class_name.split('square-')[1].split()[0]
                file = ord(square[0]) - ord('a')
                rank = 8 - int(square[1])
                return file, rank
            return None
        except Exception as e:
            logger.error(f"Error getting piece coordinates: {e}")
            return None

    def get_piece_type(self, class_name):
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
            logger.error(f"Error getting piece type: {e}")
            return ''

    def board_array_to_fen(self, board):
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
            return self.validate_fen(f"{fen} w KQkq - 0 1")
        except Exception as e:
            logger.error(f"Error converting board to FEN: {e}")
            return chess.STARTING_FEN

    def validate_fen(self, fen):
        try:
            chess.Board(fen)
            return fen
        except Exception:
            return chess.STARTING_FEN

    def play_move(self, move, board):
        try:
            from_square = chess.square_name(move.from_square)
            to_square = chess.square_name(move.to_square)
            
            from_selector, to_selector = self.platform.get_move_selectors(from_square, to_square)
            
            from_element = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, from_selector))
            )
            to_element = self.driver.find_element(By.CSS_SELECTOR, to_selector)
            
            actions = ActionChains(self.driver)
            actions.move_to_element(from_element)
            actions.click_and_hold()
            time.sleep(0.2)
            actions.move_to_element(to_element)
            time.sleep(0.1)
            actions.release()
            actions.perform()
            
            return True
        except Exception as e:
            logger.error(f"Error playing move: {e}")
            return False

    def cleanup(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")