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
    contract=input_contract();cues=read_json(ROOT/'captions.json')
    layout=read_json(ROOT/'art-layout.json');assets={a['id']:a for a in layout['assets']}
    if any(a.get('containsIdentity') for a in assets.values()):
        raise ValueError('Active artwork layout must exclude all identity artwork')
    # Each row binds one measured sung line to physical subjects, without
    # publishing the private lyric text. A second subject uses an aligned cut.
    edits=[
        ('19-storm-coast',None),
        ('20-rope-bond','03-support-detail'),
        ('25-woven-shelter',None),
        ('21-shared-workshop','10-threshold-detail'),
        ('23-rooted-growth','21-shared-workshop'),
        ('05-quiet-strength',None),
        ('03-shared-weight',None),
        ('10-threshold-detail','10-open-homes'),
        ('22-community-table',None),
        ('23-rooted-growth','12-many-windows'),
        ('20-rope-bond','21-shared-workshop'),
        ('25-woven-shelter','02-storm-pass'),
        ('24-river-confluence',None),
        ('09-paths-converge','24-river-confluence'),
        ('03-support-detail','19-storm-coast'),
        ('17-community-detail','17-dawn-community'),
        ('21-shared-workshop',None),
        ('10-open-homes','12-many-windows'),
        ('20-rope-bond','03-shared-weight'),
        ('25-woven-shelter',None),
        ('19-storm-coast','13-storm-return'),
        ('09-light-detail',None),
        ('13-storm-return','25-woven-shelter'),
        ('20-rope-bond','21-shared-workshop'),
        ('26-dawn-harbour',None),
        ('23-rooted-growth','17-dawn-community'),
        ('22-community-table','17-community-detail'),
        ('10-open-homes',None),
        ('24-river-confluence',None),
        ('25-woven-shelter','15-lights-return'),
        ('21-shared-workshop','20-rope-bond'),
        ('17-community-detail','26-dawn-harbour'),
    ]
    assert len(edits)==len(cues)==32
    duration=contract['duration'];scenes=[]
    close_subjects={'03-support-detail','09-light-detail','10-threshold-detail',
                    '17-community-detail','20-rope-bond','22-community-table',
                    '23-rooted-growth','25-woven-shelter'}
    def add(start,end,key,view='wide',*,transition='cut',title=None,subtitle=None,foreground=False):
        asset=assets[key]
        if asset.get('containsIdentity') or any(k in asset for k in ('faceBounds','subjectBounds')):
            raise ValueError('A person source cannot enter this film')
        s=dict(id=f's{len(scenes)+1:02d}-{key.split("-",1)[1]}',start=start,end=end,
               src=asset['path'],containsIdentity=False,layers=[],
               depthSrc=f'assets/depth/{key}.png',depthStrength=.25,
               transition=dict(kind=transition,duration=.36),captionTheme='light')
        if key in close_subjects:
            s.update(focalRect=[.015,.015,.97,.97],focalRectEnd=[.04,.025,.94,.94])
        elif view=='reveal':
            s.update(focalRect=[.13,.12,.82,.82],focalRectEnd=[.015,.015,.97,.97])
        elif view=='counter':
            s.update(focalRect=[.30,.10,.67,.67],focalRectEnd=[.28,.10,.69,.69])
        elif view=='travel':
            s.update(focalRect=[.02,.02,.94,.94],focalRectEnd=[.045,.02,.94,.94])
        else:
            s.update(focalRect=[.02,.02,.96,.96],focalRectEnd=[.01,.01,.98,.98])
        if key in {'02-storm-pass','13-storm-return','19-storm-coast','25-woven-shelter'}:
            s['atmosphere']=dict(kind='rain',strength=.10)
        elif key in {'07-light-ripples','15-lights-return','24-river-confluence','26-dawn-harbour'}:
            s['atmosphere']=dict(kind='water',strength=.10,waterLine=.68)
        else:
            s['atmosphere']=dict(kind='light',strength=.10)
        if foreground:
            s['layers'].append(dict(id='near-glass',kind='foreground',src='assets/art/foreground-glass.png',
                height=11,x=0,y=0,z=3,
                **{'from':dict(x=0,y=0,z=3),'to':dict(x=-1.7,y=0,z=3.15),'ease':'linear'}))
        if title:
            s.update(title=title,subtitle=subtitle or '',titleStyle=dict(left='9%',top='18%',width='47%',
                      color='#fff6e1',fontSize=58,subtitleSize=28))
        scenes.append(s)
    first=cues[0]['start']
    add(0,first*.33,'19-storm-coast','travel')
    add(first*.33,first*.66,'20-rope-bond',transition='luma')
    add(first*.66,first,'21-shared-workshop','travel',transition='luma',title='兄弟同心',subtitle='Dato Benz')
    for i,(cue,(first_key,second_key)) in enumerate(zip(cues,edits)):
        start=cue['start'];end=cues[i+1]['start'] if i<31 else cue['end']
        if i==15:end=cue['end']
        chapter=i in {0,4,9,13,16,20,24,28}
        view='counter' if i==22 else ('reveal' if i in {6,12,24,28} else 'travel')
        if second_key:
            cut=clause_cut(cue,end)
            add(start,cut,first_key,view,transition='luma' if chapter else 'cut')
            add(cut,end,second_key,'wide',foreground=i==7)
        else:
            add(start,end,first_key,view,transition='luma' if chapter else 'cut')
        if i==15:
            a,b=cue['end'],cues[i+1]['start'];step=(b-a)/3
            add(a,a+step,'26-dawn-harbour','travel',transition='luma')
            add(a+step,a+2*step,'07-light-ripples')
            add(a+2*step,b,'19-storm-coast','counter')
    tail=cues[-1]['end'];dedication=174.7
    assert tail<dedication<duration
    add(tail,dedication,'07-light-ripples','reveal',transition='luma')
    add(dedication,duration,'26-dawn-harbour',title='风雨同路，兄弟同心\n有难一起担，有路一起闯\n一路同行，共创辉煌',
        subtitle='献给我们敬佩的哥哥\nDato Benz')
    closing=scenes[-1]
    closing['titleStyle'].update(left='7%',top='18%',width='47%',fontSize=45)
    closing['titleAlign']='center'
    closing['focalRect']=[.012,.012,.976,.976];closing['focalRectEnd']=closing['focalRect'][:]
    closing['depthStrength']=.12;closing['atmosphere']=dict(kind='light',strength=.06,start=0,end=1)
    cursor=0
    for s in scenes:
        assert abs(s['start']-cursor)<1e-7 and s['end']>s['start']
        cursor=s['end']
    assert abs(cursor-duration)<1e-7
    used={s['src'] for s in scenes}
    expected={a['path'] for a in assets.values() if a['id'][:2].isdigit()}
    assert used==expected,'Every approved person-free main plate must appear'
    plan=dict(version=2,duration=duration,fps=24,width=1920,height=1080,background='#071319',
              identityPolicy='excluded',audio='assets/bgm.wav',captions='captions.json',scenes=scenes,
              concept='以光相伴 / The Light We Carry',native_ai_video=False,
              image_only=True,photo_card_overlays=False)
    write_json(ROOT/'edit-plan.json',plan)
    write_json(ROOT/'seam-ledger.json',[dict(time=b['start'],from_scene=a['id'],to_scene=b['id'],
        technique=b['transition']['kind'],carrier='rope / joinery / rain / water / shared light',
        source_regions=[a.get('focalRectEnd'),b.get('focalRect')],
        measured_velocity_match=False) for a,b in zip(scenes,scenes[1:])])
    print(json.dumps(dict(shots=len(scenes),duration=duration,cues=len(cues),
                         main_plates=len(used),identity_policy='excluded',identity_scenes=0)))


if __name__=='__main__':main()
