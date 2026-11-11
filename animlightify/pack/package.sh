#!/usr/bin/bash

dest="dist/animlightify"
version="$(<VERSION)"

pyinstaller --noconfirm pack/animlightify.spec &&
    cp -a ../LICENSE ../NOTICE README.md CHANGELOG.md "$dest" &&
    python pack/write_versioninfo.py &&
    pushd "$dest" &> /dev/null &&
    7z a -m0=LZMA -mx9 Animlightify-"$version"-Windows10-x64.zip ./ &&
    popd &> /dev/null
