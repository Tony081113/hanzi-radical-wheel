"""從教育部《重編國語辭典修訂本》實際建立偏旁遊戲題庫。

本程式不含任何固定題目。執行時會：
1. 爬取官方「部首索引」的部首與單字清單；
2. 逐字到官方基本檢索取得精確 dictView.jsp 詞條網址；
3. 下載 IDS 漢字構形資料，從字形的最外層自動判讀左／右／上／下部件；
4. 寫出 questions.json。

IDS 只負責字形拆解；題目字和最後開啟的詞條均來自官方辭典。請保留限速，
勿把這支程式用於高頻、大量或商業爬取。
"""
from __future__ import annotations

import argparse
import json
import random
import time
import unicodedata
import io
import zipfile
from pathlib import Path
from typing import Iterator
from urllib.parse import parse_qs, quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://dict.revised.moe.edu.tw/"
CONCISE_URL = "https://dict.concised.moe.edu.tw/"
IDS_URL = "https://raw.githubusercontent.com/cjkvi/cjkvi-ids/master/ids.txt"
UNIHAN_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"
DELAY_SECONDS = 1.2
ROOT = Path(__file__).parent
HEADERS = {"User-Agent": "HanziRadicalWheel/2.0 (educational local project)"}

# IDS 運算子：左右、上下、外包等。遊戲只出最外層可清楚表示的左右／上下結構。
BINARY_OPERATORS = {"⿰", "⿱", "⿴", "⿵", "⿶", "⿷", "⿸", "⿹", "⿺", "⿻"}
POSITION_FOR_OPERATOR = {"⿰": ("left", "right"), "⿱": ("top", "bottom")}
# 教學常見、可單獨辨識的部首（這是介面白名單，不是題庫）。
FAMILIAR_RADICALS = set("一丨丶丿乙亅二人儿入八冂冖冫几凵刀力勹匕匚十卜卩厂厶又口囗土士夂夊夕大女子宀寸小尸山川工己巾干幺广廴弓彡彳心戈戶手支文斗斤方日月木止歹比毛氏气水火爪父片牙牛犬玉瓜瓦甘生用田疒癶白皮皿目矛矢石示禾穴立竹米糸羊羽老而耳舌舟艮色艸虫血行衣見角言谷豆豕貝赤走足身車辛辰邑酉里金長門隹雨青非面革音頁風飛食首香馬骨高鬼魚鳥鹿麥麻黃黑鼠鼻齊齒龍龜氵扌忄艹灬礻衤辶阝")


def get(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    time.sleep(DELAY_SECONDS)
    return BeautifulSoup(response.text, "html.parser")


def official_radical_pages(session: requests.Session, max_radicals: int) -> list[str]:
    """由官方部首索引頁找出每一個部首的 URL，而非自行列部首。"""
    root = get(session, urljoin(BASE_URL, "searchR.jsp"))
    stroke_pages = [urljoin(BASE_URL, a["href"].split("#")[0]) for a in root.select('a[href*="searchR.jsp?ID="]')]
    radical_pages: list[str] = []
    seen: set[str] = set()
    for stroke_page in dict.fromkeys(stroke_pages):
        soup = get(session, stroke_page)
        for link in soup.select('a[href*="searchR.jsp?ID="]'):
            href = link["href"].split("#")[0]
            # 部首頁含兩個 ID；筆畫頁僅含一個 ID。
            if href.count("ID=") >= 2:
                url = urljoin(BASE_URL, href)
                if url not in seen:
                    seen.add(url); radical_pages.append(url)
    # 不固定從一畫部首開始；否則小量爬取會永遠只得到一、二、三等簡單字。
    random.shuffle(radical_pages)
    return radical_pages[:max_radicals] if max_radicals else radical_pages


def words_from_radical_page(session: requests.Session, radical_url: str) -> Iterator[str]:
    """讀取一個部首下的 ALL 列表，擷取官方索引列出的單字。"""
    separator = "&" if "?" in radical_url else "?"
    soup = get(session, radical_url + separator + "ID=-1")
    for link in soup.select('a[href*="word="]'):
        word = parse_qs(urlparse(urljoin(BASE_URL, link["href"])).query).get("word", [""])[0]
        if len(word) == 1:
            yield word


def ids_map(session: requests.Session, cache: Path) -> tuple[dict[str, str], dict[str, str]]:
    """下載（或使用快取的）IDS 構形資料，資料不含任何本遊戲題目。"""
    if not cache.exists():
        response = session.get(IDS_URL, timeout=60)
        response.raise_for_status()
        cache.write_bytes(response.content)
    result: dict[str, str] = {}
    for raw in cache.read_text(encoding="utf-8").splitlines():
        if not raw or raw.startswith(";"):
            continue
        fields = raw.split("\t")
        if len(fields) >= 3 and len(fields[1]) == 1:
            # 同字可能有多個來源；保留第一種可用拆解。
            result.setdefault(fields[1], fields[2].split("\t")[0])
    # 讓複合子樹可還原成一個可顯示的字，例如 ⿰木(喬的 IDS) 還原為「木＋喬」。
    reverse = {ids: char for char, ids in result.items()}
    return result, reverse


def stroke_map(session: requests.Session, cache: Path) -> dict[str, int]:
    """讀取 Unicode Unihan 的總筆畫，供「不接受生僻字」模式作保守過濾。"""
    if cache.exists():
        return {key: int(value) for key, value in json.loads(cache.read_text(encoding="utf-8")).items()}
    response = session.get(UNIHAN_URL, timeout=90); response.raise_for_status()
    result: dict[str, int] = {}
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        filename = next(name for name in archive.namelist() if name.endswith("Unihan_IRGSources.txt"))
        for line in archive.read(filename).decode("utf-8").splitlines():
            fields = line.split("\t")
            if len(fields) == 3 and fields[1] == "kTotalStrokes":
                try: result[chr(int(fields[0][2:], 16))] = int(fields[2].split()[0])
                except ValueError: pass
    cache.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def parse_ids(text: str, index: int = 0):
    """解析 IDS 前序表示法，回傳 (節點, 下一索引)。節點為 str 或 tuple。"""
    while index < len(text) and text[index] in "{}":
        index += 1
    if index >= len(text):
        return None, index
    char = text[index]; index += 1
    if char not in BINARY_OPERATORS:
        return char, index
    children = []
    for _ in range(2 if char not in {"⿲", "⿳"} else 3):
        child, index = parse_ids(text, index)
        if child is None:
            return None, index
        children.append(child)
    return (char, children), index


def simple_component(node) -> str | None:
    """輪盤只顯示一個 Unicode 部件；複合節點留在中央部件，避免錯位或亂拆。"""
    if not isinstance(node, str) or len(node) != 1 or node in "？?":
        return None
    # 排除 IDS 使用的圈號／數字等非字形部件，避免出現「③ 在下方」的題目。
    if unicodedata.category(node) != "Lo":
        return None
    return node


def expanded_leaf_count(node, decompositions: dict[str, str], stack: set[str] | None = None) -> int:
    """計算遞迴構形複雜度；例如「橋」會展開其部件「喬」。"""
    if not isinstance(node, str):
        return sum(expanded_leaf_count(child, decompositions, stack) for child in node[1])
    stack = stack or set()
    if node in stack:
        return 1
    nested, _ = parse_ids(decompositions.get(node, ""))
    if nested is None or nested == node:
        return 1
    return expanded_leaf_count(nested, decompositions, stack | {node})


def ids_text(node) -> str:
    return node if isinstance(node, str) else node[0] + "".join(ids_text(child) for child in node[1])


def display_component(node, reverse_ids: dict[str, str]) -> str | None:
    leaf = simple_component(node)
    if leaf:
        return leaf
    # 只有能對應回一個實際 Unicode 字的複合部件才放到中央，不能就略過。
    char = reverse_ids.get(ids_text(node))
    return char if char and unicodedata.category(char) == "Lo" else None


def question_from_ids(word: str, decomposition: str, min_parts: int, reverse_ids: dict[str, str], decompositions: dict[str, str]) -> dict | None:
    tree, _ = parse_ids(decomposition)
    if not isinstance(tree, tuple) or tree[0] not in POSITION_FOR_OPERATOR or expanded_leaf_count(tree, decompositions) < min_parts:
        return None
    left_or_top, right_or_bottom = tree[1]
    first, second = display_component(left_or_top, reverse_ids), display_component(right_or_bottom, reverse_ids)
    if not first or not second or first == second:
        return None
    first_position, second_position = POSITION_FOR_OPERATOR[tree[0]]
    # 隨機讓其中一邊作為作答偏旁，另一邊放中央；位置由 IDS 根節點嚴格決定。
    if random.choice((True, False)):
        return {"base": second, "radical": first, "position": first_position, "answer": word}
    return {"base": first, "radical": second, "position": second_position, "answer": word}


def exact_entry_url(session: requests.Session, word: str) -> str | None:
    soup = get(session, urljoin(BASE_URL, "search.jsp?word=" + quote(word)))
    for link in soup.select('a[href*="dictView.jsp"]'):
        if link.get_text("", strip=True) == word:
            return urljoin(BASE_URL, link["href"])
    return None


def is_common_character(session: requests.Session, word: str, cache: dict[str, bool]) -> bool:
    """以教育部《國語辭典簡編本》是否收錄單字作為「非生僻」的實用門檻。"""
    if word in cache:
        return cache[word]
    soup = get(session, urljoin(CONCISE_URL, "search.jsp?md=1&word=" + quote(word)))
    cache[word] = any(link.get_text("", strip=True) == word for link in soup.select('a[href*="dictView.jsp"]'))
    return cache[word]


def main() -> None:
    parser = argparse.ArgumentParser(description="實際爬取教育部辭典並建立 IDS 偏旁題庫")
    parser.add_argument("--limit", type=int, default=60, help="要輸出的題數（預設 60）")
    parser.add_argument("--max-radicals", type=int, default=24, help="要掃描的官方部首數；0 表示全部")
    parser.add_argument("--min-parts", type=int, default=3, help="遞迴字形至少包含的構件數（預設 3）")
    parser.add_argument("--allow-rare", action="store_true", help="接受未收錄於教育部《國語辭典簡編本》的生僻字")
    parser.add_argument("--max-common-strokes", type=int, default=18, help="非生僻模式的總筆畫上限（預設 18）")
    parser.add_argument("--seed", type=int, default=None, help="僅控制題目抽樣順序，方便重現結果")
    args = parser.parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    session = requests.Session(); session.headers.update(HEADERS)
    decompositions, reverse_ids = ids_map(session, ROOT / "ids.txt")
    strokes = {} if args.allow_rare else stroke_map(session, ROOT / "unihan_strokes.json")
    common_cache: dict[str, bool] = {}
    radical_pages = official_radical_pages(session, args.max_radicals)
    print(f"已取得 {len(radical_pages)} 個官方部首索引頁；開始爬取候選字…")
    candidates: list[str] = []
    seen: set[str] = set()
    for page in radical_pages:
        for word in words_from_radical_page(session, page):
            if word not in seen and question_from_ids(word, decompositions.get(word, ""), args.min_parts, reverse_ids, decompositions):
                seen.add(word); candidates.append(word)
    # 先抽樣避免題目固定，再以 IDS 遞迴構形數優先，讓橋、媽等複雜字更容易入選。
    random.shuffle(candidates)
    candidates.sort(key=lambda w: expanded_leaf_count(parse_ids(decompositions[w])[0], decompositions), reverse=True)
    print(f"官方索引取得 {len(candidates)} 個可拆組候選字；開始逐字查核詞條…")

    questions = []
    for word in candidates:
        if len(questions) >= args.limit:
            break
        question = question_from_ids(word, decompositions[word], args.min_parts, reverse_ids, decompositions)
        if not question:
            continue
        if not args.allow_rare:
            # 答案、中央部件、偏旁都要容易辨認；高筆畫字和冷僻組件均不出題。
            parts = (word, question["base"], question["radical"])
            if strokes.get(word, 99) > args.max_common_strokes:
                print(f"略過高筆畫字：{word}"); continue
            if not is_common_character(session, word, common_cache):
                print(f"略過生僻字：{word}"); continue
            if any(part not in FAMILIAR_RADICALS and not is_common_character(session, part, common_cache) for part in parts[1:]):
                print(f"略過冷僻部件：{word}"); continue
        url = exact_entry_url(session, word)
        if question and url:
            questions.append({**question, "dictionary_url": url})
            print(f"[{len(questions)}/{args.limit}] {word}: {question['radical']} 在 {question['position']}")
    output = ROOT / "questions.json"
    output.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成：{output}（{len(questions)} 題，皆由本次爬取建立）")


if __name__ == "__main__":
    main()
