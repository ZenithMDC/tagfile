# See the NOTICE file distributed with this work for additional information
# regarding copyright ownership. Licensed under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with the
# License. You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

import os
import inspect
from math import *
import queue
import threading

# Queues used for unidirectional communication from core (ChildThread) to GUI (MainThread).
pb_queue = queue.Queue() # Progressbar queue.
gv_queue = queue.Queue() # gamesys version queue.

class ThreadWithResult(threading.Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs={}, *, daemon=None):
        def function():
            self.result = target(*args, **kwargs)
        super().__init__(group=group, target=function, name=name, daemon=daemon)

def get_pyi_asset(asset):
    return asset if os.path.exists(asset) else f'_internal/{asset}'

def clamp(x, minval=None, maxval=None):
    minval_exists = minval != None
    maxval_exists = maxval != None
    if minval_exists and maxval_exists:
        return min(max(x, minval), maxval)
    if minval_exists:
        return max(x, minval)
    if maxval_exists:
        return min(x, maxval)
    return x

def dot_product(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def invert_angles(a):
    return [tau-a[0], tau-a[1], tau-a[2]]

def apply_rotation_to_points(points, angle, origin, verbose=False):
    o = origin
    a = angle[0]
    b = angle[1]
    c = angle[2]

    r = [cos(a)*cos(b), cos(a)*sin(b)*sin(c) - sin(a)*(cos(c)), cos(a)*sin(b)*cos(c) + sin(a)*sin(c),
         sin(a)*cos(b), sin(a)*sin(b)*sin(c) + cos(a)*cos(c),   sin(a)*sin(b)*cos(c) - cos(a)*sin(c),
         -sin(b),       cos(b)*sin(c),                          cos(b)*cos(c)                        ]

    rotated_points = []
    for i, p in enumerate(points):
        t = [p[0]-o[0], p[1]-o[1], p[2]-o[2]]

        th = dot_product(t, [r[0], r[1], r[2]])
        tp = dot_product(t, [r[3], r[4], r[5]])
        tb = dot_product(t, [r[6], r[7], r[8]])

        rotated_points.append([o[0]+th, o[1]+tp, o[2]+tb])

        if verbose:
            log_print('ROTATION INFO #'+str(i+1)+' =========================================================================')
            log_print(f'Origin:        [{o[0]:+7.2f} {o[1]:+7.2f} {o[2]:+7.2f} ]')
            log_print()
            log_print('Pre-rotation ----------------------------')
            log_print(f'Point:         [{p[0]:+7.2f} {p[1]:+7.2f} {p[2]:+7.2f} ]')
            log_print(f'Translation:   [{t[0]:+7.2f} {t[1]:+7.2f} {t[2]:+7.2f} ]')
            log_print()
            log_print('Post-rotation ---------------------------')
            log_print(f'Point:         [{o[0]+th:+7.2f} {o[1]+tp:+7.2f} {o[2]+tb:+7.2f} ]')
            log_print(f'Translation:   [{th:+7.2f} {tp:+7.2f} {tb:+7.2f} ]')
            log_print()
            log_print('Rotation Matrix:')
            log_print(f'[ {r[0]:+.2f} {r[1]:+.2f} {r[2]:+.2f}\n  {r[3]:+.2f} {r[4]:+.2f} {r[5]:+.2f}\n  {r[6]:+.2f} {r[7]:+.2f} {r[8]:+.2f} ]')
            log_print()
            log_print('Heading -------------------| Pitch --------------------| Bank ---------------------|')
            log_print(f'a={a:.6f} rad ({a*180/pi:.6f}°), b={b:.6f} rad ({b*180/pi:.6f}°), c={c:.6f} rad ({c*180/pi:.6f}°)')
            log_print('==========================================================================================')

    return rotated_points

def point_intersects_obb(point, obb_angle, obb_origin, obb_max, obb_min, verbose=False):
    if verbose:
        log_print('Transforming OBB => AABB for point intersection test.')
    point, aabb_max, aabb_min = apply_rotation_to_points([point, obb_max, obb_min], invert_angles(obb_angle), obb_origin)
    return point_intersects_aabb(point, aabb_max, aabb_min, verbose=verbose)

def point_intersects_aabb(point, aabb_max, aabb_min, verbose=False):
    intersection = (
        point[0] >= aabb_min[0] and
        point[0] <= aabb_max[0] and
        point[1] >= aabb_min[1] and
        point[1] <= aabb_max[1] and
        point[2] >= aabb_min[2] and
        point[2] <= aabb_max[2]
    )
    if verbose:
        log_print('INTERSECTION TEST:')
        log_print(f'box_max: {aabb_max[0]} {aabb_max[1]} {aabb_max[2]}')
        log_print(f'box_min: {aabb_min[0]} {aabb_min[1]} {aabb_min[2]}')
        log_print(f'point:   {point[0]} {point[1]} {point[2]}')
        log_print(intersection)
    return intersection

def read_config(filename, config):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf8') as fp:
            for line in fp:
                line = line.strip()
                if not line or line[0] == '#':
                    continue
                key = line.split('=')[0].strip()
                value = line.split('=')[1]
                if (comment_pos := value.find('#')) != -1:
                    value = value[:comment_pos]
                value = value.strip().replace('"', '')
                config[key]['value'] = value
                type_of_default = type(config[key]['default'])
                if type_of_default == bool:
                    config[key]['value'] = value.lower() == 'true'
                else:
                    config[key]['value'] = type_of_default(config[key]['value'])
                if type_of_default == str:
                    config[key]['value'] = config[key]['value'].replace('\\', '/').rstrip('/')
                elif type_of_default == float or type_of_default == int:
                    if 'clamp' in config[key].values():
                        if 'min' in config[key]['clamp'] and 'max' in config[key]['clamp']:
                            config[key]['value'] = clamp(config[key]['value'], config[key]['clamp']['min'], config[key]['clamp']['max'])
                        elif 'min' in config[key]['clamp']:
                            config[key]['value'] = clamp(config[key]['value'], config[key]['clamp']['min'])
                        elif 'max' in config[key]['clamp']:
                            config[key]['value'] = clamp(config[key]['value'], None, config[key]['clamp']['max'])
                elif type_of_default == bool:
                    pass
                else:
                    log_print_error(f'Unhandled type {str(type_of_default)}.')
                    sys.exit(1)
        for key, values in config.items():
            if 'value' not in values.keys():
                config[key]['value'] = config[key]['default']
    else:
        return config, False
    return config, True

def write_config(filename, config):
    log_print(f'Writing "{filename}".')
    with open(filename, 'w', encoding='utf8') as fp:
        for line in config_to_buffer(config):
            if line and line[0] != '#':
                key = line.split('=')[0].strip()
                value = line.split('=')[1].strip()
                if type(config[key]['default']) == str:
                    value = value.strip('"')
                    line = f'{key} = "{value}"'
            fp.write(line+'\n')

def get_longest_item_length(items):
    longest_so_far = 0
    for item in items:
        item_len = len(item)
        if item_len > longest_so_far:
            longest_so_far = item_len
    return longest_so_far

def config_to_buffer(config):
    buffer = []
    for key, value in config.items():
        if 'description' in value.keys():
            buffer.append(f'# {value["description"]}')
        if 'clamp' in value.keys():
            if 'min' in value['clamp'].keys() and 'max' in value['clamp'].keys() \
            and value['clamp']['min'] != None and value['clamp']['max'] != None:
                buffer.append(f'# Valid range is {value["clamp"]["min"]} to {value["clamp"]["max"]}, inclusive.')
            elif 'min' in value['clamp'] and value['clamp']['min'] != None:
                buffer.append(f'# Valid range is {value["clamp"]["min"]} to ∞, inclusive.')
            elif 'max' in value['clamp'] and value['clamp']['max'] != None:
                buffer.append(f'# Valid range is -∞ to {value["clamp"]["max"]}, inclusive.')
            buffer[-1] += (f' Defaults to {value["default"]}.')
        if 'options' in value.keys():
            buffer[-1] += (f' Defaults to {value["default"]}.')
            buffer.append('# Options:')
            max_opt_len = get_longest_item_length(value['options'].keys())
            for option, optdesc in value['options'].items():
                option = f'"{option}":'
                buffer.append(f'#     {option:{max_opt_len+3}} {optdesc}')
        if 'value' in value.keys():
            buffer.append(f'{key} = {value["value"]}')
        else:
            buffer.append(f'{key} = {value["default"]}')
        if 'newline' in value.keys():
            if value['newline']:
                buffer.append('')
        else:
            buffer.append('')
    return buffer

log_print_callback = print

def log_print(msg=''):
    log_print_callback(msg)

def log_print_error(msg=''):
    log_print_callback(f'[E:{inspect.getouterframes(inspect.currentframe())[1].function}] {msg}')

def log_print_warning(msg=''):
    log_print_callback(f'[W:{inspect.getouterframes(inspect.currentframe())[1].function}] {msg}')
