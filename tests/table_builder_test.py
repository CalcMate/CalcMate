# -*- coding: utf-8 -*-
"""tests/table_builder_test.py — TableBuilder 테스트"""
import pytest
from content_pipeline.table_builder import TableBuilder

def test_type_a_dict_list():
    data = [{"근무시간": "15시간 이상", "지급": "가능"}, {"근무시간": "15시간 미만", "지급": "불가"}]
    html = TableBuilder.from_dict_list(data)
    assert "<table>" in html
    assert "<th>근무시간</th>" in html
    assert "<td>가능</td>" in html

def test_type_b_headers_rows():
    headers = ["구분", "내용"]
    rows = [["주휴수당", "지급"], ["연차", "별도"]]
    html = TableBuilder.build_table(headers, rows)
    assert "<thead><tr><th>구분</th>" in html
    assert "<td>주휴수당</td>" in html

def test_caption():
    headers = ["A"]
    rows = [["1"]]
    html = TableBuilder.build_table(headers, rows, caption="테스트 표")
    assert "<caption>테스트 표</caption>" in html

def test_empty_data():
    assert TableBuilder.build_table([], []) == ""
    assert TableBuilder.from_dict_list([]) == ""

def test_html_escape_order():
    # Test & is escaped first (e.g., "A & B" -> "A &amp; B")
    # Test &lt; shouldn't become &amp;lt;
    headers = ["Test & Data"]
    rows = [["<Data>"]]
    html = TableBuilder.build_table(headers, rows)
    assert "<th>Test &amp; Data</th>" in html
    assert "<td>&lt;Data&gt;</td>" in html
