"""Generate an editable HTML report from actual locally saved test evidence.
This never invents Gazebo results. Open it in a browser; fill editable fields;
Print -> Save as PDF (turn off browser headers/footers to hide local paths).
"""
from __future__ import annotations
from datetime import datetime
import hashlib
import html
import json
from .core import ROOT, code_fingerprint


def generate_report(account='未記入'):
    model=json.loads((ROOT/'model/intent_model.json').read_text(encoding='utf-8'))
    path=ROOT/'artifacts/latest_gazebo_check.json'
    check=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    model_hash=hashlib.sha256((ROOT/'model/intent_model.json').read_bytes()).hexdigest()
    config_hash=hashlib.sha256((ROOT/'config/motion.json').read_bytes()).hexdigest()
    valid=(check.get('kind')=='GAZEBO_CHECK' and check.get('status')=='PASS'
           and len(check.get('rows',[]))==6 and all(r.get('status')=='PASS' for r in check.get('rows',[]))
           and check.get('code_sha256')==code_fingerprint()
           and check.get('model_sha256')==model_hash and check.get('motion_sha256')==config_hash)
    rows=[]
    for r in check.get('rows',[]):
        d=r.get('decision',{})
        detail='未完了'
        if r.get('motion'):
            detail=f"案内誤差 {r['motion'].get('max_error_rad',0):.4f} rad; 待機復帰 {r.get('reset',{}).get('passed','未確認')}"
        elif r.get('hold'):
            h=r['hold'];detail=f"新規指令 {h.get('goals_sent','?')} 件 / 最大変化 {h.get('max_motion_rad',0):.4f} rad"
        rows.append('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in [r.get('id'),r.get('text'),d.get('label'),r.get('status'),detail])+'</tr>')
    if not rows:
        rows=['<tr><td colspan="5">Gazeboでの6回確認は未実施。02_CHECK.cmd実行後にレポートを再生成してください。</td></tr>']
    status='6回の自動確認がPASS（表示・衝突の目視確認は別途必要）' if valid else '未完成：Gazebo確認が未実施・未完了、またはコード設定と結果が不一致'
    sim_date=html.escape(check.get('time_utc','未実施'))
    body=f'''<!doctype html><html lang="ja"><meta charset="utf-8"><title>AI案内アーム・ライト 提出レポート</title>
<style>
@page{{size:A4;margin:16mm}}body{{font-family:"Yu Gothic","Meiryo",sans-serif;font-size:11pt;line-height:1.6;max-width:820px;margin:24px auto;color:#202a35}}
h1{{font-size:24pt;margin-bottom:5px}}h2{{font-size:13pt;border-bottom:1px solid #bbb;margin:18px 0 6px}}
table{{border-collapse:collapse;width:100%;font-size:9pt}}td,th{{border:1px solid #aaa;padding:6px;text-align:left}}
.edit{{background:#fff2c9}}.status{{padding:10px;border:2px solid #555;font-weight:bold}}.note{{font-size:9pt}}
@media print{{body{{max-width:none;margin:0}}.instructions{{display:none}}}}
</style><body>
<div class="instructions">黄色の欄は追加記録用です。PDF保存時はブラウザのヘッダーとフッターをオフにしてください。編集内容はページの再読み込みで消えます。</div>
<h1>AI案内アーム・ライト</h1>
<p>Omnicampusアカウント名：<span class="edit" contenteditable="true">{html.escape(account)}</span><br>Gazebo確認日時（UTC）：{sim_date}</p>
<div class="status">{status}</div>
<h2>1. 目的・タスク</h2>
<p>日本語の短い依頼文から受付または出口を判定し、Gazebo上のCRANE+ V2でその方向を示す。曖昧・対象外と判定した依頼では、新しい動作指令を送らない。対象を二つの案内先に限定したシミュレータ専用の実証である。</p>
<h2>2. システムとAIの役割</h2>
<p>文章 → 文字2～4-gramのTF-IDF → 多クラスロジスティック回帰 → 受付/出口/保留 → ROS 2のFollowJointTrajectory → 関節状態で到達確認。独自の合成例文{model['training_samples']}件で学習したモデルをJSONとして同梱し、実行時はPython標準ライブラリで推論する。AIは関節角を生成せず、事前に定めた二つの姿勢を選択する。分類スコアは実運用の正答確率を保証しない。</p>
<p>実行環境の補足：<span class="edit" contenteditable="true">未記録</span></p>
<h2>3. 工夫した点</h2>
<p>講義の状態取得・関節指令の仕組みを案内タスクへ応用。AIによる文章分類、保留時の指令抑制、動作結果の確認、記録保存を組み合わせた。保留・制約のルールは動作を抑えるためにのみ使用し、案内先の選択には学習済みモデルを用いた。</p>
<h2>4. 動作確認の結果</h2>
<table><thead><tr><th>試行</th><th>依頼</th><th>判定</th><th>結果</th><th>観測</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p class="note">3場面×2回は限定された機能確認であり、一般的な日本語認識精度の評価ではない。デモの3入力は学習例文にも含む。関節到達の自動確認は、見た目・衝突回避・実機の安全性を保証しない。</p>
<p>画面での確認・失敗・修正の記録：<span class="edit" contenteditable="true">未記録</span></p>
<h2>5. 限界・出典</h2>
<p>自由な会話、音声認識、複雑な否定、任意の未知入力、実機制御は対象外。保留は新しい動作を開始しない処理で、非常停止ではない。失敗した場合は原因を記録して再検証する。</p>
<p class="note">参考：Physical AI応用編1 第4・5回講義。実行基盤：AI-Robot-Book-Humble/docker-ros2-desktop-ai-robot-book-humble、同crane_plus（各ライセンスは配布元に従う）。学習：scikit-learnのTfidfVectorizer / LogisticRegression。コード・例文・学習手順・出典一覧はリポジトリに収録。</p>
<p class="note">モデルSHA-256（先頭12桁）：{model_hash[:12]} / 設定：{config_hash[:12]}</p>
</body></html>'''
    target=ROOT/'artifacts/report_draft.html'
    target.parent.mkdir(exist_ok=True)
    target.write_text(body,encoding='utf-8')
    return target
