# -*- coding: utf-8 -*-
"""table_builder.py — HTML 표 생성 유틸리티"""

class TableBuilder:
    @staticmethod
    def _escape(text: str) -> str:
        """Mandated escape order: & first, then <, >, ", '"""
        if not text:
            return ""
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")

    @staticmethod
    def build_table(headers: list, rows: list, caption: str = None) -> str:
        """Type B: build from headers and rows"""
        if not headers and not rows:
            return ""
        
        html = ["<table>"]
        if caption:
            html.append(f"<caption>{TableBuilder._escape(caption)}</caption>")
        
        html.append("<thead><tr>")
        for h in headers:
            html.append(f"<th>{TableBuilder._escape(h)}</th>")
        html.append("</tr></thead>")
        
        html.append("<tbody>")
        for row in rows:
            html.append("<tr>")
            for cell in row:
                html.append(f"<td>{TableBuilder._escape(cell)}</td>")
            html.append("</tr>")
        html.append("</tbody></table>")
        
        return "".join(html)

    @staticmethod
    def from_dict_list(data_list: list, caption: str = None) -> str:
        """Type A: build from List[Dict]"""
        if not data_list:
            return ""
        
        headers = list(data_list[0].keys())
        rows = [[str(d.get(h, "")) for h in headers] for d in data_list]
        return TableBuilder.build_table(headers, rows, caption)
