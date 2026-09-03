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


def left_align_code(styles_xml: str) -> str:
    """Code blocks must never be justified: force jc=left on the SourceCode style."""
    def fix(m):
        st = m.group(0)
        if "<w:jc " in st:
            st = re.sub(r'<w:jc w:val="[^"]*"\s*/>', '<w:jc w:val="left"/>', st)
        elif "<w:pPr>" in st:
            st = st.replace("</w:pPr>", '<w:jc w:val="left"/></w:pPr>', 1)
        else:
            st = st.replace("</w:style>", '<w:pPr><w:jc w:val="left"/></w:pPr></w:style>', 1)
        # 9 pt code so a 90-character listing line fits without wrapping
        if "<w:sz " in st:
            st = re.sub(r'<w:sz w:val="[^"]*"\s*/>', '<w:sz w:val="18"/>', st)
            st = re.sub(r'<w:szCs w:val="[^"]*"\s*/>', '<w:szCs w:val="18"/>', st)
        elif "<w:rPr>" in st:
            st = st.replace("</w:rPr>", '<w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr>', 1)
        else:
            st = st.replace("</w:style>",
                            '<w:rPr><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr></w:style>', 1)
        return st

    out = re.sub(
        r'<w:style [^>]*w:styleId="SourceCode".*?</w:style>', fix, styles_xml, flags=re.S
    )
    # the VerbatimChar character style carries its own w:sz, which overrides the
    # paragraph style on every code run; shrink it too or nothing changes
    def fix_char(m):
        st = m.group(0)
        st = re.sub(r'<w:sz w:val="[^"]*"\s*/>', '<w:sz w:val="18"/>', st)
        st = re.sub(r'<w:szCs w:val="[^"]*"\s*/>', '<w:szCs w:val="18"/>', st)
        return st
    return re.sub(
        r'<w:style [^>]*w:styleId="VerbatimChar".*?</w:style>', fix_char, out, flags=re.S
    )


def left_align_table_cells(xml: str) -> str:
    """Justified body text inside narrow table cells stretches into rivers of
    space; force every table-cell paragraph to left alignment."""
    def fix_ppr(m2):
        blk = m2.group(0)
        if "<w:jc " in blk:
            return re.sub(r'<w:jc w:val="[^"]*"\s*/>', '<w:jc w:val="left"/>', blk)
        return blk.replace("</w:pPr>", '<w:jc w:val="left"/></w:pPr>', 1)

    def fix_table(m):
        tbl = m.group(0)
        tbl = re.sub(r"<w:pPr>.*?</w:pPr>", fix_ppr, tbl, flags=re.S)
        tbl = re.sub(r"<w:p\b([^>]*)>(?=<w:r)",
                     r'<w:p\1><w:pPr><w:jc w:val="left"/></w:pPr>', tbl)
        return tbl

    return re.sub(r"<w:tbl\b.*?</w:tbl>", fix_table, xml, flags=re.S)


def main(path: str) -> None:
    z = zipfile.ZipFile(path)
    xml = left_align_table_cells(keep_tables_together(z.read("word/document.xml").decode("utf-8")))
    styles = left_align_code(z.read("word/styles.xml").decode("utf-8"))
    with zipfile.ZipFile(path + ".new", "w", zipfile.ZIP_DEFLATED) as out:
        for item in z.namelist():
            if item == "word/document.xml":
                out.writestr(item, xml.encode("utf-8"))
            elif item == "word/styles.xml":
                out.writestr(item, styles.encode("utf-8"))
            else:
                out.writestr(item, z.read(item))
    z.close()
    shutil.move(path + ".new", path)
    print(f"tables kept together and code left-aligned in {path}")


if __name__ == "__main__":
    main(sys.argv[1])
