# ビットコイン・アービトラージ監視アプリ

## 概要
複数国内取引所（bitFlyer, Coincheck, bitbank）からティッカー・オーダーブックを取得し、正規化・スプレッド計算・アラート判定・通知を行う監視パイプラインです。CSV/DB ではなく JSONL に現状を保存し、次フェーズでストレージや通知先を拡張できる構成です。

## 構成
- **data_collector**: 各取引所の Public API からティッカー/オーダーブックを取得し、`NormalizedTicker`/`NormalizedOrderBook` に整形。`storage_snapshots/` に JSONL で保存。
- **spread_engine**: 正規化済みデータを使い、手数料や出金コストを含めた純スプレッドを算出。候補を JSONL に出力し、さらにアラートルータ向けに提供。
- **alert_router**: 条件（net spread・volume・クールダウン）を満たすスプレッドを受け、コンソールや Slackスタブへ通知。既存の JSONL を読み込むデモもあり。
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

## 検証 & UAT
- 準実装で各モジュールの CLI での実行が通ること（上記 2-5 を実行）。
- `storage_snapshots/` に `snapshot-ticker.jsonl`, `snapshot-order_book.jsonl`, `snapshot-spread_opportunity.jsonl` が生成されることを確認。
- `tools/read_opportunities.py` で `spread_engine` 保存結果を読み取れること。
- `prometheus_client` のメトリクスが `:8000/metrics` で見えること。

## 今後の展開
- JSONL → Redis/TimescaleDB などへストレージ拡張し、リアルタイム・履歴分析を分離。
- Slack/Webhook など本番通知チャネルの実装・テンプレート化。
- スプレッド候補を API で公開し、下流（UI/通知サービス）でトリガーできるようにする。
