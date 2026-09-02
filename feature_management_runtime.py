"""UGAMAP Feature Management: persistent flags, targeting, gradual rollouts, A/B variants and evaluation history."""
import hashlib,json,os,sqlite3,time,uuid
from fastapi import APIRouter,Header,HTTPException
from pydantic import BaseModel,Field
from auth import require_permission
BASE=os.path.dirname(os.path.abspath(__file__));DB=os.path.join(BASE,'data_hub.db');router=APIRouter(prefix='/platform/feature-runtime',tags=['platform-feature-management'])
def conn():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def read(code):require_permission(code,'shipments:read')
def write(code):require_permission(code,'shipments:write')
def now():return time.time()
def init():
 c=conn();c.executescript('''CREATE TABLE IF NOT EXISTS platform_feature_audiences(id TEXT PRIMARY KEY,feature_key TEXT NOT NULL,name TEXT NOT NULL,rules TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL);CREATE TABLE IF NOT EXISTS platform_feature_evaluations(id TEXT PRIMARY KEY,feature_key TEXT NOT NULL,subject_key TEXT NOT NULL,enabled INTEGER NOT NULL,variant TEXT,reason TEXT NOT NULL,context TEXT,created_at REAL NOT NULL);CREATE TABLE IF NOT EXISTS platform_feature_releases(id TEXT PRIMARY KEY,feature_key TEXT NOT NULL,action TEXT NOT NULL,detail TEXT,actor TEXT,created_at REAL NOT NULL);''');c.commit();c.close()
init()
class FlagIn(BaseModel):feature_key:str;enabled:bool=False;rollout_percent:int=Field(default=0,ge=0,le=100);variant_a:int=Field(default=50,ge=0,le=100);variant_b:int=Field(default=50,ge=0,le=100);target_rules:dict={}
class AudienceIn(BaseModel):feature_key:str;name:str;rules:dict
class EvalIn(BaseModel):feature_key:str;subject_key:str;context:dict={}
class ReleaseIn(BaseModel):feature_key:str;action:str;actor:str='staff';detail:str=''
def bucket(feature_key,subject_key):return int(hashlib.sha256((feature_key+'|'+subject_key).encode()).hexdigest()[:8],16)%100
def matches(rules,ctx):
 for k,v in (rules or {}).items():
  actual=ctx.get(k)
  if isinstance(v,list):
   if actual not in v:return False
  elif actual!=v:return False
 return True
@router.post('/flags')
def upsert_flag(p:FlagIn,x_access_code:str=Header(default='')):
 write(x_access_code)
 if p.variant_a+p.variant_b!=100:raise HTTPException(400,'variant_a + variant_b must equal 100')
 c=conn();t=now();c.execute('INSERT OR REPLACE INTO platform_features VALUES (?,?,?,?,?,?,?)',(p.feature_key,1 if p.enabled else 0,p.rollout_percent,p.variant_a,p.variant_b,json.dumps(p.target_rules),t));c.execute('INSERT INTO platform_feature_releases VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),p.feature_key,'upsert',json.dumps({'enabled':p.enabled,'rollout_percent':p.rollout_percent,'variant_a':p.variant_a,'variant_b':p.variant_b,'target_rules':p.target_rules}),'staff',t));c.commit();c.close();return {'feature_key':p.feature_key,'enabled':p.enabled,'rollout_percent':p.rollout_percent,'variant_split':{'A':p.variant_a,'B':p.variant_b},'target_rules':p.target_rules}
@router.get('/flags')
def flags(x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT * FROM platform_features ORDER BY feature_key')];c.close()
 for x in r:x['enabled']=bool(x['enabled']);x['target_rules']=json.loads(x['target_rules'] or '{}')
 return {'results':r}
@router.post('/audiences')
def audience(p:AudienceIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();aid='AUD-'+uuid.uuid4().hex[:8].upper();t=now();c.execute('INSERT INTO platform_feature_audiences VALUES (?,?,?,?,?,?)',(aid,p.feature_key,p.name,json.dumps(p.rules),t,t));c.commit();c.close();return {'id':aid,'feature_key':p.feature_key,'name':p.name,'rules':p.rules}
@router.get('/audiences/{feature_key}')
def audiences(feature_key:str,x_access_code:str=Header(default='')):read(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT * FROM platform_feature_audiences WHERE feature_key=? ORDER BY name',(feature_key,))];c.close();
# normalize below
 return {'results':[{**x,'rules':json.loads(x['rules'] or '{}')} for x in r]}
@router.post('/evaluate')
def evaluate(p:EvalIn,x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();f=c.execute('SELECT * FROM platform_features WHERE feature_key=?',(p.feature_key,)).fetchone()
 if not f:c.close();raise HTTPException(404,'Feature flag not found')
 reason='disabled';enabled=False;variant=None;rules=json.loads(f['target_rules'] or '{}')
 if f['enabled']:
  if rules and matches(rules,p.context):enabled=True;reason='target_match'
  else:
   bs=bucket(p.feature_key,p.subject_key);enabled=bs<int(f['rollout_percent']);reason='rollout_match' if enabled else 'outside_rollout'
  if enabled:
   vb=bucket(p.feature_key+'-variant',p.subject_key);variant='A' if vb<int(f['variant_a']) else 'B'
 c.execute('INSERT INTO platform_feature_evaluations VALUES (?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),p.feature_key,p.subject_key,1 if enabled else 0,variant,reason,json.dumps(p.context),now()));c.commit();c.close();return {'feature_key':p.feature_key,'subject_key':p.subject_key,'enabled':enabled,'variant':variant,'reason':reason}
@router.post('/release')
def release(p:ReleaseIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();f=c.execute('SELECT * FROM platform_features WHERE feature_key=?',(p.feature_key,)).fetchone()
 if not f:c.close();raise HTTPException(404,'Feature flag not found')
 action=p.action.lower()
 if action=='enable':c.execute('UPDATE platform_features SET enabled=1,updated_at=? WHERE feature_key=?',(now(),p.feature_key))
 elif action=='disable':c.execute('UPDATE platform_features SET enabled=0,updated_at=? WHERE feature_key=?',(now(),p.feature_key))
 elif action=='canary':c.execute('UPDATE platform_features SET enabled=1,rollout_percent=5,updated_at=? WHERE feature_key=?',(now(),p.feature_key))
 elif action=='half':c.execute('UPDATE platform_features SET enabled=1,rollout_percent=50,updated_at=? WHERE feature_key=?',(now(),p.feature_key))
 elif action=='full':c.execute('UPDATE platform_features SET enabled=1,rollout_percent=100,updated_at=? WHERE feature_key=?',(now(),p.feature_key))
 elif action=='rollback':c.execute('UPDATE platform_features SET enabled=0,rollout_percent=0,updated_at=? WHERE feature_key=?',(now(),p.feature_key))
 else:c.close();raise HTTPException(400,'Unsupported release action')
 c.execute('INSERT INTO platform_feature_releases VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),p.feature_key,action,p.detail,p.actor,now()));c.commit();c.close();return {'feature_key':p.feature_key,'action':action,'applied':True}
@router.get('/history/{feature_key}')
def history(feature_key:str,x_access_code:str=Header(default='')):read(x_access_code);c=conn();rel=[dict(x) for x in c.execute('SELECT action,detail,actor,created_at FROM platform_feature_releases WHERE feature_key=? ORDER BY created_at DESC LIMIT 100',(feature_key,))];ev=[dict(x) for x in c.execute('SELECT subject_key,enabled,variant,reason,context,created_at FROM platform_feature_evaluations WHERE feature_key=? ORDER BY created_at DESC LIMIT 100',(feature_key,))];c.close();return {'releases':rel,'evaluations':ev}
@router.get('/summary')
def summary(x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();flags=c.execute('SELECT COUNT(*) n,SUM(enabled) enabled,AVG(rollout_percent) avg_rollout FROM platform_features').fetchone();evals=c.execute('SELECT COUNT(*) n,SUM(enabled) enabled FROM platform_feature_evaluations').fetchone();variants=[dict(x) for x in c.execute('SELECT variant,COUNT(*) n FROM platform_feature_evaluations WHERE enabled=1 GROUP BY variant')];c.close();return {'flags':dict(flags),'evaluations':dict(evals),'variants':variants}