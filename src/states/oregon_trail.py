"""Oregon Trail game state"""

import random
import time
import pygame
from src.states.base_state import BaseState


class OregonTrailState(BaseState):
    """Oregon Trail game state"""
    
    def __init__(self, game, previous_state):
        super().__init__(game)
        self.previous_state = previous_state
        
        # Game state variables
        self.m = 0      # Total mileage
        self.m2 = 0     # Previous mileage
        self.t = 700    # Cash
        self.a = 0      # Animals (Oxen)
        self.f = 0      # Food
        self.b = 0      # Ammo
        self.c = 0      # Clothing
        self.m1 = 0     # Misc Supplies
        self.d3 = 0     # Turn counter
        self.s4 = 0     # Illness flag
        self.k8 = 0     # Injury flag
        self.f1 = 0     # South Pass flag
        self.f2 = 0     # Blue Mountains flag
        self.m9 = 0     # Mileage flag
        self.x1 = -1    # Fort flag
        self.d9 = 5     # Shooting skill (default)
        self.e = 2      # Eating level (default moderate)
        
        # State machine
        self.phase = "instructions"  # instructions, shooting_skill, purchases, main_game, shooting_mini, game_over, victory
        self.input_buffer = ""
        self.messages = []
        self.waiting_for_input = True
        
        # Shooting mini-game
        self.shooting_target = None
        self.shooting_start_time = None
        self.shooting_result = None
        
        # Fort purchases
        self.fort_purchasing = None  # "food", "ammo", "cloth", "misc", None
        
        # Event handling
        self.current_event = None
        self.event_choice = None
        
        self.dates = [
        "APRIL 12", "APRIL 26", "MAY 10", "MAY 24", "JUNE 7", "JUNE 21",
        "JULY 5", "JULY 19", "AUGUST 2", "AUGUST 16", "AUGUST 31",
        "SEPTEMBER 13", "SEPTEMBER 27", "OCTOBER 11", "OCTOBER 25",
        "NOVEMBER 8", "NOVEMBER 22", "DECEMBER 6", "DECEMBER 20"
    ]

        self.game_start_time = time.time()
    
    def enter(self):
        """Called when entering this state"""
        # Ensure all attributes are initialized
        self.messages = ["DO YOU NEED INSTRUCTIONS (YES/NO)?"]
        self.waiting_for_input = True
        self.input_buffer = ""
        self.phase = "instructions"
    
    def exit(self):
        """Called when exiting this state"""
        # Track playtime
        playtime_seconds = time.time() - self.game_start_time
        self.game.save_system.add_playtime(playtime_seconds, "total")
    
    def _add_message(self, msg):
        """Add a message to display"""
        self.messages.append(msg)
        # Keep only last 20 messages for display
        if len(self.messages) > 20:
            self.messages = self.messages[-20:]
    
    def _shooting_subroutine(self, d9):
        """Handle shooting mini-game"""
        words = ["BANG", "BLAM", "POW", "WHAM"]
        self.shooting_target = random.choice(words)
        self.shooting_start_time = time.time()
        self.phase = "shooting_mini"
        self.waiting_for_input = True
        self.input_buffer = ""
        self._add_message(f"TYPE {self.shooting_target}")
    
    def _process_shooting_result(self):
        """Process shooting mini-game result"""
        if not self.shooting_start_time:
            return 9
        
        duration = time.time() - self.shooting_start_time
        b1 = (duration * 2) - (self.d9 - 1)
        
        if self.input_buffer.upper().strip() != self.shooting_target:
            b1 = 9
        
        self.shooting_start_time = None
        self.shooting_target = None
        self.phase = "main_game"  # Return to main game phase
        self.input_buffer = ""
        return b1
    
    def _process_main_turn(self):
        """Process one turn of the main game loop"""
        # Date Logic
        if self.d3 >= len(self.dates):
            self._add_message("YOU HAVE BEEN ON THE TRAIL TOO LONG.")
            self._add_message("YOUR FAMILY DIES IN THE FIRST BLIZZARD OF WINTER.")
            self.phase = "game_over"
            return

        current_date = self.dates[self.d3]
        self._add_message(f"MONDAY {current_date} 1847")
        
        # Check Supplies
        if self.f < 0: self.f = 0
        if self.b < 0: self.b = 0
        if self.c < 0: self.c = 0
        if self.m1 < 0: self.m1 = 0
        
        if self.f < 13:
            self._add_message("YOU'D BETTER DO SOME HUNTING OR BUY FOOD SOON!!!!")
            
        # Doctor's Bills
        if self.s4 == 1 or self.k8 == 1:
            self.t -= 20
            if self.t < 0:
                self._add_message("YOU CAN'T AFFORD A DOCTOR. YOU DIED.")
                self.phase = "game_over"
                return
            self._add_message("DOCTOR'S BILL IS $20")
            self.s4 = 0
            self.k8 = 0
        
        if self.m9 == 1:
            self._add_message(f"TOTAL MILEAGE: 950")
            self.m9 = 0
        else:
            self._add_message(f"TOTAL MILEAGE: {int(self.m)}")
        
        self._add_message(f"FOOD: {int(self.f)}, AMMO: {int(self.b)}, CLOTHING: {int(self.c)}, MISC: {int(self.m1)}, CASH: ${int(self.t)}")
        
        # Turn Options
        if self.x1 == -1:  # No Fort available
            self._add_message("DO YOU WANT TO (1) HUNT, OR (2) CONTINUE")
            self.waiting_for_input = True
            self.input_buffer = ""
        else:
            self._add_message("DO YOU WANT TO (1) STOP AT THE NEXT FORT, (2) HUNT, OR (3) CONTINUE")
            self.waiting_for_input = True
            self.input_buffer = ""
    
    def _process_turn_choice(self, choice):
        """Process the player's turn choice"""
        if self.x1 == -1:  # No fort
            x = 2 if choice == "1" else 3
            if x == 2 and self.b < 40:
                self._add_message("TOUGH---YOU NEED MORE BULLETS TO GO HUNTING")
                x = 3
        else:
            if choice == "1": x = 1
            elif choice == "2": x = 2
            else: x = 3
            
        self.x1 *= -1  # Toggle fort availability
        
        if x == 1:  # Fort
            self._add_message("ENTER WHAT YOU WISH TO SPEND:")
            self.fort_purchasing = "food"
            self._add_message("FOOD: ")
            self.waiting_for_input = True
            self.input_buffer = ""
        elif x == 2:  # Hunting
            self.m -= 45
            self._shooting_subroutine(self.d9)
            return  # Will continue after shooting
        else:  # Continue
            self._process_continue()
    
    def _process_fort_purchase(self, value):
        """Process fort purchase input"""
        try:
            val = int(value)
            if self.fort_purchasing == "food":
                if val <= self.t:
                    self.t -= val
                    self.f += int(val * 0.66)
                self.fort_purchasing = "ammo"
                self._add_message(f"AMMO: ")
                self.input_buffer = ""
            elif self.fort_purchasing == "ammo":
                if val <= self.t:
                    self.t -= val
                    self.b += int(val * 0.66 * 50)
                self.fort_purchasing = "cloth"
                self._add_message(f"CLOTHING: ")
                self.input_buffer = ""
            elif self.fort_purchasing == "cloth":
                if val <= self.t:
                    self.t -= val
                    self.c += int(val * 0.66)
                self.fort_purchasing = "misc"
                self._add_message(f"MISC: ")
                self.input_buffer = ""
            elif self.fort_purchasing == "misc":
                if val <= self.t:
                    self.t -= val
                    self.m1 += int(val * 0.66)
                self.m -= 45
                self.fort_purchasing = None
                self._process_continue()
        except ValueError:
            self._add_message("INVALID INPUT. TRY AGAIN.")
    
    def _process_hunting_result(self):
        """Process hunting result after shooting"""
        b1 = self._process_shooting_result()
        if b1 <= 1:
            self._add_message("RIGHT BETWEEN THE EYES---YOU GOT A BIG ONE!!!!")
            self.f += 52 + random.random() * 6
            self.b -= int(10 + random.random() * 4)
        elif 100 * random.random() < 13 * b1:
            self._add_message("YOU MISSED---AND YOUR DINNER GOT AWAY.....")
        else:
            self._add_message("NICE SHOT--RIGHT ON TARGET--GOOD EATIN' TONIGHT!!")
            self.f += 48 - 2 * b1
            self.b -= int(10 + 3 * b1)
        
        self._process_continue()
    
    def _process_continue(self):
        """Continue with eating and movement"""
        self._add_message("DO YOU WANT TO EAT (1) POORLY (2) MODERATELY (3) WELL?")
        self.waiting_for_input = True
        self.input_buffer = ""
        self.phase = "eating"
    
    def _continue_after_events(self):
        """Continue to next turn after events are processed"""
        # Next turn
        self.d3 += 1
        if self.m >= 2040:
            self._add_message("YOU FINALLY ARRIVED AT OREGON CITY!")
            self._add_message("AFTER 2040 LONG MILES---HOORAY!!!!!")
            self._add_message("PRESIDENT JAMES K. POLK SENDS HIS CONGRATULATIONS!")
            self.phase = "victory"
        else:
            self._process_main_turn()
    
    def _process_eating_choice(self, choice):
        """Process eating choice"""
        try:
            e = int(choice)
            if 1 <= e <= 3:
                self.e = e
                self.f -= (8 + 5 * e)
                if self.f < 0:
                    self._add_message("YOU RAN OUT OF FOOD AND STARVED TO DEATH.")
                    self.phase = "game_over"
                    return
                
                # Movement
                self.m2 = self.m
                self.m += 200 + (self.a - 220) / 5 + 10 * random.random()
                
                # Process random events
                self._process_random_events()
                
                # If no event is waiting for input, continue to next turn
                if not self.current_event:
                    self._continue_after_events()
        except ValueError:
            self._add_message("INVALID INPUT. ENTER 1, 2, OR 3.")
    
    def _process_random_events(self):
        """Process random events that can occur"""
        # Riders Attack
        if random.random() * 10 < ((self.m/100-4)**2 + 72) / ((self.m/100-4)**2 + 12) - 1:
            hostile = random.random() < 0.8
            if hostile:
                self._add_message("RIDERS AHEAD! THEY LOOK HOSTILE.")
            else:
                self._add_message("RIDERS AHEAD! THEY DON'T LOOK HOSTILE.")
            
            self._add_message("TACTICS: (1) RUN (2) ATTACK (3) CONTINUE (4) CIRCLE WAGONS")
            self.current_event = "riders"
            self.event_choice = None
            self.waiting_for_input = True
            self.input_buffer = ""
            return
        
        # Random Turn Events
        r1 = 100 * random.random()
        if r1 < 6:
            self._add_message("WAGON BREAKS DOWN--LOSE TIME AND SUPPLIES")
            self.m -= 15 + 5 * random.random()
            self.m1 -= 8
        elif r1 < 11:
            self._add_message("OX INJURES LEG")
            self.m -= 25
            self.a -= 20
        elif r1 < 13:
            self._add_message("DAUGHTER BROKE HER ARM")
            self.m -= 5 + 4 * random.random()
            self.m1 -= 3
        elif r1 < 15:
            self._add_message("OX WANDERS OFF")
            self.m -= 17
        elif r1 < 17:
            self._add_message("SON GETS LOST")
            self.m -= 10
        elif r1 < 22:
            self._add_message("UNSAFE WATER")
            self.m -= 10 * random.random() + 2
        elif r1 < 32:
            if self.m <= 950:
                self._add_message("HEAVY RAINS")
                self.f -= 10
                self.b -= 500
                self.m1 -= 15
                self.m -= 10 * random.random() + 5
        elif r1 < 35:
            self._add_message("BANDITS ATTACK")
            self._shooting_subroutine(self.d9)
            self.current_event = "bandits"
            return  # Will continue after shooting
        elif r1 < 37:
            self._add_message("FIRE IN WAGON")
            self.f -= 40
            self.b -= 400
            self.m1 -= random.random() * 8 + 3
            self.m -= 15
        elif r1 < 42:
            self._add_message("HEAVY FOG")
            self.m -= 10 + 5 * random.random()
        elif r1 < 44:
            self._add_message("SNAKEBITE!")
            self.b -= 10
            self.m1 -= 5
            if self.m1 < 0:
                self._add_message("YOU DIED OF SNAKEBITE.")
                self.phase = "game_over"
                return
        elif r1 < 54:
            self._add_message("SWAMPED FORDING RIVER")
            self.f -= 30
            self.c -= 20
            self.m -= 20 + 20 * random.random()
        elif r1 < 64:
            self._add_message("WILD ANIMALS!")
            self._shooting_subroutine(self.d9)
            self.current_event = "animals"
            return  # Will continue after shooting
        elif r1 < 69:
            self._add_message("HAIL STORM")
            self.m -= 5 + random.random() * 10
            self.b -= 200
            self.m1 -= 4 + random.random() * 3
        elif r1 < 95:
            # Illness Logic
            if 100 * random.random() < 10 + 35 * (self.e - 1):
                self._add_message("MILD ILLNESS---MEDICINE USED")
                self.m -= 5
                self.m1 -= 2
            elif 100 * random.random() < 100 - (40 / 4**(self.e-1)):
                self._add_message("BAD ILLNESS---MEDICINE USED")
                self.m -= 5
                self.m1 -= 5
            else:
                self._add_message("SERIOUS ILLNESS---STOP FOR MEDICAL ATTENTION")
                self.m1 -= 10
                self.s4 = 1
            if self.m1 < 0:
                self._add_message("YOU DIED OF ILLNESS.")
                self.phase = "game_over"
                return
        
        # Mountains
        if self.m > 950:
            if random.random() * 10 > 9 - ((self.m/100-15)**2+72)/((self.m/100-15)**2+12):
                self._add_message("RUGGED MOUNTAINS")
                if random.random() < 0.1:
                    self._add_message("GOT LOST")
                    self.m -= 60
                elif random.random() < 0.11:
                    self._add_message("WAGON DAMAGED")
                    self.m1 -= 5
                    self.b -= 200
                    self.m -= 20 + 30 * random.random()
                else:
                    self._add_message("THE GOING GETS SLOW")
                    self.m -= 45 + random.random() / 0.02
            
            # South Pass/Blizzard Logic
            if self.f1 == 0:
                self.f1 = 1
                if random.random() > 0.8:
                    self._add_message("BLIZZARD IN MOUNTAIN PASS")
                    self.f -= 25
                    self.m1 -= 10
                    self.b -= 300
                    self.m -= 30 + 40 * random.random()
                    if self.c < 18 + 2 * random.random():
                        self._add_message("YOU FROZE TO DEATH.")
                        self.phase = "game_over"
                        return
    
    def _process_event_choice(self, choice):
        """Process choice for current event"""
        if self.current_event == "riders":
            try:
                t1 = int(choice)
                hostile = random.random() < 0.8
                if random.random() < 0.2:
                    hostile = not hostile
                
                if hostile:
                    if t1 == 1:  # Run
                        self.m += 20
                        self.b -= 150
                        self.m1 -= 15
                        self.a -= 40
                    elif t1 == 2:  # Attack
                        self._shooting_subroutine(self.d9)
                        self.current_event = "riders_attack"
                        return
                    elif t1 == 3:  # Continue
                        if random.random() > 0.8:
                            self._add_message("THEY DID NOT ATTACK")
                        else:
                            self.b -= 150
                            self.m1 -= 15
                    else:  # Circle
                        self._shooting_subroutine(self.d9)
                        self.current_event = "riders_circle"
                        return
                else:  # Friendly
                    if t1 == 1:
                        self.m += 15
                        self.a -= 10
                    elif t1 == 2:
                        self.m -= 5
                        self.b -= 100
                    elif t1 == 4:
                        self.m -= 20
                    self._add_message("THEY WERE FRIENDLY.")
                
                self.current_event = None
                # Continue to next turn after processing riders
                self._continue_after_events()
            except ValueError:
                self._add_message("INVALID INPUT. ENTER 1-4.")
                return
        
        elif self.current_event == "riders_attack":
            # Shooting result already processed, just apply effects
            if hasattr(self, '_last_shooting_result'):
                b1 = self._last_shooting_result
                self.b -= b1 * 40 + 80
                if b1 <= 1:
                    self._add_message("NICE SHOOTING---YOU DROVE THEM OFF")
                elif b1 > 4:
                    self._add_message("LOUSY SHOT---YOU GOT KNIFED")
                    self.k8 = 1
                else:
                    self._add_message("KINDA SLOW WITH YOUR COLT .45")
                delattr(self, '_last_shooting_result')
            self.current_event = None
            self._continue_after_events()
        
        elif self.current_event == "riders_circle":
            if hasattr(self, '_last_shooting_result'):
                b1 = self._last_shooting_result
                self.b -= b1 * 30 + 80
                self.m -= 25
                delattr(self, '_last_shooting_result')
            self.current_event = None
            self._continue_after_events()
        
        elif self.current_event == "bandits":
            if hasattr(self, '_last_shooting_result'):
                b1 = self._last_shooting_result
                self.b -= 20 * b1
                if self.b < 0:
                    self._add_message("YOU RAN OUT OF AMMO, THEY TOOK YOUR CASH")
                    self.t = int(self.t / 3)
                elif b1 > 1:
                    self._add_message("SHOT IN THE LEG, THEY TOOK AN OX")
                    self.k8 = 1
                    self.a -= 20
                else:
                    self._add_message("QUICKEST DRAW IN THE WEST! YOU GOT 'EM.")
                delattr(self, '_last_shooting_result')
            self.current_event = None
            self._continue_after_events()
        
        elif self.current_event == "animals":
            if hasattr(self, '_last_shooting_result'):
                b1 = self._last_shooting_result
                if self.b < 40:
                    self._add_message("TOO LOW ON AMMO, WOLVES OVERPOWERED YOU")
                    self.phase = "game_over"
                    return
                if b1 > 2:
                    self._add_message("SLOW DRAW---THEY GOT FOOD AND CLOTHES")
                    self.c -= b1 * 4
                    self.f -= b1 * 8
                else:
                    self._add_message("NICE SHOOTIN' PARTNER.")
                self.b -= 20 * b1
                delattr(self, '_last_shooting_result')
            self.current_event = None
            self._continue_after_events()
    
    def handle_events(self, events):
        """Handle pygame events"""
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # Return to main menu
                    if self.phase in ["game_over", "victory"]:
                        self.game.change_state(self.previous_state)
                    elif self.phase == "shooting_mini":
                        # Can't escape during shooting
                        pass
                    else:
                        # Ask for confirmation
                        self._add_message("PRESS ESC AGAIN TO QUIT")
                elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    if self.waiting_for_input:
                        if self.phase == "instructions":
                            response = self.input_buffer.upper().strip()
                            if response == "YES":
                                self._add_message("")
                                self._add_message("THIS PROGRAM SIMULATES A TRIP OVER THE OREGON TRAIL FROM")
                                self._add_message("INDEPENDENCE, MISSOURI TO OREGON CITY, OREGON IN 1847.")
                                self._add_message("YOUR FAMILY OF FIVE WILL COVER THE 2040 MILE OREGON TRAIL")
                                self._add_message("IN 5-6 MONTHS --- IF YOU MAKE IT ALIVE.")
                                self._add_message("")
                                self._add_message("YOU HAD SAVED $900 TO SPEND. $200 FOR A WAGON.")
                                self._add_message("SPEND THE REST ON OXEN, FOOD, AMMO, CLOTHING, AND SUPPLIES.")
                                self._add_message("GOOD LUCK!!!")
                                self._add_message("")
                            # Move to shooting skill selection regardless of answer
                            self.phase = "shooting_skill"
                            self._add_message("HOW GOOD A SHOT ARE YOU?")
                            self._add_message("(1) ACE MARKSMAN, (2) GOOD SHOT, (3) FAIR TO MIDDLIN'")
                            self._add_message("(4) NEED MORE PRACTICE, (5) SHAKY KNEES")
                            self._add_message("ENTER 1-5: ")
                            self.input_buffer = ""
                            self.waiting_for_input = True
                        elif self.phase == "shooting_skill":
                            try:
                                self.d9 = int(self.input_buffer)
                                if not (1 <= self.d9 <= 5):
                                    self.d9 = 5
                            except:
                                self.d9 = 5
                            self.phase = "purchases"
                            self._add_message("")
                            self._add_message("INITIAL PURCHASES:")
                            self._add_message("HOW MUCH ON OXEN? ")
                            self.input_buffer = ""
                        elif self.phase == "purchases":
                            if not hasattr(self, 'purchase_step'):
                                self.purchase_step = 0
                            
                            try:
                                val = int(self.input_buffer)
                                if self.purchase_step == 0:  # Oxen
                                    if val < 200:
                                        self._add_message("NOT ENOUGH")
                                        self.input_buffer = ""
                                        return
                                    if val > 300:
                                        self._add_message("TOO MUCH")
                                        self.input_buffer = ""
                                        return
                                    self.a = val
                                    self.purchase_step = 1
                                    self._add_message("HOW MUCH ON FOOD? ")
                                    self.input_buffer = ""
                                elif self.purchase_step == 1:  # Food
                                    self.f = val
                                    self.purchase_step = 2
                                    self._add_message("HOW MUCH ON AMMUNITION? ")
                                    self.input_buffer = ""
                                elif self.purchase_step == 2:  # Ammo
                                    self.b = val
                                    self.purchase_step = 3
                                    self._add_message("HOW MUCH ON CLOTHING? ")
                                    self.input_buffer = ""
                                elif self.purchase_step == 3:  # Clothing
                                    self.c = val
                                    self.purchase_step = 4
                                    self._add_message("HOW MUCH ON MISC. SUPPLIES? ")
                                    self.input_buffer = ""
                                elif self.purchase_step == 4:  # Misc
                                    self.m1 = val
                                    self.t = 700 - self.a - self.f - self.b - self.c - self.m1
                                    if self.t < 0:
                                        self._add_message("YOU OVERSPENT! YOU ONLY HAD $700. BUY AGAIN.")
                                        self.purchase_step = 0
                                        self._add_message("HOW MUCH ON OXEN? ")
                                        self.input_buffer = ""
                                        return
                                    self.b = 50 * self.b  # $1 buys 50 bullets
                                    self._add_message(f"AFTER PURCHASES, YOU HAVE ${int(self.t)} LEFT.")
                                    self.phase = "main_game"
                                    delattr(self, 'purchase_step')
                                    self._process_main_turn()
                            except ValueError:
                                self._add_message("INVALID INPUT. TRY AGAIN.")
                                self.input_buffer = ""
                        elif self.phase == "main_game":
                            if self.fort_purchasing:
                                self._process_fort_purchase(self.input_buffer)
                            elif self.current_event:
                                self._process_event_choice(self.input_buffer)
                            else:
                                self._process_turn_choice(self.input_buffer)
                        elif self.phase == "shooting_mini":
                            if self.current_event in ["riders_attack", "riders_circle", "bandits", "animals"]:
                                # Process shooting result for event
                                b1 = self._process_shooting_result()
                                self._last_shooting_result = b1
                                self._process_event_choice("")  # Process the event with shooting result
                            else:
                                # Regular hunting
                                self._process_hunting_result()
                        elif self.phase == "eating":
                            self._process_eating_choice(self.input_buffer)
                        elif self.phase in ["game_over", "victory"]:
                            self.game.change_state(self.previous_state)
                elif event.key == pygame.K_BACKSPACE:
                    if self.waiting_for_input and len(self.input_buffer) > 0:
                        self.input_buffer = self.input_buffer[:-1]
                elif event.unicode and self.waiting_for_input:
                    if self.phase == "shooting_mini":
                        # For shooting, only accept the target word
                        if event.unicode.isalnum() or event.unicode in "!@#$%^&*()":
                            self.input_buffer += event.unicode.upper()
                    else:
                        # Regular input
                        if event.unicode.isprintable():
                            self.input_buffer += event.unicode
    
    def update(self, dt):
        """Update game logic"""
        pass
    
    def render(self):
        """Render the game state"""
        try:
            self.renderer.clear()
            
            # Ensure messages list exists and has at least one message
            if not hasattr(self, 'messages') or not self.messages:
                self.messages = ["DO YOU NEED INSTRUCTIONS (YES/NO)?"]
            
            # Ensure other attributes exist
            if not hasattr(self, 'waiting_for_input'):
                self.waiting_for_input = True
            if not hasattr(self, 'input_buffer'):
                self.input_buffer = ""
            if not hasattr(self, 'phase'):
                self.phase = "instructions"
                if not self.messages:
                    self.messages = ["DO YOU NEED INSTRUCTIONS (YES/NO)?"]
            
            # Display messages (last 20 lines)
            y = 1
            for msg in self.messages[-20:]:
                if msg:  # Only render non-empty messages
                    # Truncate long messages to fit screen
                    max_width = getattr(self.renderer, 'char_width', 80) - 2
                    if len(msg) > max_width:
                        msg = msg[:max_width]
                    self.renderer.write(1, y, msg, self.renderer.COLORS['fg'])
                    y += 1
            
            # Display current input prompt and buffer
            if self.waiting_for_input:
                if self.phase == "shooting_mini" and hasattr(self, 'shooting_target') and self.shooting_target:
                    # Show shooting target prominently
                    prompt = f"TYPE: {self.shooting_target}"
                    self.renderer.write(1, y, prompt, self.renderer.COLORS['title'])
                    y += 1
                    if self.input_buffer:
                        self.renderer.write(1, y, self.input_buffer, self.renderer.COLORS['fg'])
                    else:
                        self.renderer.write(1, y, "_", self.renderer.COLORS['fg'])
                else:
                    # Show input buffer with cursor - always show cursor to indicate input is expected
                    input_line = self.input_buffer + "_" if self.input_buffer else "_"
                    self.renderer.write(1, y, input_line, self.renderer.COLORS['menu_selected'])
            
            # Show status at bottom
            if self.phase == "main_game" and self.m > 0:
                status_y = self.renderer.char_height - 3
                self.renderer.write(1, status_y, f"MILEAGE: {int(self.m)}/2040", self.renderer.COLORS['menu_normal'])
                status_y += 1
                self.renderer.write(1, status_y, f"FOOD: {int(self.f)}  AMMO: {int(self.b)}  CASH: ${int(self.t)}", self.renderer.COLORS['menu_normal'])
            
            # Instructions at bottom
            if self.phase not in ["game_over", "victory"]:
                help_y = self.renderer.char_height - 1
                if self.phase == "shooting_mini":
                    self.renderer.write(1, help_y, "Type the word shown above, then press ENTER", self.renderer.COLORS['menu_normal'])
                else:
                    self.renderer.write(1, help_y, "Press ESC to quit", self.renderer.COLORS['menu_normal'])
            
            # Actually render the frame
            self.renderer.render()
        except Exception as e:
            # Fallback rendering if something goes wrong
            self.renderer.clear()
            self.renderer.write(1, 1, f"Error in Oregon Trail: {str(e)}", self.renderer.COLORS['fg'])
            self.renderer.write(1, 2, "Press ESC to return to menu", self.renderer.COLORS['fg'])
            self.renderer.render()
