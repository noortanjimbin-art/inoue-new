import io, os, sys

SP = sys.argv[1]
src = io.open('public/index.html', encoding='utf-8').read()


def func(name, text=src):
    i = text.index('function %s(' % name)
    j = text.index('\n}', i) + 2
    return text[i:j]


js = func('tstats')
page = '''<!doctype html><meta charset="utf-8"><title>count harness</title><script>
var CLOUD=true, W={task:null,items:[],ready:false};
var DB={anns:{}, annStats:{}, annStatsAt:0, videos:[{id:'V',dur:100}]};
function videoById(id){ return {id:'V',dur:100}; }
''' + js + '''
window.T=tstats; window.W=W; window.DB=DB; window.setCloud=function(v){ CLOUD=v; };
</script>'''
io.open(os.path.join(SP, 'counts.html'), 'w', encoding='utf-8').write(page)

lib = io.open('api/_lib.js', encoding='utf-8').read()
i = lib.index('export async function allRows')
j = lib.index('\n}\n', i) + 3
allrows = lib[i:j].replace('export async function', 'async function')
page2 = '''<!doctype html><meta charset="utf-8"><title>paging harness</title><script>
''' + allrows + '''
/* A fake PostgREST query: rows sorted by the requested keys, ties broken in a
   DIFFERENT random order on every request - which is what an unspecified order
   is allowed to do. onPage lets a test change the data between page requests. */
function makeTable(rows){
  var T={rows:rows, requests:0, onPage:null};
  T.build=function(){
    var keys=['t_start'];
    var q={ order:function(k){ keys.push(k); return q; },
            range:function(a,b){
              T.requests++; if(T.onPage) T.onPage(T.requests);
              var shuffled=T.rows.slice().sort(function(){ return Math.random()-0.5; });
              shuffled.sort(function(x,y){
                for (var i=0;i<keys.length;i++){ var k=keys[i]; if(x[k]<y[k]) return -1; if(x[k]>y[k]) return 1; }
                return 0; });
              return Promise.resolve({data:shuffled.slice(a,b+1), error:null}); } };
    return q; };
  return T;
}
window.allRows=allRows; window.makeTable=makeTable;
</script>'''
io.open(os.path.join(SP, 'paging.html'), 'w', encoding='utf-8').write(page2)
print('harnesses written')
