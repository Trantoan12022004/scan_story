# parsers/__init__.py
# Tự động detect và chọn parser phù hợp dựa trên URL

from urllib.parse import urlparse
from parsers.treeiq import TreeIQParser
from parsers.ahcms import AHCMSParser
from parsers.universal import UniversalParser

# Danh sách parser đã đăng ký chuyên biệt cho các CMS cố định
# Key: tên nhận diện, Value: (parser_class, danh sách domain hoặc pattern)
PARSER_REGISTRY = [
    (TreeIQParser, ["treeiq.biz"]),
    (AHCMSParser, ["fast2tricks.com"]),
]


def detect_parser(url: str):
    """
    Tự động phát hiện parser phù hợp dựa trên domain của URL.
    - Nếu khớp domain chuyên biệt (TreeIQ, AHCMS): sử dụng parser chuyên biệt tương ứng.
    - Nếu là bất kỳ website nào khác: tự động sử dụng UniversalParser để cào nội dung.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    for parser_class, domains in PARSER_REGISTRY:
        for domain in domains:
            if hostname.endswith(domain):
                return parser_class()

    # Tự động fallback sang UniversalParser cho mọi trang web khác
    try:
        import importlib
        import parsers.universal
        importlib.reload(parsers.universal)
        return parsers.universal.UniversalParser()
    except Exception:
        return UniversalParser()


