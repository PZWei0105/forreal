# 玩真的 FOR REAL — 給接手的 Claude

使用者 PZ（痞子葳）沒有程式背景，所有回覆用繁體中文、白話。這個 repo 是他的個人遊戲與科技資訊 App（他有經營遊戲頻道）。

## 原則（不可違反）
- 不收巴哈姆特（含 GNN）的內容與連結。他嫌那裡多是廠商廣告與業配。
- 只收官方與可信媒體的 RSS／公開資料；不轉載全文，只放標題、短摘要與原文連結。
- 濾網一律是寫在 `config/rules.json` 的固定規則，同樣的新聞永遠得到同樣的判斷；被擋下的內容要在「濾網」頁留下理由，不能默默消失。
- 遊戲為主、科技 AI 為輔。手機遊戲只要買斷制／獨立遊戲，課金手遊宣傳一律擋下。
- 特價只用官方商店價格（Steam 台灣區、Epic），不放分潤導購連結。
- 不需要推播通知；特價、發售都是 App 內的分頁。
- 個人資料（稍後看、追蹤、已讀）只存在手機 localStorage。

## 怎麼運作
- GitHub Actions（`.github/workflows/forreal.yml`）每小時跑 `pipeline/build.py`：抓 `config/sources.json` 的新聞來源、Steam／Epic／App Store、Wikipedia 發售表 → 過濾、合併同一件事、排序 → 輸出 `public/data/*.json` 並部署 GitHub Pages。
- 跨輪次資料（新聞暫存、價格紀錄、評論快取、來源狀態）存在 `state` 分支，每次只保留一個 commit。`state` 分支的 `out/` 是最近一次輸出，`runs.json` 是執行紀錄。
- 推到 `main` 時執行 `control/job.json` 指定的工作：`build`（抓資料＋發布）／`deploy`（只改介面時用）／`probe`（實測候選來源，原始回應存到 `probe-results` 分支）。
- 雲端 Claude 工作環境連不到這些網站，要實測新來源就用 `probe`。
- 本機測試：先把 `probe-results` 分支解開到 scratchpad，`PROBE=<資料夾> python3 tests/local_news.py`（看濾網與合併）、`python3 tests/local_build.py <輸出資料夾> <state 資料夾>`（跑完整一輪）。
- 翻譯：PZ 要外文新聞「先翻成繁體中文再收錄」，並附摘要。每輪在 Actions 上用 llama.cpp 跑開源模型（`scripts/llm_setup.sh` 下載、`scripts/llm_start.sh` 啟動，第一次下載後存在 GitHub 快取 `forreal-llm-v1`），`pipeline/translate.py` 依重要性先翻，結果快取在 state 分支 `zh.json`。來不及翻的標 `pend`，App 顯示「翻譯中」。不需要 API 金鑰、不花錢。
- 手動補充（選用）：若有 `ai/zh.json`（`{"items": {新聞id: {"t": 中文標題, "s": 中文摘要}}}`），build 也會合併。

## 介面
- 主題：鑑定台。牌桌綠墊、壓克力卡盒、卡盒上方的標籤條寫來源與可信度。
- 全像「真」印只給「官方來源」或「三家以上獨立報導」的消息，以及特價頁的「好價」。不要拿來裝飾。
- 被擋下的內容用紅色印章標理由。數字用 Saira（窄體），中文用系統字。
