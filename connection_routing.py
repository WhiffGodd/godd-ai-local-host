# SPDX-License-Identifier: MIT
"""Route declared terminal connections around physical component envelopes."""
import heapq


def route_wire(start,end,source_port,target_port,obstacles):
    directions={'left':(-1,0),'right':(1,0),'positive':(0,-1),'negative':(0,1)}
    def escape(point,port):
        dx,dy=directions[port]
        return (point[0]+dx*3,point[1]+dy*3)
    a,b=escape(start,source_port),escape(end,target_port)
    boxes=[(min(x)-1.2,min(y)-1.2,max(x)+1.2,max(y)+1.2) for x,y in
           (tuple(zip(*points)) for points in obstacles)]
    xs=sorted({-8.,108.,a[0],b[0],*(v for l,t,r,bot in boxes for v in (l,r))})
    ys=sorted({-8.,108.,a[1],b[1],*(v for l,t,r,bot in boxes for v in (t,bot))})
    def blocked(p,q):
        for l,t,r,bot in boxes:
            if p[1]==q[1] and t+1e-7<p[1]<bot-1e-7 and max(min(p[0],q[0]),l)<min(max(p[0],q[0]),r)-1e-7:return True
            if p[0]==q[0] and l+1e-7<p[0]<r-1e-7 and max(min(p[1],q[1]),t)<min(max(p[1],q[1]),bot)-1e-7:return True
        return False
    for p in (a,b):
        if any(l+1e-7<p[0]<r-1e-7 and t+1e-7<p[1]<bot-1e-7 for l,t,r,bot in boxes):
            raise ValueError('A connected terminal is hidden inside another component: leave space around wired components and their terminals')
    first=(xs.index(a[0]),ys.index(a[1]),None)
    queue=[(0.,0.,0,first)];costs={first:0.};parents={};serial=0;goal=None
    while queue:
        _,cost,_,node=heapq.heappop(queue)
        if cost>costs[node]:continue
        x,y,axis=node
        if (xs[x],ys[y])==b:goal=node;break
        for dx,dy,new_axis in ((1,0,0),(-1,0,0),(0,1,1),(0,-1,1)):
            nx,ny=x+dx,y+dy
            if not 0<=nx<len(xs) or not 0<=ny<len(ys):continue
            p,q=(xs[x],ys[y]),(xs[nx],ys[ny])
            if blocked(p,q):continue
            candidate=cost+abs(q[0]-p[0])+abs(q[1]-p[1])+(2 if axis is not None and axis!=new_axis else 0)
            following=(nx,ny,new_axis)
            if candidate>=costs.get(following,float('inf')):continue
            costs[following]=candidate;parents[following]=node;serial+=1
            heuristic=abs(q[0]-b[0])+abs(q[1]-b[1])
            heapq.heappush(queue,(candidate+heuristic,candidate,serial,following))
    if goal is None:raise ValueError('Wire terminals have no clear route; separate the connected components')
    points=[];node=goal
    while True:
        points.append((xs[node[0]],ys[node[1]]))
        if node==first:break
        node=parents[node]
    points=[tuple(start),*reversed(points),tuple(end)]
    result=[]
    for point in points:
        if result and point==result[-1]:continue
        while len(result)>1 and ((result[-2][0]==result[-1][0]==point[0]) or (result[-2][1]==result[-1][1]==point[1])):
            # Only remove a middle vertex when it lies between its neighbors.
            p,q=result[-2:]
            if (q[0]-p[0])*(point[0]-q[0])+(q[1]-p[1])*(point[1]-q[1])<0:break
            result.pop()
        result.append(point)
    if len(result)<2 or len(set(result))<2:raise ValueError('Connected components need distinct exposed terminal positions')
    return [list(point) for point in result]
