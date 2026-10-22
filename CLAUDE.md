# 玩真的 FOR REAL — 給接手的 Claude

使用者 PZ（痞子葳）沒有程式背景，所有回覆用繁體中文、白話。這個 repo 是他的個人遊戲與科技資訊 App（他有經營遊戲頻道）。

## 原則（不可違反）
- 不收巴哈姆特（含 GNN）的內容與連結。他嫌那裡多是廠商廣告與業配。
- 只收官方與可信媒體的 RSS／公開資料；不轉載全文，只放標題、短摘要與原文連結。
- 濾網一律是寫在 `config/rules.json` 的固定規則，同樣的新聞永遠得到同樣的判斷；被擋下的內容要在「濾網」頁留下理由，不能默默消失。（依來源自己標的分類擋下的清單也在 `rules.json` 的 `block_cats`，`* movies` 代表結尾是「 movies」的分類。改規則前先用新舊規則跑一遍 state 分支的 `items.json.gz` 比對差異，確認沒有誤擋。）
- 「影視娛樂（非遊戲）」`film_tv`：GamesRadar、Polygon、Kotaku 的 RSS 會混進大量電影、影集、漫畫新聞（DC、漫威、Glee…）。只有「來源標了影視分類（`block_cats.film_tv`）＋標題摘要完全沒有遊戲跡象（`game_words`、`game_signal`：遊戲字眼、主機、遊戲作品名）」才擋；改編自遊戲的動畫電影（Edgerunners、快打旋風電影、質量效應影集）照常收錄。只用在遊戲區，科技區的 Netflix、Spotify 商業新聞不受影響。
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
- 翻譯：PZ 要外文新聞「先翻成繁體中文再收錄」，並附摘要。每輪在 Actions 上用 llama.cpp 跑開源模型（`scripts/llm_setup.sh` 下載、`scripts/llm_start.sh` 啟動，第一次下載後存在 GitHub 快取 `forreal-llm-v2-qwen3-8b`；4B 模型會翻錯遊戲名、亂加「傳聞」，已改用 8B 加範例，並刪掉原文沒有的「傳聞／尚未證實」句子），`pipeline/translate.py` 依重要性先翻，結果快取在 state 分支 `zh.json`。來不及翻的標 `pend`，App 顯示「翻譯中」。不需要 API 金鑰、不花錢。每輪翻譯器都是剛啟動、沒有提示快取，第一批 4 則要從頭讀完整段提示（4 核心機器上 5 分多鐘），所以請求等待上限是 600 秒（`READ_TIMEOUT`）；以前設 300 秒，排最前面的重要新聞每輪逾時、卡在「翻譯中」好幾天。llama-server 的記錄尾段每輪存在 state 分支 `diag/llama.log`。簡體字偵測用 OpenCC 字典裡「只在簡體出現」的字（約 3,800 字，已剔除群、件、秘、硬這類台灣也用的字），出現就整句轉台灣正體；轉完一律把「臺」換成「台」。
- 翻譯檢查（`translate.check()`，固定規則）：8B 模型常把金額的「億」算錯（$25 billion 寫成 25 億美元，應為 250 億）、把美元寫成「元」、自己猜日本人名漢字（櫻井政博寫成坂井悠真）、抄範例答案。每則翻完都檢查：①標題裡有 `config/glossary.json` 的名稱，翻譯就要用指定譯名或照抄原文；②翻譯裡的每個金額與「萬／億」大數字都要對得上原文（幣別也要對；只抓寫錯或自己加的，省略不算錯）；③原標題講的是實體版，中文標題就要寫出「實體」（以前把「PS5 實體版 2027 年推出」翻成「2027 年發售」）；④不能出現範例答案才有的字句。不過就把錯在哪、正確寫法附在題目後重翻一次，再錯就算失敗、下輪再試（6 輪後顯示原文）。題目一開始就附上「譯名」與「金額」的正確中文寫法（`hints()`）。快取裡的舊翻譯每輪也重新檢查，過不了就重翻（`stats.recheck`）。固定譯名只放人名與非遊戲作品；遊戲名交給 `names.py`。《》以外的英文原名翻完會換成譯名。小修提示詞不用加 `PROMPT_VERSION`（加一會讓三百多則全部重翻）。
- 遊戲中文名（`pipeline/names.py`）：翻譯裡的《英文遊戲名》換成台灣官方中文名，發售日曆也加中文名。先查 Steam 台灣商店（英文名完全相同、100 則評論以上或即將推出），再查維基百科中文版台灣正體（必須是電子遊戲條目；轉址到段落、別的作品、數字對不上都不收）。短名稱兩邊不一致時以維基百科為準（防撞名）。寧可保留英文也不要換錯；規則改了就把 `VERSION` 加一，快取（state 分支 `names.json`）會重查。
- 手動補充（選用）：若有 `ai/zh.json`（`{"items": {新聞id: {"t": 中文標題, "s": 中文摘要}}}`），build 也會合併。
- 「活動」分頁（`pipeline/events.py` → `events.json`，PZ 要的「Steam 平台的各項活動與內容」）：
  - 官方時程：Steamworks 文件 Upcoming Steam Events。日期用英文版（`?language=english`，中文版會落後），中文名稱與說明取中文版表格（用報名網址 `optin/sale/<代號>` 對應）。英文版會拿掉已結束的活動，所以和上次的時程合併、保留結束 21 天內的。
  - Steam 活動一律太平洋時間上午 10 點開始／結束（台灣隔天凌晨 1 或 2 點，看夏令時間）。
  - 正在進行的主題節、季節特賣：Steam 商店「內容中心」帳號（clan 41316928）的活動清單 `events/ajaxgetpartnereventspageable`，活動的 jsondata 有確切時間、`source_content_hub`、報名標籤 `optin_tagid`。季節特賣是全站特賣，參加遊戲直接用特價頁的好價。
  - 新品節：時程顯示進行中時，抓 `store.steampowered.com/sale/nextfest` 活動頁（`data-partnereventstore`），排行榜用 `saleaction/ajaxgetsaledynamicappquery`（clanAnnouncementGID 要用 announcement_body.gid，不是活動 gid；flavor：dailyactiveuserdemo／topwishlisted／trendingwishlisted），榜上的試玩版換成正式遊戲（related_items.parent_appid）。
  - 參加遊戲：任何 Steam 特賣活動都可以用 `actions/ajaxgetdynamicsaleitems?tagids_featured=<標籤>` 依熱門程度列出（主題節用 optin_tagid，新品節與發行商特賣用 featured_app_tagid）。
  - 發行商／系列作特賣、展會：`saleaction/ajaxgetlivesaleevents` → `events/ajaxgetbatchedpartnerevent` → 上面的參加遊戲清單；依參加遊戲的評論數排序。每日特惠與首頁焦點：`api/featuredcategories`。
  - 遊戲資料：`IStoreBrowseService/GetItems`（tchinese、TW）：台灣區價格、折扣與截止時間、評價、標籤（`GetTagList` 中文名）、繁中／簡中支援、試玩版、發售日。英文簡介先找開發商的簡中簡介（OpenCC 轉台灣正體），沒有才交給翻譯器（快取 state 分支 `extra_zh.json`，每輪最多 4 分鐘，重要的先翻；App 在機器翻譯的簡介前標「機翻」）。發行商特賣的活動名稱不翻（專有名詞常被翻錯，保留原文）。成人限定（content descriptor 3、4）與標了色情內容／Hentai 的小眾作品（評論 2 萬則以下）不收。
  - 限時免費（`build_free`）：免費領取（領了就永久留在收藏庫）用 Steam 搜尋 `search/results/?maxprice=free&specials=1`（會混到 DLC，DLC 也收、排在遊戲後面），再用 GetItems 的 `best_purchase_option.is_free_to_keep`、`free_to_keep_ends` 確認與取截止時間。免費週末只看 GetItems 的 `free_weekend` 欄位和行銷訊息 type 14（`is_free_temporarily` 在免費領取時也是 true，不能拿來判斷免費週末）。
  - Steam 用戶端行銷訊息 `IMarketingMessagesService/GetActiveMarketingMessages/v1/?country=TW&anonymous_user=true`：週末特價（2）、週中特價（11）、每日特惠（12）、免費週末（14）、特賣頁（15）的確切起訖，用來補「今日特惠與首頁焦點」的截止時間。抓不到時只記警告，免費領取照做。
  - 離線測試：`python3 tests/local_events.py [模擬時間 ISO] [輸出 events.json]`（`PROBES` 指向解開的 probe 資料夾）。
- Steam 願望清單（`pipeline/wishlist.py` → deals.json 的 `wish`，PZ 2026/10 要的）：`config/steam.json` 的 `profile` 填 Steam 個人檔案網址（/id/xxx 或 /profiles/7656…）。個人檔案 `?xml=1` 換 SteamID64、拿顯示名稱與隱私狀態；`IWishlistService/GetWishlist` 拿清單（願望清單要公開，「遊戲詳細資料」設公開）；遊戲資料用 `events.get_items`／`norm_item`（台灣區價格、折扣截止、評價、發售日），另外查英文名對應發售日曆（`mark_calendar` 在發售表加 `wl`）。價格記錄和特價頁共用 `prices.json`。沒設定時 App 顯示「還沒有連結」。GetWishlist 對「沒公開」和「空的」都回 `{"response":{}}`，所以清單是空的時候再開商店願望清單頁（`?l=tchinese`）：沒公開會出現「無法載入使用者的願望清單」，App 依此顯示「沒有公開」或「目前是空的」（2026/10/22 實測：PZ 的清單已公開、目前是空的）。
- 訂閱片單（`pipeline/subs.py` → releases.json 的 `subs`，「上市」頁的「訂閱片單」）：
  - Game Pass：`catalog.gamepass.com/sigls/v2`（TW、zh-tw）的最近新增／即將加入／即將離開清單＋`displaycatalog.mp.microsoft.com`（台灣官方中文名、圖、台灣售價）。日期與方案（Ultimate／Premium／PC、首日加入）來自 Xbox Wire 每月兩次的「Coming to XBOX Game Pass」文章（從新聞暫存裡 xboxwire 的文章找，解析結果存在 cache `gp_wire`，保留 50 天）；文章有、清單還沒有的也列出（英文名）。
  - PS Plus：台灣官網 `playstation.com/zh-hant-tw/ps-plus/whats-new/`。頁面是好幾個區塊，各有 `data-on-time`／`data-off-time`（網頁用 JS 切換，HTML 裡會留著過期的舊區塊），只採用現在有效的：每月遊戲、遊戲目錄本月新增、經典遊戲目錄、遊戲試玩。日期來自 PlayStation Blog 繁中版的 PS Plus 分類 RSS（`blog.zh-hant.playstation.com/category/ps-plus/feed/`）：每月遊戲公告寫「10月6日星期二至11月2日星期一」、遊戲目錄公告寫「將於10月20日起開放遊玩」；公告標題要提到目前片單裡的遊戲才套用（避免月份錯配）。小真在換新片單的那一週提一次、截止前 3 天提醒；行事曆有每月遊戲最後一天與 Game Pass 離開日。
- 主機特價（`pipeline/console.py` → deals.json 的 `ps`，「特價」頁的「主機」）：PlayStation Store 台灣區。用網頁自己的 GraphQL（persisted query，一定要帶 `content-type: application/json` 標頭，不然會被當成跨站請求擋掉）：`getExperience`（alias deals）找出這週的促銷分類，`categoryStrandRetrieve` 取商品（原價、優惠價、折扣、是否 PS Plus 會員價）。同款遊戲只留一個版本（標準版優先），不收追加內容；每個促銷最多取 300 款（「所有優惠」有兩千多款），照 Sony 頁面的順序排。Store 沒有公開優惠截止時間。查詢的 sha256Hash 寫在 `HASH`；Sony 改版後如果壞掉（濾網頁的來源狀態會顯示錯誤），用 probe_browser 打開 store.playstation.com/zh-hant-tw/pages/deals 抓新的 hash。任天堂：台灣 eShop 有台灣價格（`api.ec.nintendo.com/v1/price?country=TW&ids=<nsuid>` 回新台幣），但沒有公開的特價清單（ec.nintendo.com 的 search/sales 都 404、香港商店網頁擋程式），只做得出不完整的清單，所以沒做。
- 行事曆（`pipeline/ical.py`）：`data/ics/<id>.ics` 是單一遊戲（發售表每筆有 `ics` 代號，App 的行事曆按鈕連過去，發售當天早上 9 點提醒）；`data/cal/releases.ics`（大廠、Steam 期待榜、願望清單的發售日）與 `data/cal/deals.ics`（Steam 官方活動起訖、Steam／Epic 限時免費截止）給手機訂閱，每小時更新。iPhone 用 webcal:// 訂閱；Google 日曆要在電腦版「加入日曆網址」。.ics 不存 state 分支，deploy 模式用上一輪的 JSON 重新產生。
- 離線測試新功能：`PROBE=<probe 資料夾> python3 tests/local_extras.py <預覽站 data 資料夾> <state 資料夾> [模擬時間]`（願望清單用假資料）。

## 介面
- 主題：防偽情報中樞（2026/10 改版，取代原本的鑑定台）。深藍墨色底，用鈔票、護照的防偽印刷當視覺語言：扭索紋花飾（`fx.js` 的 `rosette()`）、全像箔、紫外線掃描光、凹版紅色「攔截」印章、切角的「保全文件」卡片（`.doc`）。標題用 Noto Serif TC 900，數字用 Saira（窄體），內文用系統字。只有深色模式。
- 全像箔只用在：「真」印、選中的分頁、小真的核心。「真」印只給「官方來源」或「三家以上獨立報導」的消息、特價頁的「好價」，以及「活動」頁的 Steam 官方活動（發行商自己辦的特賣不給）。不要拿來裝飾。
- 小真：PZ 的情報秘書，「簡報」分頁最上面的簡報。內容用固定規則從當輪資料組出來（`brief.js` 的 `buildBrief`，不是 AI 生成）：頭號消息、Steam 活動、限時免費、好價、7 天內大作、追蹤關鍵字、濾網統計。可以用手機內建語音（speechSynthesis、zh-TW）播報，唸到哪一行就亮哪一行。
- 聲光：`sfx.js` 用 Web Audio 即時合成音效（不載音檔）並搭配震動；`fx.js` 是開機動畫（每次打開 App 播一次、輕觸略過）、全像光影（跟著捲動或傾斜手機變色）、紫外線掃描、數字滾動、提示框。全部都能在「設定」關掉或切省電；系統開了「減少動態效果」時一律不播。設定存在 localStorage（`fr.sfx`、`fr.fx`）。
- 搜尋（右上放大鏡）：同時搜新聞、特價、Steam 活動、發售表，可以把關鍵字直接加到追蹤。
- 「活動」頁：進行中的官方活動放最上面（倒數圓環、時間、剩幾天、參加遊戲榜單），沒有進行中的就顯示下一場；再來是限時免費、今日特惠與首頁焦點、發行商／系列作特賣、官方活動時程（依月份）。時間一律顯示台灣時間。
- 被擋下的內容用紅色印章標理由。
- 手機常把 App 放在背景好幾小時：切回來超過 10 分鐘就當成新的一次查看（問候語、簡報、「新進」標記重算），資料超過 65 分鐘沒更新就自動重抓。問候語的時間一律用台灣時間，從 `formatToParts` 取「時」（中文格式會輸出「17時」，不能直接轉數字）。
- `app.js` 用 `?v=__BUILD__` 匯入其他模組；`build.py` 的 `copy_site` 會把所有 .js、.html 裡的 `__BUILD__` 換成這輪的 build id（`sw.js` 也是），改版後手機不會卡在舊檔。
