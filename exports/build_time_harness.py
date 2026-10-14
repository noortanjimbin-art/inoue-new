import io, os, re, sys

SP = sys.argv[1]
src = io.open('public/index.html', encoding='utf-8').read()


def func(name):
    i = src.index('function %s(' % name)
    j = src.index('\n}', i) + 2
    return src[i:j]


def between(a, b):
    i = src.index(a); j = src.index(b, i)
    return src[i:j]


css = between('<style>', '</style>') + '</style>'
js = '\n'.join([
    func('fmt'),
    between('var QA_EPS=1/30;', 'function sameHandOverlaps('),
    func('sameHandOverlaps'),
    between('function parseTime(', 'var MIN_SPAN'),
    'var MIN_SPAN=1/30;',
    func('editTime'), func('refocusAfterRender'), func('noteNextFocus'),
    func('renderRows'),
    func('annName'), func('annOf'), func('exRows'),
    # wAnns' request body, built exactly as the shipped code builds it
    'var annBusy={}, annNext={};', func('wAnns'),
])
# wAnns references api(); stub that captures the PUT body the server would receive
page = '''<!doctype html><meta charset="utf-8"><title>time edit harness</title>''' + css + '''
<div id="work" style="width:560px;padding:16px">
 <div class="lhead"><span>Recorded</span> <span id="count"></span></div>
 <div class="cols colhead lcols"><div>Start</div><div>End</div><div class="qaonly">QA</div><div>Work details</div><div></div></div>
 <div id="rows"></div><div id="err"></div><input id="exVideo"><input id="exUser"><input id="exStatus">
</div>
<script>
var I18N={editTime:'edit',eTimeFormat:'FORMAT',eTimeOrder:'ORDER',eTimePastEnd:'PAST {d}',timeSaved:'SAVED',
  seekHere:'seek',editCap:'edit',capEmpty:'',capSaved:'cap saved',ovTag:'Overlap',ovCount:'{n} overlaps',
  ovTip:'tip',noRecords:'none',eSaveFail:'SAVEFAIL',eStale:'STALE'};
function t(k,v){ var s=I18N[k]||k; if(v) for(var p in v) s=s.split('{'+p+'}').join(v[p]); return s; }
function $(id){ return document.getElementById(id); }
var LOG={msgs:[], puts:[], persists:0};
function oops(m){ LOG.msgs.push('ERR:'+m); } function flash(m){ LOG.msgs.push('OK:'+m); } function say(){}
function cerr(){} function segs(){ LOG.segs=(LOG.segs||0)+1; }
var CLOUD=true, me={role:'annotator'}, W={items:[],task:{id:'T1'},ready:true,base:3,loaded:true};
var vid={duration:600,currentTime:0};
function api(path,opts){ LOG.puts.push({path:path, body:JSON.parse(JSON.stringify(opts.body))});
  return Promise.resolve({ok:true,count:opts.body.items.length}); }
function persist(){ LOG.persists++; DB.anns[W.task.id]=W.items.slice(); wAnns(W.task.id,W.items); }
function pull(){}
var DB={anns:{}, tasks:[{id:'T1',videoId:'V1',userId:'U1',status:'doing'}]};
function videoById(){ return {name:'TEST.mp4'}; } function userById(){ return {name:'Tester'}; }
''' + js + '''
window.H={ load:function(items,role){ me={role:role||'annotator'}; W.items=items; LOG={msgs:[],puts:[],persists:0};
             DB.anns.T1=items; renderRows(); },
  field:function(row,f){ return document.querySelectorAll('#rows .arow')[row].querySelector('[data-f="'+f+'"]'); },
  type:function(row,f,txt,nextRow,nextF){
    var el=H.field(row,f); el.focus(); el.value=txt;
    var nx=nextRow==null?null:H.field(nextRow,nextF);
    var ev=new FocusEvent('blur',{relatedTarget:nx}); el.onblur(ev); return LOG; },
  items:function(){ return W.items.map(function(i){return [i.start,i.end,i.caption];}); },
  parse:parseTime, exRows:exRows, LOG:function(){return LOG;} };
</script>'''
io.open(os.path.join(SP, 'time.html'), 'w', encoding='utf-8').write(page)

# the server-side validation, extracted verbatim from api/anns.js
a = io.open('api/anns.js', encoding='utf-8').read()
i = a.index('    if (!Array.isArray(items))'); j = a.index('\n    }\n', a.index('for (let k = 0', i)) + 7
check = a[i:j]
srv = '''<!doctype html><meta charset="utf-8"><title>server validation</title><script>
function json(res,code,body){ return {code:code, body:body}; }
function validate(items){ var res=null;
''' + check + '''
  return {code:200}; }
window.V=validate;
</script>'''
io.open(os.path.join(SP, 'srv.html'), 'w', encoding='utf-8').write(srv)
print('harnesses written')
