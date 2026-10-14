import os, json, urllib.request, urllib.parse
BASE=os.environ['SB_URL'].rstrip('/')+'/rest/v1'; KEY=os.environ['SB_KEY']
H={'apikey':KEY,'Authorization':'Bearer '+KEY,'Accept-Profile':'inoue_new'}
def get(p,q,page=1000):
    out,f=[],0
    while True:
        u=BASE+'/'+p+'?'+urllib.parse.urlencode(q)
        c=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers=dict(H,Range='%d-%d'%(f,f+page-1))),timeout=120).read())
        out+=c
        if len(c)<page: return out
        f+=page
vids={v['id']:v['name'] for v in get('videos',{'select':'id,name'})}
users={u['id']:u['name'] for u in get('users',{'select':'id,name'})}
tasks=get('tasks',{'select':'id,video_id,user_id,status'})
def hand(c):
    c=c.lower().strip()
    return 'L' if c.startswith('left') else 'R' if c.startswith('right') else 'B'
def tc(s): return '%02d:%05.2f'%(s//60,s%60)
for name in ('E06-S01a.mp4','E09-S01a.mp4'):
    ts=[t for t in tasks if vids.get(t['video_id'])==name]
    print('=== %s : %d tasks ===' % (name,len(ts)))
    A={}
    for t in ts:
        A[t['id']]=get('anns',{'select':'t_start,t_end,caption','task_id':'eq.'+t['id'],'order':'t_start'})
        print('  %-20s %-6s %4d captions  %s..%s' % (users.get(t['user_id']),t['status'],len(A[t['id']]),
              tc(A[t['id']][0]['t_start']),tc(max(a['t_end'] for a in A[t['id']]))))
    a,b=[A[t['id']] for t in ts]
    for label,thr in (('overlap >=50% (same hand)',0.5),('any overlap (same hand)',0.0)):
        used=set(); pairs=[]
        for x in a:
            best=None
            for j,y in enumerate(b):
                if j in used or hand(x['caption'])!=hand(y['caption']): continue
                inter=min(x['t_end'],y['t_end'])-max(x['t_start'],y['t_start'])
                if inter<=0: continue
                iou=inter/(max(x['t_end'],y['t_end'])-min(x['t_start'],y['t_start']))
                if iou>=thr and (best is None or iou>best[0]): best=(iou,j,y)
            if best: used.add(best[1]); pairs.append((x,best[2],best[0]))
        print('  matched pairs, %s: %d' % (label,len(pairs)))
        if thr==0.5:
            same=sum(1 for x,y,_ in pairs if x['caption'].strip().lower()==y['caption'].strip().lower())
            print('    of which identical wording: %d  -> different wording: %d' % (same,len(pairs)-same))
            for x,y,_ in pairs[:3]:
                print('    %s  "%s"\n    %s  "%s"' % (tc(x['t_start']),x['caption'][:55],tc(y['t_start']),y['caption'][:55]))
    if name=='E06-S01a.mp4':
        print('  --- around 01:38 ---')
        for t in ts:
            for r in A[t['id']]:
                if r['t_start']<=100 and r['t_end']>=96 and hand(r['caption'])=='R':
                    print('   %-18s %s-%s  %s' % (users.get(t['user_id']),tc(r['t_start']),tc(r['t_end']),r['caption']))
