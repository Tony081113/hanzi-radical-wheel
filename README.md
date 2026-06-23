# 偏旁組字輪盤

遊戲會顯示中央部件，再亮起一個或兩個方向的偏旁輪盤。亮起的方向就是偏旁在成字後的相對位置，例如「十 + 口」只能是口在下方的「古」，不會被出成右方；部分三構件字會要求在兩個方向各選一個偏旁。雙偏旁題預設隨機比例為 35%。轉動滑鼠滾輪選擇偏旁後按「確認答案」；可自行關閉答對後開啟教育部《重編國語辭典修訂本》詞條的彈出頁。

偏旁位置由 IDS 構形資料決定，輪盤會依上、下、左、右位置動態調整部件比例；有標準 Unicode 偏旁異體時優先採用，例如水→氵、心→忄、手→扌、言→訁、示→礻、艸→艹、竹→⺮。「雨」放在上方時會以較扁平的比例呈現。中央圓形顯示的是組字基底，會保留原字形，不套用偏旁異體。

## 正式偏旁 SVG 資產

專案採 GPL-3.0-or-later。若要以真正筆畫 SVG 取代文字偏旁，請自行下載符合授權條件的 GlyphWiki dump，並取得 [KAGE Python engine](https://github.com/HowardZorn/kage-engine) 的本機 clone，再執行：

```powershell
python tools/generate_radical_svgs.py --kage-dir C:\tools\kage-engine --glyphwiki-dump C:\downloads\dump_newest_only.txt
```

首次請先執行 `python -m pip install -r requirements-glyphs.txt`。目前的資產組會生成竹、艸、水、心、手、言、示、雨等常見偏旁；包括既有題庫與應急題庫，偵測到 SVG 後就會自動使用。

產生的 SVG 僅放在本機 `assets/radicals/`，不會推送 Git。重新爬取題庫後，每個偏旁都會攜帶對應 SVG 資產鍵；前端會優先使用 SVG，資產尚未建立時才回退到 Unicode 偏旁字形。

## 產生題庫（爬蟲）

最簡單的方式是在 PowerShell 執行下列檔案；它會詢問要建立幾題：

```powershell
.\run_crawler.ps1
```

也可以直接指定數量：

```powershell
cd C:\Users\tonyl\Documents\Codex\2026-06-21\new-chat\outputs\hanzi-radical-wheel
python -m pip install -r requirements.txt
python scrape_dictionary.py --limit 80
```

爬蟲沒有固定題庫。它會實際爬取教育部辭典的「部首索引」取得候選單字，並逐一搜尋官方詞條取得精確網址。接著會下載 IDS 漢字構形資料，自動判讀字形最外層的左右或上下關係，再輸出 `questions.json`。

```powershell
# 從各筆畫的官方部首中抽樣 24 個索引，建立至少三構件的 60 題
python scrape_dictionary.py

# 完整掃描所有部首索引（耗時較久，請只在必要時使用）
python scrape_dictionary.py --max-radicals 0 --limit 300

# 將雙偏旁題比例提高為 50%
python scrape_dictionary.py --multi-radical-chance 0.5
```

爬蟲以單線程自適應節流請求教育部網站：起始間隔為 0.9 秒，連續成功後才緩慢加速，最低維持 0.7 秒；收到 429、5xx、逾時或連線中斷時會立即退避並最多自動重試 6 次，429 會優先遵守伺服器的 `Retry-After` 指示。它會立即保存已查過的常見字結果與詞條網址到本機快取，因此中斷後重跑不必從頭查。為了加速，預設題庫只存教育部官方搜尋連結，不會逐題額外抓取 `dictView` 精確網址；若需要精確網址，改用 `--exact-entry-links`，但會明顯變慢。請以少量、教育用途執行，勿加入並發請求或移除節流。IDS 資料僅用於判斷字形的相對位置；題目目標字與跳轉詞條均由教育部網站本次爬得。

預設會略過生僻字：答案必須同時存在於教育部《國語辭典簡編本》、總筆畫不超過 18，且中央部件與偏旁也必須是常見字或常用部首。若希望題庫也包含較生僻、但存在於《重編國語辭典修訂本》的字，使用：

```powershell
python scrape_dictionary.py --limit 80 --allow-rare
```

互動式的 `run_crawler.ps1` 也會直接詢問是否接受生僻字。

## 啟動

遊戲頁可直接按「重爬題目並刷新題庫」，會顯示目前的爬取進度，完成後自動載入新題庫。正式 `questions.json` 是本機產生檔，不會推送 Git：第一次啟動時若找不到它，伺服器會自動在背景建立；遊戲頁會暫時使用內建的 10 題應急題庫，完成後自動切換成正式題庫。請使用內建的本機伺服器啟動遊戲：

```powershell
.\run_game.ps1
```

然後開啟 `http://localhost:8000`，把啟動視窗顯示的「題庫更新密鑰」貼進遊戲頁，才可使用重爬功能。密鑰每次啟動都會更新，且不會寫入檔案。
