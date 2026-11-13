#!/usr/bin/env python3
"""Croise le journal du Jury (prompts notés) avec l'historique Wispr Flow (dictées) et les transcripts Claude Code
pour mesurer vitesse et précision : audio vs clavier."""
import json, sqlite3, re, glob, os, statistics as st, unicodedata, datetime, difflib, collections
J=[json.loads(l) for l in open(os.path.expanduser('~/.local/share/damienprime/jury/journal.jsonl')) if l.strip()]
db=sqlite3.connect('/tmp/flow.sqlite')
W=db.execute("select timestamp, coalesce(editedText,formattedText,asrText), asrText, speechDuration, duration, numWords, app, editDistanceToDictated from History where timestamp>'2026-10-24' and numWords>=3").fetchall()
def norm(s): return re.sub(r'\s+',' ',unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower()).strip()
def ts(s): return datetime.datetime.fromisoformat(s.replace(' +00:00','+00:00')).timestamp()
Wn=[(ts(w[0]),norm(w[1]),w) for w in W]
def match(p):
    """dictée Wispr dont le texte est contenu dans le prompt (ou l'inverse), dans les 20 min avant l'envoi"""
    pn=norm(p['prompt']); t=p['ts']; best=None
    for wt,wn,w in Wn:
        if not (t-1500 < wt < t+60) or len(wn)<15: continue
        if wn[:60] in pn or pn[:60] in wn:
            best=w if best is None else best
    return best
ACC=re.compile(r'[éèêàçùôîû]')
rows=[]
for p in J:
    w=match(p); txt=p['prompt']; n=len(txt.split())
    if w: src='audio'
    elif not ACC.search(txt) and (txt[:1].islower() or ' ,' in txt or ' .' in txt): src='clavier'
    elif ACC.search(txt) and txt[:1].isupper() and n>=8: src='audio?'   # dictée iPhone probable (Apple), pas dans Wispr
    else: src='?'
    propre=p.get('propre') or ''
    m=re.search(r'Pas encore dit : (.*)',propre)
    trous=len([x for x in m.group(1).split(' ; ') if x.strip()]) if m else 0
    rows.append(dict(ts=p['ts'],session=p['session'],src=src,mots=n,moy=p['moyenne'],but=p['notes'].get('but'),gf=p['notes'].get('gardefou'),
        q=p['verdict']=='question',rem=p['verdict']=='remarques',trous=trous,fid=p.get('fid'),
        parole=w[3] if w else None,wmots=w[5] if w else None,edit=w[7] if w else None,prompt=txt[:160]))
# vitesse : délai entre la fin de la réponse de Claude et l'envoi du prompt (transcripts)
idx={}
for f in glob.glob(os.path.expanduser('~/.claude/projects/*/*.jsonl')):
    sid=os.path.basename(f)[:-6]
    if sid in {r['session'] for r in rows}: idx[sid]=f
def delais(sid):
    out=[]; last_a=None
    try:
        for l in open(idx[sid]):
            try: e=json.loads(l)
            except: continue
            t=e.get('timestamp'); 
            if not t: continue
            tt=datetime.datetime.fromisoformat(t.replace('Z','+00:00')).timestamp()
            if e.get('type')=='assistant': last_a=tt
            elif e.get('type')=='user':
                c=e.get('message',{}).get('content')
                if isinstance(c,str) and last_a: out.append((tt,norm(c)[:80],tt-last_a))
                elif isinstance(c,list) and c and c[0].get('type')=='text' and last_a: out.append((tt,norm(c[0]['text'])[:80],tt-last_a))
    except Exception as ex: pass
    return out
cache={}
for r in rows:
    if r['session'] not in idx: continue
    if r['session'] not in cache: cache[r['session']]=delais(r['session'])
    pn=norm(r['prompt'])[:80]
    for tt,c,d in cache[r['session']]:
        if c==pn or (abs(tt-r['ts'])<120 and c[:40]==pn[:40]): r['delai']=d; break
json.dump(rows,open(os.path.expanduser('~/Documents/guide-dictee-claude/mesure/prompts.json'),'w'),ensure_ascii=False)
def med(x): x=[v for v in x if v is not None]; return round(st.median(x),1) if x else None
def mean(x): x=[v for v in x if v is not None]; return round(st.mean(x),2) if x else None
print('n =',len(rows), collections.Counter(r['src'] for r in rows))
for s in ['audio','audio?','clavier','?']:
    g=[r for r in rows if r['src']==s]
    if not g: continue
    print(f"\n[{s}] n={len(g)} mots med={med([r['mots'] for r in g])} moy={mean([r['moy'] for r in g])} but={mean([r['but'] for r in g])} question={round(100*mean([r['q'] for r in g]))}% remarques={round(100*mean([r['rem'] for r in g]))}% trous/prompt={mean([r['trous'] for r in g])} fid={mean([float(r['fid']) for r in g if r['fid'] not in (None,'None')])}")
    d=[r['delai'] for r in g if r.get('delai') and 5<r['delai']<1800]
    print(f"  délai avant envoi (5 s à 30 min) : n={len(d)} med={med(d)} s ; mots/min d'écriture (mots/délai) med={med([r['mots']/(r['delai']/60) for r in g if r.get('delai') and 5<r['delai']<1800])}")
    if s=='audio':
        print(f"  parole : mots/min med={med([r['wmots']/(r['parole']/60) for r in g if r['parole'] and r['parole']>1])} ; parole med={med([r['parole'] for r in g])} s ; édition après dictée med={med([r['edit'] for r in g])}")
# longueur vs précision
print('\nPar longueur (tous) :')
for lo,hi in [(0,10),(10,25),(25,50),(50,100),(100,10000)]:
    g=[r for r in rows if lo<=r['mots']<hi]
    print(f"  {lo}-{hi} mots n={len(g)} moy={mean([r['moy'] for r in g])} question={round(100*mean([r['q'] for r in g]))}% trous={mean([r['trous'] for r in g])}")
