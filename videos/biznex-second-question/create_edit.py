"""Author this film's reusable voice anchors and art direction; no guessed release timing."""
import argparse
import json
from pathlib import Path


def write_project(project: Path, *, baseline: bool = False) -> None:
    rows = [
        ('s01', None, 'phone.png', 'object', 'phone', 'phone-macro', 'extreme_close', 'push_in', 'phone'),
        ('s02', 'A new account', 'phone.png', 'interface', 'signup', 'full-signup', 'insert', 'tracking', 'signup'),
        ('s03', ('A fresh start', 1), 'mira-wide.png', 'environment', 'apartment', 'room-wide', 'wide', 'pull_out', 'photo'),
        ('s04', 'Then a smaller thought', 'mira-night.png', 'character', 'mira', 'night-closeup', 'close', 'locked', 'photo'),
        ('s05', ('A fresh start', 2), 'mira-mirror.png', 'character', 'reflection', 'mirror-medium', 'medium', 'push_in', 'photo'),
        ('s06', 'doing what', 'mira-mirror.png', 'typography', 'question', 'mirror-question', 'close', 'locked', 'thought'),
        ('s07', 'This is a fictional scene', 'mira-wide.png', 'environment', 'apartment', 'room-wide', 'wide', 'pan', 'photo'),
        ('s08', 'Mira closed the signup page', 'phone.png', 'object', 'phone', 'phone-macro', 'insert', 'locked', 'phone'),
        ('s09', 'and opened a blank note', 'phone.png', 'interface', 'note', 'full-note', 'insert', 'tracking', 'notes'),
        ('s10', 'What do I need', 'phone.png', 'interface', 'note', 'full-note', 'insert', 'push_in', 'note-question'),
        ('s11', 'What will it cost', 'phone.png', 'interface', 'question', 'cost-question', 'close', 'pan', 'question'),
        ('s12', 'What am I agreeing to', 'mira-mirror.png', 'character', 'reflection', 'mirror-question', 'medium', 'locked', 'thought'),
        ('s13', 'Atomy was the business', 'mira-night.png', 'character', 'mira', 'night-closeup', 'close', 'pull_out', 'photo'),
        ('s14', 'This time', 'mira-wide.png', 'interface', 'terms', 'research-terms', 'insert', 'push_in', 'terms'),
        ('s15', 'She still wanted a new beginning', 'mira-morning.png', 'character', 'mira', 'morning-writing', 'medium', 'locked', 'photo'),
        ('s16', 'Now she wanted to understand it', 'mira-dawn.png', 'environment', 'apartment', 'morning-window', 'wide', 'pull_out', 'photo'),
        ('s17', 'Before the next tap', 'phone-morning.png', 'object', 'phone', 'phone-macro', 'extreme_close', 'push_in', 'phone'),
        ('s18', 'ask the second question', 'mira-dawn.png', 'character', 'mira', 'final-resolve', 'wide', 'locked', 'ending'),
    ]
    actions = [
        'A fingertip pauses just above the account button.',
        'Move into an editable illustrated account screen.',
        'Reveal Mira alone in her room beside the rainy window.',
        'Mira breathes and hesitates before her decision.',
        'Her own reflection redirects her attention inward.',
        'The unresolved question replaces the promise of a new start.',
        'Return to her room and state that this scene is fictional.',
        'The signup screen recedes from her unfinished action.',
        'A clean note opens, ready for her own questions.',
        'Write the first concrete question about her needs.',
        'Change scale and write the practical question about cost.',
        'Finish the note by asking what the agreement means.',
        'Name Atomy as the subject of her research, without a promised outcome.',
        'Show the next research step: current local terms before deciding.',
        'Morning light finds Mira writing rather than rushing.',
        'Widen to show her calmer posture and the open window.',
        'Return to the opening fingertip with a different question.',
        'Resolve with one useful action and the BizNex Stories identity.',
    ]
    shots, directions = [], {}
    for index, (ident, phrase, asset, kind, subject, layout, framing, camera, mode) in enumerate(rows):
        anchor = {'boundary': 'start'} if phrase is None else (
            {'phrase': phrase[0], 'occurrence': phrase[1]} if isinstance(phrase, tuple) else {'phrase': phrase})
        motion = project / f'assets/motion/{Path(asset).stem}.mp4'
        moving = ident in {'s04', 's15'} and motion.is_file()
        asset_path = f'assets/motion/{motion.name}' if moving else f'assets/plates/{asset}'
        transition = {'kind': 'cut', 'frames': 0}
        if ident in {'s02', 's09'}:
            transition = {'kind': 'match_cut', 'frames': 0}
        if ident == 's15':
            transition = {'kind': 'dissolve', 'frames': 12}
        shots.append({'id':ident,'start':anchor,'asset':asset_path,'visual_kind':kind,
                      'subject':subject,'location':'morning-apartment' if ident in {'s15','s16','s17','s18'} else 'night-apartment',
                      'layout':layout,'framing':framing,'camera':camera,
                      'subject_motion':'performance' if moving else ('action' if mode in {'signup','notes','question'} else 'still'),
                      'action':actions[index],'expression':'Reflective, then quietly hopeful.',
                      'cut_reason':actions[index],'transition':transition})
        directions[ident] = {'mode': mode, 'camera_from':[1.04,0,0], 'camera_to':[1.04,0,0]}
        if camera == 'push_in':
            directions[ident].update(camera_from=[1.02,0,0],camera_to=[1.10,-15,15])
        elif camera == 'pull_out':
            directions[ident].update(camera_from=[1.11,12,12],camera_to=[1.03,0,0])
        elif camera == 'pan':
            directions[ident].update(camera_from=[1.08,-32,0],camera_to=[1.08,32,0])
        if camera == 'tracking':
            directions[ident].update(camera_from=[1,0,0],camera_to=[1.02,0,10])
    directions['s01'].update(heading='A fresh|start?',button='Create account',small='One tap can wait.')
    directions['s02']['hide_captions']=True
    directions['s04']['focus']={'anchorX':51,'anchorY':42,'startZoom':1.04,'endZoom':1.04,'driftX':0,'driftY':0}
    directions['s06'].update(heading='doing|what?',hide_captions=True)
    directions['s07']['disclosure']=True
    directions['s08'].update(heading='Not|quite yet.',button='Back',small='First, a question.')
    for ident,heading,detail in [('s10','What do|I need?','Start with your own reason.'),('s11','What will|it cost?','Understand the full commitment.'),('s12','What am I|agreeing to?','Read before you decide.')]:
        directions[ident].update(heading=heading,detail=detail,hide_captions=True)
    directions['s12']['prefix']='BEFORE THE DECISION'
    directions['s13'].update(caption_y=1160)
    directions['s15']['caption_y']=1160
    directions['s17'].update(heading='Before|the tap.',button='Understand first',small='The second question matters.')
    directions['s18'].update(hide_captions=True)
    audio=[
        {'id':'voice','role':'voice','asset':'assets/audio/narration-baseline.wav' if baseline else 'assets/audio/narration.wav','start':{'boundary':'start'},'end':{'boundary':'end'},'gain_db':0},
        {'id':'score','role':'music','asset':'assets/audio/hiraeth.mp3','start':{'boundary':'start'},'end':{'boundary':'end'},'source_start_frame':30*68,'gain_db':-10,'duck_db':-10,'fade_in_frames':30,'fade_out_frames':45,
         'gain_keyframes':[
             {'at':{'boundary':'start'},'offset_db':0},
             {'at':{'phrase':'Before the next tap','offset_frames':-6},'offset_db':0},
             {'at':{'phrase':'Before the next tap'},'offset_db':-6},
             {'at':{'boundary':'end'},'offset_db':-6},
         ]},
    ]
    # Optional acquired stems are added only when the licensed files really exist.
    if (project/'assets/audio/rain.wav').is_file():
        audio.append({'id':'rain','role':'ambience','asset':'assets/audio/rain.wav','start':{'boundary':'start'},'end':{'phrase':'She still wanted a new beginning'},'gain_db':-24,'duck_db':-3,'fade_in_frames':12,'fade_out_frames':24})
    for ident,phrase in [('open-note','and opened a blank note'),('turn-back','Mira closed the signup page')]:
        if (project/'assets/audio/click.wav').is_file():
            audio.append({'id':ident,'role':'foley','asset':'assets/audio/click.wav','start':{'phrase':phrase},'duration_frames':6,'gain_db':-18,'fade_in_frames':0,'fade_out_frames':2})
    plan={'schema_version':1,'project_id':'biznex-second-question','fps':30,'width':1080,'height':1920,
          'timing_file':'baseline-timing.json' if baseline else 'timing.json','shots':shots,'audio':audio,
          'captions':{'max_words':4,'max_characters':32,'hold_frames':3},
          'policy':{'min_shots':12,'min_visual_kinds':3,'min_visual_assets':4,'min_layouts':5,'min_subjects':3,'min_framings':4,'min_camera_moves':3,'max_shot_seconds':6,'max_same_layout_seconds':7,'max_static_seconds':4.5,'require_layered_audio':True}}
    direction={'schema_version':1,'title':'The Second Question — BizNex Stories','audio_master':'assets/audio/master.wav','shots':directions,'review_state':'baseline development' if baseline else 'expressive candidate'}
    for name,value in [('EDIT_PLAN.json',plan),('DIRECTION.json',direction)]:
        (project/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',action='store_true')
    args=parser.parse_args()
    write_project(Path(__file__).resolve().parent,baseline=args.baseline)
