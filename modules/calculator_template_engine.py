# -*- coding: utf-8 -*-
# shim: 실제 코드는 content.calculator.template 로 이동됨. 하위 호환 유지.
from content.calculator.template import *  # noqa: F401,F403
from content.calculator.template import (  # noqa: F401
    build_calculator_html,
    _LABELS, _to_dict, _label, _input_type,
)
