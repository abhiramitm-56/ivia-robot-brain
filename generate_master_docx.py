import re
import os
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
        node = OxmlElement(m)
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def add_callout(doc, text, title="NOTE", fill_hex="EDF2F7", border_hex="3182CE"):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    cell = table.cell(0, 0)
    cell.width = Inches(6.5)
    set_cell_background(cell, fill_hex)
    set_cell_margins(cell, top=140, bottom=140, left=200, right=200)
    
    # Left border only
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(f'''
        <w:tcBorders {nsdecls("w")}>
            <w:top w:val="none"/>
            <w:left w:val="single" w:sz="24" w:space="0" w:color="{border_hex}"/>
            <w:bottom w:val="none"/>
            <w:right w:val="none"/>
        </w:tcBorders>
    ''')
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    run_t = p.add_run(f"[{title}] ")
    run_t.bold = True
    run_t.font.name = "Segoe UI"
    run_t.font.size = Pt(10)
    run_t.font.color.rgb = RGBColor(0x2B, 0x6C, 0xB0)
    
    run_b = p.add_run(text)
    run_b.font.name = "Segoe UI"
    run_b.font.size = Pt(9.5)
    run_b.font.color.rgb = RGBColor(0x2D, 0x37, 0x48)
    
    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(4)

def build_docx(md_path, output_docx_path):
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    doc = Document()
    
    # Page setup
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # Style defaults
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Segoe UI'
    normal_style.font.size = Pt(10.5)
    normal_style.font.color.rgb = RGBColor(0x2D, 0x37, 0x48)

    in_table = False
    table_lines = []
    in_code_block = False
    code_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i].rstrip('\r\n')
        
        # Code block handling
        if line.strip().startswith('```'):
            if in_code_block:
                in_code_block = False
                # flush code block
                table = doc.add_table(rows=1, cols=1)
                table.alignment = WD_TABLE_ALIGNMENT.CENTER
                cell = table.cell(0, 0)
                cell.width = Inches(6.5)
                set_cell_background(cell, "F7FAFC")
                set_cell_margins(cell, top=100, bottom=100, left=150, right=150)
                tcPr = cell._tc.get_or_add_tcPr()
                borders = parse_xml(f'''
                    <w:tcBorders {nsdecls("w")}>
                        <w:top w:val="single" w:sz="6" w:space="0" w:color="CBD5E0"/>
                        <w:left w:val="single" w:sz="18" w:space="0" w:color="4A5568"/>
                        <w:bottom w:val="single" w:sz="6" w:space="0" w:color="CBD5E0"/>
                        <w:right w:val="single" w:sz="6" w:space="0" w:color="CBD5E0"/>
                    </w:tcBorders>
                ''')
                tcPr.append(borders)
                cp = cell.paragraphs[0]
                cp.paragraph_format.space_before = Pt(2)
                cp.paragraph_format.space_after = Pt(2)
                c_run = cp.add_run("\n".join(code_lines))
                c_run.font.name = "Consolas"
                c_run.font.size = Pt(8.5)
                c_run.font.color.rgb = RGBColor(0x1A, 0x20, 0x2C)
                
                doc.add_paragraph().paragraph_format.space_after = Pt(4)
                code_lines = []
            else:
                in_code_block = True
                code_lines = []
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # Table handling
        if line.strip().startswith('|') and '|' in line.strip()[1:]:
            table_lines.append(line.strip())
            i += 1
            continue
        else:
            if table_lines:
                # Render table
                # Filter out separator line like |---|---|
                data_rows = []
                for tl in table_lines:
                    cols = [c.strip() for c in tl.split('|')[1:-1]]
                    if cols and all(re.match(r'^:?-+:?$', c) for c in cols):
                        continue
                    data_rows.append(cols)
                
                if data_rows:
                    num_cols = max(len(r) for r in data_rows)
                    t = doc.add_table(rows=len(data_rows), cols=num_cols)
                    t.alignment = WD_TABLE_ALIGNMENT.CENTER
                    
                    for r_idx, row_data in enumerate(data_rows):
                        for c_idx in range(num_cols):
                            val = row_data[c_idx] if c_idx < len(row_data) else ""
                            cell = t.cell(r_idx, c_idx)
                            set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
                            p = cell.paragraphs[0]
                            p.paragraph_format.space_before = Pt(2)
                            p.paragraph_format.space_after = Pt(2)
                            
                            # Clean markdown bold/code from cell text
                            clean_val = val.replace('**', '').replace('`', '')
                            
                            if r_idx == 0:
                                # Header row
                                set_cell_background(cell, "1A365D")
                                run = p.add_run(clean_val)
                                run.bold = True
                                run.font.name = "Segoe UI"
                                run.font.size = Pt(9.5)
                                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                            else:
                                if r_idx % 2 == 1:
                                    set_cell_background(cell, "FFFFFF")
                                else:
                                    set_cell_background(cell, "F7FAFC")
                                run = p.add_run(clean_val)
                                run.font.name = "Segoe UI"
                                run.font.size = Pt(9)
                                run.font.color.rgb = RGBColor(0x2D, 0x37, 0x48)
                                
                    # Table border
                    tblPr = t._tbl.tblPr
                    tblBorders = parse_xml(f'''
                        <w:tblBorders {nsdecls("w")}>
                            <w:top w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
                            <w:left w:val="none"/>
                            <w:bottom w:val="single" w:sz="6" w:space="0" w:color="CBD5E0"/>
                            <w:right w:val="none"/>
                            <w:insideH w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
                            <w:insideV w:val="none"/>
                        </w:tblBorders>
                    ''')
                    tblPr.append(tblBorders)
                    doc.add_paragraph().paragraph_format.space_after = Pt(4)

                table_lines = []

        # Empty lines
        if not line.strip():
            i += 1
            continue

        # Horizontal rules
        if line.strip() in ['---', '***', '___']:
            i += 1
            continue

        # Headings
        if line.startswith('# '):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(16)
            p.paragraph_format.space_after = Pt(8)
            run = p.add_run(line[2:].strip())
            run.font.name = "Segoe UI Semibold"
            run.font.size = Pt(22)
            run.bold = True
            run.font.color.rgb = RGBColor(0x1A, 0x36, 0x5D)
            i += 1
            continue
        elif line.startswith('## '):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(14)
            p.paragraph_format.space_after = Pt(6)
            run = p.add_run(line[3:].strip())
            run.font.name = "Segoe UI Semibold"
            run.font.size = Pt(16)
            run.bold = True
            run.font.color.rgb = RGBColor(0x2B, 0x6C, 0xB0)
            i += 1
            continue
        elif line.startswith('### '):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(4)
            run = p.add_run(line[4:].strip())
            run.font.name = "Segoe UI Semibold"
            run.font.size = Pt(13)
            run.bold = True
            run.font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
            i += 1
            continue

        # Blockquotes (metadata/notes)
        if line.startswith('> '):
            bq_text = line[2:].strip()
            # clean formatting
            clean_bq = bq_text.replace('**', '')
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.2)
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(2)
            run = p.add_run(clean_bq)
            run.font.name = "Segoe UI"
            run.font.size = Pt(9.5)
            run.font.italic = True
            run.font.color.rgb = RGBColor(0x4A, 0x55, 0x68)
            i += 1
            continue

        # Bullet points
        if line.strip().startswith('* ') or line.strip().startswith('- '):
            indent_level = 0
            if line.startswith('   * ') or line.startswith('   - '):
                indent_level = 1
                b_text = line.strip()[2:]
            elif line.startswith('      * ') or line.startswith('      - '):
                indent_level = 2
                b_text = line.strip()[2:]
            else:
                b_text = line.strip()[2:]
                
            p = doc.add_paragraph(style='List Bullet')
            p.paragraph_format.left_indent = Inches(0.25 * (indent_level + 1))
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(2)
            
            # Format bold/inline code within bullet
            parts = re.split(r'(\*\*.*?\*\*|`.*?`)', b_text)
            for part in parts:
                if part.startswith('**') and part.endswith('**'):
                    r = p.add_run(part[2:-2])
                    r.bold = True
                    r.font.name = "Segoe UI"
                elif part.startswith('`') and part.endswith('`'):
                    r = p.add_run(part[1:-1])
                    r.font.name = "Consolas"
                    r.font.size = Pt(9.5)
                    r.font.color.rgb = RGBColor(0x80, 0x1F, 0x4F)
                else:
                    r = p.add_run(part)
                    r.font.name = "Segoe UI"
            i += 1
            continue

        # Numbered list
        m_num = re.match(r'^(\d+)\.\s+(.*)', line.strip())
        if m_num:
            num = m_num.group(1)
            num_text = m_num.group(2)
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.25)
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            
            r_num = p.add_run(f"{num}. ")
            r_num.bold = True
            r_num.font.name = "Segoe UI"
            r_num.font.color.rgb = RGBColor(0x2B, 0x6C, 0xB0)
            
            parts = re.split(r'(\*\*.*?\*\*|`.*?`)', num_text)
            for part in parts:
                if part.startswith('**') and part.endswith('**'):
                    r = p.add_run(part[2:-2])
                    r.bold = True
                    r.font.name = "Segoe UI"
                elif part.startswith('`') and part.endswith('`'):
                    r = p.add_run(part[1:-1])
                    r.font.name = "Consolas"
                    r.font.size = Pt(9.5)
                    r.font.color.rgb = RGBColor(0x80, 0x1F, 0x4F)
                else:
                    r = p.add_run(part)
                    r.font.name = "Segoe UI"
            i += 1
            continue

        # Standard Paragraph
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(4)
        parts = re.split(r'(\*\*.*?\*\*|`.*?`|\*.*?\*)', line)
        for part in parts:
            if part.startswith('**') and part.endswith('**'):
                r = p.add_run(part[2:-2])
                r.bold = True
                r.font.name = "Segoe UI"
            elif part.startswith('*') and part.endswith('*') and len(part) > 2:
                r = p.add_run(part[1:-1])
                r.italic = True
                r.font.name = "Segoe UI"
            elif part.startswith('`') and part.endswith('`'):
                r = p.add_run(part[1:-1])
                r.font.name = "Consolas"
                r.font.size = Pt(9.5)
                r.font.color.rgb = RGBColor(0x80, 0x1F, 0x4F)
            else:
                r = p.add_run(part)
                r.font.name = "Segoe UI"
        i += 1

    doc.save(output_docx_path)
    print(f"Successfully generated DOCX at: {output_docx_path}")

if __name__ == '__main__':
    md_file = r"C:\Users\ABHIRAMI\.gemini\antigravity\brain\f530f260-19ba-4943-b44b-19d96e66f22d\IVIA_COMPLETE_PROJECT_DOCUMENTATION_MASTER.md"
    out_file = r"c:\Users\ABHIRAMI\Desktop\VOICE_OF_IVIA\IVIA_Project_Documentation_Master.docx"
    build_docx(md_file, out_file)

