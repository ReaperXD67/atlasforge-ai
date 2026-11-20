"""Compare rendered FX-on/off frames at the same camera; not face recognition.

The protected crop is a manually selected interior of the person in the completed
integrated artwork, not a claim that generation kept original-photo bytes intact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('captures',type=Path)
    parser.add_argument('--reference',default='frame-001.png')
    parser.add_argument('--effects',nargs='+',default=['frame-003.png','frame-005.png','frame-007.png'])
    parser.add_argument('--crop',default='250,120,680,935',help='Protected interior source crop in screenshot pixels: left,top,width,height')
    args=parser.parse_args()
    x,y,w,h=map(int,args.crop.split(','))
    reference=args.captures/args.reference
    a=np.asarray(Image.open(reference).convert('RGB')).astype(np.int16)
    if min(x,y)<0 or min(w,h)<=0 or x+w>a.shape[1] or y+h>a.shape[0]:
        raise ValueError('Protected crop is outside the screenshot.')
    rows=[]
    for name in args.effects:
        path=args.captures/name
        b=np.asarray(Image.open(path).convert('RGB')).astype(np.int16)
        if a.shape!=b.shape: raise ValueError('Screenshot dimensions must match; no resize/alignment fitting.')
        difference=np.abs(a-b);protected=difference[y:y+h,x:x+w]
        rows.append(dict(frame=name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         whole_image_mae=float(difference.mean()),
                         protected_core_mae=float(protected.mean()),protected_core_max=int(protected.max()),
                         changed_pixels=int(np.any(difference>0,axis=2).sum()),
                         passed=bool(protected.max()==0 and np.any(difference>0))))
    report=dict(passed=all(x['passed'] for x in rows),reference=args.reference,
                reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),
                protected_crop_pixels=[x,y,w,h],screenshots_compared_without_alignment_or_colour_fitting=True,
                samples=rows,limits='Same-camera renderer proof only: preserves protected finished-artwork pixels, not a semantic likeness metric or original-photo identity claim.')
    (args.captures/'subject-protection-test.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':
    main()
