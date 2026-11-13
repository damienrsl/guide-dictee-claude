#!/usr/bin/env python3
"""Remesure hebdo : rejoue mesure.py sur les 7 derniers jours et envoie 3 chiffres dans l'Encart (rapport, rien d'autre)."""
import json, subprocess, os, time, statistics as st, shutil, datetime
H=os.path.expanduser; W=H('~/Library/Application Support/Wispr Flow/flow.sqlite')
shutil.copy(W,'/tmp/flow.sqlite'); 
if os.path.exists(W+'-wal'): shutil.copy(W+'-wal','/tmp/flow.sqlite-wal')
subprocess.run(['python3',H('~/Documents/guide-dictee-claude/mesure/mesure.py')],capture_output=True)
R=json.load(open(H('~/Documents/guide-dictee-claude/mesure/prompts.json')))
g=[r for r in R if r['src']=='audio' and r['ts']>time.time()-7*86400]
if len(g)<20: txt=f"Trop peu de dictées cette semaine ({len(g)}) pour mesurer."
else:
    mots=st.median([r['mots'] for r in g]); q=round(100*st.mean([r['q'] for r in g])); trous=round(st.mean([r['trous'] for r in g]),2)
    txt=f"Audio, 7 derniers jours ({len(g)} messages) : {mots:.0f} mots par message (était 43, cible 30) · {q} % de questions (était 12, cible 7) · {trous} trou par message (était 0,49, cible 0,20)."
open(H('~/Documents/guide-dictee-claude/mesure/historique.txt'),'a').write(datetime.date.today().isoformat()+' '+txt+'\n')
subprocess.run([H('~/.local/bin/encart-demande'),'rapport','--titre','Dictée : les 3 chiffres de la semaine','--texte',txt,'--url','https://damienrsl.github.io/guide-dictee-claude/'])
