# UAT/Release Runbook

## 1. 目的
- 現行パイプライン（データ取得→正規化→スプレッド→アラート）が一貫して動作し、保存・観測・通知が動くことを担保します。

## 2. 準備
1. Python 3.9+ を用意。仮想環境を推奨: `python3 -m venv .venv && source .venv/bin/activate`
2. 必要パッケージをインストール: `pip install -r requirements.txt`

## 3. 手順
1. **データ収集**  
   - `python3 -m data_collector.runner` を実行し、`storage_snapshots/snapshot-ticker.jsonl`/`snapshot-order_book.jsonl` が更新されることを確認。エラーが発生した場合は各取引所の API レスポンスやタイムアウト設定を確認。
2. **スプレッド計算**  
   - `python3 -m spread_engine.runner` を実行して `storage_snapshots/snapshot-spread_opportunity.jsonl` が生成されるか確認し、コンソールに `Spread opportunities` 以下の出力（正味利益）があるかチェック。
3. **アラートルーティング**  
   - `python3 -m alert_router.demo` で保存済み候補を読み込み、コンソール/Slack スタブに通知が出力されることを確認。しきい値・クールダウンを調整したい場合は `AlertRule` を変更。
4. **観測性確認**  
   - `python3 -m observability.server` を起動し、`http://localhost:8000/metrics` にアクセスして Prometheus メトリクス（API リクエストやスプレッド候補）のカウントが増えていることを確認。

## 4. トラブルシュート
- API に失敗する: ネットワーク制限／証明書／レート制限を確認し、`track_api_request` メトリクスで失敗数を確認。
- スプレッドが出ない: `spread_engine.calc` の料金配列を緩和（`DEFAULT_FEES`）するか、JSONL に流れた `tickers` と `order_book` にズレがないか比較。
- アラートが送られない: `AlertRule` の `min_net_spread`/`min_volume` を下げ、クールダウン時間を短縮。

## 5. リリースノート要点
- 各サービスはファイルベースの永続化を使っているため、`storage_snapshots/` の権限/ローテーションを確認。
- メトリクスは `prometheus_client` を使って Prometheus へスクレイプ可能。`observability/server.py` で `start_http_server` を起動。
