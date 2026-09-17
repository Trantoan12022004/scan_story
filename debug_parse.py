import requests, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

url = "https://sad.treeiq.biz/blog/two-children-appeared-at-adrian-s-wedding-and-called-him-daddy-then-his-bride-tried-to-drag-them-away-before-he-could-ask-why/chapter-1"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}, timeout=30)
html = r.text

from bs4 import BeautifulSoup

# Test cả 2 parser
soup_lxml = BeautifulSoup(html, "lxml")
soup_htmlp = BeautifulSoup(html, "html.parser")

# Test og:title với lxml
og1 = soup_lxml.find("meta", property="og:title")
print("lxml og:title:", og1["content"][:80] if og1 and og1.get("content") else "NONE")

# Test og:title với html.parser
og2 = soup_htmlp.find("meta", property="og:title")
print("html.parser og:title:", og2["content"][:80] if og2 and og2.get("content") else "NONE")

# Test attrs
og3 = soup_lxml.find("meta", attrs={"property": "og:title"})
print("lxml attrs og:title:", og3["content"][:80] if og3 and og3.get("content") else "NONE")

# Test tìm tất cả meta
all_meta = soup_lxml.find_all("meta")
print("Total meta tags:", len(all_meta))
for m in all_meta:
    prop = m.get("property", "")
    if "og:" in prop:
        print(f"  META property={prop} content={m.get('content', '')[:60]}")

# Test chapter span with string regex
ch = soup_lxml.find("span", string=re.compile(r"Chapter\s+\d+\s*/\s*\d+"))
print("Chapter span (string regex):", ch.get_text() if ch else "NONE")

# Test tìm bằng text thay vì string
all_spans = soup_lxml.find_all("span")
found = False
for s in all_spans:
    txt = s.get_text(strip=True)
    if re.search(r"Chapter\s+\d+\s*/\s*\d+", txt):
        print("Chapter span (manual):", txt)
        found = True
        break
if not found:
    print("Chapter span (manual): NONE")

# Now simulate the parser
sys.path.insert(0, ".")
from parsers.treeiq import TreeIQParser
parser = TreeIQParser()
info = parser.get_story_info(html, url)
print("\nPARSER RESULT:")
print("  title:", info.title)
print("  slug:", info.slug)
print("  total:", info.total_chapters)
print("  base_url:", info.base_url)
