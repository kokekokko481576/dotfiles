#!/usr/bin/env python3
"""
DeepSeek CLI — ターミナルからDeepSeekに質問する軽量ツール(標準ライブラリのみ)。

使い方:
  ask.py "1+1は?"
  echo "このログを要約して" | ask.py
  cat main.py | ask.py "このコードをレビューして"
  ask.py --reasoner "難しい数学の問題..."     # deepseek-reasoner(推論モデル)を使う

APIキー: 環境変数 DEEPSEEK_API_KEY、無ければ ~/dotfiles/server/.env の DEEPSEEK_API_KEY を読む。
DeepSeek APIはOpenAI互換なので、自宅サーバーのlitellmを経由せず直接 api.deepseek.com を叩く
(ラップトップ/スマホのDeXなど、サーバー外からでも使える)。
"""
import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

API_URL = "https://api.deepseek.com/chat/completions"


def load_key() -> str | None:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    candidates = [
        Path.home() / "dotfiles" / "server" / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    for path in candidates:
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("DEEPSEEK_API_KEY=") and not line.startswith("#"):
                    return line.split("=", 1)[1].strip()
        except OSError:
            continue
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="DeepSeekにターミナルから質問する")
    ap.add_argument("prompt", nargs="*", help="質問文(省略時は標準入力を読む)")
    ap.add_argument("--model", default="deepseek-chat", help="モデル名(既定: deepseek-chat)")
    ap.add_argument("--reasoner", action="store_true", help="deepseek-reasoner(推論モデル)を使う")
    ap.add_argument("--system", default="簡潔に、日本語で答えてください。",
                    help="システムプロンプト")
    ap.add_argument("--no-stream", action="store_true", help="ストリーミングせず一括表示")
    args = ap.parse_args()

    prompt = " ".join(args.prompt).strip()
    if not prompt and not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()
    if not prompt:
        print("プロンプトが空です。引数か標準入力で渡してください。", file=sys.stderr)
        return 2

    key = load_key()
    if not key:
        print("DEEPSEEK_API_KEY が未設定です。環境変数か server/.env に設定してください。",
              file=sys.stderr)
        return 1

    model = "deepseek-reasoner" if args.reasoner else args.model
    stream = not args.no_stream
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": args.system},
            {"role": "user", "content": prompt},
        ],
        "stream": stream,
    }
    req = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            if not stream:
                data = json.loads(resp.read())
                print(data["choices"][0]["message"]["content"])
                return 0
            for raw in resp:
                line = raw.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                chunk = line[len("data:"):].strip()
                if chunk == "[DONE]":
                    break
                try:
                    obj = json.loads(chunk)
                    delta = obj["choices"][0]["delta"].get("content")
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if delta:
                    sys.stdout.write(delta)
                    sys.stdout.flush()
            print()
    except urllib.error.HTTPError as e:
        print(f"APIエラー: HTTP {e.code} {e.read().decode('utf-8', 'ignore')[:300]}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
