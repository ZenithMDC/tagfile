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
import io
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

def concatenate_tag_version(ver_maj, ver_min):
    return str(ver_maj)+'.'+str(ver_min)

def split_tag_version(tagver):
    ver_maj, ver_min = str(tagver).split('.')
    return int(ver_maj), int(ver_min)

def write_tag_header(fp, tagname, tagver):
    tag_off = fp.tell()
    fp.write(canonicalize_tagname(tagname))
    ver_maj, ver_min = split_tag_version(tagver)
    fp.write(struct.pack('<I', ver_maj))
    fp.write(struct.pack('<I', ver_min))
    fp.write(struct.pack('<I', 0)) # ???
    return tag_off

def list_tags(fp):
    return [tag for tag in get_region('', fp)]

def get_region(tagname, fp):
    tags = []
    tagname = canonicalize_tagname(tagname)

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
            tags.append((toc_tag, region_off, region_len))
        elif tagname == toc_tag:
            found_tagname = True
            region_off = struct.unpack('<I', fp.read(4))[0]
            region_len = struct.unpack('<I', fp.read(4))[0]
            break
        else:
            fp.seek(8, os.SEEK_CUR)
        toc_entries -= 1
    if tagname[0] == 0:
        return sorted(tags, key=lambda tag: tag[1])
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
    txlist = {'version': concatenate_tag_version(ver_maj, ver_min)}
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
            tn_toks.append(struct.unpack('B', fp.read(1))[0])
        tn['tokens']   = tn_toks
        tn['name']     = struct.unpack('%us' % max_name_len, fp.read(max_name_len))[0].split(b'\x00')[0].decode('latin1')
        tn['reserved'] = struct.unpack('B', fp.read(1))[0]
        tok_names.append(tn)
    tx['tok_names'] = tok_names
    txlist['data'] = tx
    return txlist

def write_txlist(fp, txlist):
    tag_off = write_tag_header(fp, 'TXLIST', txlist['version'])
    max_tok_len = 16
    max_tokens_per = 4
    max_name_len = 15
    tx = txlist['data']
    fp.write(struct.pack('<i', tx['block_size']))
    fp.write(struct.pack('<i', tx['count']))
    fp.write(struct.pack('<i', tx['tok_count']))
    for token in tx['tokens']:
        fp.write(token.encode('latin1') + b'\x00' * (max_tok_len - len(token)))
    for tn in tx['tok_names']:
        for i in range(max_tokens_per):
            fp.write(struct.pack('B', tn['tokens'][i]))
        fp.write(tn['name'].encode('latin1') + b'\x00' * (max_name_len - len(tn['name'])))
        fp.write(struct.pack('B', tn['reserved']))
    tag_len = fp.tell() - tag_off - 24
    return tag_off, tag_len

def parse_lmetaprop(fp, end=None, ver_maj=None, ver_min=None):
    if end == None or ver_maj == None or ver_min == None:
        fp, end, ver_maj, ver_min = get_region('L$MetaProp', fp)
    #print('%-12s %u.%u' % ('L$MetaProp', ver_maj, ver_min))
    lmetaprop = {'version': concatenate_tag_version(ver_maj, ver_min)}
    mps = []
    while fp.tell() < end:
        mp = dict()
        mp['link_id'] = struct.unpack('<i', fp.read(4))[0]
        mp['source']  = struct.unpack('<i', fp.read(4))[0]
        mp['dest']    = struct.unpack('<i', fp.read(4))[0]
        mp['flavor']  = struct.unpack('<h', fp.read(2))[0]
        mps.append(mp)
    lmetaprop['data'] = mps
    return lmetaprop

def write_lmetaprop(fp, lmetaprop):
    tag_off = write_tag_header(fp, 'L$MetaProp', lmetaprop['version'])
    mps = lmetaprop['data']
    for mp in mps:
        fp.write(struct.pack('<i', mp['link_id']))
        fp.write(struct.pack('<i', mp['source']))
        fp.write(struct.pack('<i', mp['dest']))
        fp.write(struct.pack('<h', mp['flavor']))
    tag_len = fp.tell() - tag_off - 24
    return tag_off, tag_len

def parse_plight(fp, end=None, ver_maj=None, ver_min=None):
    if end == None or ver_maj == None or ver_min == None:
        fp, end, ver_maj, ver_min = get_region('P$Light', fp)
    plight = {'version': concatenate_tag_version(ver_maj, ver_min)}
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
    plight['data'] = lts
    return plight

def write_plight(fp, plight):
    tag_off = write_tag_header(fp, 'P$Light', plight['version'])
    ver_maj, ver_min = split_tag_version(plight['version'])
    lts = plight['data']
    for lt in lts:
        fp.write(struct.pack('<i', lt['obj_id']))
        fp.write(struct.pack('<I', lt['len']))
        fp.write(struct.pack('<f', lt['brightness']))
        offset = lt['offset']
        fp.write(struct.pack('<f', offset['x']))
        fp.write(struct.pack('<f', offset['y']))
        fp.write(struct.pack('<f', offset['z']))
        fp.write(struct.pack('<f', lt['radius']))
        if ver_maj >= 2 and ver_min > 20:
            fp.write(struct.pack('<I', lt['quad']))
            fp.write(struct.pack('<f', lt['inner_radius']))
    tag_len = fp.tell() - tag_off - 24
    return tag_off, tag_len

def parse_psymname(fp, end=None, ver_maj=None, ver_min=None):
    if end == None or ver_maj == None or ver_min == None:
        fp, end, ver_maj, ver_min = get_region('P$SymName', fp)
    psymname = {'version': concatenate_tag_version(ver_maj, ver_min)}
    #print('%-12s %u.%u' % ('P$SymName', ver_maj, ver_min))
    sns = []
    while fp.tell() < end:
        sn = dict()
        sn['obj_id'] = struct.unpack('<i', fp.read(4))[0]
        sn['len']    = struct.unpack('<I', fp.read(4))[0]
        sn['size']   = struct.unpack('<I', fp.read(4))[0]
        sn['name']   = fp.read(sn['size'])[:-1].decode('latin1')
        sns.append(sn)
    psymname['data'] = sns
    return psymname

def write_psymname(fp, psymname):
    tag_off = write_tag_header(fp, 'P$SymName', psymname['version'])
    sns = psymname['data']
    for sn in sns:
        fp.write(struct.pack('<i', sn['obj_id']))
        fp.write(struct.pack('<I', sn['len']))
        fp.write(struct.pack('<I', sn['size']))
        fp.write(sn['name'].encode('latin1') + b'\x00' * (sn['size'] - len(sn['name'])))
    tag_len = fp.tell() - tag_off - 24
    return tag_off, tag_len

def parse_obj_map(fp, end=None, ver_maj=None, ver_min=None):
    if end == None or ver_maj == None or ver_min == None:
        fp, end, ver_maj, ver_min = get_region('OBJ_MAP', fp)
    obj_map = {'version': concatenate_tag_version(ver_maj, ver_min)}
    #print('%-12s %u.%u' % ('OBJ_MAP', ver_maj, ver_min))
    oms = []
    while fp.tell() < end:
        om = dict()
        om['obj_id'] = struct.unpack('<i', fp.read(4))[0]
        om['size']   = struct.unpack('<I', fp.read(4))[0]
        om['name']   = fp.read(om['size'])[:-1].decode('latin1')
        oms.append(om)
    obj_map['data'] = oms
    return obj_map

def write_obj_map(fp, obj_map):
    tag_off = write_tag_header(fp, 'OBJ_MAP', obj_map['version'])
    oms = obj_map['data']
    for om in oms:
        fp.write(struct.pack('<i', om['obj_id']))
        fp.write(struct.pack('<I', om['size']))
        fp.write(om['name'].encode('latin1') + b'\x00' * (om['size'] - len(om['name'])))
    tag_len = fp.tell() - tag_off - 24
    return tag_off, tag_len

def parse_gam_file(fp, end=None, ver_maj=None, ver_min=None):
    if end == None or ver_maj == None or ver_min == None:
        fp, end, ver_maj, ver_min = get_region('GAM_FILE', fp)
    gam_file = {'version': concatenate_tag_version(ver_maj, ver_min)}
    #print('%-12s %u.%u' % ('GAM_FILE', ver_maj, ver_min))
    gam_file['data'] = fp.read(256).split(b'\x00')[0].decode('latin1')
    return gam_file

def write_gam_file(fp, gam_file):
    tag_off = write_tag_header(fp, 'GAM_FILE', gam_file['version'])
    fp.write(gam_file['data'].encode('latin1') + b'\x00' * (256 - len(gam_file['data'])))
    tag_len = fp.tell() - tag_off - 24
    return tag_off, tag_len

def parse_brlist(fp, end=None, ver_maj=None, ver_min=None):
    if end == None or ver_maj == None or ver_min == None:
        fp, end, ver_maj, ver_min = get_region('BRLIST', fp)
    #print('%-12s %u.%u' % ('BRLIST', ver_maj, ver_min))
    brlist = {'version': concatenate_tag_version(ver_maj, ver_min)}
    brs = []
    prev_br_id = 1
    while fp.tell() < end:
        mark = fp.tell()
        br = dict()
        br['br_id']          = struct.unpack('<h', fp.read(2))[0]
        br['timestamp']      = struct.unpack('<h', fp.read(2))[0]
        br['primal_id']      = struct.unpack('<i', fp.read(4))[0]
        br['tx_id']          = struct.unpack('<h', fp.read(2))[0]
        br['media']          = struct.unpack('b', fp.read(1))[0]
        br['flags']          = struct.unpack('b', fp.read(1))[0]
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
        br['num_faces']      = struct.unpack('B', fp.read(1))[0]
        br['edge']           = struct.unpack('b', fp.read(1))[0]
        br['point']          = struct.unpack('b', fp.read(1))[0]
        br['use_flg']        = struct.unpack('b', fp.read(1))[0]
        br['group_id']       = struct.unpack('b', fp.read(1))[0]
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
        brlist['data'] = brs
    return brlist

def write_brlist(fp, brlist):
    tag_off = write_tag_header(fp, 'BRLIST', brlist['version'])
    brs = brlist['data']
    for br in brs:
        fp.write(struct.pack('<h', br['br_id']))
        fp.write(struct.pack('<h', br['timestamp']))
        fp.write(struct.pack('<i', br['primal_id']))
        fp.write(struct.pack('<h', br['tx_id']))
        fp.write(struct.pack('b', br['media']))
        fp.write(struct.pack('b', br['flags']))
        pos = br['pos']
        fp.write(struct.pack('<f', pos['x']))
        fp.write(struct.pack('<f', pos['y']))
        fp.write(struct.pack('<f', pos['z']))

        sz = br['sz']
        fp.write(struct.pack('<f', sz['d']))
        fp.write(struct.pack('<f', sz['w']))
        fp.write(struct.pack('<f', sz['h']))

        ang = br['ang']
        fp.write(struct.pack('<H', ang['tx']))
        fp.write(struct.pack('<H', ang['ty']))
        fp.write(struct.pack('<H', ang['tz']))

        fp.write(struct.pack('<h', br['cur_face']))
        grid = br['grid']
        fp.write(struct.pack('<f', grid['line_spacing']))
        phase_shift = grid['phase_shift']
        fp.write(struct.pack('<f', phase_shift['x']))
        fp.write(struct.pack('<f', phase_shift['y']))
        fp.write(struct.pack('<f', phase_shift['z']))

        orientation = grid['orientation']
        fp.write(struct.pack('<H', orientation['tx']))
        fp.write(struct.pack('<H', orientation['ty']))
        fp.write(struct.pack('<H', orientation['tz']))

        fp.write(struct.pack('<?', grid['grid_enabled']))

        fp.write(struct.pack('B', br['num_faces']))
        fp.write(struct.pack('b', br['edge']))
        fp.write(struct.pack('b', br['point']))
        fp.write(struct.pack('b', br['use_flg']))
        fp.write(struct.pack('b', br['group_id']))
        fp.write(struct.pack('<i', br['pad0']))

        if br['media'] >= BR_TERRAIN:
            for i in range(br['num_faces']):
                texinfo = br['txs'][i]
                fp.write(struct.pack('<h', texinfo['tx_id']))
                fp.write(struct.pack('<H', texinfo['tx_rot']))
                fp.write(struct.pack('<h', texinfo['tx_scale']))
                fp.write(struct.pack('<H', texinfo['tx_x']))
                fp.write(struct.pack('<H', texinfo['tx_y']))
    tag_len = fp.tell() - tag_off - 24
    return tag_off, tag_len

def parse_unimplemented(fp, ver_maj, ver_min, _len):
    unimplemented = {
        'version': concatenate_tag_version(ver_maj, ver_min),
        'data': {'_base85': base64.b85encode(fp.read(_len)).decode('latin1')}
    }
    return unimplemented

def write_unimplemented(fp, tagname, unimplemented):
    tag_off = write_tag_header(fp, tagname, unimplemented['version'])
    fp.write(base64.b85decode(unimplemented['data']['_base85']))
    tag_len = fp.tell() - tag_off - 24
    return tag_off, tag_len

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
        canonicalize_tagname('BRLIST'):     parse_brlist,
        canonicalize_tagname('GAM_FILE'):   parse_gam_file,
        canonicalize_tagname('OBJ_MAP'):    parse_obj_map,
        canonicalize_tagname('P$SymName'):  parse_psymname,
        canonicalize_tagname('P$Light'):    parse_plight,
        canonicalize_tagname('L$MetaProp'): parse_lmetaprop,
        canonicalize_tagname('TXLIST'):     parse_txlist
    }

    fp.seek(0, os.SEEK_SET)
    toc_off = struct.unpack('<I', fp.read(4))[0]
    toc_ver_maj = struct.unpack('<I', fp.read(4))[0]
    toc_ver_min = struct.unpack('<I', fp.read(4))[0]
    fp.seek(268, os.SEEK_SET)
    toc_deadbeef = struct.unpack('>I', fp.read(4))[0]
    tag_dict['__toc_header__'] = {
        'offset': toc_off,
        'version': concatenate_tag_version(toc_ver_maj, toc_ver_min),
        'deadbeef': toc_deadbeef,
        'toc_idx': -1,
        'tag_off': 0
    }
    fp.seek(toc_off, os.SEEK_SET)
    toc_entries = struct.unpack('<I', fp.read(4))[0]
    for i in range(toc_entries):
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
            #    parsed_tag = parse_ai(fp)
            #else:
            parsed_tag = parse_unimplemented(fp, ver_maj, ver_min, tag_len)
        parsed_tag['toc_idx'] = i
        parsed_tag['tag_off'] = tag_off
        tag_dict[tagname] = parsed_tag
        fp.seek(prev_pos, os.SEEK_SET)

    return dict(sorted(tag_dict.items(), key=lambda d: d[1]['tag_off']))

def from_dict(fp, tag_dict):
    toc = []
    write_tag = {
        canonicalize_tagname('BRLIST'):     write_brlist,
        canonicalize_tagname('GAM_FILE'):   write_gam_file,
        canonicalize_tagname('OBJ_MAP'):    write_obj_map,
        canonicalize_tagname('P$SymName'):  write_psymname,
        canonicalize_tagname('P$Light'):    write_plight,
        canonicalize_tagname('L$MetaProp'): write_lmetaprop,
        canonicalize_tagname('TXLIST'):     write_txlist
    }

    # Reserve the TOC header block.
    fp.write(b'\x00'*272)

    num_tags = 0
    for tag in tag_dict.keys():
        if tag == '__toc_header__':
            continue
        try:
            tag_off, tag_len = write_tag[tag](fp, tag_dict[tag])
        except KeyError:
            # We'll do something special like this for the AI tags eventually...
            #if m := re.search(b'AI_+([0-9A-Fa-f]+)_+([0-9A-Fa-f]+)_+([0-9A-Fa-f]+)', tagname):
            #    tag_off, tag_len = write_ai(fp, tag)
            #else:
            tag_off, tag_len = write_unimplemented(fp, tag, tag_dict[tag])
        toc.append({'tagname': tag, 'tag_off': tag_off, 'tag_len': tag_len, 'toc_idx': tag_dict[tag]['toc_idx']})
        num_tags += 1

    toc = sorted(toc, key=lambda d: d['toc_idx'])

    toc_off = struct.pack('<I', fp.tell())
    fp.write(struct.pack('<I', num_tags))
    for entry in toc:
        fp.write(entry['tagname'])
        fp.write(struct.pack('<I', entry['tag_off']))
        fp.write(struct.pack('<I', entry['tag_len']))

    # Backpatch the TOC header.
    fp.seek(0, os.SEEK_SET)
    toc_ver_maj, toc_ver_min = split_tag_version(tag_dict['__toc_header__']['version'])
    fp.write(toc_off)
    fp.write(struct.pack('<I', toc_ver_maj))
    fp.write(struct.pack('<I', toc_ver_min))
    fp.seek(268, os.SEEK_SET)
    fp.write(struct.pack('>I', 0xdeadbeef))

    return fp

def canonicalize_tagname(name):
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
             'from_dict':       from_dict}

    if len(args) < 3:
        print('arg1: Tag file (.mis .gam ...etc)')
        print('arg2: Func')
        return 1

    tagfile = args[1]
    func = funcs[args[2]]

    with open(tagfile, 'rb') as fp:
        check_integrity(fp)
        if func != from_dict:
            rv = func(fp)
        else:
            rv = to_dict(fp)
    if func != from_dict:
        pprint.pp(rv)
    else:
        with io.BytesIO() as iobuf:
            iobuf = from_dict(iobuf, rv)
            sys.stdout.buffer.write(iobuf.getvalue())

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
