"""Shorten narration using complete sentences while keeping every visual beat."""

import re


SENTENCES = re.compile(r'(?<=[.!?])\s+')
CAUSAL = re.compile(r'\b(?:because|allows?|causes?|keeps?|moves?|push\w*|pull\w*|turn\w*|rotat\w*|roll\w*|compress\w*|releas\w*|transfer\w*|rais\w*|lowers?|converts?|prevents?|so|therefore)\b',re.I)
STOP_WORDS = {'the','a','an','of','to','and','in','with','how','why','this','that','is','are'}


def word_count(scenes):
    return sum(len(scene['narration'].split()) for scene in scenes)


def compact_sentences(scenes,budget):
    """Return an extractive shorter script, or None if sentences need rewriting.

    Never cut a sentence or delete a scene. The hook and the last sentence of
    the payoff stay intact. Added detail keeps its original order within a beat.
    """
    if word_count(scenes)<=budget:
        return [dict(scene) for scene in scenes]
    if len(scenes)<2:
        return None
    rows,selected,scores = [],[],[]
    used = len(scenes[0]['narration'].split())
    for index,scene in enumerate(scenes[1:]):
        sentences = [text.strip() for text in SENTENCES.split(scene['narration'].strip()) if text.strip()]
        if not sentences or any(not re.search(r'[.!?]["\u201d\u2019]?$',text) for text in sentences):
            return None
        subject = set(re.findall(r'\w+',scene['heading'].casefold()))-STOP_WORDS
        rank = []
        for position,text in enumerate(sentences):
            words = set(re.findall(r'\w+',text.casefold()))-STOP_WORDS
            score = len(subject&words)*2+len(CAUSAL.findall(text))+(1 if position==0 else 0)
            rank.append(score)
        core = len(sentences)-1 if index==len(scenes)-2 else max(range(len(sentences)),key=lambda pos:rank[pos])
        rows.append(sentences)
        scores.append(rank)
        selected.append({core})
        used += len(sentences[core].split())
    if used>budget:
        return None
    extras = [(scores[row][position]+(2 if position==0 else 0),row,position)
              for row,sentences in enumerate(rows) for position in range(len(sentences))
              if position not in selected[row]]
    for _,row,position in sorted(extras,key=lambda item:(-item[0],item[1],item[2])):
        count = len(rows[row][position].split())
        if used+count<=budget:
            selected[row].add(position)
            used += count
    result = [dict(scenes[0])]
    for scene,sentences,chosen in zip(scenes[1:],rows,selected):
        narration = ' '.join(sentences[position] for position in sorted(chosen))
        caption = narration if len(narration)<=96 else scene['heading']+'.'
        result.append({**scene,'narration':narration,'caption':caption})
    return result
