import sys
import re

sys.path.append(
    re.match(r'^(.*)/[a-zA-Z0-9_-]+/[a-zA-Z0-9_\-\.]+?$',
             __file__
            ).groups()[0]
    )
