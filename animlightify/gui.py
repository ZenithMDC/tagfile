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
# GUI for Animlightify, for those with an uncordial disposition towards command
# lines and tweaking config files.
#

# XXX Clearing the output log doesn't free the memory reserved for the text, and
# it seems there's nothing that can be done about this. Would've been nice to be
# able to configure a maximum buffer size and have it behave like a ring buffer,
# but oh well...
#
# It also would've been nice to be able to use lambdas in place of the status
# bind functions, but Python doesn't allow assigning subscripted vars in them.
#

import os
import re
import io
import sys
import threading
import subprocess
import queue
import time
import tkinter.filedialog
import tkinter as tk
from tkinter import ttk

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import utils
import animlightify

brs_queue = queue.Queue()

# This is here so widgets instantiated before the Inital Root section don't end
# up creating extraneous windows.
root = tk.Tk()

# Pseudo-forward declarations.
label_status = ttk.Label()
gamesys_version = None
button_run_mode = 'animlightify'
button_run_animlightify = None
progressbar_run = ttk.Progressbar()

def thief_path_is_valid():
    tpath = {1: entry_t1r.get()+'/thief.exe', 2: entry_t2r.get()+'/thief2.exe'}
    return os.path.exists(tpath[gamesys_version])

# XXX Invoking powershell is slow... need a better method. TASKLIST doesn't have
# any information avaliable regarding a process's path, so that's out. WMIC is
# no longer available on Windows 11, so that, too, is out. Ugh... Perhaps I'll
# be needing to get the relevant info from WINAPI and access it from Python via
# CFFI. ...Or maybe try something saner like pywin32... idk.
def dromed_is_running():
    troot = {1: entry_t1r.get().lower(), 2: entry_t2r.get().lower()}
    result = subprocess.run(
        'powershell -Command "Get-Process dromed | Select-Object -ExpandProperty Path"',
        capture_output=True,
        text=True
    )

    if result.stderr:
        #print('dromed_is_running: False')
        return False

    drompaths = [dp.lower() for dp in result.stdout.strip().replace('\\', '/').split('\n')]
    for drompath in drompaths:
        #print(f'Comparing {troot[gamesys_version]}/dromed.exe and {drompath}')
        if f'{troot[gamesys_version]}/dromed.exe' == drompath:
            #print('dromed_is_running: True')
            return True

# XXX Invoking powershell is slow... need a better method.
# TODO Check the version once, then store the file's timestamp and see if it
# changes. If it does, then check the version again. Should be much cheaper to
# do that.
def dromed_version_is_valid():
    troot = {1: entry_t1r.get(), 2: entry_t2r.get()}
    result = subprocess.run(
        f'powershell -Command "(Get-Item {troot[gamesys_version]}/dromed.exe).VersionInfo.ProductVersion"',
        capture_output=True,
        text=True
    )

    ver_maj, ver_min = [int(ver_part) for ver_part in result.stdout.strip().split('.')]
    #print(f'dromed_version_is_valid: {ver_maj >= 1 and ver_min >= 29}')
    return ver_maj >= 1 and ver_min >= 29

def dromed_path_is_valid():
    troot = {1: entry_t1r.get(), 2: entry_t2r.get()}
    drompath = {1: troot[1]+'/dromed.exe', 2: troot[2]+'/dromed.exe'}
    return os.path.exists(troot[gamesys_version]) and os.path.exists(drompath[gamesys_version])

def set_button_state(button, state_true, state_false, condition):
    button['state'] = state_true if condition else state_false

def populate_entry_with_filename(entry, title='Open File', filetypes=[]):
    filetypes.append(('All Files', '*.*'))
    if filepath := tk.filedialog.askopenfilename(title=title, filetypes=filetypes):
        entry.delete(0, 'end')
        entry.insert(0, filepath)

def populate_entry_with_dirname(entry, title='Select Folder'):
    if dirpath := tk.filedialog.askdirectory(title=title):
        entry.delete(0, 'end')
        entry.insert(0, dirpath)

def set_entry_value(entry, value):
    entry.delete(0, 'end')
    entry.insert(0, str(value))

def validate_success():
    set_button_run_mode_animlightify(state='normal' if len(entry_mf.get()) else 'disabled')
    label_status['text'] = ''
    return True

def validate_failure():
    root.bell()
    return False

def validate_float_entry(value, state, clamp={'min': None, 'max': None}):
    if not value:
        return validate_success()
    state['incomplete'] = True
    if 'min' not in clamp:
        clamp['min'] = None
    if 'max' not in clamp:
        clamp['max'] = None

    if not value or value == '.':
        return validate_success()

    clamp_min_exists = clamp['min'] != None
    clamp_max_exists = clamp['max'] != None
    re_negative = r'-?'
    if clamp_min_exists and clamp_max_exists:
        if sinage := float(clamp['min']) < 0.0 and float(clamp['max']) < 0.0:
            re_negative = r'-'
        elif float(clamp['min']) >= 0.0 and float(clamp['max']) >= 0.0:
            re_negative = r''
    elif clamp_min_exists and float(clamp['min']) >= 0.0:
            re_negative = r''
    elif clamp_max_exists and float(clamp['max']) < 0.0:
            re_negative = '-'
    else:
        sinage = False

    if re.search(r'^' + re_negative + r'(?:0|[1-9][0-9]*)?(?:\.[0-9]*)?$', value):
        try:
            float(value)
        except:
            value = '0'

        #debug
        #utils.log_print(f'{float(value)} {clamp["min"]} {clamp["max"]}')
        #debug

        if clamp_min_exists:
            if float(value) < clamp['min']:
                if ((not sinage and value.find('.') != -1) or sinage) or \
                len(value) >= len(str(clamp['min']).split('.')[0]):
                    label_status['text'] = f'Value cannot subceed {clamp["min"]}.'
                    label_status['text'] += f' Valid range is {clamp["min"]} to {clamp["max"]}, inclusive.' if clamp_max_exists else ''
                    return validate_failure()
                else:
                    return validate_success()
        if clamp_max_exists:
            if float(value) > clamp['max']:
                if ((sinage and value.find('.') != -1) or not sinage) or \
                len(value) >= len(str(clamp['max']).split('.')[0]):
                    label_status['text'] = f'Value cannot exceed {clamp["max"]}.'
                    label_status['text'] += f' Valid range is {clamp["min"]} to {clamp["max"]}, inclusive.' if clamp_min_exists else ''
                    return validate_failure()
                else:
                    return validate_success()
        state['incomplete'] = False
        return validate_success()
    else:
        if clamp_min_exists and clamp_max_exists:
            label_status['text'] = f'Valid range is {clamp["min"]} to {clamp["max"]}, inclusive.'
        elif clamp_min_exists:
            label_status['text'] = f'Valid range is {clamp["min"]} to ∞, inclusive.'
        elif clamp_max_exists:
            label_status['text'] = f'Valid range is -∞ to {clamp["max"]}, inclusive.'
        return validate_failure()

def validate_float_entry_final(entry, default_value, state, clamp={'min': None, 'max': None}):
    if not entry.get() or entry.get() in ['.', '-']:
        set_entry_value(entry, default_value)
        return
    if 'min' not in clamp:
        clamp['min'] = None
    if 'max' not in clamp:
        clamp['max'] = None
    value = float(entry.get())
    entry.delete(0, 'end')
    if state['incomplete']:
        if clamp['min'] != None and value < clamp['min']:
            entry.insert(0, str(clamp['min']))
        elif clamp['max'] != None and value > clamp['max']:
            entry.insert(0, str(clamp['max']))
    entry.insert(0, value)

def set_button_run_mode_animlightify(state='normal', reset_progressbar=True):
    global button_run_mode
    button_run_mode = 'animlightify'
    button_run.configure(text='Animlightify', command=button_run_animlightify)
    if state:
        button_run['state'] = state
    if reset_progressbar:
        progressbar_run['value'] = 0

def set_button_run_mode_dromed(state='normal', reset_progressbar=True):
    global button_run_mode
    button_run_mode = 'dromed'
    button_run.configure(text=f'Launch T{gamesys_version} DromEd', command=button_run_dromed)
    if state:
        button_run['state'] = state
    if reset_progressbar:
        progressbar_run['value'] = 0

# Initialize Root ==============================================================
# Root is instantiated at the top of this file.
root.iconbitmap(utils.get_pyi_asset('res/logo.ico'))
root.title(f'Animlightify v{animlightify.version["string"]}')

gui_width = animlightify.config['gui_width']['value']
gui_height = animlightify.config['gui_height']['value']

geometry_str = f'{gui_width}x{gui_height}'
match animlightify.config['gui_position_mode']['value']:
    case 'OS':
        geometry_str = ''
    case 'Stored':
        gui_pos_x = animlightify.config['gui_pos_x']['value']
        gui_pos_y = animlightify.config['gui_pos_y']['value']
        geometry_str += f'+{gui_pos_x}+{gui_pos_y}'
    case 'Centered' | _:
        gui_pos_x = (root.winfo_screenwidth() - gui_width) // 2
        gui_pos_y = (root.winfo_screenheight() - gui_height) // 2
        geometry_str += f'+{gui_pos_x}+{gui_pos_y}'

root.geometry(geometry_str)
root.minsize(animlightify.config['gui_width']['default'], animlightify.config['gui_height']['default'])
root.update()

def root_on_close():
    if animlightify_thread and animlightify_thread.is_alive():
        return
    validate_float_entry_final(entry_ob, animlightify.config['outer_bound']['default'], entry_ob_state)
    validate_float_entry_final(entry_ib, animlightify.config['inner_bound']['default'], entry_ib_state)
    validate_float_entry_final(entry_wlv, animlightify.config['wl_volume']['default'], entry_wlv_state)
    update_config_vars()
    utils.write_config(animlightify.config_name, animlightify.config)
    root.destroy()

root.protocol('WM_DELETE_WINDOW', root_on_close)

# Initialize Frames ============================================================
frame_mf = ttk.LabelFrame(root, text='Mission File', labelanchor='n', pad=10)
frame_log = ttk.LabelFrame(root, text='Output Log', labelanchor='n', pad=10)
frame_cfg = ttk.LabelFrame(root, text='Configuration', labelanchor='n', pad=10)
frame_run = ttk.LabelFrame(root, text='Run', labelanchor='n', pad=10)
frame_status = ttk.Frame(root, relief="flat", pad=2)

root.columnconfigure((0,1), weight=2, uniform='_')
root.columnconfigure(1, weight=3)
root.rowconfigure((1), weight=1)
frame_mf.grid(row=0, column=0, sticky='new', padx=5, pady=(5,0))
frame_log.grid(row=0, rowspan=3, column=1, sticky='nesw', padx=(0,5), pady=(5,5))
frame_cfg.grid(row=1, column=0, sticky='nesw', padx=5, pady=(5,0))
frame_run.grid(row=2, column=0, sticky='new', padx=5, pady=(5,5))
frame_status.grid(row=3, column=0, columnspan=2, sticky='ew')

# Mission File Widgets =========================================================
def entry_mf_trace(var):
    if len(var.get()):
        set_button_run_mode_animlightify()
    else:
        button_run['state'] = 'disabled'
        progressbar_run['value'] = 0
    #style.configure('text.Horizontal.TProgressbar', text='0 %')

stringvar_entry_mf = tk.StringVar()
stringvar_entry_mf.trace_add('write', lambda name, index, mode, var=stringvar_entry_mf: entry_mf_trace(var))
button_mf = ttk.Button(frame_mf, text='Choose', pad=-1, command=lambda: populate_entry_with_filename(entry_mf, title='Select Mission File', filetypes=[('Mission Files', '*.mis')]))
entry_mf = ttk.Entry(frame_mf, textvariable=stringvar_entry_mf)

frame_mf.columnconfigure(1, weight=1)
button_mf.grid(row=0, column=0, sticky='nw')
entry_mf.grid(row=0, column=1, sticky='new', padx=(10,0))

# Configuration Widgets ========================================================
def update_config_vars():
    animlightify.config['t1_root']['value'] = entry_t1r.get()
    animlightify.config['t2_root']['value'] = entry_t2r.get()
    animlightify.config['outer_bound']['value'] = float(entry_ob.get())
    animlightify.config['inner_bound']['value'] = float(entry_ib.get())
    animlightify.config['wl_volume']['value'] = float(entry_wlv.get())
    animlightify.config['gui_width']['value'] = int(root.winfo_width())
    animlightify.config['gui_height']['value'] = int(root.winfo_height())
    animlightify.config['gui_pos_x']['value'] = int(root.winfo_rootx())
    animlightify.config['gui_pos_y']['value'] = int(root.winfo_rooty())
    #animlightify.config['gui_position_mode']['value'] = <This isn't modified at runtime>
    #animlightify.config['gui_auto_clear_log']['value'] = bool(<This isn't modified at runtime>)

button_run = ttk.Button()

def entry_troot_trace(var):
    if button_run_mode == 'dromed' and thief_path_is_valid() and dromed_path_is_valid():
        button_run['state'] = 'normal'
    else:
        if not entry_mf.get():
            button_run['state'] = 'disabled'

label_paths = ttk.Label(frame_cfg, text='Paths')
label_t1r = ttk.Label(frame_cfg, text='t1_root')
label_t2r = ttk.Label(frame_cfg, text='t2_root')
label_wlp = ttk.Label(frame_cfg, text='Window Light Parameters')
label_ob = ttk.Label(frame_cfg, text='outer_bound')
label_ib = ttk.Label(frame_cfg, text='inner_bound')
label_wlv = ttk.Label(frame_cfg, text='wl_volume')

button_t1r = ttk.Button(frame_cfg, text='t1_root', pad=-1, command=lambda: populate_entry_with_dirname(entry_t1r, title='Select Thief 1 Root Directory'))
stringvar_entry_t1r = tk.StringVar()
stringvar_entry_t1r.trace_add('write', lambda name, index, mode, var=stringvar_entry_t1r: entry_troot_trace(var))
entry_t1r = ttk.Entry(frame_cfg, textvariable=stringvar_entry_t1r)
set_entry_value(entry_t1r, animlightify.config['t1_root']['value'])

button_t2r = ttk.Button(frame_cfg, text='t2_root', pad=-1, command=lambda: populate_entry_with_dirname(entry_t2r, title='Select Thief 2 Root Directory'))
stringvar_entry_t2r = tk.StringVar()
stringvar_entry_t2r.trace_add('write', lambda name, index, mode, var=stringvar_entry_t2r: entry_troot_trace(var))
entry_t2r = ttk.Entry(frame_cfg, textvariable=stringvar_entry_t2r)
set_entry_value(entry_t2r, animlightify.config['t2_root']['value'])

entry_ob_clamp = animlightify.config['outer_bound']['clamp']
entry_ob_state = dict()
entry_ob = ttk.Entry(frame_cfg, validate='key', validatecommand=(frame_cfg.register(lambda value: validate_float_entry(value, entry_ob_state, clamp=entry_ob_clamp)), '%P'))
set_entry_value(entry_ob, animlightify.config['outer_bound']['value'])
entry_ob.bind('<FocusOut>', lambda event: validate_float_entry_final(entry_ob, animlightify.config['outer_bound']['default'], entry_ob_state))

entry_ib_clamp = animlightify.config['inner_bound']['clamp']
entry_ib_state = dict()
entry_ib = ttk.Entry(frame_cfg, validate='key', validatecommand=(frame_cfg.register(lambda value: validate_float_entry(value, entry_ib_state, clamp=entry_ib_clamp)), '%P'))
set_entry_value(entry_ib, animlightify.config['inner_bound']['value'])
entry_ib.bind('<FocusOut>', lambda event: validate_float_entry_final(entry_ib, animlightify.config['inner_bound']['default'], entry_ib_state))

entry_wlv_clamp = animlightify.config['wl_volume']['clamp']
entry_wlv_state = dict()
entry_wlv = ttk.Entry(frame_cfg, validate='key', validatecommand=(frame_cfg.register(lambda value: validate_float_entry(value, entry_wlv_state, clamp=entry_wlv_clamp)), '%P'))
set_entry_value(entry_wlv, animlightify.config['wl_volume']['value'])
entry_wlv.bind('<FocusOut>', lambda event: validate_float_entry_final(entry_wlv, animlightify.config['wl_volume']['default'], entry_wlv_state, clamp=entry_wlv_clamp))

frame_cfg.columnconfigure(1, weight=1)
frame_cfg.rowconfigure((1,4,5), pad=5)
label_paths.grid(row=0, columnspan=3, pady=(0,0))
entry_t1r.grid(row=1, column=1, columnspan=2, sticky='new')
button_t1r.grid(row=1, column=0, sticky='nw')
button_t2r.grid(row=2, column=0, sticky='nw')
entry_t2r.grid(row=2, column=1, columnspan=2, sticky='new')
label_wlp.grid(row=3, columnspan=3, pady=(10,0))
label_ob.grid(row=4, sticky='ne', padx=(0,10))
entry_ob.grid(row=4, column=1, sticky='new')
label_ib.grid(row=5, sticky='ne', padx=(0,10))
entry_ib.grid(row=5, column=1, sticky='new')
label_wlv.grid(row=6, sticky='ne', padx=(0,10))
entry_wlv.grid(row=6, column=1, sticky='new')

# Log Widgets ==================================================================
def text_log_write(msg):
    text_log['state'] = 'normal'
    lines = msg.split('\n')
    for line in lines:
        text_log.insert('end', line+'\n')
        text_log.see('end')
    text_log['state'] = 'disabled'

def text_log_clear():
    text_log['state'] = 'normal'
    text_log.delete('1.0', 'end')
    text_log['state'] = 'disabled'

text_log = tk.Text(frame_log, state='disabled', bg=root['bg'])
scrollbar_log = ttk.Scrollbar(frame_log)
button_log = ttk.Button(frame_log, text='Clear', pad=-1, command=text_log_clear)

text_log.place(width=-scrollbar_log.winfo_reqwidth(), height=-button_log.winfo_reqheight()-10, relwidth=1.0, relheight=1.0)
scrollbar_log.pack(side='right', fill='y', pady=(0,button_log.winfo_reqheight()+10))
button_log.pack(side='bottom', padx=(scrollbar_log.winfo_reqwidth(),0))
text_log.config(yscrollcommand=scrollbar_log.set)
scrollbar_log.config(command=text_log.yview)

# Run Widgets ==================================================================
#style = ttk.Style(root)
#style.layout('text.Horizontal.TProgressbar',
#             [('Horizontal.Progressbar.trough',
#              {'children': [('Horizontal.Progressbar.pbar',
#                             {'side': 'left', 'sticky': 'ns'})],
#               'sticky': 'nswe'}),
#             ('Horizontal.Progressbar.label', {'sticky': ''})])
#style.configure('text.Horizontal.TProgressbar', text='0 %')

animlightify_thread = None
dromed_thread = None

def watch_animlightify_thread():
    global gamesys_version
    global dromed_thread
    if not animlightify_thread.is_alive():
        #print('animlightify_thread is dead.')
        if not utils.gv_queue.empty():
            gamesys_version = utils.gv_queue.get_nowait()
        else:
            # Something went wrong...
            set_button_run_mode_animlightify()
            return
        try:
            animlightify_thread.result
        except AttributeError:
            # Assume animlightify sys.exit(1)'d.
            set_button_run_mode_animlightify()
            return
        if dromed_path_is_valid():
            button_run['state'] = 'normal'
        else:
            pass
        set_button_run_mode_dromed(state='disabled', reset_progressbar=False)

        if not dromed_version_is_valid():
            tk.messagebox.showwarning(title='Warning', message=f'You need to upgrade to Dromed 1.29 for Thief {gamesys_version}.')
        dromed_thread = threading.Thread(target=check_dromed, daemon=True)
        dromed_thread.start()
        root.after(0, watch_for_dromed_state_changes)
        return
    #print('animlightify_thread is alive.')
    root.after(100, watch_animlightify_thread)

def watch_for_dromed_state_changes():
    #print('watch_for_dromed_state_changes')
    if button_run_mode == 'dromed' and dromed_thread and dromed_thread.is_alive():
        if not brs_queue.empty():
            #print('Got something...')
            button_run['state'] = brs_queue.get_nowait()
        root.after(500, watch_for_dromed_state_changes)

def update_progressbar():
    if not animlightify_thread.is_alive():
        try:
            rv = animlightify_thread.result
        except AttributeError:
            rv = 1 # Assume animlightify sys.exit(1)'d.

        if rv == 0:
            progressbar_run['value'] = 100
            #style.configure('text.Horizontal.TProgressbar', text='100 %')
        else:
            tk.messagebox.showerror(title='Error', message='An error occurred while processing.\nCheck the output log for details.')
        return
    if not utils.pb_queue.empty():
        progressbar_run['value'] += utils.pb_queue.get_nowait()
        #style.configure('text.Horizontal.TProgressbar', text=f'{progressbar_run["value"]:.2f} %')
    root.after(16, update_progressbar)

def button_run_animlightify():
    global animlightify_thread
    update_config_vars()
    if animlightify.config['gui_auto_clear_log']['value']:
        text_log_clear()
    button_run['state'] = 'disabled'
    progressbar_run['value'] = 0
    animlightify_thread = utils.ThreadWithResult(target=animlightify.main, args=[['gui', stringvar_entry_mf.get()]])
    animlightify_thread.start()
    root.after(0, watch_animlightify_thread)
    root.after(0, update_progressbar)

# This function is run on a separate thread, 'cause it's slow...
def check_dromed():
    #print('check_dromed')
    while True:
        if button_run_mode == 'dromed':
            if not thief_path_is_valid() \
            or not dromed_path_is_valid() \
            or not dromed_version_is_valid() \
            or dromed_is_running():
                if str(button_run['state']) != 'disabled':
                    #print('setting disabled')
                    brs_queue.put_nowait('disabled')
            else:
                if str(button_run['state']) != 'normal':
                    #print('setting normal')
                    brs_queue.put_nowait('normal')
        else:
            #print('check_dromed terminated')
            return
        time.sleep(1)

def button_run_dromed():
    troot = {1: entry_t1r.get(), 2: entry_t2r.get()}
    drompath = {1: troot[1]+'/dromed.exe', 2: troot[2]+'/dromed.exe'}
    button_run['state'] = 'disabled'
    subprocess.Popen(drompath[gamesys_version], cwd=troot[gamesys_version])

label_run = ttk.Label(frame_run, text='Progress')
button_run = ttk.Button(frame_run, state='disabled', text='Animlightify', pad=5, command=button_run_animlightify)
progressbar_run = ttk.Progressbar(frame_run, orient='horizontal', mode='determinate', style='text.Horizontal.TProgressbar')

button_run.pack()
label_run.pack(pady=(10,0))
progressbar_run.pack(fill='both')

# Status Widgets ===============================================================
label_status = ttk.Label(frame_status, text='')
label_status.pack(side='left')

# Status Binds =================================================================
def get_valid_range(_type, clamp):
    s = f'({_type}'
    if clamp_min_exists := 'min' in clamp and clamp['min'] != None:
        clamp_min_sign = '-' if float(clamp['min']) < 0.0 else ''
    if clamp_max_exists := 'max' in clamp and clamp['max'] != None:
        clamp_max_sign = '-' if float(clamp['max']) < 0.0 else ''
        clamp_min_sign = clamp_max_sign
    if clamp_min_exists and clamp_max_exists:
        s += f'[{clamp["min"]}, {clamp["max"]}])  '
    elif clamp_min_exists:
        s += f'[{clamp["min"]}, ∞])  '
    elif clamp_max_exists:
        s += f'[-∞, {clamp["max"]}])  '
    else:
        s += ')  '
    return s
def button_mf_bind_enter(event): label_status['text'] = 'Choose the mission file you wish to process.'
def entry_mf_bind_enter(event): label_status['text'] = '(string)  Path to the mission file.'
def button_t1r_bind_enter(event): label_status['text'] = 'Choose Thief 1\'s root directory.'
def button_t2r_bind_enter(event): label_status['text'] = 'Choose Thief 2\'s root directory.'
def entry_t1r_bind_enter(event): label_status['text'] = '(string)  Root directory for Thief 1, which must be specified for FMs that use the default gamesys.'
def entry_t2r_bind_enter(event): label_status['text'] = '(string)  Root directory for Thief 2, which must be specified for FMs that use the default gamesys.'
def entry_ob_bind_enter(event): label_status['text'] = get_valid_range('float', entry_ob_clamp) + animlightify.config['outer_bound']['description']
def entry_ib_bind_enter(event): label_status['text'] = get_valid_range('float', entry_ib_clamp) + animlightify.config['inner_bound']['description']
def entry_wlv_bind_enter(event): label_status['text'] = get_valid_range('float', entry_wlv_clamp) + animlightify.config['wl_volume']['description']
def button_log_bind_enter(event): label_status['text'] = 'Erase the contents of the output log.'
def button_run_bind_enter(event):
    if button_run_mode == 'animlightify':
        msg = 'Generate a DML to convert all brush/static lights to animlights'
        if str(button_run['state']) == 'disabled':
            if not animlightify_thread or not animlightify_thread.is_alive():
                msg += ' (you need to choose a mission file first)'
    elif button_run_mode == 'dromed':
        msg = f'Launch DromEd for Thief {gamesys_version}'
        # Also check if the process is already running...
        if not thief_path_is_valid():
            msg += f' (Invalid t{gamesys_version}_root path)'
        elif not dromed_path_is_valid():
            msg += f' (you need to install DromEd 1.29 for Thief {gamesys_version} first)'
        elif str(button_run['state']) == 'disabled':
            msg += ' (either already running or wrong version)'
        # Sadly, these checks are too slow...
        #elif not dromed_version_is_valid():
        #    msg += f' (you need to upgrade DromEd to 1.29 for Thief {gamesys_version} first)'
        #elif dromed_is_running():
        #    msg += ' (already running)'
    label_status['text'] = msg + '.'
def bind_leave(event): label_status['text'] = ''

button_mf.bind('<Enter>', button_mf_bind_enter)
entry_mf.bind('<Enter>', entry_mf_bind_enter)
button_t1r.bind('<Enter>', button_t1r_bind_enter)
button_t2r.bind('<Enter>', button_t2r_bind_enter)
entry_t1r.bind('<Enter>', entry_t1r_bind_enter)
entry_t2r.bind('<Enter>', entry_t2r_bind_enter)
entry_ob.bind('<Enter>', entry_ob_bind_enter)
entry_ib.bind('<Enter>', entry_ib_bind_enter)
entry_wlv.bind('<Enter>', entry_wlv_bind_enter)
button_log.bind('<Enter>', button_log_bind_enter)
button_run.bind('<Enter>', button_run_bind_enter)
root.bind('<Leave>', bind_leave)

# Main Loop =====================================================================
utils.log_print_callback = text_log_write
sys.exit(root.mainloop())
