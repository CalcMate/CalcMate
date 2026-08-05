# -*- coding: utf-8 -*-
# shim: 실제 코드는 content.calculator.writer 로 이동됨. 하위 호환 유지.
from content.calculator.writer import *  # noqa: F401,F403
from content.calculator.writer import (  # noqa: F401
    generate_article, auto_generate_all,
)
