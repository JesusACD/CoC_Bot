import sys
from pathlib import Path
from multiprocessing import freeze_support

# Ensure src is in sys.path
src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import utils
from launch import cmd_rotate

if __name__ == "__main__":
    freeze_support()
    args = utils.parse_args(gui=False, rotate=True)
    args.rotate = True
    args.gui = False
    cmd_rotate(args)
