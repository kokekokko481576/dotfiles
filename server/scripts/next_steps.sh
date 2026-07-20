#!/bin/bash
# 次回 Gemini CLI を再開する際に実行するコマンド一覧

# --- 1. llm_client.py の修正を反映させるためのビルドとテスト実行 ---

# a. Dockerイメージをキャッシュなしで再ビルドする
# 説明: llm_client.pyに加えた major_events の読み込みロジックの修正を反映させます。
echo "### Step 1/4: Rebuilding Docker image..."
docker compose -f server/docker-compose.yml build --no-cache task-agent-daily-plan

# b. 夜間バッチジョブを手動でテスト実行する
# 説明: 新しいDockerイメージを使ってジョブを実行し、動作をテストします。
echo "### Step 2/4: Running manual test..."
sudo systemctl start task-agent-daily-plan.service

# c. ジョブの実行結果（ステータス）を確認する
# 説明: サービスがエラーなく正常に完了したかを確認します。
echo "### Step 3/4: Checking service status..."
sleep 5 # systemdが状態を更新するのを少し待つ
systemctl status task-agent-daily-plan.service

# d. 生成されたJSONファイルの中身を確認する
# 説明: major_events の内容が反映された、期待通りのタスクが生成されているかを確認します。
echo "### Step 4/4: Verifying the output file..."
cat /mnt/data/ai/wani/daily_plan.json

echo "### All steps are ready to be executed."
