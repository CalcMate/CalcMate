# -*- coding: utf-8 -*-
"""
modules/json_utils.py — 하위호환 shim.
정규 위치는 modules/utils/parser.py 로 이동했다. 기존 import 경로 보존용.
"""
from .utils.parser import parse_json_lenient, try_parse_json  # noqa: F401
