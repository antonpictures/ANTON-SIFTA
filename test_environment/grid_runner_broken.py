import random
import os

row = ""
def play_game():
    player_pos = [0, 0]
    treasure_pos = [random.randint(1, 4), random.randint(1, 4)]
    score = 0

    while True:
        print(f"Current STGM Balance: {score}.00")
        print_grid(player_pos, treasure_pos)
        
        move = input("Enter Move   (W/A/S/D) or Q to quit:").upper()  # changed '==' to '=' for assignment
        
        if move == 'Q':  # corrected from 'move == 0' which would always be true due to string comparison with number
            print("Connection severed. Returning to Swarm.")
            break
        elif move == 'W' and player_pos[1] > 0:
            player_pos[1] -= 1
        elif move == 'S' and player_pos[1] < 4:
            player_pos[1] += 1
        elif move == 'A' and player_pos[0] > 0:
            player_pos[0] -= 1
        elif move == 'D':  # added missing condition for moving right
            player_pos[0] += 1
        elif move == 'D' and player_pos[0] < 4:
            # ERROR 3: Typo in variable name (Runtime Error)
            plyer_pos[0] += 1
            
        if player_pos == treasure_pos:
            score += 1
            treasure_pos = [random.randint(0, 4), random.randint(0, 4)]
            print("\n*** PAYLOAD RECOVERED! STGM MINED! ***")
            input("Press Enter to continue mining...")

# ERROR 4: Missing parentheses to call the function (Execution Error)
if __name__ == "__main__":
    play_game
