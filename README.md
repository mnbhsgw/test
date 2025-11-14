# ビットコイン・アービトラージ監視アプリ

## 概要
複数国内取引所（bitFlyer, Coincheck, bitbank）からティッカー・オーダーブックを取得し、正規化・スプレッド計算・アラート判定・通知を行う監視パイプラインです。CSV/DB ではなく JSONL に現状を保存し、次フェーズでストレージや通知先を拡張できる構成です。

## 構成
- **data_collector**: 各取引所の Public API からティッカー/オーダーブックを取得し、`NormalizedTicker`/`NormalizedOrderBook` に整形。`storage_snapshots/` に JSONL で保存。
- **spread_engine**: 正規化済みデータを使い、手数料や出金コストを含めた純スプレッドを算出。候補を JSONL に出力し、さらにアラートルータ向けに提供。
- **alert_router**: 条件（net spread・volume・クールダウン）を満たすスプレッドを受け、コンソール、Slackスタブ、またはWebhookへ通知。既存の JSONL を読み込むデモもあり。
- **monitor**: 継続的な監視パイプライン。データ収集→スプレッド計算→アラート送信を自動で繰り返し実行。
- **api**: REST API サーバー（FastAPI）。スプレッド候補の取得、アラート履歴の取得、設定管理が可能。
- **config**: 設定管理機能。アラート閾値や取引所の手数料プロファイルを動的に変更可能。
- **observability**: Prometheus 用メトリクスを収集し、HTTP エンドポイント（デフォルト `:8000`）で公開。`start_metrics_server` を使って監視可能。

## 実行方法

1. 依存関係をインストール  
```bash
python3 -m pip install -r requirements.txt
```

2. データ収集 + 正規化 + 保存（JSONL 出力）  
```bash
python3 -m data_collector.runner
```

3. スプレッド計算（正味利益候補を抽出）  
```bash
python3 -m spread_engine.runner
```

4. アラートルート（保存済み候補を Slack/Console に流すデモ）  
```bash
python3 -m alert_router.demo
```

5. メトリクス公開（Prometheus スクレイプ）  
```bash
python3 -m observability.server
```

6. 継続監視パイプライン（データ収集→計算→アラートを自動実行）  
```bash
python3 -m monitor.pipeline --interval 5.0 --min-net-spread 1000.0 --webhook-url https://example.com/webhook

7. REST API サーバー起動  
```bash
python3 -m api.server
# または
uvicorn api.server:app --host 0.0.0.0 --port 8080
```
API ドキュメントは `http://localhost:8080/docs` で確認できます。

## 検証 & UAT
- 準実装で各モジュールの CLI での実行が通ること（上記 2-5 を実行）。
- `storage_snapshots/` に `snapshot-ticker.jsonl`, `snapshot-order_book.jsonl`, `snapshot-spread_opportunity.jsonl` が生成されることを確認。
- `tools/read_opportunities.py` で `spread_engine` 保存結果を読み取れること。
- `prometheus_client` のメトリクスが `:8000/metrics` で見えること。

## API エンドポイント

### スプレッド候補取得
```bash
GET /api/v1/opportunities?min_net_spread=1000&min_volume=0.01
```

### アラート履歴取得
```bash
GET /api/v1/alerts?limit=100
```

### 設定管理
```bash
# 現在の設定を取得
GET /api/v1/config

# アラートルールを更新
PUT /api/v1/config/alert-rule
{
  "min_net_spread": 1500.0,
  "min_volume": 0.02,
  "cooldown_seconds": 300
}

# 取引所の手数料プロファイルを更新
PUT /api/v1/config/fee-profile/bitFlyer
{
  "taker_percent": 0.0003,
  "withdrawal_fee": 100.0
}
```

## 今後の展開
- JSONL → Redis/TimescaleDB などへストレージ拡張し、リアルタイム・履歴分析を分離。
- Slack本番実装（現在はスタブのみ）。
- WebダッシュボードUIの実装。
- WebSocketによるリアルタイムスプレッド配信。
