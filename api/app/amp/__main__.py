"""Allow running AMP inspector as a module: python -m app.amp.amp_inspector"""

import sys

from .amp_inspector import main

if __name__ == "__main__":
    sys.exit(main())

