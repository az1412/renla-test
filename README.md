# AI Morning Brief

每天北京时间 `09:05` 通过 GitHub Actions 生成并发送一份 AI 晨报到飞书和 Telegram。

## 覆盖范围

- Claude / Anthropic
- OpenAI
- Google / Gemini / DeepMind
- DeepSeek
- Kimi / Moonshot
- 不足时补充通义、豆包、文心、智谱
- GitHub 热门 agent / AI 公司相关项目
- 延锋官方最新动态

## GitHub Secrets

在仓库 `Settings -> Secrets and variables -> Actions` 里创建这 3 个 secret：

- `FEISHU_WEBHOOK_URL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_HOME_CHANNEL`

## 手动触发

仓库里打开 `Actions -> AI Morning Brief -> Run workflow` 即可手动试跑。
如果只是想先看生成结果，不想真实发消息，可以把 `dry_run` 勾成 `true`。

## 本地测试

```powershell
pip install -r requirements.txt
python scripts/generate_and_send_brief.py --dry-run
```
