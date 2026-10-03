"""Independent unbounded threat witness checker. No search/primary imports."""
from collections import deque
from functools import lru_cache


DIRS=((1,0),(0,1),(1,1),(-1,1))


@lru_cache(maxsize=16384)
def lines(stones,minimum=1):
    result=set()
    if len(stones)<minimum:return result
    for dx,dy in DIRS:
        parallel={}
        for x,y in stones:parallel.setdefault(dx*y-dy*x,[]).append((x,y))
        for group in parallel.values():
            if len(group)<minimum:continue
            candidates={frozenset((x+(j-i)*dx,y+(j-i)*dy) for j in range(5))
                        for x,y in group for i in range(5)}
            result.update(s for s in candidates if len(s&stones)>=minimum)
    return result


def five(stones):return bool(lines(stones,5))


def wins(a,d):
    return {next(iter(s-a)) for s in lines(a,4) if not s&d and len(s&a)==4}


def signatures():
    result=set()
    def add(kind,stones,cost,extra=()):
        for g in stones:
            shift=lambda ps:frozenset((x-g[0],y-g[1]) for x,y in ps)
            result.add((kind,shift(set(stones)-{g}),shift(cost),shift(set(cost)|set(extra)|{g})))
    for dx,dy in DIRS:
        p=[(i*dx,i*dy) for i in range(7)]
        add('five',p[:5],())
        for q in p[:5]:add('four',set(p[:5])-{q},{q})
        add('straight_four',p[1:5],(p[0],p[5]))
        for q in p[1:5]:add('three' if q in (p[1],p[4]) else 'broken_three',set(p[1:5])-{q},{p[0],p[5],q})
        add('open_three',p[2:5],(p[1],p[5]),(p[0],p[6]))
    return result


PATTERNS=signatures()


def parse(raw):
    assert isinstance(raw,list) and raw
    def pt(p):
        assert isinstance(p,list) and len(p)==2 and all(type(v) is int for v in p)
        return tuple(p)
    steps=[]
    for row in raw:
        g=pt(row['gain']);ss=[]
        for name in ('required','cost','empty'):
            assert isinstance(row[name],list)
            s=frozenset(pt(p) for p in row[name]);assert len(s)==len(row[name]);ss.append(s)
        offset=lambda s:frozenset((x-g[0],y-g[1]) for x,y in s)
        assert (row['kind'],*(offset(s) for s in ss)) in PATTERNS
        steps.append((g,row['kind'],*ss))
    return steps


@lru_cache(maxsize=8192)
def one_remote_exclusions(positions):
    result=set()
    for a,d in positions:
        for s in lines(d,2):
            if len(s&d)>=2 and not s&a:result.update(s-d)
    return frozenset(result)


def verify(b,w,raw,remaining,*,concrete=False):
    if not __debug__:
        raise RuntimeError('Refusing to verify: Python assertions are disabled')
    assert b and not b&w and not five(b) and not five(w)
    steps=parse(raw)
    # Transitive closure by repeated expansion, separate from the searcher's BFS.
    group={min(b)}
    while True:
        nxt=group|{p for p in b|w if any(abs(p[0]-q[0])<=4 and abs(p[1]-q[1])<=4 for q in group)}
        if nxt==group:break
        group=nxt
    assert b<=group
    # Audit-only path checks a fully specified concrete board, with ALL old
    # White stones present. Certificate verification never enables this flag.
    if concrete:group=b|w
    remote=w-group
    assert not lines(frozenset(remote),3)
    footprint=set(group);positions={(b,frozenset(w&group))}
    for g,_,r,c,e in steps:footprint.update(r|c|e|{g})
    # Work items count actual alternating moves, NOT the number of virtual
    # defenders accumulated by the all-defences sufficient condition.
    pending=deque([(0,b,frozenset(w&group),0)]);seen=set();longest=0
    while pending:
        i,a,d,used=pending.popleft()
        key=i,a,d,used
        if key in seen:continue
        seen.add(key);assert len(seen)<=200000 and i<len(steps)
        gain,kind,required,cost,empty=steps[i]
        assert not five(d) and required<=a and not empty&(a|d)
        a=a|{gain};used+=1;assert used<=remaining
        footprint.update(a|d)
        positions.add((a,d))
        if five(a):longest=max(longest,used);continue
        assert not wins(d,a)
        if kind=='straight_four':longest=max(longest,used+2);continue
        suffix=set()
        for g,_,r,c,e in steps[i:]:suffix.update({g}|r|c|e)
        counters=deque([(a,d,used)]);visited=set()
        while counters:
            aa,dd,count=counters.popleft()
            if (aa,dd,count) in visited:continue
            visited.add((aa,dd,count));assert len(visited)<=200000
            footprint.update(aa|dd)
            positions.add((aa,dd))
            assert not wins(dd,aa)
            if kind in ('three','broken_three','open_three'):
                candidates=set()
                for s in lines(dd,3):
                    if not s&aa and len(s&dd)>=3:candidates.update(s-dd)
                for p in candidates:
                    nd=dd|{p};forced=wins(nd,aa)
                    if not forced:continue
                    assert len(forced)==1 and not (forced|{p})&suffix
                    assert count+2<remaining
                    counters.append((aa|forced,nd,count+2))
            assert not cost&aa and not five(dd|cost)
            longest=max(longest,count+(4 if kind in ('three','broken_three','open_three') else 2))
            assert longest<=remaining
            pending.append((i+1,aa,dd|cost,count+1))
            footprint.update(aa|dd|cost)
            positions.add((aa,dd|cost))
    assert longest<=remaining
    if not remote:return longest
    # Compute independently whether an old remote coordinate can equal a
    # queried coordinate, from the ordered capped gaps separating it from C.
    ranges={}
    for p in remote:
        bounds=[]
        for axis in (0,1):
            vals=sorted({0}|{q[axis] for q in b|w})
            cmin=min(q[axis] for q in group);cmax=max(q[axis] for q in group)
            if cmin<=p[axis]<=cmax:bounds.append((p[axis],p[axis]));continue
            endpoint=cmin if p[axis]<cmin else cmax
            path=vals[ min(vals.index(endpoint),vals.index(p[axis])):max(vals.index(endpoint),vals.index(p[axis]))+1 ]
            capped=any(path[j+1]-path[j]==5 for j in range(len(path)-1))
            bounds.append((None,p[axis]) if capped and p[axis]<cmin else
                          (p[axis],None) if capped else (p[axis],p[axis]))
        ranges[p]=bounds
    def possible(old,q):
        (xlo,xhi),(ylo,yhi)=ranges[old];x,y=q
        return ((xlo is None or x>=xlo) and (xhi is None or x<=xhi)
                and (ylo is None or y>=ylo) and (yhi is None or y<=yhi))
    assert not any(possible(p,q) for p in remote for q in footprint)
    if len(remote)==1:
        old=next(iter(remote))
        assert not any(possible(old,q) for q in one_remote_exclusions(frozenset(positions)))
        return longest
    for a,d in positions:
        for segment in lines(d,max(1,3-len(remote))):
            if segment&a:continue
            if len(segment&d)+len(remote)<3:continue
            extra={p for p in remote if any(possible(p,q) for q in segment-d)}
            assert not extra or len(segment&d)+len(extra)<3
    return longest
