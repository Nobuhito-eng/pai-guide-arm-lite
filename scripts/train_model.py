"""Optional reproducible model training. End users do NOT need to run this.
Run from repository root: python scripts/train_model.py
Dependencies for training only: scikit-learn and numpy.
"""
from pathlib import Path
import hashlib
import json
import platform
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from guide_lite.core import normalize
import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


def main():
    rows = json.loads((ROOT / 'data/train.json').read_text(encoding='utf-8'))
    texts = [normalize(r['text']) for r in rows]
    assert len(texts) == len(set(texts)), 'Duplicate training sentences'
    v = TfidfVectorizer(analyzer='char', ngram_range=(2, 4), lowercase=False,
                        norm='l2', sublinear_tf=False, dtype=np.float64)
    x = v.fit_transform(texts)
    model = LogisticRegression(C=8.0, solver='lbfgs', max_iter=2000,
                               class_weight='balanced', random_state=42)
    model.fit(x, [r['label'] for r in rows])
    data = {
        'format': 'guide-lite-tfidf-logreg-v1',
        'model_version': '3.0.0',
        'classes': model.classes_.tolist(),
        'ngram_range': [2,4],
        'vocabulary': {k:int(i) for k,i in v.vocabulary_.items()},
        'idf': v.idf_.tolist(), 'coef': model.coef_.tolist(),
        'intercept': model.intercept_.tolist(),
        'hold_threshold': .60, 'margin_threshold': .18,
        'training_samples': len(rows),
        'training_sha256': hashlib.sha256((ROOT/'data/train.json').read_bytes()).hexdigest(),
        'training_versions': {'python':platform.python_version(),'numpy':np.__version__,'sklearn':sklearn.__version__},
        'note': 'Original synthetic examples; scores are not calibrated guarantees. No claim of broad language understanding.'
    }
    (ROOT/'model/intent_model.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    # Independent numeric reference for testing stdlib export (not an accuracy test).
    probes = texts + [r['text'] for r in json.loads((ROOT/'data/checks.json').read_text(encoding='utf-8'))]
    ref = [{'text':s, 'scores':dict(zip(model.classes_.tolist(), model.predict_proba(v.transform([normalize(s)]))[0].tolist()))} for s in probes]
    (ROOT/'model/reference_scores.json').write_text(json.dumps(ref,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'TRAINED: {len(rows)} synthetic samples, {x.shape[1]} features; training-only accuracy {model.score(x,[r["label"] for r in rows]):.3f}')
    print('Exported pure-Python inference weights. Gazebo has NOT been tested by this command.')

if __name__ == '__main__':
    main()
