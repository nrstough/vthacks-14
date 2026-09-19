"""Synthetic residual-spending experiment. No bank data; not a production model.

Run generate, audit, then train. NumPy-only MLP with Adam and analytical gradients.
Days are relative synthetic days. Labels are simulated observations, not human data.
"""
from pathlib import Path
import argparse, hashlib, json, time
import numpy as np

ROOT = Path(__file__).resolve().parent
CTX, H = 56, 14
SEED = 20260919

def dump(name, obj):
    (ROOT / name).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')

def features(history, origin):
    # Only observations strictly before the forecast origin enter features.
    scale = max(float(np.mean(history[-28:])), 5.0)
    lag = history[-CTX:] / scale
    future_days = np.arange(origin, origin + H) % 7
    hist_days = np.arange(origin - CTX, origin) % 7
    weekday = np.array([history[hist_days == d].mean() for d in future_days]) / scale
    x = np.concatenate([lag, weekday, np.sin(2*np.pi*future_days/7),
                        np.cos(2*np.pi*future_days/7), [np.log1p(scale)]])
    return x, scale, weekday

def generate():
    rng = np.random.default_rng(SEED)
    splits = [('train', 1800), ('validation', 300), ('test', 300), ('stress', 300)]
    arrays, gid = {}, 0
    for split, n in splits:
        rows = {k: [] for k in ['x','y','scale','group','origin','history','recent','weekday','regime']}
        for _ in range(n):
            gid += 1
            days = np.arange(224)
            base = rng.uniform(8, 50)
            weekend = rng.uniform(0.7, 2.4)
            period = int(rng.choice([7,14,28]))
            phase = int(rng.integers(period))
            payday_effect = 1 + rng.uniform(0, 0.9)*np.exp(-((days-phase)%period)/3)
            weekly = np.where(days%7 >= 5, weekend, 1)
            trend = np.exp(rng.uniform(-.002,.002)*days)
            regime = rng.choice(['steady','sparse','bursty'])
            p = {'steady':.82,'sparse':.35,'bursty':.60}[regime]
            means = base * weekly * payday_effect * trend
            series = (rng.random(len(days)) < p) * rng.gamma(2.0, means/2)
            if regime == 'bursty':
                series += (rng.random(len(days)) < .035)*rng.uniform(50,180,len(days))
            if split == 'stress':
                # Entirely separate accounts and an unseen post-origin regime shift.
                series[160:] *= float(rng.choice([.45, 1.8, 2.4]))
            series = np.round(series,2)
            origins = [160] if split == 'stress' else [70,84,98,112,126,140,154,168,182,196,210]
            for origin in origins:
                hist = series[origin-CTX:origin].copy()
                x, scale, weekday = features(hist, origin)
                rows['x'].append(x)
                rows['y'].append(series[origin:origin+H])
                rows['scale'].append(scale)
                rows['group'].append(gid)
                rows['origin'].append(origin)
                rows['history'].append(hist)
                rows['recent'].append(np.repeat(hist[-28:].mean(),H))
                rows['weekday'].append(weekday*scale)
                rows['regime'].append(regime)
        for k,v in rows.items(): arrays[f'{split}_{k}'] = np.asarray(v)
    np.savez_compressed(ROOT/'data.npz', **arrays)
    dump('manifest.json', {'seed':SEED,'provenance':'entirely synthetic; no real users or Nessie records',
         'target':'14 next-day ordinary outflows, USD in this artificial simulator',
         'context_days':CTX,'horizon_days':H,'model_features':99,
         'split_unit':'whole simulated account','generator_regimes':['steady','sparse','bursty'],
         'stress':'held-out accounts, unseen spend multiplier starting at origin; not predictable from history',
         'known_bills_and_income':'excluded by construction; real-data cleaning not implemented',
         'missing_data':'none simulated; missingness robustness not established'})
    print('Generated', ROOT/'data.npz', flush=True)

def audit():
    d=np.load(ROOT/'data.npz', allow_pickle=False)
    report={'provenance':'synthetic simulated outcomes, not real financial ground truth','splits':{},'blocking':[]}
    group_sets, hashes = {}, {}
    for s in ['train','validation','test','stress']:
        x,y,hist=d[s+'_x'],d[s+'_y'],d[s+'_history']
        group_sets[s]=set(d[s+'_group'].tolist())
        hashes[s]=set(hashlib.sha256(a.tobytes()+b.tobytes()).hexdigest() for a,b in zip(hist,y))
        nonfinite=int((~np.isfinite(x)).sum()+(~np.isfinite(y)).sum())
        feature_replay=all(np.allclose(features(h,int(o))[0],a) for h,o,a in zip(hist,d[s+'_origin'],x))
        rr={'records':len(x),'accounts':len(group_sets[s]),'feature_shape':list(x.shape),
            'target_shape':list(y.shape),'dtype':str(x.dtype),'nonfinite':nonfinite,
            'feature_min':float(x.min()),'feature_max':float(x.max()),
            'all_zero_history_rows':int(np.all(hist==0,axis=1).sum()),
            'duplicate_history_target_records':len(x)-len(hashes[s]),
            'zero_target_fraction_by_day':(y==0).mean(axis=0).tolist(),
            'target_mean_by_day':y.mean(axis=0).tolist(),
            'target_quantiles':np.quantile(y,[0,.05,.5,.95,1]).tolist(),
            'regime_counts':{str(k):int(v) for k,v in zip(*np.unique(d[s+'_regime'],return_counts=True))},
            'sequence_lengths':{'min':56,'max':56,'mean':56,'median':56,'p5':56,'p95':56},
            'all_features_reproduced_from_history_and_calendar':bool(feature_replay)}
        report['splits'][s]=rr
        if nonfinite or x.shape!=(len(x),99) or y.shape!=(len(x),H) or not feature_replay:
            report['blocking'].append(s+' invalid tensors or feature replay')
    report['overlap']={}
    names=list(group_sets)
    for i,s in enumerate(names):
        for v in names[i+1:]:
            pair={'accounts':len(group_sets[s]&group_sets[v]),'exact_records':len(hashes[s]&hashes[v])}
            report['overlap'][s+' / '+v]=pair
            if any(pair.values()):report['blocking'].append('leakage '+s+' '+v)
    report['verdict']='TRAIN: synthetic pipeline experiment only' if not report['blocking'] else 'DO NOT TRAIN'
    dump('audit.json',report)
    print(json.dumps(report,indent=2),flush=True)
    if report['blocking']:raise RuntimeError(report['blocking'])

def init(rng):
    return {'w1':rng.normal(0,np.sqrt(2/99),(99,64)), 'b1':np.zeros(64),
            'w2':rng.normal(0,np.sqrt(2/64),(64,32)), 'b2':np.zeros(32),
            'w3':rng.normal(0,.03,(32,H)), 'b3':np.full(H,np.log(np.expm1(1.0)))}

def forward(x,p):
    a=np.maximum(x@p['w1']+p['b1'],0)
    b=np.maximum(a@p['w2']+p['b2'],0)
    z=b@p['w3']+p['b3']
    pred=np.logaddexp(0,z)
    return pred,(a,b,z)

def loss_grads(x,y,p):
    pred,(a,b,z)=forward(x,p)
    loss=np.mean((pred-y)**2)
    dz=2*(pred-y)/pred.size/(1+np.exp(-np.clip(z,-60,60)))
    db=(dz@p['w3'].T)*(b>0)
    da=(db@p['w2'].T)*(a>0)
    return loss,{'w3':b.T@dz,'b3':dz.sum(0),'w2':a.T@db,'b2':db.sum(0),'w1':x.T@da,'b1':da.sum(0)}

def gradient_check():
    rng=np.random.default_rng(17);p=init(rng);x=rng.normal(0,.3,(5,99));y=rng.uniform(0,2,(5,H))
    _,g=loss_grads(x,y,p);errs=[]
    for k in p:
        for _ in range(4):
            idx=tuple(rng.integers(n) for n in p[k].shape);old=p[k][idx];eps=1e-5
            p[k][idx]=old+eps;plus=loss_grads(x,y,p)[0]
            p[k][idx]=old-eps;minus=loss_grads(x,y,p)[0];p[k][idx]=old
            num=(plus-minus)/(2*eps);errs.append(abs(num-g[k][idx]))
    maximum=float(max(errs));assert maximum<1e-6,maximum
    return {'coordinates':len(errs),'max_abs_error':maximum}

def metrics(y,p):
    return {'daily_mae_usd':float(np.mean(np.abs(y-p))),
            '7day_total_mae_usd':float(np.mean(np.abs(y[:,:7].sum(1)-p[:,:7].sum(1)))),
            '14day_total_mae_usd':float(np.mean(np.abs(y.sum(1)-p.sum(1)))),
            '14day_mean_underprediction_usd':float(np.mean(np.maximum(y.sum(1)-p.sum(1),0))),
            '14day_bias_pred_minus_actual_usd':float(np.mean(p.sum(1)-y.sum(1)))}

def train():
    report=json.loads((ROOT/'audit.json').read_text());assert not report['blocking']
    started=time.monotonic(); gc=gradient_check();d=np.load(ROOT/'data.npz',allow_pickle=False)
    mu=d['train_x'].mean(0);sd=np.maximum(d['train_x'].std(0),.1)
    xs={s:(d[s+'_x']-mu)/sd for s in ['train','validation','test','stress']}
    y=d['train_y']/d['train_scale'][:,None]
    x=xs['train'];results=[];best_global=None;best_score=float('inf')
    for seed in [11,23,47]:
        rng=np.random.default_rng(seed);p=init(rng)
        m={k:np.zeros_like(v) for k,v in p.items()};v={k:np.zeros_like(v) for k,v in p.items()}
        steps=0;best=float('inf');bad=0;history=[];seed_start=time.monotonic()
        for epoch in range(1,61):
            order=rng.permutation(len(x))
            for j in range(0,len(x),256):
                ix=order[j:j+256];_,g=loss_grads(x[ix],y[ix],p);steps+=1
                norm=np.sqrt(sum(float(np.sum(a*a)) for a in g.values()))
                for k in p:
                    g[k]*=min(1,5/max(norm,1e-12))
                    m[k]=.9*m[k]+.1*g[k];v[k]=.999*v[k]+.001*g[k]**2
                    p[k]-=.001*(m[k]/(1-.9**steps))/(np.sqrt(v[k]/(1-.999**steps))+1e-8)
            pv=forward(xs['validation'],p)[0]*d['validation_scale'][:,None]
            score=metrics(d['validation_y'],pv)['14day_total_mae_usd'];history.append(score)
            if score<best:
                best=score;checkpoint={k:a.copy() for k,a in p.items()};best_epoch=epoch;bad=0
            else:bad+=1
            if epoch==1 or epoch%5==0:print(f'seed={seed} epoch={epoch} validation_14day_MAE=${score:.2f} elapsed={time.monotonic()-seed_start:.1f}s',flush=True)
            if bad>=10:break
        np.savez_compressed(ROOT/f'model-seed-{seed}.npz',**checkpoint,feature_mean=mu,feature_std=sd)
        results.append({'seed':seed,'best_epoch':best_epoch,'epochs_run':epoch,'validation_14day_MAE':best,
                        'training_seconds':time.monotonic()-seed_start,'validation_history':history})
        if best<best_score:best_score=best;best_global=checkpoint;chosen=seed
    # Select only on validation. Test and stress are evaluated once after selection.
    evaluation={}
    for s in ['validation','test','stress']:
        preds=forward(xs[s],best_global)[0]*d[s+'_scale'][:,None]
        assert preds.shape==d[s+'_y'].shape and np.isfinite(preds).all() and (preds>=0).all()
        evaluation[s]={'neural':metrics(d[s+'_y'],preds),
            'recent_28day_mean':metrics(d[s+'_y'],d[s+'_recent']),
            'weekday_8week_mean':metrics(d[s+'_y'],d[s+'_weekday'])}
        np.savez_compressed(ROOT/f'predictions-{s}.npz',predicted=preds,actual=d[s+'_y'],group=d[s+'_group'],origin=d[s+'_origin'])
    np.savez_compressed(ROOT/'model-selected.npz',**best_global,feature_mean=mu,feature_std=sd)
    # Verify weight serialization round trip.
    saved=np.load(ROOT/'model-selected.npz');q={k:saved[k] for k in best_global}
    assert np.array_equal(forward(xs['test'][:4],q)[0],forward(xs['test'][:4],best_global)[0])
    out={'status':'complete','provenance':'SYNTHETIC ONLY','model':'99→64 ReLU→32 ReLU→14 softplus; Adam, normalized MSE',
         'parameters':int(sum(a.size for a in best_global.values())), 'selected_seed':chosen,
         'selection':'lowest validation 14-day total MAE; no test-based selection',
         'gradient_check':gc,'serialization_roundtrip':True,'runs':results,'evaluation':evaluation,
         'elapsed_seconds':time.monotonic()-started,
         'limitations':['No real-data validation','No calibrated uncertainty','No decision/solver evaluation',
                       'Synthetic known-bill exclusion is perfect; real extraction unimplemented',
                       'No missing-observation test','Stress shift is unknowable at forecast origin']}
    dump('results.json',out);print(json.dumps(out,indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['generate','audit','train']);args=parser.parse_args()
    {'generate':generate,'audit':audit,'train':train}[args.mode]()
