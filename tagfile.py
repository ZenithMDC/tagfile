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

# This is an incomplete tagfile parser. Additional features will be implemented
# on an as-needed basis.

import struct
import sys
import os
import pprint
from math import *
import inspect

BR_TERRAIN =  0
BR_LIGHT   = -1
BR_AREA    = -2
BR_OBJECT  = -3
BR_FLOW    = -4
BR_ROOM    = -5

BR_PRIM_SPECIAL   = 0
BR_PRIM_CYLINDER  = 1
BR_PRIM_PYRAMID   = 2
BR_PRIM_CORNERPYR = 3
# The following are derived from BR_PRIM_SPECIAL (see get_br_prim_type):
BR_SPRIM_CUBE  = 1
BR_SPRIM_DODEC = 6
BR_SPRIM_WEDGE = 7
BR_SPRIM_LINE  = 8
BR_SPRIM_LIGHT = 9

br_prim_names = {BR_PRIM_SPECIAL: 'Special', BR_PRIM_CYLINDER: 'Cylinder', BR_PRIM_PYRAMID: 'Pyramid', BR_PRIM_CORNERPYR: 'Corner-Apex Pyramid'}
br_sprim_names = {BR_SPRIM_CUBE: 'Cube', BR_SPRIM_DODEC: 'Dodecahedron', BR_SPRIM_WEDGE: 'Wedge', BR_SPRIM_LINE: 'Line', BR_SPRIM_LIGHT: 'Light'}

def fixang_to_radians(fixang):
    return fixang * tau / 65536

# If prim_type is BR_PRIM_SPECIAL, use sprim_type.
def get_br_prim_type(primal_id):
    prim_type = primal_id >> 9
    sprim_type = 0
    if prim_type == BR_PRIM_SPECIAL:
        sprim_type = primal_id
    return prim_type, sprim_type

def list_tags(fp):
    for tag in get_region('', fp):
        print(tag)

def get_region(tagname, fp):
    tags = []

    tag_len = 24 # TagName(12) + MajorVer(4) + MinorVer(4) + ???(4)
    nice_tagname = tagname
    tagname += '\x00' * (12 - len(tagname))
    tagname = tagname.encode()
    found_tagname = False

    fp.seek(0, os.SEEK_SET)
    toc_off = struct.unpack('<I', fp.read(4))[0]
    fp.seek(toc_off, os.SEEK_SET)
    toc_entries = struct.unpack('<I', fp.read(4))[0]
    while toc_entries:
        toc_tag = fp.read(len(tagname))
        if tagname[0] == 0:
            region_off = struct.unpack('<I', fp.read(4))[0]
            region_len = struct.unpack('<I', fp.read(4))[0]
            tags.append((toc_tag.split(b'\x00')[0].decode('utf8'), region_len))
        elif tagname == toc_tag:
            found_tagname = True
            region_off = struct.unpack('<I', fp.read(4))[0]
            region_len = struct.unpack('<I', fp.read(4))[0]
            break
        else:
            fp.seek(8, os.SEEK_CUR)
        toc_entries -= 1
    if tagname[0] == 0:
        return tags
    if not found_tagname:
        print('[E:%s] There aren\'t any %s tags in this mission.' % (inspect.currentframe().f_code.co_name, nice_tagname))
        sys.exit(1)

    fp.seek(region_off + tag_len, os.SEEK_SET)
    end = region_off+region_len+tag_len
    return fp, end

# These fields are named horribly... For the sake of clarification:
#     tx['count'] is the number of textures
#     tx['tok_count'] is the number of family palettes
#     tx['tok_names'][?]['tokens'] is a 4-byte index array, where each byte's
#                                  index is the path depth and each byte's
#                                  value is an index into tx['tokens']
#                                  (which is 1-based), which determines
#                                  what family a texture belongs to as well
#                                  as its path.
# If tok_names['tokens'] is still confusing to understand, try this example:
#     tx['tokens'] = ['fam', 'CITY', 'newcity', ...]
#     tx['tok_names'] = [{'name': 'WIN326L', 'reserved': 0, 'tokens': [1, 2, 0, 0]}, ...]
# Here, the texture path is: 'fam/CITY/WIN326L', where:
#     'fam' is  tx['tokens'][tx['tok_names'][0]['tokens'][0]],
#     'CITY' is tx['tokens'][tx['tok_names'][0]['tokens'][1]],
# and the remainder of tx['tok_names'][0]['tokens'] is unused (0's).
def parse_txlist(fp):
    fp, end = get_region('TXLIST', fp)
    max_tok_len = 16
    max_tokens_per = 4
    max_name_len = 15
    tx = dict()
    tx['block_size'] = struct.unpack('<i', fp.read(4))[0]
    tx['count']      = struct.unpack('<i', fp.read(4))[0]
    tx['tok_count']  = struct.unpack('<i', fp.read(4))[0]
    tokens = []
    for _ in range(tx['tok_count']):
        tokens.append(struct.unpack('%us' % max_tok_len, fp.read(max_tok_len))[0].split(b'\x00')[0].decode('utf8'))
    tx['tokens'] = tokens
    tok_names = []
    for _ in range(tx['count']):
        tn = dict()
        tn_toks = []
        for __ in range(max_tokens_per):
            tn_toks.append(struct.unpack('<B', fp.read(1))[0])
        tn['tokens']   = tn_toks
        tn['name']     = struct.unpack('%us' % max_name_len, fp.read(max_name_len))[0].split(b'\x00')[0].decode('utf8')
        tn['reserved'] = struct.unpack('B', fp.read(1))[0]
        tok_names.append(tn)
    tx['tok_names'] = tok_names
    return tx

def parse_lmetaprop(fp):
    fp, end = get_region('L$MetaProp', fp)
    mps = []
    while fp.tell() < end:
        mp = dict()
        mp['link_id'] = struct.unpack('<i', fp.read(4))[0]
        mp['source']  = struct.unpack('<i', fp.read(4))[0]
        mp['dest']    = struct.unpack('<i', fp.read(4))[0]
        mp['flavor']  = struct.unpack('<h', fp.read(2))[0]
        mps.append(mp)
    return mps

def parse_plight(fp):
    fp, end = get_region('P$Light', fp)
    lts = []
    while fp.tell() < end:
        lt = dict()
        lt['obj_id']       = struct.unpack('<i', fp.read(4))[0]
        lt['len']          = struct.unpack('<I', fp.read(4))[0]
        lt['brightness']   = struct.unpack('<f', fp.read(4))[0]
        offset = dict()
        offset['x']        = struct.unpack('<f', fp.read(4))[0]
        offset['y']        = struct.unpack('<f', fp.read(4))[0]
        offset['z']        = struct.unpack('<f', fp.read(4))[0]
        lt['offset'] = offset
        lt['radius']       = struct.unpack('<f', fp.read(4))[0]
        lt['quad']    = bool(struct.unpack('<I', fp.read(4))[0])
        lt['inner_radius'] = struct.unpack('<f', fp.read(4))[0]
        lts.append(lt)
    return lts

def parse_obj_map(fp):
    fp, end = get_region('OBJ_MAP', fp)
    oms = []
    while fp.tell() < end:
        om = dict()
        om['obj_id'] = struct.unpack('<i', fp.read(4))[0]
        om['size']   = struct.unpack('<I', fp.read(4))[0]
        om['name']   = fp.read(om['size'])[:-1].decode('utf8')
        oms.append(om)
    return oms

def parse_gam_file(fp):
    fp, end = get_region('GAM_FILE', fp)
    return fp.read(256).split(b'\x00')[0].decode('utf8')

def parse_brlist(fp):
    fp, end = get_region('BRLIST', fp)
    brs = []
    prev_br_id = 1
    while fp.tell() < end:
        mark = fp.tell()
        br = dict()
        br['br_id']          = struct.unpack('<h', fp.read(2))[0]
        br['timestamp']      = struct.unpack('<h', fp.read(2))[0]
        br['primal_id']      = struct.unpack('<i', fp.read(4))[0]
        br['tx_id']          = struct.unpack('<h', fp.read(2))[0]
        br['media']          = struct.unpack('<b', fp.read(1))[0]
        br['flags']          = struct.unpack('<b', fp.read(1))[0]
        pos = dict()
        pos['x']             = struct.unpack('<f', fp.read(4))[0]
        pos['y']             = struct.unpack('<f', fp.read(4))[0]
        pos['z']             = struct.unpack('<f', fp.read(4))[0]
        br['pos'] = pos
        sz = dict()
        sz['d']              = struct.unpack('<f', fp.read(4))[0]
        sz['w']              = struct.unpack('<f', fp.read(4))[0]
        sz['h']              = struct.unpack('<f', fp.read(4))[0]
        br['sz'] = sz
        ang = dict()
        ang['tx']            = struct.unpack('<H', fp.read(2))[0]
        ang['ty']            = struct.unpack('<H', fp.read(2))[0]
        ang['tz']            = struct.unpack('<H', fp.read(2))[0]
        br['ang'] = ang
        br['cur_face']       = struct.unpack('<h', fp.read(2))[0]
        grid = dict()
        grid['line_spacing'] = struct.unpack('<f', fp.read(4))[0]
        phase_shift = dict()
        phase_shift['x']     = struct.unpack('<f', fp.read(4))[0]
        phase_shift['y']     = struct.unpack('<f', fp.read(4))[0]
        phase_shift['z']     = struct.unpack('<f', fp.read(4))[0]
        grid['phase_shift'] = phase_shift
        orientation = dict()
        orientation['tx']    = struct.unpack('<H', fp.read(2))[0]
        orientation['ty']    = struct.unpack('<H', fp.read(2))[0]
        orientation['tz']    = struct.unpack('<H', fp.read(2))[0]
        grid['orientation'] = orientation
        grid['grid_enabled'] = struct.unpack('<?', fp.read(1))[0]
        br['grid'] = grid
        br['num_faces']      = struct.unpack('<B', fp.read(1))[0]
        br['edge']           = struct.unpack('<b', fp.read(1))[0]
        br['point']          = struct.unpack('<b', fp.read(1))[0]
        br['use_flg']        = struct.unpack('<b', fp.read(1))[0]
        br['group_id']       = struct.unpack('<b', fp.read(1))[0]
        br['pad0']           = struct.unpack('<i', fp.read(4))[0]
        txs = []
        if br['media'] not in [BR_AREA, BR_OBJECT, BR_FLOW, BR_ROOM]:
            for i in range(br['num_faces']):
                texinfo = dict()
                texinfo['tx_id']    = struct.unpack('<h', fp.read(2))[0]
                texinfo['tx_rot']   = struct.unpack('<H', fp.read(2))[0]
                texinfo['tx_scale'] = struct.unpack('<h', fp.read(2))[0]
                texinfo['tx_x']     = struct.unpack('<H', fp.read(2))[0]
                texinfo['tx_y']     = struct.unpack('<H', fp.read(2))[0]
                txs.append(texinfo)
        br['txs'] = txs
        brs.append(br)
        if br['br_id'] < prev_br_id:
            print('[E:%s] Something\'s going down with the brlist parser...' % inspect.currentframe().f_code.co_name)
            print('Okay. We gots us a problem at brush ' + str(len(brs)-1))
            print('Somewhere around position ' + str(mark))
            print('Current: ' + str(br['br_id']))
            print('Previous: ' + str(prev_br_id))
            print()
            pprint.pprint(brs[-2])
            sys.exit(1)
        prev_br_id = br['br_id']
    return brs

def filter_br_by_type(brtype, brlist):
    if type(brtype) == int:
        brtype = [brtype]
    return [br for br in brlist if br['media'] in brtype]

def check_integrity(fp):
    prev_off = fp.tell()
    fp.seek(0, os.SEEK_SET)
    fp.seek(268, os.SEEK_SET)
    deadbeef = struct.unpack('4s', fp.read(4))[0]
    fp.seek(prev_off, os.SEEK_SET)
    if deadbeef != b'\xDE\xAD\xBE\xEF':
        print('[E:%s] This tagfile is either corrupt or not a tagfile at all.' % inspect.currentframe().f_code.co_name)
        sys.exit(1)

def main(args):
    funcs = {'parse_txlist':    parse_txlist,
             'parse_lmetaprop': parse_lmetaprop,
             'parse_plight':    parse_plight,
             'parse_obj_map':   parse_obj_map,
             'parse_gam_file':  parse_gam_file,
             'parse_brlist':    parse_brlist,
             'list_tags':       list_tags,
             'check_integrity': check_integrity}

    if len(args) < 3:
        print('arg1: Mission file')
        print('arg2: Func')
        return 1

    mis = args[1]
    func = funcs[args[2]]

    with open(mis, 'rb') as fp:
        rv = func(fp)
    pprint.pprint(rv)

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
