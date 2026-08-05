# -*- coding: utf-8 -*-
"""image_builder.py — 본문 이미지 자동 삽입"""
import re
from modules.logger import get_logger

LOG = get_logger()

class ImageBuilder:
    def __init__(self):
        # 섹션별 이미지 타입 매핑 (설계문서 기준)
        self.section_image_map = {
            "계산방법": "flow",
            "계산 방법": "flow",
            "계산예시": "comparison",
            "계산 예시": "comparison",
            "주의사항": "checklist"
        }
        self.image_types = {
            "flow": "Modern infographic flow chart illustrating process steps, minimalist, vector, clean style, no text, no numbers, no legal claims",
            "comparison": "Comparison infographic style illustration, clean, professional, flat vector, no text, no numbers, no legal claims",
            "checklist": "Modern minimalist illustration for checklist, flat vector art, clean background, high quality, no text, no numbers, no legal claims"
        }

    def _get_alt_text(self, calculator_name, section_name):
        return f"{calculator_name} {section_name}"

    def _get_placeholder_url(self, section_name):
        url_map = {"계산방법": "method", "계산 방법": "method", "계산예시": "example", "계산 예시": "example", "주의사항": "warning"}
        return f"https://placeholder.invalid/inline-image-{url_map.get(section_name, 'section')}.webp"

    def build(self, calculator_id: str, title: str, category: str) -> dict:
        """계산기 metadata를 바탕으로 이미지 생성 정보를 빌드합니다."""
        filename = f"{calculator_id}_featured.png"
        return {
            "image_prompt": f"Financial information blog illustration for {calculator_id}, clean modern style, no text, no numbers, vector flat design",
            "filename": filename,
            "alt_text": f"{title} 관련 계산기 및 근로시간 정보"
        }

    def build_images(self, content: str, calculator_name: str, calculator_id: str) -> str:
        """본문에 이미지를 삽입합니다 (HTML 구조 유지)."""
        # 1. 섹션 파싱 (<h2> 기준)
        sections = re.split(r'(<h2>.*?</h2>)', content, flags=re.DOTALL)
        if len(sections) < 3: # <h2> 태그가 없거나 구조가 이상하면 스킵
            return content

        new_content = [sections[0]]
        for i in range(1, len(sections), 2):
            header = sections[i]
            body = sections[i+1]
            
            # 섹션 이름 추출 (<h2>태그 제거)
            section_name = re.sub(r'</?h2>', '', header).strip()
            
            # 이미 이미지 블록이 있는지 확인 (중복 삽입 방지)
            if "<!-- wp:image -->" in body:
                new_content.extend([header, body])
                continue
                
            # 문단 수 확인 (2개 이상만 후보)
            paragraphs = re.findall(r'<p>.*?</p>', body, re.DOTALL)
            
            if len(paragraphs) >= 2 and section_name in self.section_image_map:
                # 이미지 삽입
                img_type = self.section_image_map[section_name]
                alt = self._get_alt_text(calculator_name, section_name)
                url = self._get_placeholder_url(section_name)
                
                img_block = (
                    f"\n\n<!-- wp:image -->\n"
                    f'<figure class="wp-block-image">\n'
                    f'<img src="{url}" alt="{alt}">\n'
                    f'</figure>\n'
                    f"<!-- /wp:image -->\n\n"
                )
                
                # 내부링크보다 앞에 오도록 삽입 (섹션 본문의 첫 문단 뒤에 삽입)
                paragraphs = re.findall(r'<p>.*?</p>', body, re.DOTALL)
                if paragraphs:
                    # 첫 문단 뒤에 삽입
                    body = body.replace(paragraphs[0], paragraphs[0] + img_block, 1)
                else:
                    # 문단 없으면 본문 맨 앞
                    body = img_block + body

            elif section_name in self.section_image_map and len(paragraphs) < 2:
                LOG.warning(f"WARNING: Image insertion skipped\ncalculator={calculator_id}\nreason=insufficient_paragraphs\nsection={section_name}")
            elif section_name not in self.section_image_map and "<h2>" in header:
                pass # 후보 섹션 아님
            else:
                LOG.warning(f"WARNING: Image insertion skipped\ncalculator={calculator_id}\nreason=section_not_found\nsection={section_name}")

            new_content.extend([header, body])

        return "".join(new_content)
