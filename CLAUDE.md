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
- 翻譯：PZ 要外文新聞「先翻成繁體中文再收錄」，並附摘要。每輪在 Actions 上用 llama.cpp 跑開源模型（`scripts/llm_setup.sh` 下載、`scripts/llm_start.sh` 啟動，第一次下載後存在 GitHub 快取 `forreal-llm-v2-qwen3-8b`；4B 模型會翻錯遊戲名、亂加「傳聞」，已改用 8B 加範例，並刪掉原文沒有的「傳聞／尚未證實」句子），`pipeline/translate.py` 依重要性先翻，結果快取在 state 分支 `zh.json`。來不及翻的標 `pend`，App 顯示「翻譯中」。不需要 API 金鑰、不花錢。
- 遊戲中文名（`pipeline/names.py`）：翻譯裡的《英文遊戲名》換成台灣官方中文名，發售日曆也加中文名。先查 Steam 台灣商店（英文名完全相同、100 則評論以上或即將推出），再查維基百科中文版台灣正體（必須是電子遊戲條目；轉址到段落、別的作品、數字對不上都不收）。短名稱兩邊不一致時以維基百科為準（防撞名）。寧可保留英文也不要換錯；規則改了就把 `VERSION` 加一，快取（state 分支 `names.json`）會重查。
- 手動補充（選用）：若有 `ai/zh.json`（`{"items": {新聞id: {"t": 中文標題, "s": 中文摘要}}}`），build 也會合併。
- 「活動」分頁（`pipeline/events.py` → `events.json`，PZ 要的「Steam 平台的各項活動與內容」）：
  - 官方時程：Steamworks 文件 Upcoming Steam Events。日期用英文版（`?language=english`，中文版會落後），中文名稱與說明取中文版表格（用報名網址 `optin/sale/<代號>` 對應）。英文版會拿掉已結束的活動，所以和上次的時程合併、保留結束 21 天內的。
  - Steam 活動一律太平洋時間上午 10 點開始／結束（台灣隔天凌晨 1 或 2 點，看夏令時間）。
  - 正在進行的主題節、季節特賣：Steam 商店「內容中心」帳號（clan 41316928）的活動清單 `events/ajaxgetpartnereventspageable`，活動的 jsondata 有確切時間、`source_content_hub`、報名標籤 `optin_tagid`。季節特賣是全站特賣，參加遊戲直接用特價頁的好價。
  - 新品節：時程顯示進行中時，抓 `store.steampowered.com/sale/nextfest` 活動頁（`data-partnereventstore`），排行榜用 `saleaction/ajaxgetsaledynamicappquery`（clanAnnouncementGID 要用 announcement_body.gid，不是活動 gid；flavor：dailyactiveuserdemo／topwishlisted／trendingwishlisted），榜上的試玩版換成正式遊戲（related_items.parent_appid）。
  - 參加遊戲：任何 Steam 特賣活動都可以用 `actions/ajaxgetdynamicsaleitems?tagids_featured=<標籤>` 依熱門程度列出（主題節用 optin_tagid，新品節與發行商特賣用 featured_app_tagid）。
  - 發行商／系列作特賣、展會：`saleaction/ajaxgetlivesaleevents` → `events/ajaxgetbatchedpartnerevent` → 上面的參加遊戲清單；依參加遊戲的評論數排序。每日特惠與首頁焦點：`api/featuredcategories`。
  - 遊戲資料：`IStoreBrowseService/GetItems`（tchinese、TW）：台灣區價格、折扣與截止時間、評價、標籤（`GetTagList` 中文名）、繁中／簡中支援、試玩版、發售日。成人內容（content descriptor 3、4）排除。英文簡介先找開發商的簡中簡介（OpenCC 轉台灣正體），沒有才交給翻譯器（快取 state 分支 `extra_zh.json`，每輪最多 4 分鐘，重要的先翻）；英文的特賣活動名稱也會翻。
  - 離線測試：`python3 tests/local_events.py [模擬時間 ISO] [輸出 events.json]`（`PROBES` 指向解開的 probe 資料夾）。

## 介面
- 主題：鑑定台。牌桌綠墊、壓克力卡盒、卡盒上方的標籤條寫來源與可信度。
- 全像「真」印只給「官方來源」或「三家以上獨立報導」的消息、特價頁的「好價」，以及「活動」頁的 Steam 官方活動（發行商自己辦的特賣不給）。不要拿來裝飾。
- 「活動」頁：進行中的官方活動放最上面（時間、進度條、剩幾天、參加遊戲榜單），沒有進行中的就顯示下一場；再來是今日特惠、發行商／系列作特賣、官方活動時程（依月份）。時間一律顯示台灣時間。
- 被擋下的內容用紅色印章標理由。數字用 Saira（窄體），中文用系統字。
