import time

from main import GameState


def perft(depth, game_state):
    """
    Returns the total number of legal move paths at a given depth.
    """
    if depth == 0:
        return 1

    moves = game_state.get_valid_moves()
    nodes = 0

    for move in moves:
        game_state.make_move(move)
        nodes += perft(depth - 1, game_state)
        game_state.undo_move()

    return nodes

if __name__ == "__main__":
    game_state = GameState()
    depth = 0
    correct_results = {
        1: 20,
        2: 400,
        3: 8902,
        4: 197281,
        5: 4865609,
    }
    all_correct = True
    print("-"*80)
    while depth < max(correct_results.keys()):
        start_time = time.time()
        depth += 1
        total_nodes_found = perft(depth, game_state)

        for correct_depth, correct_nodes in correct_results.items():
            if correct_depth == depth:
                if total_nodes_found == correct_nodes:
                    print(f"Depth {depth} results: {total_nodes_found:,} nodes generated in {time.time() - start_time:.2f} seconds. Correct!")
                    print("-"*80)
                else:
                    print(f"Depth {depth} results: {total_nodes_found:,} nodes generated in {time.time() - start_time:.2f} seconds. Incorrect!")
                    print(f"{correct_nodes:,} is the correct number of nodes.")
                    print("-"*80)
                    all_correct = False
    if all_correct:
        print("All depths tested correctly!")
    else:
        print("Some depths were incorrect.")
    exit()
