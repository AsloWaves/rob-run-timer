"""Write the Windows version resource (product name, version, publisher text) for PyInstaller.
Usage: python tools/make_version_info.py <output file>   (version is read from rob_run_timer.py)"""
import os, re, sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(root, "rob_run_timer.py"), encoding="utf-8").read()
ver = re.search(r'^VERSION = "([\d.]+)"', src, re.M).group(1)
nums = (ver.split(".") + ["0", "0", "0"])[:3] + ["0"]
tup = ", ".join(nums)
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "version_info.txt")
open(out, "w", encoding="utf-8").write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({tup}), prodvers=({tup}), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'AsloWaves'),
      StringStruct('FileDescription', 'Rob Run Harvest Timer'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', 'RobRunTimer'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 AsloWaves. MIT License.'),
      StringStruct('OriginalFilename', 'RobRunTimer.exe'),
      StringStruct('ProductName', 'Rob Run Harvest Timer'),
      StringStruct('ProductVersion', '{ver}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""")
print("version info", ver, "->", out)
