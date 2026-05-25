"""
This module serves as the core state machine and physics engine for the chess application.
It encapsulates data structures for tracking board configurations, turn histories, draw triggers,
and features an explicit ray-casting move generator handling absolute pins, checks, and specialized moves.
"""

class GameState():
    """
    Manages the internal state of a chess game, tracking piece locations, game logs,
    castling rights, draw conditions, and evaluating pseudo-legal vs. legal moves.
    """
    def __init__(self):
        """
        Initializes an 8x8 chessboard matrix, turn indicators, move logs,
        king tracking coordinates, castling flags, and draw rule states.
        """
        # The 8x8 matrix representing the physical board layout.
        # Format: 'w'/'b' prefix for color + piece type code ('R', 'N', 'B', 'Q', 'K', 'P').
        # '--' represents an empty square.
        self.board = [
            ["bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR"],
            ["bP", "bP", "bP", "bP", "bP", "bP", "bP", "bP"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["wP", "wP", "wP", "wP", "wP", "wP", "wP", "wP"],
            ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR"],
        ]
        self.white_to_move = True  # True if it is White's turn, False if Black's
        self.move_log = []         # Collection of all executed Move objects

        # Track king coordinates dynamically to optimize check and pin calculations
        self.white_king_location = (7, 4)
        self.black_king_location = (0, 4)

        # Advanced check/pin tracking fields populated during move generation
        self.in_check = False
        self.pins = []    # Format: (row, col, direction_x, direction_y)
        self.checks = []  # Format: (row, col, direction_x, direction_y)

        # Castling rights parameters
        self.castle_rights = CastleRights(True, True, True, True)
        self.castle_rights_log = [CastleRights(True, True, True, True)]

        # --- DRAW TRACKERS ---
        self.fifty_move_counter = 0
        self.fifty_move_log = [0]
        self.board_history_log = [self.get_board_string()]

        # --- EN PASSANT TARGETS ---
        self.enpassant_possible = ()       # Coordinate square where an en passant capture is legal
        self.enpassant_possible_log = [()] # Stack tracking en passant history across undos

    def get_board_string(self):
        """
        Flattens the 2D board matrix into a single 128-character string token.
        Used to track structural repetition across historical turns.
        """
        return "".join(["".join(row) for row in self.board])

    def check_insufficient_material(self):
        """
        Scans the active board matrix to evaluate if either side has sufficient piece material
        left to mathematically force a checkmate sequence under FIDE rules.

        Returns:
            bool: True if a draw by insufficient material is triggered, False otherwise.
        """
        all_pieces = []
        for row in self.board:
            for piece in row:
                if piece != "--":
                    all_pieces.append(piece)
        total_pieces = len(all_pieces)

        if total_pieces > 4:
            return False

        if total_pieces == 2:  # King vs King
            return True

        if total_pieces == 3:  # King + Minor Piece vs King
            minor_pieces = [p[1] for p in all_pieces if p[1] != "K"]
            if minor_pieces[0] in ("B", "N"):
                return True

        if total_pieces == 4:  # King + Minor Piece vs King + Minor Piece
            white_minors = [p[1] for p in all_pieces if p[0] == "w" and p[1] != "K"]
            black_minors = [p[1] for p in all_pieces if p[0] == "b" and p[1] != "K"]
            if len(white_minors) == 1 and len(black_minors) == 1:
                w_p, b_p = white_minors[0], black_minors[0]
                # Double knights, matching bishops, or knight vs bishop cannot force mate
                if (w_p == "B" and b_p == "B") or (w_p == "N" and b_p == "N") or \
                   (w_p == "B" and b_p == "N") or (w_p == "N" and b_p == "B"):
                    return True
        return False

    def check_threefold_repetition(self):
        """
        Queries historical board log states to see if the current position string
        token matches occurrences across previous turns.

        Returns:
            bool: True if the exact spatial board state has occurred 3 or more times.
        """
        return self.board_history_log.count(self.get_board_string()) >= 3

    def make_move(self, move):
        """
        Executes a Move object on the board matrix, updates tracking states
        (Kings, logs, and draw variables), and flips the active player turn.

        Args:
            move (Move): The move data structure containing start/end coordinates.
        """
        self.board[move.start_row][move.start_col] = "--"

        # Handle pawn promotions
        if move.is_pawn_promotion:
            self.board[move.end_row][move.end_col] = move.piece_moved[0] + move.promotion_choice
        else:
            self.board[move.end_row][move.end_col] = move.piece_moved

        self.move_log.append(move)

        # Synchronize king location tracking
        if move.piece_moved == "wK":
            self.white_king_location = (move.end_row, move.end_col)
        elif move.piece_moved == "bK":
            self.black_king_location = (move.end_row, move.end_col)

        # Handle en passant capture modifications
        if move.is_enpassant_move:
            self.board[move.start_row][move.end_col] = "--"

        # Handle castling rook configurations
        if move.is_castle_move:
            if move.end_col - move.start_col == 2:  # Kingside
                self.board[move.end_row][move.end_col-1] = self.board[move.end_row][7]
                self.board[move.end_row][7] = "--"
            else:  # Queenside
                self.board[move.end_row][move.end_col+1] = self.board[move.end_row][0]
                self.board[move.end_row][0] = "--"

        # Update castling history profiles
        self.update_castle_rights(move)
        self.castle_rights_log.append(CastleRights(self.castle_rights.white_king_side, self.castle_rights.white_queen_side,
                                                   self.castle_rights.black_king_side, self.castle_rights.black_queen_side))

        # Update en passant availability coordinates
        if move.piece_moved[1] == "P" and abs(move.start_row - move.end_row) == 2:
            self.enpassant_possible = ((move.start_row + move.end_row) // 2, move.start_col)
        else:
            self.enpassant_possible = ()
        self.enpassant_possible_log.append(self.enpassant_possible)

        # Process the 50-move rule counter (resets on pawn pushes or any captures)
        if move.piece_moved[1] == "P" or move.piece_captured != "--":
            self.fifty_move_counter = 0
        else:
            self.fifty_move_counter += 1
        self.fifty_move_log.append(self.fifty_move_counter)
        self.board_history_log.append(self.get_board_string())

        # Swap player turn control
        self.white_to_move = not self.white_to_move

    def undo_move(self):
        """
        Reverses the last recorded move in the transaction history logs,
        restoring prior board matrices, metadata coordinates, and rule trackers.
        """
        if self.move_log:
            last_move = self.move_log.pop()
            self.board[last_move.start_row][last_move.start_col] = last_move.piece_moved

            # Rollback pieces captured during en passant or normal moves
            if last_move.is_enpassant_move:
                self.board[last_move.end_row][last_move.end_col] = "--"
                self.board[last_move.start_row][last_move.end_col] = last_move.piece_captured
            else:
                self.board[last_move.end_row][last_move.end_col] = last_move.piece_captured

            # Toggle active player colors back
            self.white_to_move = not self.white_to_move
            if last_move.piece_moved == "wK":
                self.white_king_location = (last_move.start_row, last_move.start_col)
            elif last_move.piece_moved == "bK":
                self.black_king_location = (last_move.start_row, last_move.start_col)

            # Rollback castling rook structures
            if last_move.is_castle_move:
                if last_move.end_col - last_move.start_col == 2:
                    self.board[last_move.end_row][7] = self.board[last_move.end_row][last_move.end_col-1]
                    self.board[last_move.end_row][last_move.end_col-1] = "--"
                else:
                    self.board[last_move.end_row][0] = self.board[last_move.end_row][last_move.end_col+1]
                    self.board[last_move.end_row][last_move.end_col+1] = "--"

            # Safe log pops (prevent IndexError when reverting to base state)
            if len(self.castle_rights_log) > 1:
                self.castle_rights_log.pop()
                previous_rights = self.castle_rights_log[-1]
                self.castle_rights = CastleRights(previous_rights.white_king_side, previous_rights.white_queen_side,
                                                  previous_rights.black_king_side, previous_rights.black_queen_side)

            if len(self.fifty_move_log) > 1:
                self.fifty_move_log.pop()
                self.fifty_move_counter = self.fifty_move_log[-1]

            if len(self.board_history_log) > 1:
                self.board_history_log.pop()

            if len(self.enpassant_possible_log) > 1:
                self.enpassant_possible_log.pop()
                self.enpassant_possible = self.enpassant_possible_log[-1]

    def get_valid_moves(self):
        """
        Generates and filters complete legal chess moves, accounting for absolute pins,
        active single/double check lines, and restricted king movements.

        Returns:
            list[Move]: Legal Move instances available to the active player.
        """
        moves = []
        # Populate current pins, checks, and in_check status via ray-casting
        self.in_check, self.pins, self.checks = self.check_for_pins_and_checks()

        king_row, king_col = self.white_king_location if self.white_to_move else self.black_king_location

        if self.in_check:
            if len(self.checks) == 1:  # Single Check: Pieces can block, capture threat, or King can flee
                all_possible_moves = self.get_possible_moves()
                check = self.checks[0]
                check_row, check_col = check[0], check[1]
                piece_checking = self.board[check_row][check_col]
                valid_squares = []  # Squares that non-king pieces are legally allowed to land on

                # Knights must be captured directly; sliding pieces can have their vectors blocked
                if piece_checking[1] == "N":
                    valid_squares = [(check_row, check_col)]
                else:
                    for i in range(1, 8):
                        valid_square = (king_row + check[2] * i, king_col + check[3] * i)
                        valid_squares.append(valid_square)
                        if valid_square[0] == check_row and valid_square[1] == check_col:
                            break

                # Filter pseudo-legal non-king moves down to blocking/capturing options
                for i in range(len(all_possible_moves) - 1, -1, -1):
                    if all_possible_moves[i].piece_moved[1] != "K":
                        if (all_possible_moves[i].end_row, all_possible_moves[i].end_col) in valid_squares:
                            moves.append(all_possible_moves[i])

                # Evaluate escape paths for the king
                self.get_king_moves(king_row, king_col, moves)
            else:
                # Double Check: King is forced to move; blocking or capturing is mathematically impossible
                self.get_king_moves(king_row, king_col, moves)
        else:
            # King is safe; collect all base moves plus castling privileges
            moves = self.get_possible_moves()
            self.get_castle_moves(king_row, king_col, moves)

        return moves

    def get_possible_moves(self):
        """
        Collects all pseudo-legal moves for the active side based purely on
        unfiltered geometry shapes, ignoring pins and checks.

        Returns:
            list[Move]: A collection of pseudo-legal moves.
        """
        valid_moves = []
        for row in range(len(self.board)):
            for col in range(len(self.board[row])):
                turn = self.board[row][col][0]
                if (turn == "w" and self.white_to_move) or (turn == "b" and not self.white_to_move):
                    piece = self.board[row][col][1]
                    if piece == "P":
                        self.get_pawn_moves(row, col, valid_moves)
                    elif piece == "R":
                        self.get_rook_moves(row, col, valid_moves)
                    elif piece == "N":
                        self.get_knight_moves(row, col, valid_moves)
                    elif piece == "B":
                        self.get_bishop_moves(row, col, valid_moves)
                    elif piece == "Q":
                        self.get_queen_moves(row, col, valid_moves)
                    elif piece == "K":
                        self.get_king_moves(row, col, valid_moves)
        return valid_moves

    def check_for_pins_and_checks(self):
        """
        Performs an outward, multi-directional ray-cast from the active king's square.
        Identifies ally pieces acting as absolute absolute pins and enemy check lines.

        Returns:
            tuple: (bool in_check, list pins, list checks)
        """
        pins, checks, in_check = [], [], False
        if self.white_to_move:
            enemy_color, ally_color = "b", "w"
            start_row, start_col = self.white_king_location
        else:
            enemy_color, ally_color = "w", "b"
            start_row, start_col = self.black_king_location

        # Orthogonal and diagonal compass search rays
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]

        for j in range(len(directions)):
            direction = directions[j]
            possiblePin = ()
            for i in range(1, 8):
                end_row = start_row + direction[0] * i
                end_col = start_col + direction[1] * i

                if 0 <= end_row < 8 and 0 <= end_col < 8:
                    end_piece = self.board[end_row][end_col]
                    if end_piece[0] == ally_color:
                        if possiblePin == ():  # First ally piece encountered along ray
                            possiblePin = (end_row, end_col, direction[0], direction[1])
                        else:                  # Second ally piece blocks any pinning possibility
                            break
                    elif end_piece != "--" and end_piece[0] == enemy_color:
                        piece_type = end_piece[1]

                        # Conditional matching mapping geometric rays to piece behaviors
                        if (0 <= j <= 3 and piece_type == "R") or \
                           (4 <= j <= 7 and piece_type == "B") or \
                           (i == 1 and piece_type == "P" and ((enemy_color == "w" and 4 <= j <= 5) or (enemy_color == "b" and 6 <= j <= 7))) or \
                           (piece_type == "Q") or (i == 1 and piece_type == "K"):

                            if possiblePin == ():  # No protecting piece found; king is in check
                                in_check = True
                                checks.append((end_row, end_col, direction[0], direction[1]))
                            else:                  # Guard piece acts as an absolute pin ray
                                pins.append(possiblePin)
                                break
                        else:
                            break  # Enemy piece does not attack along this line shape
                else:
                    break  # Edge of board boundary reached

        # Check for non-sliding knight threats separately
        knight_moves = [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]
        for move in knight_moves:
            end_row, end_col = start_row + move[0], start_col + move[1]
            if 0 <= end_row < 8 and 0 <= end_col < 8:
                end_piece = self.board[end_row][end_col]
                if end_piece[0] == enemy_color and end_piece[1] == "N":
                    in_check = True
                    checks.append((end_row, end_col, move[0], move[1]))

        return in_check, pins, checks

    def get_pawn_moves(self, row, col, valid_moves):
        """Generates legal pawn steps, captures, en passant options, and absolute pin constraints."""
        piece_pinned, pin_direction = self.get_piece_pin_status(row, col)
        if self.white_to_move:
            direction, start_row, enemy_color = -1, 6, "b"
        else:
            direction, start_row, enemy_color = 1, 1, "w"

        # 1-Square vertical advance steps
        next_row = row + direction
        if self.board[next_row][col] == "--":
            if not piece_pinned or pin_direction == (direction, 0):
                valid_moves.append(Move((row, col), (next_row, col), self.board))

            # 2-Square initial sprint steps
            two_step_row = row + 2 * direction
            if (row == start_row and self.board[two_step_row][col] == "--"
                and (not piece_pinned or pin_direction == (direction, 0))):
                valid_moves.append(Move((row, col), (two_step_row, col), self.board))

        # Diagonal attack steps
        for dc in (-1, 1):
            new_col = col + dc
            if not (0 <= new_col < 8):
                continue
            if piece_pinned and pin_direction != (direction, dc):
                continue

            target = self.board[next_row][new_col]
            if target.startswith(enemy_color):
                valid_moves.append(Move((row, col), (next_row, new_col), self.board))

            # En Passant evaluation via coordinate checking
            if (next_row, new_col) == self.enpassant_possible:
                king_row, king_col = self.white_king_location if self.white_to_move else self.black_king_location
                attacking_piece = blocking_piece = False

                # Handle the horizontal absolute row-pin edge case unique to en passant
                if king_row == row:
                    if king_col < col:
                        inside_range, outside_range = range(king_col + 1, col), range(col + 1, 8)
                    else:
                        inside_range, outside_range = range(king_col - 1, col, -1), range(col - 1, -1, -1)

                    for i in inside_range:
                        if self.board[row][i] != "--":
                            blocking_piece = True
                            break
                    for i in outside_range:
                        square = self.board[row][i]
                        if i == new_col: continue
                        if square != "--":
                            if square[0] == enemy_color and square[1] in ("R", "Q"):
                                attacking_piece = True
                            else:
                                blocking_piece = True
                            break

                if not attacking_piece or blocking_piece:
                    valid_moves.append(Move((row, col), (next_row, new_col), self.board, is_enpassant_move=True))

    def get_sliding_moves(self, row, col, directions, piece_pinned, pin_direction, valid_moves):
        """
        Generic trace routine used to slide linear piece types along ray direction matrices
        until encountering the board boundary or another piece structure.
        """
        enemy_color = "b" if self.white_to_move else "w"
        for d in directions:
            # Pinned pieces can only move along their pinning vector ray line
            if piece_pinned and pin_direction != d and pin_direction != (-d[0], -d[1]):
                continue
            for i in range(1, 8):
                new_row, new_col = row + d[0] * i, col + d[1] * i
                if 0 <= new_row < 8 and 0 <= new_col < 8:
                    target = self.board[new_row][new_col]
                    if target == "--":
                        valid_moves.append(Move((row, col), (new_row, new_col), self.board))
                    elif target[0] == enemy_color: # Legal capture possible before block
                        valid_moves.append(Move((row, col), (new_row, new_col), self.board))
                        break
                    else:
                        break # Blocked by friendly piece
                else:
                    break # Out of board boundaries

    def get_rook_moves(self, row, col, valid_moves):
        """Collects pseudo-legal orthogonal slide options."""
        piece_pinned, pin_direction = self.get_piece_pin_status(row, col)
        self.get_sliding_moves(row, col, [(1, 0), (-1, 0), (0, 1), (0, -1)], piece_pinned, pin_direction, valid_moves)

    def get_bishop_moves(self, row, col, valid_moves):
        """Collects pseudo-legal diagonal slide options."""
        piece_pinned, pin_direction = self.get_piece_pin_status(row, col)
        self.get_sliding_moves(row, col, [(1, 1), (1, -1), (-1, 1), (-1, -1)], piece_pinned, pin_direction, valid_moves)

    def get_piece_pin_status(self, row, col):
        """Helper checking if a coordinate matches existing active absolute king pin rays."""
        for pin in self.pins:
            if pin[0] == row and pin[1] == col:
                return True, (pin[2], pin[3])
        return False, ()

    def get_knight_moves(self, row, col, valid_moves):
        """Generates legal L-shape hops. Knights cannot move if trapped in an absolute pin."""
        for i in range(len(self.pins) - 1, -1, -1):
            if self.pins[i][0] == row and self.pins[i][1] == col:
                return # Pinned knights cannot shift along diagonal or orthogonal rays safely

        enemy_color = "b" if self.white_to_move else "w"
        directions = [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]
        for d in directions:
            new_row, new_col = row + d[0], col + d[1]
            if 0 <= new_row < 8 and 0 <= new_col < 8:
                target = self.board[new_row][new_col]
                if target == "--" or target[0] == enemy_color:
                    valid_moves.append(Move((row, col), (new_row, new_col), self.board))

    def get_queen_moves(self, row, col, valid_moves):
        """Combines rook and bishop sliding vector movements."""
        self.get_rook_moves(row, col, valid_moves)
        self.get_bishop_moves(row, col, valid_moves)

    def get_king_moves(self, row, col, valid_moves):
        """
        Generates standard 1-square king shifts, systematically simulating the step location
        to confirm the king does not walk directly into an active enemy attack line.
        """
        ally_color = "w" if self.white_to_move else "b"
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]

        for d in directions:
            new_row, new_col = row + d[0], col + d[1]
            if not (0 <= new_row < 8 and 0 <= new_col < 8): continue
            target = self.board[new_row][new_col]
            if target != "--" and target[0] == ally_color: continue

            # Speculatively make the king move onto target square to check validity
            saved_piece = self.board[new_row][new_col]
            self.board[row][col], self.board[new_row][new_col] = "--", ally_color + "K"

            if self.white_to_move:
                self.white_king_location = (new_row, new_col)
            else:
                self.black_king_location = (new_row, new_col)

            king_in_check, _, _ = self.check_for_pins_and_checks()

            # Rollback speculative values instantly
            if self.white_to_move:
                self.white_king_location = (row, col)
            else:
                self.black_king_location = (row, col)

            self.board[row][col], self.board[new_row][new_col] = ally_color + "K", saved_piece

            if not king_in_check:
                valid_moves.append(Move((row, col), (new_row, new_col), self.board))

    def get_castle_moves(self, row, col, moves):
        """Evaluates rights to register kingside and queenside castle moves."""
        if self.in_check: return
        sides = []
        if (self.white_to_move and self.castle_rights.white_king_side) or (not self.white_to_move and self.castle_rights.black_king_side):
            sides.append((1, [col+1, col+2], col+2))
        if (self.white_to_move and self.castle_rights.white_queen_side) or (not self.white_to_move and self.castle_rights.black_queen_side):
            sides.append((-1, [col-1, col-2, col-3], col-2))

        for direction, empty_cols, target_col in sides:
            # All intermediate squares must be completely empty
            if all(self.board[row][c] == "--" for c in empty_cols):
                # The king cannot pass through any square attacked by an enemy piece
                if self.is_square_safe(row, col + direction) and self.is_square_safe(row, col + (2 * direction)):
                    moves.append(Move((row, col), (row, target_col), self.board))

    def update_castle_rights(self, move):
        """Updates castling rights if a king or rook moves or is captured."""
        if move.piece_moved == "wK":
            self.castle_rights.white_king_side = self.castle_rights.white_queen_side = False
        elif move.piece_moved == "bK":
            self.castle_rights.black_king_side = self.castle_rights.black_queen_side = False
        elif move.piece_moved == "wR":
            if move.start_row == 7:
                if move.start_col == 0: self.castle_rights.white_queen_side = False
                elif move.start_col == 7: self.castle_rights.white_king_side = False
        elif move.piece_moved == "bR":
            if move.start_row == 0:
                if move.start_col == 0: self.castle_rights.black_queen_side = False
                elif move.start_col == 7: self.castle_rights.black_king_side = False

    def is_square_safe(self, row, col):
        """Temporary shifts king profile positions to check if a landing square is actively attacked."""
        original_location = self.white_king_location if self.white_to_move else self.black_king_location
        if self.white_to_move: self.white_king_location = (row, col)
        else: self.black_king_location = (row, col)

        square_in_check, _, _ = self.check_for_pins_and_checks()

        if self.white_to_move: self.white_king_location = original_location
        else: self.black_king_location = original_location
        return not square_in_check


class Move():
    """
    Encapsulates coordinate parameters for a chess move transaction.
    Handles coordinate translations to Standard Algebraic Notation.
    """
    ranks_to_rows = {"1": 7, "2": 6, "3": 5, "4": 4, "5": 3, "6": 2, "7": 1, "8": 0}
    rows_to_ranks = {v: k for k, v in ranks_to_rows.items()}
    files_to_cols = {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4, "f": 5, "g": 6, "h": 7}
    cols_to_files = {v: k for k, v in files_to_cols.items()}

    def __init__(self, start_square, end_square, board, is_enpassant_move=False, promotion_choice="Q"):
        """Initializes a Move object with metadata flags for type sorting evaluations."""
        self.start_row = start_square[0]
        self.start_col = start_square[1]
        self.end_row = end_square[0]
        self.end_col = end_square[1]
        self.piece_moved = board[self.start_row][self.start_col]

        # Check for castling actions (King shifts 2 squares horizontally)
        self.is_castle_move = (self.piece_moved[1] == "K" and abs(self.start_col - self.end_col) == 2)

        # Identify pawn promotions
        self.is_pawn_promotion = False
        if (self.piece_moved == "wP" and self.end_row == 0) or (self.piece_moved == "bP" and self.end_row == 7):
            self.is_pawn_promotion = True

        self.promotion_choice = promotion_choice

        if is_enpassant_move:
            self.piece_captured = "bP" if self.piece_moved.startswith("w") else "wP"
        else:
            self.piece_captured = board[self.end_row][self.end_col]

        # Unique integer hash key used to compare moves efficiently
        self.move_id = self.start_row * 1000 + self.start_col * 100 + self.end_row * 10 + self.end_col
        self.is_enpassant_move = is_enpassant_move

    def get_chess_notation(self):
        """Converts coordinates into a standard string sequence (e.g., e2e4)."""
        return self.get_rank_file((self.start_row, self.start_col)) + self.get_rank_file((self.end_row, self.end_col))

    def get_rank_file(self, square):
        """Maps matrix rows and columns directly to rank and file characters."""
        return self.cols_to_files[square[1]] + self.rows_to_ranks[square[0]]

    def __eq__(self, other):
        """Compares moves using their unique move IDs."""
        if isinstance(other, Move):
            return self.move_id == other.move_id
        return False


class CastleRights():
    """
    Simple container class tracking individual castling privileges
    for both kingside and queenside configurations.
    """
    def __init__(self, white_king_side, white_queen_side, black_king_side, black_queen_side):
        self.white_king_side = white_king_side
        self.white_queen_side = white_queen_side
        self.black_king_side = black_king_side
        self.black_queen_side = black_queen_side
