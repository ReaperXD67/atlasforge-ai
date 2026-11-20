"""Make a review contact sheet from actual smoke PNGs, without changing sources."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

parser=argparse.ArgumentParser()
parser.add_argument('--result',default='smoke-result.json')
parser.add_argument('--last-per-scene',action='store_true')
args=parser.parse_args()
here=Path(__file__).resolve().parent
source=here/args.result
data=json.loads(source.read_text(encoding='utf8'))
kind='targeted' if source.name.startswith('targeted') else 'seams' if source.name.startswith('seam-') else 'smoke'
folder=here/'renders'/kind
items=list(enumerate(data['samples']))
if args.last_per_scene:
    grouped={}
    for index,sample in items:
        grouped[sample['scene']]=(index,sample)
    items=list(grouped.values())
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
records=[]
for first in range(0,len(items),16):
    sheet=Image.new('RGB',(1920,1080),'#173e3b')
    draw=ImageDraw.Draw(sheet)
    sheet_name=f'contact-{first//16+1:02}.png'
    for slot,(index,sample) in enumerate(items[first:first+16]):
        filename=folder/f'frame-{index:03}.png'
        thumb=Image.open(filename).convert('RGB').resize((480,270),Image.Resampling.LANCZOS)
        x,y=slot%4*480,slot//4*270
        sheet.paste(thumb,(x,y))
        draw.rectangle((x,y,x+480,y+24),fill='#102824')
        draw.text((x+8,y+3),f"{sample['scene']} | {sample['time']:.2f}s | {sample['transition']}",font=font,fill='#f1e6d0')
        records.append({'scene':sample['scene'],'time':sample['time'],'source':str(filename),'sheet':sheet_name,'slot':slot})
    sheet.save(folder/sheet_name)
(folder/'contact-sheets.json').write_text(json.dumps(records,indent=2),encoding='utf8')
print(json.dumps({'samples':len(items),'sheets':(len(items)+15)//16,'folder':str(folder)}))
