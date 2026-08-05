# -*- coding: utf-8 -*-
# shim: 실제 코드는 content.calculator.prompt 로 이동됨. 하위 호환 유지.
from content.calculator.prompt import *  # noqa: F401,F403
from content.calculator.prompt import (  # noqa: F401
    CURRENT_YEAR, QUALITY,
    _ctx, get_seo_prompt, get_faq_prompt, get_article_prompt,
    get_cta_prompt, get_image_prompt,
)
