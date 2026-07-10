# codex-skills

Codex 専用のグローバルスキル正本リポジトリ。各トップレベルディレクトリが1スキルで、
定義は各 `SKILL.md` に置く。

スキルは `$HOME/.codex/skills/<skill-name>` から各正本ディレクトリへの
シンボリックリンクで発見させる。端末間の取得とリンク再構築は、グローバルスキルの
bootstrap ワークフローで行う。
