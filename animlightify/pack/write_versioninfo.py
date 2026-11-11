import os
import sys
from PyInstaller.utils.win32.versioninfo import *

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from animlightify import version, get_version

prjname = 'Animlightify'
dest_exe = f'dist/animlightify/{prjname}.exe'
with open('../NOTICE', 'r', encoding='utf8') as fp:
    _copyright = fp.read().strip()

# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
write_version_info_to_executable(dest_exe, VSVersionInfo(
  ffi=FixedFileInfo(
    # filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
    # Set not needed items to zero 0.
    filevers=(version['major'], version['minor'], version['patch'], 0),
    prodvers=(version['major'], version['minor'], version['patch'], 0),
    # Contains a bitmask that specifies the valid bits 'flags'r
    mask=0x3f,
    # Contains a bitmask that specifies the Boolean attributes of the file.
    flags=0x0,
    # The operating system for which this file was designed.
    # 0x4 - NT and there is no need to change it.
    OS=0x4,
    # The general type of file.
    # 0x1 - the file is an application.
    fileType=0x1,
    # The function of the file.
    # 0x0 - the function is not defined for this fileType
    subtype=0x0,
    # Creation date and time stamp.
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', ''),
        StringStruct('FileDescription', 'Dark Engine HWTL Light Conversion Tool'),
        StringStruct('FileVersion', f'{version["major"]}, {version["minor"]}, {version["patch"]}, 0'),
        StringStruct('LegalCopyright', _copyright),
        StringStruct('OriginalFilename', f'{prjname}.exe'),
        StringStruct('ProductName', prjname),
        StringStruct('ProductVersion', version['string'])])
      ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
))
