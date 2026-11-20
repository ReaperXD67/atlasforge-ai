"""Author the image-only film from the frozen song/lyric clock, not V3 video."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DURATION = 196.760
AUDIO_SHA = '60ee65f074f36b2d31660bee652e111cd84538e51b74a0685cbd895291cd6547'
CAPTION_SHA = '6d3a6b8f711526f7944b5d391cb16340fd1e17db761d1dd41b4d76598a75bd10'
PHOTO = 'assets/references-v3/originals/photo_2026-11-19_17-27-29.jpg'
EVENT = 'assets/photos/brothers.jpg'
SEA = 'assets/photos/seaside.jpg'
ARCH = 'assets/art-v4/foreground-arch.png'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pose(x: float, y: float, z: float, look_x=0., look_y=0.) -> dict:
    return dict(x=x, y=y, z=z, look=[look_x, look_y, 0])


def travel(kind: str, variant: int = 0) -> list[dict]:
    """Explicit establish/travel/arrival; varied magnification has a story purpose."""
    if kind == 'macro':
        a, b = pose(-.9, -.3, 8.7, -.8, -.3), pose(.7, .1, 9.8, .6, 0)
    elif kind == 'wide':
        a, b = pose(-.8, .1, 11.1, -.35, .15), pose(.65, .2, 16.4, .3, .2)
    elif kind == 'dive':
        a, b = pose(-1.0, .3, 16.4, -.45, .2), pose(.7, .15, 9.8, .35, .15)
    elif kind == 'rise':
        a, b = pose(-.5, -.8, 11.8, -.35, -.6), pose(.65, .9, 13.4, .4, .8)
    elif kind == 'photo':
        a, b = pose(-.12, .05, 13.5, -.12, .05), pose(.12, .05, 13., .12, .05)
    elif kind == 'settle':
        a, b = pose(0, 0, 13.3), pose(0, 0, 13.3)
    else:
        a, b = pose(-1.4, .12, 12.2, -.7, .12), pose(1.3, .2, 11.7, .65, .2)
    # World current is leftward in image space: camera travels right. Macro/rise
    # departures and arrivals deliberately reserve the Z/Y axis for story reveals.
    return [dict(at=0, **a), dict(at=1, **b)]


def photo(source=PHOTO, x=2.7, height=7.3, crop=None) -> dict:
    if crop is None:
        crop = [115, 65, 390, 795] if source == PHOTO else (
            [482, 120, 286, 700] if source == EVENT else [0, 210, 535, 960])
    return dict(id='authentic-hock', src=source, kind='photo', crop=crop,
                x=x, y=.25, z=1, height=height, border=.065)


def region(x, y, z, dx=.8, dy=0., dz=.7) -> list[dict]:
    """A composed detail rather than another restart of the full landscape."""
    return [dict(at=0,**pose(x,y,z,x,y)),
            dict(at=1,**pose(x+dx,y+dy,z+dz,x+dx,y+dy))]


def arch(x=-4.3, z=4.5, height=12.5) -> dict:
    return dict(id='foreground-bronze', src=ARCH, kind='art', height=height,
                x=x, y=.4, z=z,
                **{'from': dict(x=x,y=.4,z=z),
                   'to': dict(x=x-3.5,y=.4,z=z+.3), 'ease':'linear'})


def main() -> None:
    assert sha(ROOT/'assets/bgm.wav') == AUDIO_SHA
    assert sha(ROOT/'captions.json') == CAPTION_SHA
    cues = json.loads((ROOT/'captions.json').read_text(encoding='utf-8'))
    assert len(cues) == 40
    scenes: list[dict] = []

    def add(a, b, plate, meaning, motion='traverse', *, picture=None,
            foreground=False, title=None, subtitle=None, dark=False,
            transition='cut', depth=.4, camera=None, title_size=62):
        s = dict(id=f's{len(scenes)+1:02d}-{plate.split("-",1)[1]}',
                 start=a, end=b, src=f'assets/art-v4/{plate}.png',
                 depthSrc=f'assets/depth-v4/{plate}.png', depthStrength=depth,
                 meaning=meaning, camera=camera or travel(motion, len(scenes)),
                 silk=False, occluder='none',
                 transition=dict(kind=transition, duration=.48), layers=[])
        if picture: s['layers'].append(picture)
        if foreground: s['layers'].append(arch())
        if title:
            s.update(title=title, subtitle=subtitle or '', titleStyle=dict(
                color='#21464a' if dark else '#fff9e8', fontSize=title_size,
                left='10%', top='18%', width='42%',background='transparent',
                padding=0,border='none'))
        scenes.append(s)

    # Designed musical introduction: recognize the person, then enter the world.
    add(0, 3.6, '01-thread', 'A genuine person is the reason for this journey', 'photo',
        picture=photo(x=-3.0, height=7.5), depth=.22)
    add(3.6, 7, '01-thread', 'Follow the small red strand into paper fibres', 'macro')
    add(7, 10.5, '02-paper-world', 'A folded page opens into a living river', 'dive')
    add(10.5, 14, '02-paper-world', 'Discover the larger landscape beyond the fold', 'wide')
    add(14, 18.2, '03-incomplete-bridge', 'Two shores and an unfinished connection', 'traverse', foreground=True)
    add(18.2, 22.3, '03-incomplete-bridge', 'Song title over the still-unfinished journey', 'wide',
        title='有你，兄弟同心', subtitle='献给拿督斯里谢惠福', title_size=64,dark=True)

    # Every sung line owns a picture. The measured vocals remain the master clock.
    verse = [
        ('04-first-chapter','A date written into a shared chapter','macro'),
        ('04-first-chapter','The river makes room for an encounter','wide'),
        ('05-memory-arch','The named honoree, from the actual photograph','photo'),
        ('05-memory-arch','A personal chapter opens onto the world','traverse'),
        ('06-shelter','Strong supports shelter the small living world','dive'),
        ('06-shelter','Warm homes held within the arch','wide'),
        ('07-warm-homes','Affection reaches the homes along the path','macro'),
        ('07-warm-homes','Care connects the whole hillside','wide'),
        ('08-confluence','Separate paths approach each other','traverse'),
        ('08-confluence','The tributaries become one','wide'),
        ('09-shared-storm','The weight of a storm becomes visible','dive'),
        ('09-shared-storm','Several supports carry the same burden','wide'),
        ('10-quiet-generosity','Quiet generosity at a human scale','macro'),
        ('10-quiet-generosity','A small light rests inside shelter','traverse'),
        ('11-enduring-braid','Many fibres become a stronger connection','macro'),
        ('11-enduring-braid','The braid endures into the next chapter','wide'),
    ]
    for i, (plate, meaning, motion) in enumerate(verse):
        a=cues[i]['start']; b=cues[i+1]['start']
        add(a,b,plate,meaning,motion,
            picture=photo(x=-3.2) if i==2 else None,
            foreground=i in (3,10))

    # First chorus alternates real identity with the bridge's first complete reveal.
    for i in range(16,24):
        a=cues[i]['start']; b=cues[i+1]['start'] if i<23 else 102.92
        plate='12-bridge-anchor' if i<22 else '13-coast'
        name=i in (16,20)
        p=photo(source=PHOTO if i==16 else EVENT, x=3.3, height=7.0) if name else None
        motion='photo' if name else ('wide' if i in (19,23) else 'traverse')
        detail={17:region(-4,-1,9.5),18:region(-.5,-1.3,10),
                19:region(4,1,10.5),21:region(4,-2.0,10.5)}
        add(a,b,plate,cues[i]['text'],motion,picture=p,foreground=False,
            camera=detail.get(i))

    # Instrumental passage gets new architecture and four distinct camera distances.
    add(102.92,106.5,'14-through-arches','Enter the first near bronze gateway','dive',foreground=True)
    add(106.5,110.4,'14-through-arches','Travel through the nested architecture','macro',foreground=True)
    add(110.4,114.9,'14-through-arches','Arches become the bridge seen from within','traverse')
    add(114.9,119.42,'14-through-arches','Emerge from depth toward living green','wide',foreground=True)

    for i in range(24,32):
        a=cues[i]['start']; b=cues[i+1]['start'] if i<31 else 149.32
        plate='15-gratitude-garden' if i<28 else '16-tea-reflection'
        p=photo(x=-3.7,height=6.7) if i==24 else None
        if i==27: p=photo(source=SEA,x=3.4,height=6.6)
        motion='photo' if p else ('macro' if i in (28,30) else ('rise' if i==26 else 'wide'))
        detail={25:region(4.2,.0,11.0,dx=.6,dz=.3),
                26:region(4.4,.2,11.1,dx=.4,dy=.6,dz=.5),
                27:region(4.1,0,11.7,dx=.3,dz=.2),
                28:region(.5,2.0,9.0,dx=1.0,dy=-.5,dz=.8),
                29:region(1.5,1.5,9.8,dx=-1.0,dy=.5,dz=-.5),
                30:region(-.3,0,16.4,dx=.6,dz=-.7)}
        add(a,b,plate,cues[i]['text'],motion,picture=p,foreground=False,
            depth=.22 if i==30 else .4,camera=detail.get(i))

    # New art for the final chorus, brighter and larger than the first, never a replay.
    for i in range(32,40):
        a=cues[i]['start']; b=cues[i+1]['start'] if i<39 else 170.10
        p=photo(source=EVENT if i==34 else PHOTO, x=3.3,height=7.0) if i in (32,34,36) else None
        motion='photo' if p else ('wide' if i in (33,39) else ('rise' if i==38 else 'traverse'))
        detail={33:region(-4.5,-1.0,9.2,dx=1.0,dz=.8),
                35:region(-6.8,1.0,9.6,dx=.6,dz=.7),
                37:region(4.5,-1.7,9.4,dx=.8,dz=.6),
                38:region(4.0,.4,11.0,dx=.2,dy=.7,dz=.7)}
        add(a,b,'17-climax',cues[i]['text'],motion,picture=p,foreground=False,
            camera=detail.get(i))

    # Do not stop at the last sung line. Resolve the journey into an actual memory.
    add(170.10,175.2,'17-climax','The connected world continues beyond the final words','wide',
        camera=region(.7,.5,16.0,dx=.25,dy=.25,dz=.7))
    add(175.2,180.5,'13-coast','Follow the connection back from the open coast','traverse')
    add(180.5,185.1,'18-memory-return','The immense world returns to a small real memory','wide')
    add(185.1,DURATION,'18-memory-return','A warm dedication to a living person','settle',
        picture=photo(x=5.3,height=7.1),
        title='有你，兄弟同心。\n愿你平安，幸福永久。\n兄弟情义 · 一路同行',
        subtitle='献给拿督斯里谢惠福\nHock Siew',dark=True,title_size=48,depth=0)

    chapter_reveals={7.,14.,22.3,51.66,58.18,66.,73.4,94.34,102.92,119.42,133.96,180.5}
    scenes[5]['titleStyle'].update(left='55%',top='12%',width='35%')
    for i,s in enumerate(scenes):
        if s['start'] in chapter_reveals:
            s['transition']=dict(kind='luma',duration=.42)
        assert abs(s['start']-(scenes[i-1]['end'] if i else 0))<1e-7
        assert s['end']>s['start']
        for key in ('src','depthSrc'):
            if not (ROOT/s[key]).is_file():
                raise FileNotFoundError(ROOT/s[key])
    plan=dict(version=4,concept='同心成桥 / The Bridge We Build',
              duration=DURATION,fps=24,width=1920,height=1080,
              audio='assets/bgm.wav',captions='captions.json',scenes=scenes,
              original_audio_sha256=AUDIO_SHA,canonical_caption_sha256=CAPTION_SHA,
              pacing='Frozen vocal phrase anchors; no unverified BPM claim.',
              native_ai_video=False,generated_humans=False,
              identity_policy='Original file bytes, literal crops, rigid flat photo planes; no face/body generation or displacement.')
    (ROOT/'edit-plan-v4.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    ledger=[]
    for previous,current in zip(scenes,scenes[1:]):
        ledger.append(dict(time=current['start'],from_scene=previous['id'],to_scene=current['id'],
                           technique='lyric-led match/cut',carrier='cinnabar strand / architectural contour',
                           exit_vector=dict(axis='x',sign=-1),entry_vector=dict(axis='x',sign=-1),
                           note='3D foreground overlap and plate-specific perspective; inspect encoded seam.'))
    (ROOT/'seams-v4.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(scenes=len(scenes),plates=len({s['src'] for s in scenes}),duration=DURATION,cues=len(cues))))


if __name__=='__main__':
    main()
