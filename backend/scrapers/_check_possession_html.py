import io, sys, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
logging.disable(logging.CRITICAL)
from lxml import html as lhtml, etree
import soccerdata as sd

def get_text(el):
    return "".join(el.itertext()).strip()

fbref = sd.FBref(leagues="ENG-Premier League", seasons="2526")

for table_id in ["stats_possession", "stats_passing"]:
    filepath = fbref.data_dir / f"pl_{table_id}.html"
    tree = lhtml.parse(str(filepath))
    parser = etree.HTMLParser(recover=True)
    comments = tree.xpath(f'//comment()[contains(.,"div_{table_id}")]')
    root = etree.fromstring(comments[0].text, parser)
    tbl = root.xpath(f'//table[contains(@id, "{table_id}")]')[0]
    found = False
    for row in tbl.xpath(".//tbody/tr"):
        cells = row.findall(".//td")
        if not cells:
            continue
        pc = next((c for c in cells if c.get("data-stat") == "player"), None)
        if pc is None:
            continue
        name = get_text(pc)
        if "Salah" not in name:
            continue
        skip = {"player", "nation", "pos", "squad", "age", "born", "games", "minutes_90s", "matches"}
        print(f"=== {table_id} -- Salah ===")
        for c in cells:
            stat = c.get("data-stat", "")
            if stat in skip:
                continue
            text = get_text(c)
            csk  = c.get("csk", "")
            print(f"  {stat:35s} text={text!r:10s}  csk={csk!r}")
        found = True
        break
    if not found:
        print(f"=== {table_id} -- Salah NOT FOUND ===")
