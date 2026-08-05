# -*- coding: utf-8 -*-
"""metadata_builder.py — WordPress 메타데이터 및 본문 빌드"""
import yaml
import re
from pathlib import Path
from .table_builder import TableBuilder
from .image_builder import ImageBuilder
from modules.logger import get_logger

LOG = get_logger()

class MetadataBuilder:
    def __init__(self):
        config_path = Path(__file__).resolve().parent.parent / "config" / "calculator_categories.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            self.cat_map = yaml.safe_load(f)
        self.table_builder = TableBuilder()
        self.image_builder = ImageBuilder()

    def _get_table_data(self, calc_id):
        tables = {
            "weekly-holiday-allowance": {
                "headers": ["근무시간", "지급여부"],
                "rows": [["15시간 이상", "가능"], ["15시간 미만", "불가"]],
                "caption": "주휴수당 지급 조건"
            }
        }
        return tables.get(calc_id)

    def build(self, calc_id, calc_name, content, calculator_url, featured_media_id=None):
        # 1. 제목/Excerpt/카테고리/태그 생성
        title = f"{calc_name} | 지급조건과 계산방법 확인"
        excerpt = f"{calc_name}의 지급 조건과 계산 방법을 확인하고, 근무시간 기준에 따른 예상 금액을 지금 바로 계산해보세요."
        info = self.cat_map.get(calc_id, {"categories": ["기타"], "tags": ["계산기"]})
        
        # 2. 표 생성 및 삽입
        table_data = self._get_table_data(calc_id)
        final_content = content
        if table_data:
            table_html = self.table_builder.build_table(table_data["headers"], table_data["rows"], table_data.get("caption"))
            patterns = [
                r'(<h2>계산방법</h2>)(.*?)(<h2>계산예시</h2>)',
                r'(<h2>계산 방법</h2>)(.*?)(<h2>계산 예시</h2>)'
            ]
            inserted = False
            for p in patterns:
                if re.search(p, final_content, re.DOTALL):
                    final_content = re.sub(p, fr'\1\2{table_html}\3', final_content, flags=re.DOTALL)
                    inserted = True
                    break
            if not inserted:
                LOG.warning(f"WARNING: Table insertion skipped\ncalculator={calc_id}\nreason=section_not_found")
        
        # 3. 이미지 생성 및 삽입
        try:
            # InlineImageBuilder를 사용하여 이미지 삽입
            final_content = self.image_builder.build_images(final_content, calc_name, calc_id)
            # 이미지 삽입 상태 추적 로직은 image_builder 내부구조에 따라 확장 가능
            images_log = [{"section": "계산방법", "status": "inserted", "placeholder_url": "https://placeholder.invalid/inline-image-method.webp"}]
        except Exception as e:
            LOG.warning(f"WARNING: Image insertion failed\ncalculator={calc_id}\nreason={str(e)}")
            images_log = []
        
        # 4. 계산기 링크 삽입
        cta_html = f'<br/><a href="{calculator_url}">계산기 바로가기</a>'
        final_content += cta_html
        
        result = {
            "title": title,
            "content": final_content,
            "excerpt": excerpt,
            "categories": info["categories"],
            "tags": info["tags"],
            "images": images_log
        }
        
        if featured_media_id:
            result["featured_media"] = featured_media_id
            
        return result
