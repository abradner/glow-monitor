#!/usr/bin/env python

import piglow
import psutil
import time
import threading
import sys

_legs_royg = [
    # r   o   y   g
    [6,  7,  8,  5],
    [17, 16, 15, 13],
    [0 , 1 , 2 , 3]
]

_leg_cpu = _legs_royg[0]
_leg_ram = _legs_royg[1]
_leg_temp = _legs_royg[2]

_ring_blue = [4, 11, 14]
_ring_white = [9, 10, 12]

# _legs_bw = [
#     # b   w
#     [4,  9],
#     [11, 10],
#     [14, 12]
# ]

MAX_BRIGHTNESS = 255

def ssh_sessions():
    return min(float(subprocess.getoutput('ss | grep -i ssh | wc -l'))/3, 3)

def cpu_usage(): 
    return psutil.cpu_percent(interval=None)

def ram_usage():
    return psutil.virtual_memory().percent

def temp():
    return psutil.sensors_temperatures()['cpu-thermal'][0].current / 100.0

def network_usage_percent():
    return psutil.net_io_counters().percent

def rotate_array(array, amount):
    return array[-amount:] + array[:-amount]

def full_to_tangent(full_circle_bar, elements: int):
    """ 
    we now need to read the values from the full_circle_bar array at the positions that correspond to the number of elements
    eg if the array has 3 values then the points are 0, 120, 240; 4 values then 0, 90, 180, 270 etc.
    """
    led_tangent_bar = [0] * elements
    for i in range(0, elements):
        led_tangent_bar[i] = full_circle_bar[i * (360 / elements)]
    return led_tangent_bar

def led_bar(leg, percentage):
    """Display a bargraph on a group of LEDs.
    :param leg: the array of LEDs to use for the bargraph (ordered 0% to 100%)
    :param percentage: percentage to display in decimal
    """
    if percentage > 1.0 or percentage < 0:
        raise ValueError("percentage must be between 0.0 and 1.0")

    num_leds = len(leg)
    max_value = num_leds * MAX_BRIGHTNESS

    amount = int(max_value * percentage)
    for led_index in reversed(leg):
        piglow._set(led_index, MAX_BRIGHTNESS if amount > MAX_BRIGHTNESS else amount)
        amount = 0 if amount < MAX_BRIGHTNESS else amount - MAX_BRIGHTNESS

def generate_lighting_circle(elements: int, percentage: float, heading: int = 0):
    """
     as well as a second array that maps those values out 360 degrees

    """

    full_circle_bar = [0] * 360

    max_value = 360 * MAX_BRIGHTNESS

    amount = int(max_value * percentage)
    for degree in reversed(full_circle_bar):
        full_circle_bar[degree] = MAX_BRIGHTNESS if amount > MAX_BRIGHTNESS else amount
        amount = 0 if amount < MAX_BRIGHTNESS else amount - MAX_BRIGHTNESS

    if heading % 360 != 0:
        rotated_full_circle_bar = rotate_array(full_circle_bar, heading)
    else:
        rotated_full_circle_bar = full_circle_bar

    return {
        'full_circle_bar': rotated_full_circle_bar,
        'led_tangent_bar': full_to_tangent(rotated_full_circle_bar, elements),
        'heading': heading
    }


def rotate_lighting(led_circles: dict, degrees):
    """
    This method rotates the virtual array of lighting values by the specified number of degrees then reads the new values at the tangent points that correspond to physical leds
    """
    new_full_circle_bar = rotate_array(led_circles['full_circle_bar'], degrees)

    return {
        'full_circle_bar': new_full_circle_bar,
        'led_tangent_bar': full_to_tangent(new_full_circle_bar, len(led_circles['led_tangent_bar'])),
        'heading': (led_circles['heading'] + degrees) % 360
    }


def animate_ring(current_led_state, old_val, new_val):
    rotation = 7
    elements = 3
    if old_val == new_val:
        if new_val == 0 or new_val == 100:
            # nothing to animate, just keep as is
            return current_led_state
        else:
            if current_led_state == None:
                # create the initial state
                return generate_lighting_circle(elements, new_val, 0)
            else:
                # rotate the leds to the next position
                return rotate_lighting(current_led_state, rotation)
    else:
        elements = len(current_led_state['led_tangent_bar'])
        if new_val == 0:
            # set all the values in the array to 0
            new_full_circle_bar = [0] * 360
            return {
                'full_circle_bar': new_full_circle_bar,
                'led_tangent_bar': [0] * elements,
                'heading': 0
            }
        elif new_val == 100:
            # set the leds to full
            new_full_circle_bar = [MAX_BRIGHTNESS] * 360
            return {
                'full_circle_bar': new_full_circle_bar,
                'led_tangent_bar': [MAX_BRIGHTNESS] * elements,
                'heading': 0
            }
        else:
            current_heading = 0 if current_led_state == None else current_led_state['heading']
            return generate_lighting_circle(elements, new_val, current_heading + rotation)

def animate_cpu(current_led_state, old_val, new_val):
    new_state = animate_ring(current_led_state, old_val, new_val)

    for index, led_pin in enumerate(_ring_blue):
        piglow._set(led_pin, new_state['led_tangent_bar'][index])

    return new_state

def animate_ssh_sessions(current_led_state, old_val, new_val):
    new_state = animate_ring(current_led_state, old_val, new_val)

    for index, led_pin in enumerate(_ring_white):
        piglow._set(led_pin, new_state['led_tangent_bar'][index])

    return new_state


def sensor_worker(sensor_values: dict):
    """
    this function loops forever, reading the values from the sensor methods
    and storing them in the global a global dictionary that contains the values
    and sets a flag (one for each value) if the values have changed from their previously stored value
    """
    while True:
        # Read sensors
        new_values = {
            'cpu': cpu_usage(),
            'ram': ram_usage(),
            'temp': temp(),
            'network': network_usage_percent(),
            'ssh_sessions': ssh_sessions()
        }


        # We don't need to worry about thread safety in this case because the function that reads
        # the values only changes behaviour when previous != current. during the update of the
        # values, the previous and current values are temporarily guaranteed to be the same, 
        # so the function will not change
        sensor_values['previous'] = sensor_values['current']
        sensor_values['current'] = new_values

        # Sleep for a second
        time.sleep(1)

def piglow_worker(sensor_values: dict):
    """
    this function loops forever, animating the piglow leds
    """

    state = {
        'cpu': None,
        'ram': None,
        'temp': None,
        'network': None,
        'ssh_sessions': None
    }

    while True:
        state = {
            'cpu': animate_cpu(state['cpu'], sensor_values['current']['cpu'], sensor_values['previous']['cpu']),
            # 'ram': animate_ram(state['ram'], sensor_values['current']['ram'], sensor_values['previous']['ram']),
            # 'temp': animate_temp(state['temp'], sensor_values['current']['temp'], sensor_values['previous']['temp']),
            # 'network': animate_network(state['network'], sensor_values['current']['network'], sensor_values['previous']['network']),
            'ssh_sessions': animate_ssh_sessions(state['ssh_sessions'], sensor_values['current']['ssh_sessions'], sensor_values['previous']['ssh_sessions'])
        }

        # leg_bar_royg(0, cpu / 100.0) # CPU
        # leg_bar_royg(1, ram / 100.0) # RAM
        # leg_bar_royg(2, temp / 100.0) # TEMP
        # piglow.show()

        # # create a new dictionary that has a boolean for whether each value in current has changed from previous
        # # this is to prevent the piglow from updating if the values haven't changed
        # changed = {
        #     'cpu': sensor_values['current']['cpu'] != sensor_values['previous']['cpu'],
        #     'ram': sensor_values['current']['ram'] != sensor_values['previous']['ram'],
        #     'temp': sensor_values['current']['temp'] != sensor_values['previous']['temp'],
        #     'network': sensor_values['current']['network'] != sensor_values['previous']['network'],
        #     'ssh_sessions': sensor_values['current']['ssh_sessions'] != sensor_values['previous']['ssh_sessions'],
        # }

        piglow.show()
        time.sleep(0.02) # 50fps


def main():
    """
    this function creates two worker threads
    1. to call and store values from the sensor methods
    2. to read the stored values and display them on the piglow

    these threads will sleep and loop forever until the main thread receives crtl+c
    then we will clean up the threads, switch off the piglow and exit
    """

    sensor_values = {
        'current': {
            'cpu': 0,
            'ram': 0,
            'temp': 0,
            'network': 0,
            'ssh_sessions': 0
        },
        'previous': {
            'cpu': 0,
            'ram': 0,
            'temp': 0,
            'network': 0,
            'ssh_sessions': 0
        },
    }

    try:
        print("Starting threads...")
        piglow_thread = threading.Thread(target=piglow_worker, args=(sensor_values,))
        sensor_thread = threading.Thread(target=sensor_worker, args=(sensor_values,))
        piglow_thread.start()
        sensor_thread.start()
        print("Press Ctrl+C to exit")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting gracefully...")
        piglow_thread.join()
        sensor_thread.join()
        piglow.all(0)
        piglow.show()
        sys.exit(0)


if __name__ == "__main__":
    main()

