#!/usr/bin/env python3
"""
Build script to package Fang as a standalone app
"""

import PyInstaller.__main__
import sys
import os

def build():
    args = [
        'music_organizer_gui.py',
        '--onefile',
        '--windowed',
        '--name=Fang',
        '--icon=icon.png',
        '--collect-all=mutagen',
    ]
    
    # Platform-specific options
    if sys.platform == 'darwin':  # Mac
        args.extend([
            '--osx-bundle-identifier=com.Antares-AlphaScorpii.fang',
        ])
    
    PyInstaller.__main__.run(args)
    print("\n✅ Build complete! Check the 'dist' folder for your app.")

if __name__ == '__main__':
    build()
