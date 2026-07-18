#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Bootstrap Mode E2E - pipeline 1 run"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from modules.calculator_pipeline import run_calculator_once

cfg = load_config()

print("=== G5 Bootstrap Mode E2E ===")
print("target: all calcs (max_count=1)")

result = run_calculator_once(cfg, max_count=1)
print()
print("=== result ===")
for k, v in result.items():
    print(f"  {k}: {v}")
