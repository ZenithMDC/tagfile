#!/usr/bin/env python3

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

#
# Convert all light props & brush lights to AnimLight props.
#

# TODO: Implement brush primitives other than cube in get_face_positions.
# TODO: Exclude SpotLightPoint objects from window light candidacy.

import os
import sys
#import pprint
import platform

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import utils
import tagfile

# Number of update segments for the GUI progressbar.
pb_num_segs = 6

# Amount to increase the GUI progressbar by, per update segment.
pb_incr = 100 / pb_num_segs

def get_version(filename):
    with open(filename, 'r') as fp:
        version = dict(zip(['major', 'minor', 'patch'], [int(ver_part) for ver_part in fp.read().strip().split('.')]))
        fp.seek(0, os.SEEK_SET)
        version['string'] = fp.read()
    return version

version = get_version(utils.get_pyi_asset('VERSION'))

config = {
    't1_root': {
        'default': '""',
        'description': 'Root directories for Thief 1 & 2, respectively, which must be specified for FMs that use the default gamesys.',
        'newline': False
    },
    't2_root': {
        'default': '""',
    },
    'outer_bound': {
        'default': 10.0,
        'clamp': {'min' : 0.0},
        'description': 'Boundary for a brush/hack light to be considered a window light candidate.'
    },
    'inner_bound': {
        'default': 2.1,
        'clamp': {'min': 0.0},
        'description': 'If a window light candidate is within this boundary, it will be considered a window light.'
    },
    'wl_volume': {
        'default': 0.5,
        'clamp': {'min': 0.0, 'max': 1.0},
        'description': 'Volumetric fog magnitude for window lights.'
    },
    'gui_width': {
        'default': 640,
        'description': 'GUI\'s stored width and height metrics.',
        'newline': False
    },
    'gui_height': {
        'default': 480
    },
    'gui_pos_x': {
        'default': 10,
        'description': 'GUI\'s stored X and Y positions. Only has effect if gui_position_mode is "Stored".',
        'newline': False
    },
    'gui_pos_y': {
        'default': 10
    },
    'gui_position_mode': {
        'default': '"Centered"',
        'options': {
            'Centered': 'Centered on screen.',
            'OS': 'Let the operating system decide.',
            'Stored': 'Remember the position.'
        },
        'description': 'Where the GUI should be positioned when launched.'
    },
    'gui_auto_clear_log': {
        'default': True,
        'description': 'Automatically clear the log every time the Animlightify button is activated.'
    }
}

config_name = 'animlightify.cfg'

config, config_exists = utils.read_config(config_name, config)
if not config_exists:
    utils.write_config(config_name, config)
    config, config_exists = utils.read_config(config_name, config)

if platform.system() == 'Windows':
    import tdetect
    if config['t1_root']['value'] == '':
        config['t1_root']['value'] = tdetect.report_first(tdetect.GAME[1]).replace('\\', '/')
    if config['t2_root']['value'] == '':
        config['t2_root']['value'] = tdetect.report_first(tdetect.GAME[2]).replace('\\', '/')

def create_box_around_face(face, face_ul, face_lr, angle, box_size, origin, prim_type, sprim_type):
    face_max = [max(face_ul[0], face_lr[0]), max(face_ul[1], face_lr[1]), max(face_ul[2], face_lr[2])]
    face_min = [min(face_ul[0], face_lr[0]), min(face_ul[1], face_lr[1]), min(face_ul[2], face_lr[2])]
    #utils.log_print(f'face_max: {face_max[0]} {face_max[1]} {face_max[2]}')
    #utils.log_print(f'face_min: {face_min[0]} {face_min[1]} {face_min[2]}'))
    if prim_type == tagfile.BR_PRIM_SPECIAL and sprim_type == tagfile.BR_SPRIM_CUBE:
        box_max = [face_max[0]+box_size, face_max[1]+box_size, face_max[2]+box_size]
        box_min = [face_min[0]-box_size, face_min[1]-box_size, face_min[2]-box_size]
        if not (angle[0] == 0 and angle[1] == 0 and angle[2] == 0):
            box_max, box_min = utils.apply_rotation_to_points([box_max, box_min], angle, origin)
    return {'pos': origin, 'max': box_max, 'min': box_min, 'ang': angle}

def create_box_around_brush(br, box_size):
    br_pos = [br['pos']['x' ], br['pos']['y' ], br['pos']['z' ]]
    br_sz  = [br['sz' ]['d' ], br['sz' ]['w' ], br['sz' ]['h' ]]
    br_ang = [br['ang']['tz'], br['ang']['ty'], br['ang']['tx']]

    br_ang[0] = tagfile.fixang_to_radians(br_ang[0])
    br_ang[1] = tagfile.fixang_to_radians(br_ang[1])
    br_ang[2] = tagfile.fixang_to_radians(br_ang[2])

    box_sz = [br_sz[0]+box_size, br_sz[1]+box_size, br_sz[2]+box_size]
    box_max = [br_pos[0]+box_sz[0], br_pos[1]+box_sz[1], br_pos[2]+box_sz[2]]
    box_min = [br_pos[0]-box_sz[0], br_pos[1]-box_sz[1], br_pos[2]-box_sz[2]]

    if not (br_ang[0] == 0 and br_ang[1] == 0 and br_ang[2] == 0):
        box_max, box_min = utils.apply_rotation_to_points([box_max, box_min], br_ang, br_pos)

    #utils.log_print(f'box_max: {box_max[0]} {box_max[1]} {box_max[2]}')
    #utils.log_print(f'box_min: {box_min[0]} {box_min[1]} {box_min[2]}')
    return {'pos': br_pos, 'max': box_max, 'min': box_min, 'ang': br_ang}

def filter_objs_by_obj_ids(obj_ids, objs):
    return [obj for obj in objs if obj['obj_id'] in obj_ids]

def obj_ids_to_names(mps, sns):
    id_names = dict()
    for sn in sns:
        id_names[sn['obj_id']] = sn['name']
    for mp in mps:
        for sn in sns:
            if mp['dest'] == sn['obj_id']:
                id_names[mp['source']] = sn['name']
    return id_names

def add_name_to_objs_by_id(objs, id_key, id_names):
    for obj in objs:
        for id, name in id_names.items():
            if obj[id_key] == id:
                obj['name'] = name
    return objs

def add_pos_to_objs_from_brlist(objs, brlist):
    for obj in objs:
        for br in brlist:
            if br['media'] == tagfile.BR_OBJECT and br['primal_id'] == obj['obj_id']:
                obj['pos'] = br['pos']
    return objs

def remove_zero_brightness_objs(objs):
    return [obj for obj in objs if obj['brightness'] != 0]

def get_faces_with_these_textures(faces, def_tx_id, txs):
    ret_faces = []
    for face, ti in enumerate(faces):
        if (ti['tx_id'] in txs) or (ti['tx_id'] == -1 and def_tx_id in txs):
            ret_faces.append(face)
    return ret_faces

# This returns the face's upper-left and lower-right positions, rather than the
# center of the face.
def get_face_positions(faces, br):
    br_pos = [br['pos']['x' ], br['pos']['y' ], br['pos']['z' ]]
    br_sz  = [br['sz' ]['d' ], br['sz' ]['w' ], br['sz' ]['h' ]]
    br_ang = [br['ang']['tz'], br['ang']['ty'], br['ang']['tx']]

    br_ang[0] = tagfile.fixang_to_radians(br_ang[0])
    br_ang[1] = tagfile.fixang_to_radians(br_ang[1])
    br_ang[2] = tagfile.fixang_to_radians(br_ang[2])

    face_positions = []
    prim_type, sprim_type = tagfile.get_br_prim_type(br['primal_id'])
    match prim_type:
        case tagfile.BR_PRIM_SPECIAL:
            match sprim_type:
                case tagfile.BR_SPRIM_CUBE:
                    #utils.log_print(f'br_id: {br["br_id"]}')
                    #utils.log_print(f'br_pos: {br_pos[0]} {br_pos[1]} {br_pos[2]}')
                    #utils.log_print(f'br_sz: {br_sz[0]} {br_sz[1]} {br_sz[2]}')
                    for face in faces:
                        match face:
                            case 0:
                                #utils.log_print('North')
                                face_ul = [br_pos[0]-br_sz[0], br_pos[1]-br_sz[1], br_pos[2]+br_sz[2]]
                                face_lr = [face_ul[0],         br_pos[1]+br_sz[1], br_pos[2]-br_sz[2]]
                            case 1:
                                #utils.log_print('West')
                                face_ul = [br_pos[0]+br_sz[0], br_pos[1]-br_sz[1], br_pos[2]+br_sz[2]]
                                face_lr = [br_pos[0]-br_sz[0], face_ul[1],         br_pos[2]-br_sz[2]]
                            case 2:
                                #utils.log_print('South')
                                face_ul = [br_pos[0]+br_sz[0], br_pos[1]+br_sz[1], br_pos[2]+br_sz[2]]
                                face_lr = [face_ul[0],         br_pos[1]-br_sz[1], br_pos[2]-br_sz[2]]
                            case 3:
                                #utils.log_print('East')
                                face_ul = [br_pos[0]-br_sz[0], br_pos[1]+br_sz[1], br_pos[2]+br_sz[2]]
                                face_lr = [br_pos[0]+br_sz[0], face_ul[1],         br_pos[2]-br_sz[2]]
                            case 4:
                                #utils.log_print('Top')
                                face_ul = [br_pos[0]+br_sz[0], br_pos[1]-br_sz[1], br_pos[2]+br_sz[2]]
                                face_lr = [br_pos[0]-br_sz[0], br_pos[1]+br_sz[1], face_ul[2]]
                            case 5:
                                #utils.log_print('Bottom')
                                face_ul = [br_pos[0]-br_sz[0], br_pos[1]-br_sz[1], br_pos[2]-br_sz[2]]
                                face_lr = [br_pos[0]+br_sz[0], br_pos[1]+br_sz[1], face_ul[2]]
                            case _:
                                utils.log_print_error(f'Cube "{br["br_id"]}" somehow has more then 6 faces...')
                                sys.exit(1)
                        if not (br_ang[0] == 0 and br_ang[1] == 0 and br_ang[2] == 0):
                            face_ul, face_lr = utils.apply_rotation_to_points([face_ul, face_lr], br_ang, br_pos)
                        #else:
                            #utils.log_print(f'face_ul: {face_ul[0]} {face_ul[1]} {face_ul[2]}')
                            #utils.log_print(f'face_lr: {face_lr[0]} {face_lr[1]} {face_lr[2]}')
                        face_positions.append({'ul': face_ul, 'lr': face_lr})
                    #utils.log_print()
                case _:
                    utils.log_print_warning(f'Ignoring unhandled "{tagfile.get_br_sprim_name(sprim_type)}" special primitive. br_id: {br["br_id"]}')
        case _:
            utils.log_print_warning(f'Ignoring unhandled "{tagfile.get_br_prim_name(prim_type)}" primitive. br_id: {br["br_id"]}')
    return face_positions

def get_window_lights(window_positions, window_light_candidates, inner_bound, outer_bound):
    window_lights = []
    #utils.log_print(f'{len(window_positions)} window position(s).')
    #utils.log_print(f'{sum([len(wp["faces"]) for wp in window_positions])} face(s) to check.')
    #utils.log_print(f'{len(window_light_candidates)} window light candidate(s).')
    for wp in window_positions:
        #utils.log_print('-'*80)
        #utils.log_print(f'brush id: {wp["brush"]["br_id"]}')
        wlc_within_ob = []
        #utils.log_print('Outer box max/min:')
        outer_box = create_box_around_brush(wp['brush'], outer_bound)
        for wlc in window_light_candidates:
            if not (outer_box['ang'][0] == 0 and outer_box['ang'][1] == 0 and outer_box['ang'][2] == 0):
                intersection = utils.point_intersects_obb(
                                   [wlc['pos']['x'], wlc['pos']['y'], wlc['pos']['z']],
                                   outer_box['ang'],
                                   outer_box['pos'],
                                   outer_box['max'],
                                   outer_box['min'],
                                   verbose=False
                               )
            else:
                intersection = utils.point_intersects_aabb(
                                   [wlc['pos']['x'], wlc['pos']['y'], wlc['pos']['z']],
                                   outer_box['max'],
                                   outer_box['min'],
                                   verbose=False
                               )
            if intersection:
                wlc_within_ob.append(wlc)
        if not wlc_within_ob:
            #utils.log_print('No window light candidate is within outer box -- skipping.')
            continue

        #utils.log_print(f'{len(wlc_within_ob)} window light candidate(s) are within outer box.')
        #for wlc in wlc_within_ob:
        #    type_id = get_light_type_id(wlc)
        #    utils.log_print(f'    {type_id}: {wlc[type_id]}')

        #utils.log_print(f'{len(wp["faces"]} face(s) to check:')
        #utils.log_print(wp['faces'])
        for fp in wp['face_pos']:
            for face in wp['faces']:
                #utils.log_print(f'Checking face idx {face}.')
                inner_box = create_box_around_face(
                                face,
                                fp['ul'], fp['lr'],
                                [wp['brush']['ang']['tz'], wp['brush']['ang']['ty'], wp['brush']['ang']['tx']],
                                inner_bound,
                                [wp['brush']['pos']['x'], wp['brush']['pos']['y'], wp['brush']['pos']['z']],
                                *tagfile.get_br_prim_type(wp['brush']['primal_id'])
                            )
                for wlc in wlc_within_ob:
                    type_id = get_light_type_id(wlc)
                    searching_for_list = [light[type_id] for light in window_lights if type_id in light]
                    if wlc[type_id] in searching_for_list:
                        continue
                    if not (inner_box['ang'][0] == 0 and inner_box['ang'][1] == 0 and inner_box['ang'][2] == 0):
                        intersection = utils.point_intersects_obb(
                                           [wlc['pos']['x'], wlc['pos']['y'], wlc['pos']['z']],
                                           inner_box['ang'],
                                           inner_box['pos'],
                                           inner_box['max'],
                                           inner_box['min'],
                                           verbose=False
                                       )
                    else:
                        intersection = utils.point_intersects_aabb(
                                           [wlc['pos']['x'], wlc['pos']['y'], wlc['pos']['z']],
                                           inner_box['max'],
                                           inner_box['min'],
                                           verbose=False
                                       )
                    if intersection:
                        #utils.log_print(f'{type_id} {wlc[type_id]} passes inner box test.')
                        window_lights.append(wlc)

    return window_lights

def get_window_positions(brlist, glass_txs):
    window_positions = []
    for br in brlist:
        if br['num_faces'] and br['media'] >= tagfile.BR_TERRAIN:
            if faces := get_faces_with_these_textures(br['txs'], br['tx_id'], glass_txs):
                window_positions.append({'face_pos': get_face_positions(faces, br), 'faces': faces, 'brush': br})
    return window_positions

def get_obj_ids_by_archetype_name(archetype_name, sns, mps, mps_gam, id_names):
    abstract_ids = []
    concrete_ids = []

    for sn in sns:
        if sn['name'] == archetype_name:
            target_id = sn['obj_id']
            break

    for mp in mps_gam:
        if mp['dest'] == target_id:
            abstract_ids.append(mp['source'])

    for mp in mps:
        for abstract_id in abstract_ids:
            if mp['dest'] == abstract_id:
                concrete_ids.append(mp['source'])

    return concrete_ids

def get_tx_ids_by_archetype_name(archetype_name, sns, mps_gam, id_names, txlist):
    tx_names = []
    tx_ids = []

    for sn in sns:
        if sn['name'] == archetype_name:
            target_id = sn['obj_id']
            break

    for mp in mps_gam:
        if mp['dest'] == target_id:
            tx_names.append(id_names[mp['source']][2:].lower())

    for i, tn in enumerate(txlist['tok_names']):
        fullname = ''
        for t in tn['tokens']:
            if t == 0:
                continue
            fullname += txlist['tokens'][t-1] + '/'
        fullname += tn['name']
        fullname = fullname.lower()
        for tx_name in tx_names:
            if fullname == tx_name:
                tx_ids.append(i)

    return tx_ids

def get_light_type(light):
    if 'obj_id' in light:
        return 'plights'
    elif 'br_id' in light:
        return 'brlights'

def get_light_type_id(light):
    if 'obj_id' in light:
        return 'obj_id'
    elif 'br_id' in light:
        return 'br_id'

def get_dark_gam_version(oms):
    for om in oms:
        if om['name'] == 'EvilGarrett' and om['obj_id'] == -2405:
            return 2
    return 1

def get_gamesys_path(dirname, t1_root, t2_root, oms, fp):
    gam_name = tagfile.parse_gam_file(fp)['data']
    gam_path = dirname + '/' + tagfile.parse_gam_file(fp)['data']
    gam_ver = get_dark_gam_version(oms)
    utils.gv_queue.put_nowait(gam_ver)
    if not os.path.exists(gam_path):
        if gam_ver == 1 and t1_root:
            gam_path = t1_root + '/' + gam_name
        elif gam_ver == 2 and t2_root:
            gam_path = t2_root + '/' + gam_name
        else:
            utils.log_print_error(f'Cannot find gamesys "{gam_path}".')
            utils.log_print(f'You must specify where Thief {gam_ver}\'s root directory is in "animlightify.cfg". Ex:')
            utils.log_print(f't{gam_ver}_root = "<path/to/thief{gam_ver}>"')
            sys.exit(1)
    return gam_path

def main(args):
    if len(args) < 2:
        import gui # <- This blocks and never returns.

    utils.log_print(f'Animlightify v{version["string"]}')

    cwd = os.getcwd().replace('\\', '/')
    prev_name = None
    cmd = []
    dml = []
    dml.append('DML1')
    dml.append('')
    fmt = '    %-27s %s'

    t1_root = config['t1_root']['value']
    t2_root = config['t2_root']['value']
    outer_bound = config['outer_bound']['value']
    inner_bound = config['inner_bound']['value']
    wl_volume = config['wl_volume']['value']

    mis = args[1]
    dirname = os.path.dirname(mis)
    if os.path.exists(mis):
        fp = open(mis, 'rb')
    else:
        utils.log_print_error(f'Mission File "{mis}" not found.')
        return 1
    tagfile.check_integrity(fp)

    oms = tagfile.parse_obj_map(fp)['data']
    with open(get_gamesys_path(dirname, t1_root, t2_root, oms, fp), 'rb') as fp_gam:
        mps_gam = tagfile.parse_lmetaprop(fp_gam)['data']
        sns_gam = tagfile.parse_psymname(fp_gam)['data']

    utils.pb_queue.put_nowait(pb_incr)
    mps = tagfile.parse_lmetaprop(fp)['data']
    id_names = obj_ids_to_names(mps, sns_gam)

    utils.pb_queue.put_nowait(pb_incr)
    light_objs = tagfile.parse_plight(fp)['data']
    light_objs = remove_zero_brightness_objs(light_objs)
    light_objs = add_name_to_objs_by_id(light_objs, 'obj_id', id_names)
    light_objs = sorted(light_objs, key=lambda d: d['name'])

    utils.pb_queue.put_nowait(pb_incr)
    brushes = tagfile.parse_brlist(fp)['data']
    textures = tagfile.parse_txlist(fp)['data']
    glass_txs = get_tx_ids_by_archetype_name('GlassTex', sns_gam, mps_gam, id_names, textures)
    window_positions = get_window_positions(brushes, glass_txs)

    utils.pb_queue.put_nowait(pb_incr)
    hacklight_obj_ids = get_obj_ids_by_archetype_name('HackLight', sns_gam, mps, mps_gam, id_names)
    light_objs = add_pos_to_objs_from_brlist(light_objs, brushes)
    plights = filter_objs_by_obj_ids(hacklight_obj_ids, light_objs)
    brlights = tagfile.filter_br_by_type(tagfile.BR_LIGHT, brushes)
    window_light_candidates = plights + brlights
    window_lights = get_window_lights(window_positions, window_light_candidates, inner_bound, outer_bound)
    #for light in window_lights:
    #    type_id = get_light_type_id(light)
    #    utils.log_print(f'{type_id}: {light[type_id])}')

    utils.pb_queue.put_nowait(pb_incr)
    window_plights = []
    window_brlights = []
    for wl in window_lights:
        ltype = get_light_type(wl)
        if ltype == 'plights':
            window_plights.append(wl)
        elif ltype == 'brlights':
            window_brlights.append(wl)
    #pprint.pp(window_plights)
    #pprint.pp(window_brlights)

    # Handle replacing all brush lights with anim lights.
    comment = 'Replace all brush lights'
    if brlights:
        dml.append(f'// {comment} {"-"*(80-len(comment)-3)}')
    for br in brlights:
        cmd.append(f'brush_select {br["br_id"]}')
        cmd.append('delete_brush')
        cmd.append(f'mprint deleted brush light {br["br_id"]}')
        dml.append('Create "OmniLightPoint"')
        dml.append('{')
        dml.append('    +ObjProp "Position"')
        dml.append('    {')
        dml.append(f'        "Location" {br["pos"]["x"]}, {br["pos"]["y"]}, {br["pos"]["z"]}')
        dml.append('    }')
        dml.append('    -ObjProp "Light"')
        dml.append('    +ObjProp "AnimLight"')
        dml.append('    {')
        dml.append('    ' + fmt % ('"Mode"', '"maximum brightness"'))
        dml.append('    ' + fmt % ('"max brightness"', br['sz']['d']))
        dml.append('    }')
        for window_brlight in window_brlights:
            if br['br_id'] == window_brlight['br_id']:
                dml.append('    +ObjProp "HwtlLight"')
                dml.append('    {')
                dml.append('    ' + fmt % ('"volume"', wl_volume))
                dml.append('    }')
                break
        if br['sz']['w'] or br['sz']['h']:
            dml.append('    +ObjProp "LightColor"')
            dml.append('    {')
            dml.append('    ' + fmt % ('"hue"', br['sz']['w']))
            dml.append('    ' + fmt % ('"saturation"', br['sz']['h']))
            dml.append('    }')
        dml.append('}')
        dml.append('')

    # Construct a DML, replacing all Light props with Anim Light props with the
    # appropriate parameters for each obj.
    for obj in light_objs:
        if obj['name'] != prev_name:
            comment = obj['name'].split()
            comment = comment[1] if len(comment) > 1 else comment[0]
            comment += '(s)'
            dml.append(f'// {comment} {"-"*(80-len(comment)-3)}')
            prev_name = obj['name']
        dml.append(f'-ObjProp {obj["obj_id"]} "Light"')
        dml.append(f'+ObjProp {obj["obj_id"]} "AnimLight"')
        dml.append('{')
        dml.append(fmt % ('"Mode"', '"maximum brightness"'))
        dml.append(fmt % ('"max brightness"', obj['brightness']))
        dml.append(fmt % ('"radius (0 for infinite)"', obj['radius']))
        if 'inner_radius' in obj.keys():
            dml.append(fmt % ('"inner radius (0 for none)"', obj['inner_radius']))
        if 'quad' in obj.keys():
            dml.append(fmt % ('"quad lit"', obj['quad']))
        dml.append(fmt % ('"offset from object"', f'{obj["offset"]["x"]}, {obj["offset"]["y"]}, {obj["offset"]["z"]}'))
        dml.append('}')
        for window_plight in window_plights:
            if obj['obj_id'] == window_plight['obj_id']:
                dml.append(f'+ObjProp {obj["obj_id"]} "HwtlLight"')
                dml.append('{')
                dml.append(fmt % ('"volume"', wl_volume))
                dml.append('}')
                break
        dml.append('')

    cmd.append(f'dbmod_load {cwd}/animlightify.dml')
    cmd.append('run Cmds/DoLight.cmd')

    fp.close()

    with open('animlightify.dml', 'w') as fp:
        for l in dml:
            fp.write(l+'\n')

    with open('animlightify.cmd', 'w') as fp:
        for l in cmd:
            fp.write(l+'\n')

    utils.log_print(f'{len(brlights)} brush light(s) and {len(light_objs)} light prop(s) to be replaced.')
    utils.log_print(f'{len(window_brlights)} brush light(s) and {len(window_plights)} hack light(s) detected as window lights.')
    utils.log_print(f'Window light params: outer_bound={outer_bound}, inner_bound={inner_bound}, wl_volume={wl_volume}')
    utils.log_print()
    utils.log_print(f'Run animlightify.cmd in Dromed by using the command prompt:\nrun {cwd}/animlightify.cmd')
    utils.log_print()
    utils.log_print('For additional instructions, please refer to README.md')

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
