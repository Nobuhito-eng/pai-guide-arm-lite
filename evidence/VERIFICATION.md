# 検証結果（2026-10-14）

## 実行済み
- Python 3.13.5 / Debian Linuxで、分類器を75件の合成例文から実際に学習した。
- 非ROSの単体テスト40件：PASS。これはGazeboの動作確認ではない。
- 開発用15入力：15/15が期待ラベル。学習と重なる例・調整に使った例を含み、独立精度評価ではない。
- sklearnの参照出力と標準Python推論を90入力で照合。最大絶対誤差 3.331e-16。
- Python 3.10文法の構文検査、bash -n：PASS。

## 実行できていない範囲
- このWORKにdocker CLI/daemon、ROS 2、Gazeboはない。手元Windows PCへ接続されていない。
- 実ROSバックエンドを起動して確認を試みたが、rclpy未導入で終了した。ログはgazebo_attempt.txt。
- Gazeboの起動、アームの物理挙動、衝突、Windows側のPowerShell実行は未確認。
- PowerShellスクリプトは作成・静的レビューのみ。実行済みとして扱わない。
- GUI画像や『Gazeboで成功した』動画は生成していない。

## 手元での確認
00_SETUP → 01_START_GAZEBO → 02_CHECK。実際の結果はartifacts/latest_gazebo_check.jsonへ保存。6回すべてが成功した場合だけ6/6 CHECK PASSとなる。画面で方向の違い・干渉も確認する。

モデルSHA-256：`bcff108233377e3635c6aaace12a85e8a90251649565f698c68de8d095b16033`
