# Changelog

## [Unreleased]

### Added
- **REST API Server** (`api/server.py`): FastAPIベースのREST APIサーバーを追加
  - `/api/v1/opportunities`: スプレッド候補の取得（フィルタリング対応）
  - `/api/v1/alerts`: アラート履歴の取得
  - `/api/v1/config`: 設定の取得・更新
  - `/api/v1/config/alert-rule`: アラートルールの更新
  - `/api/v1/config/fee-profile/{exchange}`: 取引所の手数料プロファイル更新
  - Swagger UI: `http://localhost:8080/docs`

- **Webhook通知チャネル** (`alert_router/webhook.py`): HTTP POSTで外部システムへ通知を送信する機能を追加

- **継続監視パイプライン** (`monitor/pipeline.py`): データ収集→スプレッド計算→アラート送信を自動で繰り返し実行する機能を追加
  - カスタマイズ可能な実行間隔
  - Webhook通知の統合
  - 設定ファイルからの動的設定読み込み

- **設定管理機能** (`config/manager.py`): アラート閾値や取引所の手数料プロファイルを動的に管理する機能を追加
  - JSONファイルベースの設定保存
  - API経由での設定更新

### Changed
- `requirements.txt`にFastAPI、uvicorn、pydanticの依存関係を追加

### Documentation
- `README.md`を更新し、新機能の使用方法を追加

