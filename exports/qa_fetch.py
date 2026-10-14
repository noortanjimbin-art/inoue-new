import os, io, json, urllib.request, urllib.parse
BASE=os.environ['SB_URL'].rstrip('/')+'/rest/v1'; KEY=os.environ['SB_KEY']
H={'apikey':KEY,'Authorization':'Bearer '+KEY,'Accept-Profile':'inoue_new'}
def get(p,q,page=1000):
    out,f=[],0
    while True:
        u=BASE+'/'+p+'?'+urllib.parse.urlencode(q)
        c=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers=dict(H,Range='%d-%d'%(f,f+page-1))),timeout=180).read())
        out+=c
        if len(c)<page: return out
        f+=page
snap={'videos':get('videos',{'select':'id,name,dur'}),
      'tasks': get('tasks',{'select':'id,video_id,user_id,status'}),
      'users': get('users',{'select':'id,name'}),
      'anns':  get('anns',{'select':'id,task_id,t_start,t_end,caption','order':'task_id,t_start,id'})}
io.open('exports/qa_snapshot.json','w',encoding='utf-8').write(json.dumps(snap))
print({k:len(v) for k,v in snap.items()})
