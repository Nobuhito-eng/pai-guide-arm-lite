# AI案内アーム・ライト

日本語の短文を小型の機械学習分類器で **受付 / 出口 / 保留** に分類し、ROS 2経由でGazebo上のCRANE+ V2を案内姿勢へ動かす、学習用の最小プロジェクトです。

**最初は `START_HERE_JA.md` を読んでください。** 通常はCMDファイルのダブルクリックで進めます。

## 検証状況

2026-10-14のLinux環境で、分類器、JSON推論との数値一致、姿勢・到達・保留の判定関数をテストしました。`evidence/` はこの非ROS検証の記録です。Gazeboでの動作結果とは区別しています。

2026-10-15（日本時間）のローカル再検証では、WindowsのPython 3.12.14と専用コンテナのPython 3.10.12で既存の非ROSテスト40件とAI開発用15入力がPASSしました。さらに、実際のGazeboで受付・出口・保留を各2回実行し、6/6 PASSを確認しました。案内4回と待機復帰4回の計8アクションは結果成功と実測関節の到達を確認し、保留2回は各40サンプルで新規指令0件・静止判定PASSでした。今回の実測ログはローカルで保管し、診断ログを含む`artifacts/`は公開コピーに含めません。

録画用のGazeboデモは別実行で6/6 PASS・計8指令成功でした。動画は109.667秒（約1分50秒）、等倍・無音です。実画面と1秒間隔の110フレーム、代表場面の確認では、受付は画面右、出口は左を示し、保留では待機姿勢を維持しました。観察範囲で明らかな干渉は見られませんでしたが、全フレーム・全角度の衝突検証ではありません。6回の結果は限定入力での機能確認であり、汎化性能や実機の安全性を保証するものではありません。

2026-10-19に説明文とHTMLレポートの表示文を整理しました。分類・動作制御・判定条件は変更していません。上記のGazebo実測は2026-10-15の実行結果です。レポート生成時はコードの一致も検査するため、以前のコードで保存したログは現在の版のPASS証拠として扱いません。

## AI・独自部分

- 文字2～4-gram TF-IDF + multinomial logistic regression。
- オリジナルの合成例文75件（各クラス25件）で学習。例文・学習コード・重みを同梱。
- 実行時にモデルで推論し、案内先に応じて動作を選択。AIは関節角を自由生成しません。
- 否定・複数案内先・空欄・未知特徴・低スコア等は保留。ガードは保留を追加するだけで、案内先を直接決めません。
- 保留時は目標を送らず、受信した関節状態と送信件数で確認。移動はアクション結果と実測関節誤差の両方で確認。
- 学習済み係数をJSONに保存。推論にはPython標準ライブラリのみを使うのでAPI、GPU、AIライブラリ追加は不要。
- デモ入力は学習例文にも含まれます。実用精度、万能な曖昧文判定、実機安全性を主張しません。
- 講義のROS通信・既存ロボットモデルを参考に、案内用途と分類/保留/ログを組み合わせています。

## ファイル

- `guide.py`：実行入口
- `guide_lite/core.py`：標準PythonのTF-IDF/ロジスティック回帰推論、保留、設定チェック
- `guide_lite/ros_backend.py`：実ROS 2アクションクライアント・関節状態・/clock・URDF確認
- `guide_lite/motion.py`：動作/保留の判定関数（物理シミュレーションではない）
- `model/intent_model.json`：学習済みモデル
- `config/motion.json`：候補姿勢と制限
- `data/train.json`：学習用75例文
- `data/checks.json`：開発用15入力（独立の盲検評価ではない）
- `data/demo_cases.json`：3場面×2回
- `scripts/`：起動、任意の再学習、公開用コピー
- `tests/`：通常環境でも実行できる非ROSのテスト
- `artifacts/`：実行環境で保存される実測結果。Git管理対象外

## Windows側

Docker DesktopでLinuxコンテナが起動できることが前提。既存コンテナは消しません。

```powershell
# ZIP展開先で実行（CMDファイルでも同じ）
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 setup
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 start
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 check
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 demo
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 report
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 stop
```

setupは既存の講義イメージを優先利用します。なければDocker Hubから取得します（大容量になる可能性があります）。ポート6088はlocalhostにのみ公開し、ROS_DOMAIN_ID=73、ROS_LOCALHOST_ONLY=1を指定します。デバイスやDockerソケットを渡さず、privilegedやhost networkingは使いません。

コンテナ名は`pai-guide-lite`。一度作成した後はZIP展開フォルダを移動しないでください。保存先は`/workspace/guide`のバインドマウントです。イメージID/ダイジェストの実使用記録は`artifacts/teaching_image.json`に残ります。

## 通常Pythonのみでできること（ROSもDockerも不要）

```bash
python guide.py ai-check
python guide.py classify --text '受付はどちらですか'
python -m unittest discover -s tests -v
```

これらは分類と非ROSのテストです。Gazeboでの動作確認には`check`を使用します。

## Gazeboでのテストの合格条件

`check`は起動中のROS 2 / Gazeboに接続して確認します。

1. /clockが進み、必要な4関節の新しい状態が届く。
2. /robot_descriptionがシミュレーションの制御プラグインを示す。
3. 設定姿勢が、その環境のURDFの関節制限内である。
4. 既知のテレオペや指令トピックの別パブリッシャがない。
5. 受付と出口はアクション成功に加え、目標との関節誤差0.05rad以内で到達する。
6. 案内後は明示的にhomeへ戻る。保留中はhomeへの復帰指令も含めて新規送信しない。
7. 保留は2秒間の新しい状態サンプルと送信件数で確認（最大変化0.02rad以内）。
8. 6試行すべて成功時のみ`6/6 CHECK PASS`と記録する。

これは衝突検証器でも安全認証でもありません。画面で姿勢と干渉、案内先の違いを確認してください。物理ロボットには使いません。ほかのアクションクライアントから指令することも禁止します。

## よくある停止点

- Dockerに接続できない：Docker Desktopが起動・準備完了か確認。
- port 6088使用中：他のアプリを確認。既存教材を勝手に削除しない。
- crane_plus_gazeboがない：講義の指定イメージか確認。09_LOGS等とともに相談。
- Gazebo not ready：GUIの再生を確認、起動を待つ。08_DIAGNOSEと09_LOGSを実行。
- not at HOME：07_HOMEの結果を確認してから02_CHECK。
- /robot_descriptionがない：ロボット起動処理/RSPの状態を調べる。確認を省略して強行しない。
- 軌道の拒否/到達エラー：ログの関節名・URDF制限・実際の値を照合。許容値を広げて成功扱いにしない。
- PowerShell/Windows/Linuxの実行箇所が違う：`.cmd`はWindows側、`ros2`は専用コンテナ内。

## 再学習（通常は不要）

既存の講義コンテナを変更せず、別のPython 3.13環境で`requirements-training.txt`を用意して`python scripts/train_model.py`を実行します。モデルを変えたら、単体テストとGazebo確認を再実行してください。古い実測結果を新モデルの結果として使わないでください。

## 配布ファイルと出典

`scripts/prepare_public.py`で、コード・設定・モデル・学習例文・説明資料を`dist/pai-guide-arm-lite`へコピーできます。実測ログ、録画、認証情報、Git履歴はコピー対象外です。

実行基盤と学習ライブラリの出典・ライセンスは`THIRD_PARTY.md`、本リポジトリのライセンスは`LICENSE`に記載しています。
