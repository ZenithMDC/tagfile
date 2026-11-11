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

import sys
import winreg
import os
import os.path

def reg_value(hive, path, subkey):
    try:
        #print('Searching: ', hive, path, subkey)
        with winreg.OpenKeyEx(hive, path) as key:
            return winreg.QueryValueEx(key, subkey)[0]
    except FileNotFoundError:
        return None

def report(path, label):
    if not path or not os.path.exists(path):
        path = '-NOT DETECTED-'
    max_path = 48
    dots = '...'
    if len(path) > max_path:
        path = dots + path[-(max_path - len(dots)):]
    print(('%-' + str(max_path) + 's %s') % (path, label))

def is64BitOS():
    return (
        os.environ.get('PROCESSOR_ARCHITEW6432', '') or
        os.environ.get('PROCESSOR_ARCHITECTURE', '')
    ) == 'AMD64'

class SteamPath():
    label = 'Steam'
    reg = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App '

    def __init__(self, appid, subdir=''):
        self.appid = appid
        self.subdir = subdir

    def full_path(self):
        base = reg_value(winreg.HKEY_LOCAL_MACHINE, SteamPath.reg + self.appid, 'InstallLocation')
        if not base:
            return None
        return os.path.join(base, self.subdir)

class GogPath():
    label = 'GOG'
    reg = r'Software' + [r'', r'\Wow6432Node'][is64BitOS()] + r'\GOG.com\Games'

    def __init__(self, gameid, subdir=''):
        self.gameid = gameid
        self.subdir = subdir

    def full_path(self):
        base = reg_value(winreg.HKEY_LOCAL_MACHINE, GogPath.reg + '\\' + self.gameid, 'path')
        if not base:
            return None
        return os.path.join(base, self.subdir)

class AppPath():
    reg = r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths'

    def __init__(self, exe, label):
        self.exe = exe
        self.label = label

    def full_path(self):
        return reg_value(winreg.HKEY_LOCAL_MACHINE, AppPath.reg + '\\' + self.exe, 'Path')

class Game():
    def __init__(self, **kwds):
        self.__dict__.update(kwds)

REPORT_ORDER_DEFAULT = ['steampath', 'gogpath', 'apppath']

def report_all(game):
    for pathtype in REPORT_ORDER_DEFAULT:
        if pathtype in game.__dict__:
            _ = game.__dict__[pathtype]; report(_.full_path(), game.title + ' (%s)' % _.label)

def report_first(game, order=REPORT_ORDER_DEFAULT):
    for pathtype in order:
        if pathtype in game.__dict__:
            _ = game.__dict__[pathtype]; full_path = _.full_path()
            if full_path:
                return full_path
    return ''

GAME = [
    Game(
        title     = 'Thief: The Dark Project',
        gogpath   = GogPath('1207658997', 'Thief The Dark Project'),
        apppath   = AppPath('Thief.exe', 'CD')
    ),

    Game(
        title     = 'Thief: Gold',
        steampath = SteamPath('211600'),
        gogpath   = GogPath('1207658997', 'Thief Gold'),
        apppath   = AppPath('Thiefg.exe', 'CD')
    ),

    Game(
        title     = 'Thief II: The Metal Age',
        steampath = SteamPath('211740'),
        gogpath   = GogPath('1207659001'),
        apppath   = AppPath('Thief2.exe', 'CD')
    )
]

def main():
    for _ in GAME:
        report_all(_)

if __name__ == '__main__':
    main()
