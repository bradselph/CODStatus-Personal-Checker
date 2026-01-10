# -*- mode: python ; coding: utf-8 -*-

# TODO: Critical packaging error - JSON data files may not exist at build time
# WHY: The datas list includes 'accounts.json', 'config.json', and 'login_credentials.json' which are
# runtime-generated files that may not exist when PyInstaller builds the executable.
# If these files don't exist at build time, PyInstaller will fail or silently skip them.
# FIX: Either create empty template versions of these files for packaging, or make them optional
# by checking if they exist before adding to datas, e.g., using conditional logic or --add-data flags.

# TODO: Chrome/chromedriver directories may not exist or may be platform-specific
# WHY: The spec file hardcodes ('chrome', 'chrome') and ('chromedriver', 'chromedriver') paths,
# but these directories might not exist on all build machines. Also, the paths in main.py use
# .exe extensions (line 28-29: "chrome/chrome.exe", "chromedriver/chromedriver.exe") which are
# Windows-specific, but this spec file doesn't indicate platform restrictions.
# FIX: Add validation to ensure chrome and chromedriver directories exist, or make them optional.
# Consider platform-specific builds or document that this only works on Windows.

a = Analysis(
    ['main.py'],
    binaries=[],
    datas=[('accounts.json', '.'), ('icon.ico','.'), ('config.json', '.'), ('login_credentials.json', '.'), ('chrome', 'chrome'), ('chromedriver', 'chromedriver')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CODStatus_Personal_Checker_2.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
