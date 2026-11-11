"""Extract published table cell text with anchors; no disease-risk decisions."""
import csv,xml.etree.ElementTree as E
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    cells=[]
    for p in (ROOT/'raw/pmc_cloud').glob('*/*.xml'):
        if p.name=='listing.xml':continue
        doc=E.parse(p)
        for table in doc.findall('.//table-wrap'):
            tid=table.get('id','');caption=' '.join(''.join(table.find('caption').itertext()).split()) if table.find('caption') is not None else ''
            for i,tr in enumerate(table.findall('.//tr'),1):
                for j,td in enumerate([x for x in tr if x.tag in ['td','th']],1):
                    cells.append(dict(pmcid=p.parent.name,source_xml=p.relative_to(ROOT).as_posix(),table_id=tid,caption=caption,row=i,column=j,rowspan=td.get('rowspan','1'),colspan=td.get('colspan','1'),original_text=' '.join(''.join(td.itertext()).split()),status='部分核验',notes='Literal published cell text; merged-cell geometry preserved through span fields; no inferred missing values'))
    if cells:
        with (ROOT/'candidate_inputs/published_table_cells.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=cells[0]);w.writeheader();w.writerows(cells)
    print('Published table cells:',len(cells))

if __name__=='__main__':main()
