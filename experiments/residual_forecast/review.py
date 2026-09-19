"""Read-only supplementary audit of the finished pilot; does not retrain."""
import hashlib, json, platform, time
from pathlib import Path
import numpy as np
from run import forward, features

root = Path(__file__).resolve().parent
d = np.load(root/'data.npz', allow_pickle=False)
out = {'python': platform.python_version(), 'numpy': np.__version__, 'splits': {}}
for s in ['train','validation','test','stress']:
    x,y,h = d[s+'_x'], d[s+'_y'],d[s+'_history']
    lens=np.full(len(h),h.shape[1])
    out['splits'][s] = {
        'schema': {k: {'shape': list(d[k].shape), 'dtype': str(d[k].dtype)} for k in d.files if k.startswith(s+'_')},
        'all_numeric_nonfinite': {k: int((~np.isfinite(d[k])).sum()) for k in d.files if k.startswith(s+'_') and d[k].dtype.kind in 'fiu'},
        'constant_history_rows': int((np.ptp(h,axis=1)==0).sum()),
        'constant_feature_columns': np.flatnonzero(np.ptp(x,axis=0)==0).tolist(),
        'negative_targets':int((y<0).sum()),
        'positive_target_count_by_day':(y>0).sum(0).tolist(),
        'origin_weekday_counts':{str(k):int(v) for k,v in zip(*np.unique(d[s+'_origin']%7,return_counts=True))},
        'sequence_lengths':{'min':int(lens.min()),'max':int(lens.max()),'mean':float(lens.mean()),'median':float(np.median(lens)),'p5':float(np.quantile(lens,.05)),'p95':float(np.quantile(lens,.95))},
        'windows_below_56':int((lens<56).sum()),
        'regime_accounts':{str(k):len(np.unique(d[s+'_group'][d[s+'_regime']==k])) for k in np.unique(d[s+'_regime'])},
        'target_bounds_within_224_day_series':bool(((d[s+'_origin']>=56)&(d[s+'_origin']+y.shape[1]<=224)).all()),
        'scale_replay':bool(all(np.isclose(features(a,int(b))[1],c) for a,b,c in zip(h,d[s+'_origin'],d[s+'_scale'])))
    }
model=np.load(root/'model-selected.npz',allow_pickle=False)
p={k:model[k] for k in ['w1','b1','w2','b2','w3','b3']}
x=(d['test_x'][:1]-model['feature_mean'])/model['feature_std']
forward(x,p)
start=time.perf_counter()
for _ in range(1000):forward(x,p)
out['warm_single_record_forward_mean_ms']=(time.perf_counter()-start)*1000/1000
out['inference_scope']='forward pass only, warm weights; excludes IO, feature extraction, solver and network'
out['artifact_sha256']={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(root.iterdir()) if f.suffix in ['.py','.npz','.json'] and f.name!='review.json'}
out['limitations_found']=[
    'All ordinary-split origins are weekday 0; 28 calendar features are constant. Accuracy on other start weekdays is untested.',
    'Stress starts on weekday 6 and changes spend level, so stress combines two shifts and does not isolate either.',
    'Eleven windows per ordinary account share history; 3300 test rows represent 300 independent accounts, not 3300.',
    'Three regimes come from the same generator family. No independently authored generator or real-world holdout.',
    'No missing-day simulation; observed zero spend cannot stand in for missing feed data.',
    'No confidence intervals or account-bootstrap significance test. Tiny difference against weekday mean is not a win.'
]
(root/'review.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='splits'},indent=2))
