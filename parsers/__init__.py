# parsers/__init__.py
# Tự động detect và chọn parser phù hợp dựa trên URL

from urllib.parse import urlparse
from parsers.treeiq import TreeIQParser
from parsers.ahcms import AHCMSParser

# Danh sách parser đã đăng ký
# Key: tên nhận diện, Value: (parser_class, danh sách domain hoặc pattern)
PARSER_REGISTRY = [
    (TreeIQParser, ["treeiq.biz"]),
    (AHCMSParser, ["fast2tricks.com"]),
]


def detect_parser(url: str):
    """
    Tự động phát hiện parser phù hợp dựa trên domain của URL.
    Trả về instance của parser nếu tìm thấy, raise Exception nếu không hỗ trợ.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    for parser_class, domains in PARSER_REGISTRY:
        for domain in domains:
            if hostname.endswith(domain):
                return parser_class()

    raise ValueError(
        f"Không hỗ trợ trang web: {hostname}\n"
        f"Các trang được hỗ trợ: {', '.join(d for _, domains in PARSER_REGISTRY for d in domains)}"
    )
