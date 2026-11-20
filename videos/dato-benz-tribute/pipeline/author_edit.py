"""Bind the image-film design to private, verified recording/caption inputs.

The executable plan stays local. No song text, audio, reference photo or
production receipt is embedded in this reusable authoring source.
"""
from __future__ import annotations

import json
import re

from media import ROOT,input_contract,read_json,write_json


def clean(text):
    return ''.join(re.findall(r'[\w\u3400-\u9fff]',text))


def clause_cut(cue,end):
    # Visual cuts use an actual aligned word near the clause boundary. Caption
    # starts/ends are never moved, nor are ASR hallucinations added to the text.
    prefix=re.split('[，,。！!；;]',cue['text'])[0]
    count=len(clean(prefix)); consumed=0; candidates=[]
    for word in cue.get('words',[]):
        at=word.get('start_seconds',word.get('start',cue['start']))
        if consumed>=count and cue['start']+1.2<at<end-1.2:return float(at)
        consumed+=len(clean(word['text']))
        if cue['start']+1.2<at<end-1.2:candidates.append(float(at))
    midpoint=(cue['start']+end)/2
    return min(candidates,key=lambda x:abs(x-midpoint)) if candidates else midpoint


def main():
    contract=input_contract(); cues=read_json(ROOT/'captions.json')
    layout=read_json(ROOT/'art-layout.json'); assets={x['id']:x for x in layout['assets']}
    names={int(k[:2]):k for k in assets if k[:2].isdigit() and not assets[k].get('variant')}
    variant_names={3:'03-support-detail',9:'09-light-detail',10:'10-threshold-detail',17:'17-community-detail'}
    duration=contract['duration']; scenes=[]
    # One table describes the film's content; supplied lyrics remain private.
    plates=[2,3,2,4,5,6,5,9,8,9,7,10,1,9,3,12,
            11,10,5,14,13,7,13,14,16,17,15,10,18,15,17,17]
    split_indices={1,7,9,10,11,13,14,15,17,20,22,25,26,27,29,30,31}
    # Regions are actual image areas, not the same zoom applied to every slide.
    details={
        2:([.03,.04,.72,.72],[.16,.02,.82,.82]),
        3:([.08,.03,.68,.68],[.18,.12,.78,.78]),
        5:([.20,.08,.66,.66],[.08,.12,.81,.81]),
        7:([.08,.08,.62,.62],[.24,.05,.70,.70]),
        9:([.10,.20,.65,.65],[.22,.08,.74,.74]),
        10:([.10,.15,.69,.69],[.26,.12,.70,.70]),
        12:([.15,.22,.68,.68],[.02,.02,.96,.96]),
        13:([.03,.10,.67,.67],[.18,.06,.78,.78]),
        15:([.14,.19,.66,.66],[.28,.04,.70,.70]),
        17:([.22,.18,.68,.68],[.02,.01,.97,.97]),
    }

    def add(start,end,number,view='wide',*,transition='cut',title=None,subtitle=None,foreground=False):
        key=variant_names.get(number,names[number]) if view=='detail' else names[number]
        if number==12 and view=='detail':key='10-threshold-detail'
        asset=assets[key]; identity=asset['containsIdentity']
        s=dict(id=f's{len(scenes)+1:02d}-{asset["id"].split("-",1)[1]}',start=start,end=end,
               src=asset['path'],containsIdentity=identity,layers=[],
               transition=dict(kind=transition,duration=.42),captionTheme='light')
        if identity:
            s.update(faceBounds=asset['faceBounds'],subjectBounds=asset['subjectBounds'],
                     faceMargin=.04,focalRect=[0,0,1,1],focalRectEnd=[.012,0,.985,.985])
            if number in (1,4,6,14):s['atmosphere']=dict(kind='rain',strength=.12)
            elif number in (16,18):s['atmosphere']=dict(kind='water',strength=.15,waterLine=.68)
            else:s['atmosphere']=dict(kind='light',strength=.12)
        else:
            s.update(depthSrc=f'assets/depth/{asset["id"]}.png',depthStrength=.30)
            a,b=details[number]
            if asset.get('variant'):
                s.update(focalRect=[.005,.005,.98,.98],focalRectEnd=[.018,.01,.965,.965])
            elif view=='tree':s.update(focalRect=[.35,.13,.55,.55],focalRectEnd=[.33,.12,.58,.58])
            elif view=='counter':
                targets={7:[.40,.24,.55,.55],13:[.40,.12,.58,.58],15:[.34,.22,.60,.60],17:[.04,.33,.60,.60]}
                r=targets.get(number,[.25,.18,.65,.65]);s.update(focalRect=r,focalRectEnd=[max(0,r[0]-.02),r[1],r[2],r[3]])
            elif view=='detail':s.update(focalRect=a,focalRectEnd=b)
            elif view=='travel':s.update(focalRect=[.02,.02,.94,.94],focalRectEnd=[.05,.01,.94,.94])
            elif view=='reveal':s.update(focalRect=a,focalRectEnd=[.012,.012,.976,.976])
            elif view=='release':s.update(focalRect=[.02,.02,.96,.96],focalRectEnd=[.012,.012,.976,.976])
            else:s.update(focalRect=[.03,.02,.94,.94],focalRectEnd=[.01,.01,.98,.98])
            if number in (2,3,13):s['atmosphere']=dict(kind='rain',strength=.16)
            elif number in (7,9,15,17):s['atmosphere']=dict(kind='water',strength=.18,waterLine=.62)
            else:s['atmosphere']=dict(kind='light',strength=.14)
            if asset.get('variant') and number==17:s['atmosphere']=dict(kind='light',strength=.14)
        if foreground:
            s['layers'].append(dict(id='near-glass',kind='foreground',src='assets/art/foreground-glass.png',
                height=11,x=0,y=0,z=3,
                **{'from':dict(x=0,y=0,z=3),'to':dict(x=-1.7,y=0,z=3.15),'ease':'linear'}))
        if title:
            s.update(title=title,subtitle=subtitle or '',titleStyle=dict(left='10%',top='18%',width='43%',
                      color='#fff6e1',fontSize=58,subtitleSize=28))
        scenes.append(s)

    # Thirteen-second original instrumental, not a restored sung dedication.
    first=cues[0]['start']
    add(0,first*.33,1)
    add(first*.33,first*.66,7,'detail',transition='luma')
    add(first*.66,first,2,'travel',transition='luma',title='兄弟同心',subtitle='Dato Benz')

    for i,cue in enumerate(cues):
        start=cue['start'];end=cues[i+1]['start'] if i<31 else cue['end']
        if i==15:end=cue['end']
        n=plates[i]; chapter=i in (0,4,9,13,16,20,25,29)
        if i in split_indices and end-start>=3.3:
            cut=clause_cut(cue,end)
            add(start,cut,n,'tree' if i==31 else 'detail',transition='luma' if chapter else 'cut')
            second='release' if i in (15,31) else ('counter' if n in (7,13,15) or i==30 else 'travel')
            add(cut,end,n,second)
        else:
            add(start,end,n,'reveal' if i in (2,4,6,18,22) else 'wide',
                transition='luma' if chapter and not assets[names[n]]['containsIdentity'] else 'cut',
                foreground=n in (4,14))
        if i==15:
            a,b=cue['end'],cues[i+1]['start']; step=(b-a)/3
            add(a,a+step,7,'detail',transition='luma')
            add(a+step,a+2*step,9,'travel')
            add(a+2*step,b,12,'reveal')

    tail=cues[-1]['end'];dedication=174.7
    assert tail<dedication<duration
    add(tail,dedication,7,'reveal',transition='luma')
    add(dedication,duration,18,title='风雨同路，兄弟同心\n有难一起担，有路一起闯\n一路同行，共创辉煌',
        subtitle='献给我们敬佩的哥哥\nDato Benz')
    scenes[-1]['titleStyle'].update(fontSize=45,top='21%',width='43%')
    scenes[-1]['focalRectEnd']=scenes[-1]['focalRect']
    scenes[-1]['atmosphere']=dict(kind='light',strength=.08,start=0,end=1)

    cursor=0
    for s in scenes:
        assert abs(s['start']-cursor)<1e-7 and s['end']>s['start']
        cursor=s['end']
    assert abs(cursor-duration)<1e-7
    plan=dict(version=1,duration=duration,fps=24,width=1920,height=1080,background='#071319',
              audio='assets/bgm.wav',captions='captions.json',scenes=scenes,
              concept='以光相伴 / The Light We Carry',native_ai_video=False,
              image_only=True,photo_card_overlays=False)
    write_json(ROOT/'edit-plan.json',plan)
    # Actual deltas/regions are the evidence. Do not claim a velocity-matching
    # numeric seam gate for an intentionally cut music montage.
    write_json(ROOT/'seam-ledger.json',[dict(time=b['start'],from_scene=a['id'],to_scene=b['id'],
        technique=b['transition']['kind'],carrier='warm light / rain glass / architectural edge',
        source_regions=[a.get('focalRectEnd'),b.get('focalRect')],
        measured_velocity_match=False) for a,b in zip(scenes,scenes[1:])])
    print(json.dumps(dict(shots=len(scenes),duration=duration,cues=len(cues),
                         identity_scenes=sum(s['containsIdentity'] for s in scenes))))


if __name__=='__main__':main()
