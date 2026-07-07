from __future__ import annotations

import html
from typing import Optional

BRAND_VERSION = "cx4.0"
BRAND_NAME = "Repliq"
BRAND_PRIMARY = "#6757F5"
BRAND_SECONDARY = "#9A5CFF"
BRAND_INK = "#17142B"

# The symbol keeps the original rounded violet tile but replaces the generic R
# with a continuous reply-loop monogram. The bowl reads as R, while the diagonal
# exit also reads as the tail of a Q / message reply.
_MARK_GLYPH = """
<path d="M15 34V14h10.5C32 14 36 17.4 36 22.5S32 31 25.5 31H15" fill="none" stroke="white" stroke-width="4.2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M25.2 31 35.6 40" fill="none" stroke="white" stroke-width="4.2" stroke-linecap="round" stroke-linejoin="round"/>
""".strip()

# Inter Display SemiBold outlines converted to SVG paths during CX-4 development.
# No font file is shipped or required at runtime. The final q is the brand accent.
_WORDMARK_GLYPHS = (
    (0, "M112 0H364V598C364 763 457 846 577 846C627 846 677 841 696 838V1062C676 1064 648 1066 614 1066C478 1066 397 1002 358 881H355V1056H112Z", False),
    (694, "M578 -24C825 -24 1021 119 1061 326H825C796 236 711 175 584 175C414 175 316 290 310 462H1074V531C1074 855 872 1080 568 1080C272 1080 63 848 63 527C63 207 261 -24 578 -24ZM312 636C329 787 426 880 572 880C718 880 816 787 832 636Z", False),
    (1792, "M112 -418H364V159H367C433 39 544 -21 682 -21C958 -21 1139 200 1139 529C1139 854 955 1077 683 1077C546 1077 429 1021 363 909H360V1056H112ZM623 190C458 190 350 323 350 529C350 734 458 868 623 868C779 868 884 747 884 529C884 310 779 190 623 190Z", False),
    (2959, "M364 1490H112V0H364Z", False),
    (3400, "M112 0H364V1056H112ZM238 1213C324 1213 389 1275 389 1357C389 1438 324 1500 238 1500C152 1500 87 1438 87 1357C87 1275 152 1213 238 1213Z", False),
    (3841, "M1090 -418V1056H842V909H838C773 1021 655 1077 518 1077C247 1077 63 854 63 529C63 200 244 -21 520 -21C658 -21 769 39 835 159H838V-418ZM579 190C423 190 318 310 318 529C318 747 423 868 579 868C744 868 852 734 852 529C852 323 744 190 579 190Z", True),
)


def brand_mark_glyph_html(*, class_name: str = "") -> str:
    css_class = html.escape(str(class_name or ""), quote=True)
    class_attr = f' class="{css_class}"' if css_class else ""
    return (
        f'<svg{class_attr} viewBox="0 0 48 48" aria-hidden="true" focusable="false" '
        f'preserveAspectRatio="xMidYMid meet">{_MARK_GLYPH}</svg>'
    )


def brand_wordmark_html(*, class_name: str = "") -> str:
    css_class = html.escape(str(class_name or ""), quote=True)
    class_attr = f' class="{css_class}"' if css_class else ""
    paths = "".join(
        f'<path transform="translate({x} 0)" d="{d}" class="repliq-wordmark-accent"/>'
        if accent
        else f'<path transform="translate({x} 0)" d="{d}"/>'
        for x, d, accent in _WORDMARK_GLYPHS
    )
    return (
        f'<svg{class_attr} viewBox="0 0 5043 1918" aria-hidden="true" focusable="false" '
        f'preserveAspectRatio="xMinYMid meet"><g transform="translate(0 1500) scale(1 -1)">{paths}</g></svg>'
    )


def brand_mark_svg(*, title: Optional[str] = None) -> str:
    title_text = str(title or BRAND_NAME).strip() or BRAND_NAME
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-labelledby="title">
<title id="title">{html.escape(title_text)}</title>
<defs><linearGradient id="repliqBrandGradient" x1="8" y1="5" x2="57" y2="60" gradientUnits="userSpaceOnUse"><stop stop-color="{BRAND_PRIMARY}"/><stop offset="1" stop-color="{BRAND_SECONDARY}"/></linearGradient></defs>
<rect x="3" y="3" width="58" height="58" rx="19" fill="url(#repliqBrandGradient)"/>
<g transform="translate(8 8)">{_MARK_GLYPH}</g>
</svg>"""


def brand_lockup_svg(*, dark: bool = False, title: Optional[str] = None) -> str:
    title_text = str(title or BRAND_NAME).strip() or BRAND_NAME
    ink = "#FFFFFF" if dark else BRAND_INK
    glyphs = "".join(
        f'<path transform="translate({x} 0)" d="{d}" fill="{BRAND_SECONDARY}"/>'
        if accent
        else f'<path transform="translate({x} 0)" d="{d}" fill="{ink}"/>'
        for x, d, accent in _WORDMARK_GLYPHS
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 128" role="img" aria-labelledby="title">
<title id="title">{html.escape(title_text)}</title>
<defs><linearGradient id="repliqBrandGradient" x1="8" y1="5" x2="57" y2="60" gradientUnits="userSpaceOnUse"><stop stop-color="{BRAND_PRIMARY}"/><stop offset="1" stop-color="{BRAND_SECONDARY}"/></linearGradient></defs>
<rect x="4" y="4" width="120" height="120" rx="38" fill="url(#repliqBrandGradient)"/>
<g transform="translate(16 16) scale(2)">{_MARK_GLYPH}</g>
<g transform="translate(154 17) scale(.102)"><g transform="translate(0 1500) scale(1 -1)">{glyphs}</g></g>
</svg>"""
