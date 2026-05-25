import random

def find_random_move(valid_moves):
    """
    Picks and returns a completely random legal move.
    """
    if len(valid_moves) > 0:
        return random.choice(valid_moves)
    return None
