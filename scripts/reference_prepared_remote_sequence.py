"""Independent checker for standalone prepared-remote threat certificates.

Standard library and the pre-existing independent local threat checker only.
No imports from src, proposal/search code, or the primary geometric guard.
"""
import argparse
import hashlib
import json
from pathlib import Path
from collections import deque
from scripts.reference_infinite_threat_witness import verify as local_verify, parse, lines, wins, five

FORMAT='freestyle-gomoku-prepared-remote-sequence'


def normalized(b,w):
    mappings=[]
    for axis in (0,1):
        vals=sorted({0}|{p[axis] for p in b|w}); ds=[0]
        for a,c in zip(vals,vals[1:]):
            ds.append(ds[-1]+min(c-a,5))
        zero=ds[vals.index(0)]
        mappings.append(dict(zip(vals,(v-zero for v in ds))))
    return tuple(frozenset((mappings[0][x],mappings[1][y]) for x,y in s) for s in (b,w))


def pt(raw):
    assert isinstance(raw,list) and len(raw)==2 and all(type(v) is int for v in raw)
    return tuple(raw)


def stone_set(raw):
    assert isinstance(raw,list)
    result=frozenset(map(pt,raw)); assert len(result)==len(raw)
    return result


def rigid_group(b,w,anchor):
    assert anchor in b
    group={anchor}
    while True:
        more={q for q in b|w if any(abs(q[0]-p[0])<5 and abs(q[1]-p[1])<5 for p in group)}
        if more<=group:
            return frozenset(group)
        group.update(more)


def record_closure(a,d,steps,h):
    footprint=set(a|d)
    for g,_,r,c,e in steps:
        footprint.update({g}|r|c|e)
    positions={(a,d)}; work=deque([(0,a,d,0)]); seen=set()
    while work:
        i,a,d,used=work.popleft()
        if (i,a,d,used) in seen:
            continue
        seen.add((i,a,d,used)); assert len(seen)<=200000 and i<len(steps)
        gain,kind,_,cost,_=steps[i]
        a=a|{gain}; used+=1
        footprint.update(a|d); positions.add((a,d))
        if five(a) or kind=='straight_four':
            continue
        counters=deque([(a,d,used)]); done=set()
        while counters:
            aa,dd,n=counters.popleft()
            if (aa,dd,n) in done:
                continue
            done.add((aa,dd,n)); assert len(done)<=200000 and n<=h
            footprint.update(aa|dd); positions.add((aa,dd))
            if kind in ('three','broken_three','open_three'):
                candidates=set()
                for s in lines(dd,3):
                    if not s&aa:
                        candidates.update(s-dd)
                for q in candidates:
                    nd=dd|{q}; targets=wins(nd,aa)
                    if not targets:
                        continue
                    assert len(targets)==1
                    nb=aa|targets
                    footprint.update(nb|nd); positions.add((nb,nd))
                    counters.append((nb,nd,n+2))
            following=(aa,dd|cost)
            footprint.update(following[0]|following[1]); positions.add(following)
            work.append((i+1,*following,n+1))
    return frozenset(footprint), positions


def envelopes(b,w,group,outsiders):
    result=[]
    for p in outsiders:
        bounds=[]
        for axis in (0,1):
            values=sorted({0}|{q[axis] for q in b|w})
            lo,hi=min(q[axis] for q in group),max(q[axis] for q in group)
            endpoint=lo if p[axis]<lo else hi if p[axis]>hi else p[axis]
            i,j=sorted((values.index(p[axis]),values.index(endpoint)))
            stretchy=any(values[k+1]-values[k]==5 for k in range(i,j))
            bounds.append((None,p[axis]) if stretchy and p[axis]<lo else
                          (p[axis],None) if stretchy and p[axis]>hi else (p[axis],p[axis]))
        result.append(tuple(bounds))
    return result


def may_equal(box,q):
    (a,b),(c,d)=box; x,y=q
    return (a is None or x>=a) and (b is None or x<=b) and (c is None or y>=c) and (d is None or y<=d)


def concrete_threat_bound(b,w,raw,h):
    """Audit a concrete preimage with ALL stones, including distant Black.

    Used for rejection/regression audits, never as a shortcut establishing
    an abstract certificate. No component or distance guard is assumed.
    """
    assert b and not b&w and not five(b) and not five(w)
    steps=parse(raw);pending=deque([(0,b,w,0)]);seen=set();longest=0
    while pending:
        i,a,d,used=pending.popleft()
        if (i,a,d,used) in seen:continue
        seen.add((i,a,d,used));assert len(seen)<=200000 and i<len(steps)
        gain,kind,required,cost,empty=steps[i]
        assert not five(d) and required<=a and not empty&(a|d)
        a=a|{gain};used+=1;assert used<=h
        if five(a):longest=max(longest,used);continue
        assert not wins(d,a)
        if kind=='straight_four':longest=max(longest,used+2);continue
        suffix=set()
        for g,_,r,c,e in steps[i:]:suffix.update({g}|r|c|e)
        counters=deque([(a,d,used)]);done=set()
        while counters:
            aa,dd,n=counters.popleft()
            if (aa,dd,n) in done:continue
            done.add((aa,dd,n));assert len(done)<=200000 and not wins(dd,aa)
            if kind in ('three','broken_three','open_three'):
                candidates=set()
                for s in lines(dd,3):
                    if not s&aa:candidates.update(s-dd)
                for q in candidates:
                    nd=dd|{q};targets=wins(nd,aa)
                    if not targets:continue
                    assert len(targets)==1 and not ({q}|targets)&suffix and n+2<h
                    counters.append((aa|targets,nd,n+2))
            assert not cost&aa and not five(dd|cost)
            longest=max(longest,n+(4 if kind in ('three','broken_three','open_three') else 2))
            assert longest<=h
            pending.append((i+1,aa,dd|cost,n+1))
    assert longest<=h
    return longest


def verify(data):
    if not __debug__:
        raise RuntimeError('Refusing to verify: Python assertions are disabled')
    assert data['format']==FORMAT and data['version']==1
    assert data['rules']=={'target':5,'overline_wins':True,'forbidden_moves':False}
    b,w=stone_set(data['black']),stone_set(data['white'])
    assert b and not b&w and not five(b) and not five(w)
    assert normalized(b,w)==(b,w)
    assert data['to_move']=='black' and len(b)==len(w)
    h=data['max_total_plies']-len(b)-len(w)
    assert type(data['max_total_plies']) is int and h>=1
    anchor=pt(data['anchor']); group=rigid_group(b,w,anchor)
    a,d=b&group,w&group
    bound=local_verify(a,d,data['sequence'],h)
    footprint,positions=record_closure(a,d,parse(data['sequence']),h)
    rb,rw=b-group,w-group
    for segment in lines(frozenset(rw),3):
        assert segment&b
    boxes_b=envelopes(b,w,group,rb); boxes_w=envelopes(b,w,group,rw)
    assert not any(may_equal(box,q) for box in boxes_b+boxes_w for q in footprint)
    for aa,dd in positions:
        for segment in lines(dd,1):
            if segment&aa:
                continue
            n=sum(any(may_equal(box,q) for q in segment-dd) for box in boxes_w)
            assert n==0 or len(segment&dd)+n<3
    return dict(status='VERIFIED_PREPARED_REMOTE_STATE', root_black=data['black'],
                root_white=data['white'], max_total_plies=data['max_total_plies'],
                remaining_plies=bound, latest_win_ply=len(b)+len(w)+bound,
                footprint_size=len(footprint), closure_positions=len(positions),
                remote_black_count=len(rb),remote_white_count=len(rw),
                scope='all integer preimages of this normalized root; all future White legal moves')


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('certificate',type=Path); ap.add_argument('--output',type=Path)
    args=ap.parse_args(); data=json.loads(args.certificate.read_text(encoding='utf-8'))
    receipt=verify(data)
    receipt['certificate_sha256']=hashlib.sha256(args.certificate.read_bytes()).hexdigest()
    receipt['checker_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    receipt['local_checker_sha256']=hashlib.sha256(Path('scripts/reference_infinite_threat_witness.py').read_bytes()).hexdigest()
    text=json.dumps(receipt,ensure_ascii=False,indent=2)
    if args.output:
        args.output.write_text(text+'\n',encoding='utf-8')
    print(text)


if __name__=='__main__':
    main()
