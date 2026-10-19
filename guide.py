#!/usr/bin/env python3
"""Entry point: classify, ai-check, doctor, check, demo, console, home, report.
ROS modes never silently fall back to a simulated/stub success.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import traceback
from guide_lite.core import Classifier, LABELS, REASONS, ROOT, load_motion_config, plan_for, code_fingerprint


def write_json(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)


def read_rows(name):
    return json.loads((ROOT/'data'/name).read_text(encoding='utf-8'))


def show(d):
    print(f'AI判定: {LABELS[d.label]}')
    print(f'理由: {REASONS[d.reason]}')
    if d.scores:
        print('分類スコア（正答率の保証ではありません）: '+
              ' / '.join(f'{LABELS[k].split(" /")[0]}={v:.3f}' for k,v in d.scores.items()))
    sys.stdout.flush()


def ai_check(c):
    checks=read_rows('checks.json')
    rows=[]
    train={r['text'] for r in read_rows('train.json')}
    for r in checks:
        t=time.perf_counter()
        d=c.decide(r['text'])
        out={**r,**d.to_dict(),'passed':d.label==r['expected'],
             'training_exact_overlap':r['text'] in train,'inference_ms':(time.perf_counter()-t)*1000}
        rows.append(out)
        print(('PASS' if out['passed'] else 'FAIL'),r['text'] or '(empty)','=>',d.label)
    result={'kind':'AI_ONLY_DEVELOPMENT_CHECK_NOT_GAZEBO','python':platform.python_version(),
            'model_sha256':c.sha256,'total':len(rows),'passed':sum(x['passed'] for x in rows),'rows':rows,
            'note':'Synthetic development examples. Not a blind accuracy or physical safety evaluation.'}
    write_json(ROOT/'artifacts/ai_check.json',result)
    return 0 if result['total']==result['passed'] else 1


def ros_run(mode,c,ack):
    if not ack:
        raise RuntimeError('--confirm-simulation is required; never use this on a physical robot')
    # No concurrent app processes. This protects this application, not all ROS clients.
    import fcntl
    lock=(ROOT/'artifacts/application.lock').open('a')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another Guide Arm Lite process is running')
    from guide_lite.ros_backend import RosArm
    arm=None
    config=load_motion_config()
    now=datetime.now(timezone.utc)
    run_id=now.strftime('%Y%m%dT%H%M%S%fZ')
    report={'kind':'GAZEBO_CHECK' if mode=='check' else 'GAZEBO_'+mode.upper(),
            'run_id':run_id,'time_utc':now.isoformat(),'status':'STARTED',
            'code_sha256':code_fingerprint(),'model_sha256':c.sha256,'motion_sha256':hashlib.sha256((ROOT/'config/motion.json').read_bytes()).hexdigest(),
            'rows':[], 'visual_review':'NOT_CONFIRMED_BY_USER',
            'note':'Joint-state/action checks do not certify collision-free motion or physical safety.'}
    path=ROOT/'artifacts/gazebo'/f'{run_id}_{mode}.json'
    train={x['text'] for x in read_rows('train.json')}
    try:
        arm=RosArm(config)
        report['preflight']=arm.prepare()
        if mode=='doctor':
            report['status']='PREFLIGHT_PASS'
            print('Gazebo接続確認 PASS（まだロボットは動かしていません）')
        elif mode=='home':
            report['rows'].append(arm.move('home'))
            report['status']='HOME_REACHED'
            print('HOME到達')
        else:
            arm.ensure_home()
            if mode in ('check','demo'):
                cases=read_rows('demo_cases.json')
                print('\nAI案内アーム・ライト / シミュレータ専用\n受付 = A方向（ベース関節 +0.65 rad）\n出口 = B方向（ベース関節 -0.65 rad）\n保留 = 新しい動作指令を送らない\n')
                if mode=='demo':
                    print('収録用: 6場面を順に実演します。Ctrl+Cで中止。')
                    arm.pump(8)
            else:
                cases=None
            idx=0
            while True:
                if cases is not None:
                    if idx>=len(cases):
                        break
                    case=cases[idx]
                else:
                    text=input('\n依頼文（quitで終了）> ')
                    if text.strip().lower()=='quit':
                        break
                    case={'id':f'input_{idx+1}','text':text,'expected':None}
                idx+=1
                print(f'\n=== {idx} / {len(cases) if cases else "対話"} ===\n依頼: {case["text"]}')
                decision=c.decide(case['text'])
                show(decision)
                row={**case,'decision':decision.to_dict(),'training_exact_overlap':case['text'] in train,
                     'guide_goals':0,'reset_goals':0,'status':'STARTED'}
                report['rows'].append(row)
                write_json(path,report)
                if case['expected'] is not None and decision.label!=case['expected']:
                    row['status']='FAIL_CLASSIFICATION'
                    raise RuntimeError('Unexpected AI classification: no motion sent for this case')
                arm.ensure_home()
                target=plan_for(decision,config)
                if target is None:
                    row['hold']=arm.hold_check(3.0 if mode=='demo' else 2.0)
                    if not row['hold']['passed']:
                        row['status']='FAIL_HOLD'
                        raise RuntimeError('HOLD drift/no-command check failed')
                    print('保留確認: 新規指令0件。観測した関節変化は許容範囲内。')
                else:
                    row['motion']=arm.move(decision.label)
                    row['guide_goals']=1
                    print('案内姿勢に到達。')
                    arm.pump(3.0 if mode=='demo' else .5)
                    print('次の依頼のため、明示した待機姿勢に戻ります。')
                    row['reset']=arm.move('home')
                    row['reset_goals']=1
                row['status']='PASS'
                write_json(path,report)
                if mode=='demo':
                    arm.pump(4.0)
            report['status']='PASS'
            print('\n'+('6/6 CHECK PASS' if cases else 'SESSION COMPLETE'))
            print('注意: これは限定入力・関節到達・新規指令の確認です。見た目と衝突は画面で確認してください。')
    except KeyboardInterrupt:
        report['status']='CANCELLED'
        report['error']='User cancelled; cancel request is best effort, not an emergency stop.'
        raise
    except BaseException as exc:
        report['status']='FAIL'
        report['error']=f'{type(exc).__name__}: {exc}'
        raise
    finally:
        if arm is not None:
            report['total_goals_sent']=arm.sent_goals
        write_json(path,report)
        if mode=='check':
            write_json(ROOT/'artifacts/latest_gazebo_check.json',report)
        if arm is not None:
            arm.close()
        lock.close()
        print(f'結果ファイル: artifacts/gazebo/{path.name}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['classify','ai-check','doctor','check','demo','console','home','report'])
    parser.add_argument('--text',default='受付はどちらですか')
    parser.add_argument('--confirm-simulation',action='store_true')
    parser.add_argument('--account',default='未記入')
    args=parser.parse_args()
    (ROOT/'artifacts').mkdir(exist_ok=True)
    if args.mode=='report':
        from guide_lite.report import generate_report
        print(generate_report(args.account))
        return 0
    c=Classifier()
    if args.mode=='classify':
        show(c.decide(args.text)); return 0
    if args.mode=='ai-check':
        return ai_check(c)
    ros_run(args.mode,c,args.confirm_simulation)
    return 0

if __name__=='__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\n中止しました。動きが続く場合は専用コンテナを停止してください。',file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f'ERROR: {type(e).__name__}: {e}',file=sys.stderr)
        print('失敗をPASSとして扱いません。READMEの切り分けとartifactsの記録を確認してください。',file=sys.stderr)
        sys.exit(2)
