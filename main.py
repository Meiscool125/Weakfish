# BIG THANKS TO EDDIE SHARICK ON YOUTUBE FOR HELPING ME GET STARTED WITH THIS PROJECT!!!! https://www.youtube.com/watch?v=-QHAPDk5tgs&list=PLBwF487qi8MGU81nDGaeNE1EnNEPYWKY_&index=11

"""
This module handles visual rendering, game loop frames, asset allocations,
and user inputs using Pygame. It synchronizes human actions and engine calculations.
"""

from game_state_handler import GameState, Move
import engine
import pygame
pygame.init()

# Global configuration properties defining screen scale geometry parameters
WIDTH = HEIGHT = 1024
DIMENSION = 8
SQUARE_SIZE = HEIGHT / DIMENSION
MAX_FPS = 15
IMAGES = {}

# Mode parameters toggles: True means human control, False delegates actions to AI engine loops
PLAYER_ONE = True  # White configuration player type
PLAYER_TWO = True  # Black configuration player type


def load_images():
    """
    Pre-loads high-resolution piece images into memory.
    Saves performance by avoiding disk reads during frame redraws.
    """
    pieces = ["bR", "bN", "bB", "bQ", "bK", "bP", "wR", "wN", "wB", "wQ", "wK", "wP"]
    for piece in pieces:
        IMAGES[piece] = pygame.transform.scale(pygame.image.load(f"piece-images/{piece}.png"), (SQUARE_SIZE, SQUARE_SIZE))

def draw_board(screen):
    """Draws the alternating light and dark squares of the chessboard background."""
    colors = [pygame.Color(217, 228, 232), pygame.Color(113, 149, 170)]
    for row in range(DIMENSION):
        for column in range(DIMENSION):
            pygame.draw.rect(screen, colors[(row+column)%2], pygame.Rect(column*SQUARE_SIZE, row*SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE))

def draw_pieces(screen, board):
    """Blits the pre-loaded piece assets onto their respective board coordinates."""
    for row in range(DIMENSION):
        for column in range(DIMENSION):
            piece = board[row][column]
            if piece != "--":
                screen.blit(IMAGES[piece], pygame.Rect(column*SQUARE_SIZE, row*SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE))

def draw_game_state(screen, gameState, valid_moves, selected_square):
    """Coordinates drawing the board background, move highlights, and active pieces."""
    draw_board(screen)
    highlight_squares(screen, gameState, valid_moves, selected_square)
    draw_pieces(screen, gameState.board)

def highlight_squares(screen, gameState, valid_moves, selected_square):
    """
    Highlights the last move made, the currently selected piece,
    and indicators for all available legal destination squares.
    """
    # Highlight the last move made in translucent yellow
    if len(gameState.move_log) > 0:
        last_move = gameState.move_log[-1]
        move_surface = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE))
        move_surface.fill(pygame.Color(247, 247, 105))
        move_surface.set_alpha(70)
        screen.blit(move_surface, (last_move.start_col * SQUARE_SIZE, last_move.start_row * SQUARE_SIZE))
        screen.blit(move_surface, (last_move.end_col * SQUARE_SIZE, last_move.end_row * SQUARE_SIZE))

    # Highlight the selected piece and its valid destination paths
    if selected_square != ():
        row, col = selected_square
        if gameState.board[row][col] != "--" and gameState.board[row][col][0] == ('w' if gameState.white_to_move else 'b'):
            s = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE))
            s.fill(pygame.Color(255, 255, 0))
            s.set_alpha(110)
            screen.blit(s, (col * SQUARE_SIZE, row * SQUARE_SIZE))

            s.fill(pygame.Color(173, 216, 230))
            s.set_alpha(120)
            for move in valid_moves:
                if move.start_row == row and move.start_col == col:
                    screen.blit(s, (move.end_col * SQUARE_SIZE, move.end_row * SQUARE_SIZE))

    # Highlight the king's square in red if currently in check
    if gameState.in_check:
        king_row, king_col = gameState.white_king_location if gameState.white_to_move else gameState.black_king_location
        check_surface = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE))
        check_surface.fill(pygame.Color(255, 0, 0))
        check_surface.set_alpha(70)
        screen.blit(check_surface, (king_col * SQUARE_SIZE, king_row * SQUARE_SIZE))

def draw_text_with_outline(screen, text, font, text_color, outline_color, center_pos, thickness=4):
    """
    Renders high-visibility text by offsetting a dark outline border underneath
    the primary colored text layer. Replaces basic unreadable elements.
    """
    text_surface = font.render(text, True, text_color)
    outline_surface = font.render(text, True, outline_color)
    text_rect = text_surface.get_rect(center=center_pos)
    x, y = text_rect.x, text_rect.y

    # Blit outline layer offsets across compass positions
    for dx in range(-thickness, thickness + 1):
        for dy in range(-thickness, thickness + 1):
            if dx != 0 or dy != 0:
                screen.blit(outline_surface, (x + dx, y + dy))
    screen.blit(text_surface, (x, y))

def get_promotion_choice(screen, color):
    """
    Freezes the main loop to overlay a selection menu when a human promotes a pawn.
    Returns the piece type character code chosen by the user.
    """
    overlay = pygame.Surface(screen.get_size())
    overlay.fill((128, 128, 128))
    overlay.set_alpha(180)
    screen.blit(overlay, (0, 0))

    options, box_size, padding = ["Q", "R", "B", "N"], SQUARE_SIZE, 20
    total_width = (box_size * 4) + (padding * 3)
    start_x, y_pos = (WIDTH - total_width) // 2, (HEIGHT - box_size) // 2

    option_rects = {}
    for i, option in enumerate(options):
        x_pos = start_x + i * (box_size + padding)
        rect = pygame.Rect(x_pos, y_pos, box_size, box_size)
        option_rects[option] = rect

        pygame.draw.rect(screen, pygame.Color(240, 240, 240), rect)
        pygame.draw.rect(screen, pygame.Color(50, 50, 50), rect, 3)
        screen.blit(IMAGES[color + option], (x_pos, y_pos))

    pygame.display.flip()

    # Dedicated input polling wait loop for selection interaction events
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                import sys; sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                for option, rect in option_rects.items():
                    if rect.collidepoint(mouse_pos):
                        return option

def handle_user_events(event, gameState, valid_moves, selected_square, player_clicks, game_over):
    """
    Processes discrete user mouse clicks or key combinations.
    Handles square selections, move executions, or undo actions.
    """
    move_made = False
    if event.type == pygame.MOUSEBUTTONDOWN and not game_over:
        location = pygame.mouse.get_pos()
        col, row = int(location[0] // SQUARE_SIZE), int(location[1] // SQUARE_SIZE)

        if selected_square == (row, col): # Clicked the same square twice; deselect
            selected_square, player_clicks = (), []
        else:
            selected_square = (row, col)
            player_clicks.append(selected_square)

        if len(player_clicks) == 2: # Two clicks registered; attempt to move
            end_row, end_col = player_clicks[1]
            destination_piece = gameState.board[end_row][end_col]
            current_player_color = 'w' if gameState.white_to_move else 'b'

            # If second click is on a friendly piece, treat it as a new selection instead
            if destination_piece != "--" and destination_piece[0] == current_player_color:
                player_clicks = [selected_square]
            else:
                move = Move(player_clicks[0], player_clicks[1], gameState.board)
                if move in valid_moves:
                    actual_move = valid_moves[valid_moves.index(move)]
                    if actual_move.is_pawn_promotion:
                        choice = get_promotion_choice(pygame.display.get_surface(), actual_move.piece_moved[0])
                        actual_move.promotion_choice = choice

                    gameState.make_move(actual_move)
                    move_made = True
                    selected_square, player_clicks = (), []
                else:
                    selected_square, player_clicks = (), []

    # Revert turns using the Left Arrow key
    elif event.type == pygame.KEYDOWN and event.key == pygame.K_LEFT:
        gameState.undo_move()
        selected_square, player_clicks, move_made = (), [], True

    return selected_square, player_clicks, move_made

def main():
    """Main application setup, initialization, and primary state iteration loop."""
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    game_over_surface = pygame.Surface(screen.get_size())
    game_over_surface.fill((128, 128, 128))
    game_over_surface.set_alpha(230)
    font = pygame.font.SysFont("Arial", 48)

    load_images()
    gameState = GameState()
    valid_moves = gameState.get_valid_moves()

    move_made = False
    running = True
    selected_square = ()
    player_clicks = []
    game_over = False

    while running:
        # --- PHASE 1: HUMAN EVENT PROCESSING ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                human_turn = (gameState.white_to_move and PLAYER_ONE) or (not gameState.white_to_move and PLAYER_TWO)
                if human_turn:
                    selected_square, player_clicks, user_moved = handle_user_events(
                        event, gameState, valid_moves, selected_square, player_clicks, game_over
                    )
                    if user_moved: move_made = True

        # --- PHASE 2: EVALUATING STATE DRAWS & END CONDITIONS ---
        if move_made:
            valid_moves = gameState.get_valid_moves()
            if not valid_moves:
                game_over = True
            elif gameState.check_insufficient_material() or gameState.check_threefold_repetition() or gameState.fifty_move_counter >= 100:
                game_over = True
            move_made = False

        # --- PHASE 3: EVENT POLLING FOR AI ENGINES ---
        human_turn = (gameState.white_to_move and PLAYER_ONE) or (not gameState.white_to_move and PLAYER_TWO)
        if not game_over and not human_turn:
            # Render a "Thinking..." overlay only if a human is playing in the match
            if PLAYER_ONE or PLAYER_TWO:
                draw_game_state(screen, gameState, valid_moves, selected_square)
                msg = "White is thinking..." if gameState.white_to_move else "Black is thinking..."
                draw_text_with_outline(screen, msg, font, pygame.Color(255, 255, 255), pygame.Color(0, 0, 0), (WIDTH // 2, HEIGHT // 2))
                pygame.display.flip()

            ai_move = engine.find_random_move(valid_moves)
            if ai_move is not None:
                if ai_move.is_pawn_promotion:
                    ai_move.promotion_choice = "Q" # AI automatically defaults to Queen promotion
                gameState.make_move(ai_move)
                move_made = True
                selected_square, player_clicks = (), []

        # --- PHASE 4: RENDERING FRAME BUFFERS ---
        draw_game_state(screen, gameState, valid_moves, selected_square)

        # Overlay end-of-game screens if termination triggers are tripped
        if game_over:
            screen.blit(game_over_surface, (0, 0))
            if not valid_moves and gameState.in_check:
                msg = "Black wins by checkmate." if gameState.white_to_move else "White wins by checkmate."
            elif not valid_moves and not gameState.in_check:
                msg = "Draw by stalemate."
            elif gameState.check_insufficient_material():
                msg = "Draw by insufficient material."
            elif gameState.check_threefold_repetition():
                msg = "Draw by threefold repetition."
            elif gameState.fifty_move_counter >= 100:
                msg = "Draw by 50-move rule."
            else:
                msg = "Game Over."

            draw_text_with_outline(screen, msg, font, pygame.Color(255, 0, 0), pygame.Color(0, 0, 0), (WIDTH // 2, HEIGHT // 2))

        clock.tick(MAX_FPS)
        pygame.display.flip()

if __name__ == "__main__":
    main()
