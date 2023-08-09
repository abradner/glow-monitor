# This library exposes three methods: draw, _set and show.
# We will be rendering a virtual piglow to the screen using python's graphics library
# the piglow has 18 LEDs, 3 each of red, orange, yellow, green, blue, and white
# when we call draw, we will be rendering a virtual piglow to the screen with the leds in off state
# when we call _set, we will be setting the value of a virtual LED 0-255 but not rendering it
# when we call show, we will be updating the on-screen virtual piglow with the updated values

import pygame
import math
from time import sleep

# Constants for the virtual PiGlow
LED_RADIUS = 10
ARC_RADIUS = 100
ARC_COUNT = 3
LED_COUNT_PER_ARC = 6

_live_values = [0] * 18
_buffer_values = [0] * 18

_led_pins = [] + [
    #r  o   y   g   b   w
    6,  7,  8,  5,  4,  9,
    17, 16, 15, 13, 11, 10,
    0,  1,  2,  3,  14, 12,
]

positions = None

screen = None
running = True

WIDTH = 320
HEIGHT = 240
CENTRE_X = WIDTH / 2
CENTRE_Y = HEIGHT / 2

iteration = 0

WHITE = (255, 255, 255)
BLUE = (0, 0, 255)
GREEN = (0, 128, 0)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
RED = (255, 0, 0)

colours = [WHITE, BLUE, GREEN, YELLOW, ORANGE, RED]


# def _calculate_led_positions():
#     positions = []
#     arc_length = 120  # Degrees for each arc
#     led_count_per_arc = 6
#     max_radius = 100  # The maximum distance from the center to the LEDs; you can adjust this
#     center_x, center_y = WIDTH // 2, HEIGHT // 2

#     # Iterate over the three arcs
#     for arc in range(3):
#         # Iterate over the LEDs in each arc, starting from 1 to leave space for the imaginary 0th LED
#         for led in range(1, led_count_per_arc + 1):
#             # Calculate the current radius based on the position of the LED along the arc
#             radius = max_radius * led / (led_count_per_arc + 1)
#             # Calculate angle in radians
#             angle = math.radians(arc * arc_length)
#             # Calculate x and y using polar coordinates
#             x = center_x + radius * math.cos(angle)
#             y = center_y + radius * math.sin(angle)
#             positions.append((x, y))
#     return positions

import math

def _calculate_led_positions():
    positions = []
    arc_length = 120  # Degrees for each arc
    led_count_per_arc = 6
    radius = 100  # The radius of the original circle
    center_x, center_y = WIDTH // 2, HEIGHT // 2
    curvature_factor = 1.5    # Adjust this value to control the curvature

    # Iterate over the three arcs
    for arc in range(3):
        # Determine the starting angle of the arc
        angle = arc * arc_length
        
        # Determine the start (center) and end points of the arc
        start_x, start_y = center_x, center_y
        end_x = center_x + radius * math.cos(math.radians(angle))
        end_y = center_y + radius * math.sin(math.radians(angle))
        
        # Calculate the control point
        control_x = (start_x + end_x) / 2 + curvature_factor * (end_y - start_y) / 2
        control_y = (start_y + end_y) / 2 - curvature_factor * (end_x - start_x) / 2

        # Iterate over the LEDs in each arc, determining their positions along the curve
        for led in range(led_count_per_arc):
            t = (led + 1) / (led_count_per_arc + 1)  # Parameter for the curve
            # Compute the quadratic Bezier curve formula
            x = (1 - t)**2 * start_x + 2 * (1 - t) * t * control_x + t**2 * end_x
            y = (1 - t)**2 * start_y + 2 * (1 - t) * t * control_y + t**2 * end_y
            positions.append((x, y))

    return positions

def _map_colors(values: list) -> list[tuple[int,int,int]]:
    global _led_pins

    limit = min(len(values), len(_led_pins))
    mapped_leds = [(0,0,0)] * limit

    for i in range(limit):
        mapped_leds[i] = tuple([int(values[i]*float(x)/255) for x in colours[i % 6]])
    return mapped_leds

def _draw():
    # handle the creation of the virtual piglow, taking 18 (x,y,r,g,b) tuples and placing them on the screen
    # we will be using the python graphics library to draw the virtual piglow
    global _live_values
    global screen
    global positions

    screen.fill((0, 0, 0))

    if positions is None:
        positions = _calculate_led_positions()

    print(_live_values)

    led_brightness = _map_colors(_live_values)
    # print(led_brightness)
    #_live_values[i]
    for i in range(18):
        pygame.draw.circle(screen, led_brightness[i], (int(positions[i][0]), int(positions[i][1])), LED_RADIUS)
    pygame.display.flip()

def handle_exit():
    global running
    running = False
    pygame.quit()


def init():
    global screen
    # Initialize Pygame
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    screen.fill((0, 0, 0))
    pygame.display.set_caption("Virtual PiGlow")



def virtual_piglow_worker():
    global running
    global screen

    while screen is None:
        sleep(0.5)

    # Main Pygame loop
    while running:
        _draw()  # Assuming draw() uses the screen variable

        # Handle Pygame events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False


def _set(leds, value): # library compatibility
    return set(leds, value)

def set(leds, value):
    global _buffer_values
    
    if isinstance(leds, list):
        if isinstance(value, list):
            for x in range(len(value)):
                _buffer_values[leds[x] % 18] = (value[x] % 256)
        else:
            for led_index in leds:
                _buffer_values[led_index % 18] = (value % 256)

    elif isinstance(leds, int):
        leds %= 18
        if isinstance(value, list):
            _buffer_values[leds:leds + len(value)] = map(lambda v: v % 256, value)
            if len(_buffer_values) > 18:
                wrap = _buffer_values[18:]
                _buffer_values = _buffer_values[:18]
                set(0, wrap)
        else:
            _buffer_values[leds] = (value % 256)
    else:
        raise ValueError("Invalid LED(s)")

def show():
    # handle the updating of the virtual piglow, taking 18 (x,y,r,g,b) tuples and updating the on-screen virtual piglow
    # we will be using the python graphics library to update the virtual piglow
    global _live_values
    global _buffer_values

    _live_values = _buffer_values

# # Usage example
# draw()
# _set(range(18), [50] * 18)
# show()
