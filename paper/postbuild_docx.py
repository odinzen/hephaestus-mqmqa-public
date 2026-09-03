"""Post-process a pandoc .docx: keep each table on one page.

Adds cantSplit to every table row (no row breaks mid-row) and keepNext to the
paragraphs of every row except the table's last (so a table that does not fit
moves to the next page as a block). Run after every pandoc rebuild:

    python postbuild_docx.py Bustamante_Hephaestus_JORS_manuscript.docx
"""
import re
import shutil
import sys
import zipfile

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def keep_tables_together(xml: str) -> str:
    def fix_table(m):
        tbl = m.group(0)
        rows = re.findall(r"<w:tr\b.*?</w:tr>", tbl, re.S)
        for i, row in enumerate(rows):
            new = row
            if "<w:cantSplit/>" not in new:
                if "<w:trPr>" in new:
                    new = new.replace("<w:trPr>", "<w:trPr><w:cantSplit/>", 1)
                else:
                    new = re.sub(r"(<w:tr\b[^>]*>)", r"\1<w:trPr><w:cantSplit/></w:trPr>", new, 1)
            if i < len(rows) - 1:
                new = re.sub(
                    r"<w:p\b([^>]*)>(?!<w:pPr>)", r'<w:p\1><w:pPr><w:keepNext/></w:pPr>', new
                )
                new = new.replace("<w:pPr>", "<w:pPr><w:keepNext/>", 1) if "<w:keepNext/>" not in new else new
                # rows built by pandoc carry <w:pPr> already; ensure keepNext inside each
                new = re.sub(r"<w:pPr>(?!<w:keepNext/>)", "<w:pPr><w:keepNext/>", new)
            tbl = tbl.replace(row, new, 1)
        return tbl

    return re.sub(r"<w:tbl\b.*?</w:tbl>", fix_table, xml, flags=re.S)


def main(path: str) -> None:
    z = zipfile.ZipFile(path)
    xml = z.read("word/document.xml").decode("utf-8")
    fixed = keep_tables_together(xml)
    with zipfile.ZipFile(path + ".new", "w", zipfile.ZIP_DEFLATED) as out:
        for item in z.namelist():
            out.writestr(item, fixed.encode("utf-8") if item == "word/document.xml" else z.read(item))
    z.close()
    shutil.move(path + ".new", path)
    print(f"tables kept together in {path}")


if __name__ == "__main__":
    main(sys.argv[1])
