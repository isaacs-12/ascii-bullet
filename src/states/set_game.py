"""
Set card game implementation
"""

import pygame
import random
import time
from src.states.base_state import BaseState


class SetCard:
    """Represents a Set card"""
    
    def __init__(self, number, color, shape, shading):
        """
        Initialize a Set card
        
        Args:
            number: 1, 2, or 3
            color: 'red', 'green', or 'purple'
            shape: 'oval', 'squiggle', or 'diamond'
            shading: 'solid', 'striped', or 'open'
        """
        self.number = number
        self.color = color
        self.shape = shape
        self.shading = shading
        self.selected = False
    
    def __eq__(self, other):
        return (self.number == other.number and
                self.color == other.color and
                self.shape == other.shape and
                self.shading == other.shading)
    
    def __hash__(self):
        return hash((self.number, self.color, self.shape, self.shading))
    
    def get_ascii_art(self):
        """Get ASCII representation of the card using provided designs"""
        # Determine color code and border
        if self.color == 'red':
            color_code = (255, 100, 100)
            border_char = 'R'
        elif self.color == 'green':
            color_code = (100, 255, 100)
            border_char = 'G'
        else:  # purple
            color_code = (200, 100, 255)
            border_char = 'P'
        
        # Get the card art based on shape, number, and shading
        card_art = self._get_card_design()
        
        # Add color border
        lines = []
        top_border = f"+{border_char}{'='*9}{border_char}+"
        lines.append(top_border)
        for line in card_art:
            lines.append(line)
        lines.append(top_border)
        
        return lines, color_code
    
    def _get_card_design(self):
        """Get the card design based on shape, number, and shading"""
        if self.shape == 'diamond':
            if self.shading == 'open':
                if self.number == 1:
                    return [
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|     /\\    |",
                        "|    /  \\   |",
                        "|    \\  /   |",
                        "|     \\/    |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |"
                    ]
                elif self.number == 2:
                    return [
                        "|    /\\     |",
                        "|   /  \\    |",
                        "|   \\  /    |",
                        "|    \\/     |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|       /\\  |",
                        "|      /  \\ |",
                        "|      \\  / |",
                        "|       \\/  |"
                    ]
                else:  # 3
                    return [
                        "|    /\\      |",
                        "|   /  \\     |",
                        "|   \\  /     |",
                        "|    \\/      |",
                        "|      /\\    |",
                        "|     /  \\   |",
                        "|     \\  /   |",
                        "|      \\/    |",
                        "|        /\\  |",
                        "|       /  \\ |",
                        "|       \\  / |",
                        "|        \\/  |"
                    ]
            elif self.shading == 'solid':
                if self.number == 1:
                    return [
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|      /\\   |",
                        "|     /#x\\  |",
                        "|     \\x#/  |",
                        "|      \\/   |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |"
                    ]
                elif self.number == 2:
                    return [
                        "|    /\\     |",
                        "|   /#x\\    |",
                        "|   \\x#/    |",
                        "|    \\/     |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|       /\\  |",
                        "|      /#x\\ |",
                        "|      \\x#/ |",
                        "|       \\/  |"
                    ]
                else:  # 3
                    return [
                        "|   /\\       |",
                        "|  /#x\\      |",
                        "|  \\x#/      |",
                        "|   \\/       |",
                        "|      /\\    |",
                        "|     /#x\\   |",
                        "|     \\x#/   |",
                        "|      \\/    |",
                        "|        /\\  |",
                        "|       /#x\\ |",
                        "|       \\x#/ |",
                        "|        \\/  |"
                    ]
            else:  # striped/hashed
                if self.number == 1:
                    return [
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|     /\\    |",
                        "|    //\\\   |",
                        "|    \\\\//   |",
                        "|     \\/    |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |"
                    ]
                elif self.number == 2:
                    return [
                        "|   /\\      |",
                        "|  //\\\     |",
                        "|  \\\\//     |",
                        "|   \\/      |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|       /\\  |",
                        "|      //\\\ |",
                        "|      \\\\// |",
                        "|       \\/  |"
                    ]
                else:  # 3
                    return [
                        "|   /\\      |",
                        "|  //\\\     |",
                        "|  \\\\//     |",
                        "|   \\/      |",
                        "|     /\\    |",
                        "|    //\\\   |",
                        "|    \\\\//   |",
                        "|     \\/    |",
                        "|       /\\  |",
                        "|      //\\\ |",
                        "|      \\\\// |",
                        "|       \\/  |"
                    ]
        
        elif self.shape == 'squiggle':
            if self.shading == 'open':
                if self.number == 1:
                    return [
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|    oo     |",
                        "|  o0 0o0   |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |"
                    ]
                elif self.number == 2:
                    return [
                        "|    oo     |",
                        "|  o0 0o0   |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|    oo     |",
                        "|  o0 0o0   |",
                        "|           |",
                        "|           |"
                    ]
                else:  # 3
                    return [
                        "|    oo     |",
                        "|  o0 0o0   |",
                        "|           |",
                        "|           |",
                        "|    oo     |",
                        "|  o0 0o0   |",
                        "|           |",
                        "|           |",
                        "|    oo     |",
                        "|  o0 0o0   |",
                        "|           |",
                        "|           |"
                    ]
            elif self.shading == 'solid':
                if self.number == 1:
                    return [
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|    xx     |",
                        "|  xX XxX   |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |"
                    ]
                elif self.number == 2:
                    return [
                        "|    xx     |",
                        "|  xX XxX   |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|    xx     |",
                        "|  xX XxX   |",
                        "|           |",
                        "|           |"
                    ]
                else:  # 3
                    return [
                        "|    xx     |",
                        "|  xX XxX   |",
                        "|           |",
                        "|           |",
                        "|    xx     |",
                        "|  xX XxX   |",
                        "|           |",
                        "|           |",
                        "|    xx     |",
                        "|  xX XxX   |",
                        "|           |",
                        "|           |"
                    ]
            else:  # striped/hashed
                if self.number == 1:
                    return [
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|   //\\\    |",
                        "| /// \\\//  |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |"
                    ]
                elif self.number == 2:
                    return [
                        "|   //\\\    |",
                        "| /// \\\//  |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|   //\\\    |",
                        "| /// \\\//  |",
                        "|           |",
                        "|           |"
                    ]
                else:  # 3
                    return [
                        "|   //\\\    |",
                        "| /// \\\//  |",
                        "|           |",
                        "|           |",
                        "|   //\\\    |",
                        "| /// \\\//  |",
                        "|           |",
                        "|           |",
                        "|   //\\\    |",
                        "| /// \\\//  |",
                        "|           |",
                        "|           |"
                    ]
        
        else:  # oval
            if self.shading == 'open':
                if self.number == 1:
                    return [
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|     [  ]  |",
                        "|     [  ]  |",
                        "|     [  ]  |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |"
                    ]
                elif self.number == 2:
                    return [
                        "|   [  ]    |",
                        "|   [  ]    |",
                        "|   [  ]    |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|     [  ]  |",
                        "|     [  ]  |",
                        "|     [  ]  |",
                        "|           |"
                    ]
                else:  # 3
                    return [
                        "|   [  ]    |",
                        "|   [  ]    |",
                        "|   [  ]    |",
                        "|           |",
                        "|     [  ]  |",
                        "|     [  ]  |",
                        "|     [  ]  |",
                        "|           |",
                        "|       [  ]|",
                        "|       [  ]|",
                        "|       [  ]|",
                        "|           |"
                    ]
            elif self.shading == 'solid':
                if self.number == 1:
                    return [
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|     [##]  |",
                        "|     [##]  |",
                        "|     [##]  |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |"
                    ]
                elif self.number == 2:
                    return [
                        "|   [##]    |",
                        "|   [##]    |",
                        "|   [##]    |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|     [##]  |",
                        "|     [##]  |",
                        "|     [##]  |",
                        "|           |"
                    ]
                else:  # 3
                    return [
                        "|   [##]    |",
                        "|   [##]    |",
                        "|   [##]    |",
                        "|           |",
                        "|     [##]  |",
                        "|     [##]  |",
                        "|     [##]  |",
                        "|           |",
                        "|       [##]|",
                        "|       [##]|",
                        "|       [##]|",
                        "|           |"
                    ]
            else:  # striped/hashed
                if self.number == 1:
                    return [
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|    [//]   |",
                        "|    [//]   |",
                        "|    [//]   |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |"
                    ]
                elif self.number == 2:
                    return [
                        "|  [//]     |",
                        "|  [//]     |",
                        "|  [//]     |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|           |",
                        "|    [//]   |",
                        "|    [//]   |",
                        "|    [//]   |",
                        "|           |"
                    ]
                else:  # 3
                    return [
                        "|  [//]     |",
                        "|  [//]     |",
                        "|  [//]     |",
                        "|           |",
                        "|    [//]   |",
                        "|    [//]   |",
                        "|    [//]   |",
                        "|           |",
                        "|      [//] |",
                        "|      [//] |",
                        "|      [//] |",
                        "|           |"
                    ]
    
    def get_card_width(self):
        """Get card width from actual rendered art"""
        art, _ = self.get_ascii_art()
        if art:
            return len(art[0])  # Width is length of first line
        return 13
    
    def get_card_height(self):
        """Get card height from actual rendered art"""
        art, _ = self.get_ascii_art()
        return len(art)  # Height is number of lines
    
    def get_card_height(self):
        return 7


def is_set(card1, card2, card3):
    """Check if three cards form a valid Set"""
    # For each property, all must be same OR all must be different
    properties = [
        (card1.number, card2.number, card3.number),
        (card1.color, card2.color, card3.color),
        (card1.shape, card2.shape, card3.shape),
        (card1.shading, card2.shading, card3.shading),
    ]
    
    for prop in properties:
        # All same
        if prop[0] == prop[1] == prop[2]:
            continue
        # All different
        elif prop[0] != prop[1] and prop[1] != prop[2] and prop[0] != prop[2]:
            continue
        else:
            return False
    
    return True


def generate_deck():
    """Generate the full Set deck (81 cards)"""
    deck = []
    numbers = [1, 2, 3]
    colors = ['red', 'green', 'purple']
    shapes = ['oval', 'squiggle', 'diamond']
    shadings = ['solid', 'striped', 'open']
    
    for number in numbers:
        for color in colors:
            for shape in shapes:
                for shading in shadings:
                    deck.append(SetCard(number, color, shape, shading))
    
    random.shuffle(deck)
    return deck


def find_sets_on_board(board):
    """Find all valid sets on the board"""
    sets = []
    for i in range(len(board)):
        for j in range(i + 1, len(board)):
            for k in range(j + 1, len(board)):
                if is_set(board[i], board[j], board[k]):
                    sets.append((i, j, k))
    return sets


class SetGameState(BaseState):
    """Set card game state"""
    
    def __init__(self, game, previous_state):
        super().__init__(game)
        self.previous_state = previous_state
        
        # Game state
        self.deck = generate_deck()
        self.board = []
        self.selected_cards = []
        self.player_sets = 0
        self.computer_sets = 0
        self.game_over = False
        self.winner = None
        self.stats_recorded = False  # Track if stats have been recorded
        
        # Computer AI
        self.computer_difficulty = "normal"  # normal, easy, hard
        self.computer_timer = 0
        # Normal: 12-45 seconds, Hard: 5-25 seconds
        if self.computer_difficulty == "normal":
            self.computer_next_action_time = random.uniform(12.0, 45.0)
        elif self.computer_difficulty == "hard":
            self.computer_next_action_time = random.uniform(5.0, 25.0)
        else:  # easy
            self.computer_next_action_time = random.uniform(20.0, 60.0)
        
        # Deal initial 12 cards
        for _ in range(12):
            if self.deck:
                self.board.append(self.deck.pop())
        
        # Layout: 3 rows, 4 columns (or more if needed)
        self.cards_per_row = 4
        self.card_spacing_x = 18  # Increased to prevent overlap
        
        # Calculate spacing based on actual card size from board (after cards are dealt)
        if self.board:
            art, _ = self.board[0].get_ascii_art()
            actual_height = len(art)
            # Spacing should equal card height to prevent overlap
            self.card_spacing_y = actual_height
        else:
            self.card_spacing_y = 14  # Default fallback
        self.start_x = 1
        self.start_y = 2
    
    def enter(self):
        """Called when entering this state"""
        pass
    
    def exit(self):
        """Called when exiting this state"""
        pass
    
    def handle_events(self, events):
        """Handle input events"""
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # Return to terminal
                    self.game.change_state(self.previous_state, call_enter=False)
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    self._handle_click(event.pos)
    
    def _handle_click(self, pos):
        """Handle mouse click on board"""
        if self.game_over:
            return
        
        # Convert screen position to character grid position
        char_width = self.renderer.char_pixel_width
        char_height = self.renderer.char_pixel_height
        click_x = pos[0] // char_width
        click_y = pos[1] // char_height
        
        # Find which card was clicked - check in reverse order so topmost cards are checked first
        for i in range(len(self.board) - 1, -1, -1):
            card = self.board[i]
            row = i // self.cards_per_row
            col = i % self.cards_per_row
            
            card_x = self.start_x + col * self.card_spacing_x
            card_y = self.start_y + row * self.card_spacing_y
            
            # Get actual card dimensions from rendered art
            art, _ = card.get_ascii_art()
            card_width = len(art[0]) if art else 13
            card_height = len(art)
            
            # Use inclusive bounds on both ends to make the entire card clickable
            if (card_x <= click_x <= card_x + card_width - 1 and
                card_y <= click_y <= card_y + card_height - 1):
                
                # Toggle selection
                if i in self.selected_cards:
                    self.selected_cards.remove(i)
                    self.board[i].selected = False
                else:
                    if len(self.selected_cards) < 3:
                        self.selected_cards.append(i)
                        self.board[i].selected = True
                
                # Check if we have a set
                if len(self.selected_cards) == 3:
                    if self._check_and_remove_set():
                        self.player_sets += 1
                        self._replace_cards()
                    else:
                        # Invalid set - deselect
                        for idx in self.selected_cards:
                            if idx < len(self.board):
                                self.board[idx].selected = False
                        self.selected_cards = []
                
                # Break after finding the clicked card
                return
    
    def _check_and_remove_set(self):
        """Check if selected cards form a set and remove them if valid"""
        if len(self.selected_cards) != 3:
            return False
        
        idx1, idx2, idx3 = self.selected_cards
        card1 = self.board[idx1]
        card2 = self.board[idx2]
        card3 = self.board[idx3]
        
        if is_set(card1, card2, card3):
            # Remove cards (in reverse order to maintain indices)
            indices_to_remove = sorted(self.selected_cards, reverse=True)
            for idx in indices_to_remove:
                self.board.pop(idx)
            
            self.selected_cards = []
            return True
        
        return False
    
    def _replace_cards(self):
        """Replace removed cards from deck"""
        while len(self.board) < 12 and self.deck:
            self.board.append(self.deck.pop())
    
    def _computer_take_set(self):
        """Computer finds and takes a valid set"""
        sets = find_sets_on_board(self.board)
        if sets:
            # Pick a random set
            idx1, idx2, idx3 = random.choice(sets)
            
            # Remove cards
            indices_to_remove = sorted([idx1, idx2, idx3], reverse=True)
            for idx in indices_to_remove:
                self.board.pop(idx)
            
            self.computer_sets += 1
            self._replace_cards()
            return True
        return False
    
    def _check_game_over(self):
        """Check if game should end"""
        if self.game_over:
            return
        
        # Check if deck is empty and no sets exist
        sets = find_sets_on_board(self.board)
        if not self.deck and not sets:
            self.game_over = True
            if self.player_sets > self.computer_sets:
                self.winner = "player"
            elif self.computer_sets > self.player_sets:
                self.winner = "computer"
            else:
                self.winner = "tie"
            
            # Record stats (only once)
            if not self.stats_recorded:
                self.stats_recorded = True
                won = (self.winner == "player")
                self.game.save_system.record_set_game(
                    self.player_sets,
                    self.computer_sets,
                    won
                )
            return
        
        # If no sets, add 3 more cards
        if not sets and self.deck:
            for _ in range(3):
                if self.deck:
                    self.board.append(self.deck.pop())
    
    def update(self, dt):
        """Update game logic"""
        if self.game_over:
            return
        
        dt_seconds = dt / 1000.0
        
        # Update computer timer
        self.computer_timer += dt_seconds
        if self.computer_timer >= self.computer_next_action_time:
            self.computer_timer = 0
            # Normal: 12-45 seconds, Hard: 5-25 seconds
            if self.computer_difficulty == "normal":
                self.computer_next_action_time = random.uniform(12.0, 45.0)
            elif self.computer_difficulty == "hard":
                self.computer_next_action_time = random.uniform(5.0, 25.0)
            else:  # easy
                self.computer_next_action_time = random.uniform(20.0, 60.0)
            
            # Computer tries to take a set
            if self._computer_take_set():
                # Clear player selection if computer took cards
                for idx in self.selected_cards:
                    if idx < len(self.board):
                        self.board[idx].selected = False
                self.selected_cards = []
        
        # Check game over conditions
        self._check_game_over()
    
    def render(self):
        """Render the game"""
        self.renderer.clear()
        
        # Title
        self.renderer.write_centered(0, "SET", (255, 255, 0))
        
        # Score
        score_text = f"Player: {self.player_sets}  |  Computer: {self.computer_sets}  |  Deck: {len(self.deck)}"
        self.renderer.write_centered(1, score_text, (200, 200, 200))
        
        # Draw board
        for i, card in enumerate(self.board):
            row = i // self.cards_per_row
            col = i % self.cards_per_row
            
            x = self.start_x + col * self.card_spacing_x
            y = self.start_y + row * self.card_spacing_y
            
            art, color = card.get_ascii_art()
            
            # Get actual dimensions from the art
            card_width = len(art[0]) if art else 13
            card_height = len(art)
            
            # Highlight if selected
            if card.selected:
                # Draw selection box using actual art dimensions
                for dy in range(card_height):
                    self.renderer.write(x - 1, y + dy, "|", (255, 255, 0))
                    self.renderer.write(x + card_width, y + dy, "|", (255, 255, 0))
                for dx in range(card_width + 2):
                    self.renderer.write(x - 1 + dx, y - 1, "-", (255, 255, 0))
                    self.renderer.write(x - 1 + dx, y + card_height, "-", (255, 255, 0))
            
            # Draw card
            for line_idx, line in enumerate(art):
                self.renderer.write(x, y + line_idx, line, color)
        
        # Instructions
        if not self.game_over:
            self.renderer.write(2, self.renderer.char_height - 3, 
                              "Click cards to select (3 for a set)", (150, 150, 150))
            self.renderer.write(2, self.renderer.char_height - 2, 
                              "Press ESC to quit", (150, 150, 150))
        else:
            # Game over message
            if self.winner == "player":
                self.renderer.write_centered(self.renderer.char_height // 2, 
                                           "YOU WIN!", (0, 255, 0))
            elif self.winner == "computer":
                self.renderer.write_centered(self.renderer.char_height // 2, 
                                           "COMPUTER WINS!", (255, 0, 0))
            else:
                self.renderer.write_centered(self.renderer.char_height // 2, 
                                           "TIE GAME!", (255, 255, 0))
            
            self.renderer.write_centered(self.renderer.char_height // 2 + 2, 
                                        f"Final Score: Player {self.player_sets} - Computer {self.computer_sets}", 
                                        (200, 200, 200))
            self.renderer.write_centered(self.renderer.char_height - 2, 
                                        "Press ESC to return to terminal", (150, 150, 150))
        
        self.renderer.render()

