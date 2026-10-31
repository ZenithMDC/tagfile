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
import base64
from math import *

from utils import *

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

def fixang_to_radians(fixang):
    return fixang * tau / 65536

# If prim_type is BR_PRIM_SPECIAL, use sprim_type.
def get_br_prim_type(primal_id):
    prim_type = primal_id >> 9
    sprim_type = 0
    if prim_type == BR_PRIM_SPECIAL:
        sprim_type = primal_id
    return prim_type, sprim_type

def get_br_prim_name(prim_type):
    br_prim_names = {BR_PRIM_SPECIAL: 'Special', BR_PRIM_CYLINDER: 'Cylinder', BR_PRIM_PYRAMID: 'Pyramid', BR_PRIM_CORNERPYR: 'Corner-Apex Pyramid'}
    try:
        return br_prim_names[prim_type]
    except KeyError:
        return 'Unknown'+str(prim_type)

def get_br_sprim_name(sprim_type):
    br_sprim_names = {BR_SPRIM_CUBE: 'Cube', BR_SPRIM_DODEC: 'Dodecahedron', BR_SPRIM_WEDGE: 'Wedge', BR_SPRIM_LINE: 'Line', BR_SPRIM_LIGHT: 'Light'}
    try:
        return br_sprim_names[sprim_type]
    except KeyError:
        return 'Unknown'+str(sprim_type)

def list_tags(fp):
    return [tag for tag in get_region('', fp)]

def get_region(tagname, fp):
    tags = []
    tagname = canonical_tagname(tagname)

    tag_name_max = 12
    tag_len = 24 # TagName(12) + MajorVer(4) + MinorVer(4) + ???(4)
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
            tags.append((toc_tag, region_len))
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
        print_error('There aren\'t any %s tags in this mission.' % tagname)
        sys.exit(1)

    fp.seek(region_off + tag_name_max, os.SEEK_SET)
    ver_maj = struct.unpack('<I', fp.read(4))[0]
    ver_min = struct.unpack('<I', fp.read(4))[0]
    fp.seek(4, os.SEEK_CUR)
    end = region_off+region_len+tag_len
    return fp, end, ver_maj, ver_min

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
def parse_txlist(fp, end=None, ver_maj=None, ver_min=None):
    if end == None or ver_maj == None or ver_min == None:
        fp, end, ver_maj, ver_min = get_region('TXLIST', fp)
    #print('%-12s %u.%u' % ('TXLIST', ver_maj, ver_min))
    max_tok_len = 16
    max_tokens_per = 4
    max_name_len = 15
    tx = dict()
    tx['block_size'] = struct.unpack('<i', fp.read(4))[0]
    tx['count']      = struct.unpack('<i', fp.read(4))[0]
    tx['tok_count']  = struct.unpack('<i', fp.read(4))[0]
    tokens = []
    for _ in range(tx['tok_count']):
        tokens.append(struct.unpack('%us' % max_tok_len, fp.read(max_tok_len))[0].split(b'\x00')[0].decode('latin1'))
    tx['tokens'] = tokens
    tok_names = []
    for _ in range(tx['count']):
        tn = dict()
        tn_toks = []
        for __ in range(max_tokens_per):
            tn_toks.append(struct.unpack('<B', fp.read(1))[0])
        tn['tokens']   = tn_toks
        tn['name']     = struct.unpack('%us' % max_name_len, fp.read(max_name_len))[0].split(b'\x00')[0].decode('latin1')
        tn['reserved'] = struct.unpack('B', fp.read(1))[0]
        tok_names.append(tn)
    tx['tok_names'] = tok_names
    return tx

def parse_lmetaprop(fp, end=None, ver_maj=None, ver_min=None):
    if end == None or ver_maj == None or ver_min == None:
        fp, end, ver_maj, ver_min = get_region('L$MetaProp', fp)
    #print('%-12s %u.%u' % ('L$MetaProp', ver_maj, ver_min))
    mps = []
    while fp.tell() < end:
        mp = dict()
        mp['link_id'] = struct.unpack('<i', fp.read(4))[0]
        mp['source']  = struct.unpack('<i', fp.read(4))[0]
        mp['dest']    = struct.unpack('<i', fp.read(4))[0]
        mp['flavor']  = struct.unpack('<h', fp.read(2))[0]
        mps.append(mp)
    return mps

def parse_plight(fp, end=None, ver_maj=None, ver_min=None):
    if end == None or ver_maj == None or ver_min == None:
        fp, end, ver_maj, ver_min = get_region('P$Light', fp)
    #print('%-12s %u.%u' % ('P$Light', ver_maj, ver_min))
    lts = []
    while fp.tell() < end:
        mark = fp.tell()
        lt = dict()
        lt['obj_id']       = struct.unpack('<i', fp.read(4))[0]
        lt['len']          = struct.unpack('<I', fp.read(4))[0]; _len = lt['len']
        lt['brightness']   = struct.unpack('<f', fp.read(4))[0]; _len -= 4
        offset = dict()
        offset['x']        = struct.unpack('<f', fp.read(4))[0]; _len -= 4
        offset['y']        = struct.unpack('<f', fp.read(4))[0]; _len -= 4
        offset['z']        = struct.unpack('<f', fp.read(4))[0]; _len -= 4
        lt['offset'] = offset
        lt['radius']       = struct.unpack('<f', fp.read(4))[0]; _len -= 4
        if ver_maj >= 2 and ver_min > 20:
            lt['quad']         = bool(struct.unpack('<I', fp.read(4))[0]); _len -= 4
            lt['inner_radius'] = struct.unpack('<f', fp.read(4))[0]; _len -= 4
        if _len != 0:
            print_error('The P$Light parser poked its head out and was ended quick-like...')
            print('The fatal move occurred while it was parsing object %s at %u.' % (lt['obj_id'], mark))
            print('May it rest in peace eternal.')
            print()
            pprint.pp(lt)
            sys.exit(1)
        lts.append(lt)
    return lts

def parse_psymname(fp, end=None, ver_maj=None, ver_min=None):
    if end == None or ver_maj == None or ver_min == None:
        fp, end, ver_maj, ver_min = get_region('P$SymName', fp)
    #print('%-12s %u.%u' % ('P$SymName', ver_maj, ver_min))
    sns = []
    while fp.tell() < end:
        sn = dict()
        sn['obj_id'] = struct.unpack('<i', fp.read(4))[0]
        sn['len']    = struct.unpack('<I', fp.read(4))[0]
        sn['size']   = struct.unpack('<I', fp.read(4))[0]
        sn['name']   = fp.read(sn['size'])[:-1].decode('latin1')
        sns.append(sn)
    return sns

def parse_obj_map(fp, end=None, ver_maj=None, ver_min=None):
    if end == None or ver_maj == None or ver_min == None:
        fp, end, ver_maj, ver_min = get_region('OBJ_MAP', fp)
    #print('%-12s %u.%u' % ('OBJ_MAP', ver_maj, ver_min))
    oms = []
    while fp.tell() < end:
        om = dict()
        om['obj_id'] = struct.unpack('<i', fp.read(4))[0]
        om['size']   = struct.unpack('<I', fp.read(4))[0]
        om['name']   = fp.read(om['size'])[:-1].decode('latin1')
        oms.append(om)
    return oms

def parse_gam_file(fp, end=None, ver_maj=None, ver_min=None):
    if end == None or ver_maj == None or ver_min == None:
        fp, end, ver_maj, ver_min = get_region('GAM_FILE', fp)
    #print('%-12s %u.%u' % ('GAM_FILE', ver_maj, ver_min))
    return fp.read(256).split(b'\x00')[0].decode('latin1')

def parse_brlist(fp, end=None, ver_maj=None, ver_min=None):
    if end == None or ver_maj == None or ver_min == None:
        fp, end, ver_maj, ver_min = get_region('BRLIST', fp)
    #print('%-12s %u.%u' % ('BRLIST', ver_maj, ver_min))
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
        if br['media'] >= BR_TERRAIN:
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
            print_error('Something\'s going down with the brlist parser...')
            print('Okay. We gots us a problem at brush ' + str(len(brs)-1))
            print('Somewhere around position ' + str(mark))
            print('Current: ' + str(br['br_id']))
            print('Previous: ' + str(prev_br_id))
            print()
            pprint.pp(brs[-2])
            sys.exit(1)
        prev_br_id = br['br_id']
    return brs

def parse_unimplemented(fp, _len):
    return {'_base85': base64.b85encode(fp.read(_len)).decode('latin1')}

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
        print_error('This tagfile is either corrupt or not a tagfile at all.')
        sys.exit(1)

def to_dict(fp):
    tag_dict = dict()
    parse_tag = {
        canonical_tagname('BRLIST'):     parse_brlist,
        canonical_tagname('GAM_FILE'):   parse_gam_file,
        canonical_tagname('OBJ_MAP'):    parse_obj_map,
        canonical_tagname('P$SymName'):  parse_psymname,
        canonical_tagname('P$Light'):    parse_plight,
        canonical_tagname('L$MetaProp'): parse_lmetaprop,
        canonical_tagname('TXLIST'):     parse_txlist
    }

    fp.seek(0, os.SEEK_SET)
    toc_off = struct.unpack('<I', fp.read(4))[0]
    fp.seek(toc_off, os.SEEK_SET)
    toc_entries = struct.unpack('<I', fp.read(4))[0]
    while toc_entries:
        tagname = fp.read(12)
        tag_off = struct.unpack('<I', fp.read(4))[0]
        tag_len = struct.unpack('<I', fp.read(4))[0]
        prev_pos = fp.tell()
        fp.seek(tag_off+12, os.SEEK_SET)
        ver_maj = struct.unpack('<I', fp.read(4))[0]
        ver_min = struct.unpack('<I', fp.read(4))[0]
        fp.seek(4, os.SEEK_CUR)
        end = tag_off+tag_len+12
        try:
            parsed_tag = parse_tag[tagname](fp, end, ver_maj, ver_min)
        except KeyError:
            # We'll do something special like this for the AI tags eventually...
            #if m := re.search(b'AI_+([0-9A-Fa-f]+)_+([0-9A-Fa-f]+)_+([0-9A-Fa-f]+)', tagname):
            #    parse_ai(fp)
            #else:
            parsed_tag = parse_unimplemented(fp, tag_len)
        tag_dict[tagname] = parsed_tag
        fp.seek(prev_pos, os.SEEK_SET)
        toc_entries -= 1

    return tag_dict

def canonical_tagname(name):
    tagname_max = 12
    name = name[0:tagname_max]
    remaining_space = tagname_max - len(name)
    if type(name) == str:
        name += '\x00' * remaining_space
        return name.encode('latin1')
    else:
        name += b'\x00' * remaining_space
        return name

def main(args):
    funcs = {'parse_txlist':    parse_txlist,
             'parse_lmetaprop': parse_lmetaprop,
             'parse_plight':    parse_plight,
             'parse_psymname':  parse_psymname,
             'parse_obj_map':   parse_obj_map,
             'parse_gam_file':  parse_gam_file,
             'parse_brlist':    parse_brlist,
             'list_tags':       list_tags,
             'to_dict':         to_dict,
             'check_integrity': check_integrity}

    if len(args) < 3:
        print('arg1: Mission file')
        print('arg2: Func')
        return 1

    mis = args[1]
    func = funcs[args[2]]

    with open(mis, 'rb') as fp:
        rv = func(fp)
    pprint.pp(rv)

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
