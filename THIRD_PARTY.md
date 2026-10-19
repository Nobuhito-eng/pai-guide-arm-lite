# 出典・再利用・制作範囲

## この配布物
- アプリケーションコード、合成例文75件、例文から学習した小型分類器、確認用コードは本課題向けに生成AI支援で作成した。
- ロボットの既存の関節軌道インターフェースを利用する。新しい物理モデルやロボット制御器を独力で開発したとは主張しない。
- 講義スライド・配布Notebook・動画・他者のモデルメッシュはこのZIPには含めない。
- 75例文とデモ入力の重複を公開する。デモは盲検評価ではない。

## 実行時に利用する配布元（別配布、各ライセンスに従う）
1. AI-Robot-Book-Humble/docker-ros2-desktop-ai-robot-book-humble
   https://github.com/AI-Robot-Book-Humble/docker-ros2-desktop-ai-robot-book-humble
   DockerfileおよびセットアップスクリプトはApache-2.0の記載。イメージ内の各依存ソフトはそれぞれのライセンスに従う。
   確認したDockerfile blob: c60eb67d40ceaeb8a152c60983d428a9e12fe56d
   確認したai-robot-book.sh blob: 1cfb878d7c49d151ca8efba53310a0ccab51fd8b
2. AI-Robot-Book-Humble/crane_plus（講義イメージ内で使用）
   https://github.com/AI-Robot-Book-Humble/crane_plus
   講義用ブランチで使う起動ファイル: crane_plus_gazebo/launch/crane_plus_with_table.launch.py
   確認したlaunch blob: 67a2187da01b32c0fae822aad005fc4c1cf980e3
   URDF blob: a5fc930b1d61c25dc99d11267830212be443424f
3. RT Corporation / crane_plus（上流）
   https://github.com/rt-net/crane_plus
   Apache-2.0（個別ファイルで指定がある場合はその指定）。関節名・制御インターフェース・URDFの制限を参照した。
4. ROS 2 Humble / ros2_control
   https://control.ros.org/humble/doc/ros2_controllers/joint_trajectory_controller/doc/userdoc.html
   FollowJointTrajectoryの結果監視、関節軌道メッセージ仕様を参照した。
5. scikit-learn（学習時のみ利用、BSD-3-Clause）
   https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html
   https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html
   実際の学習環境: Python 3.13.5 / scikit-learn 1.8.0。実行時は同梱重みを標準Pythonで計算し、数値一致をテストした。
6. Docker
   https://docs.docker.com/engine/storage/bind-mounts/
   ホストの課題フォルダをマウントする方法を参照した。

参照確認日: 2026-10-14。参照した現在のソースと、受講者PCに既にあるイメージの内容が同一とは限らない。setupは実使用イメージIDをartifacts/teaching_image.jsonに記録する。
