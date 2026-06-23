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
from typing import Callable, Iterator
from urllib.parse import parse_qs, quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from radical_forms import radical_form

BASE_URL = "https://dict.revised.moe.edu.tw/"
CONCISE_URL = "https://dict.concised.moe.edu.tw/"
IDS_URL = "https://raw.githubusercontent.com/cjkvi/cjkvi-ids/master/ids.txt"
UNIHAN_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"
# 教育部網站請求採單線程節流；成功一段時間後才小幅加速，429 則立刻退避。
INITIAL_DELAY_SECONDS = 0.9
MIN_DELAY_SECONDS = 0.7
MAX_DELAY_SECONDS = 12.0
ROOT = Path(__file__).parent
CACHE_FILE = ROOT / "dictionary_lookup_cache.json"
HEADERS = {"User-Agent": "HanziRadicalWheel/2.0 (educational local project)"}

# IDS 運算子：左右、上下、外包等。遊戲只出最外層可清楚表示的左右／上下結構。
BINARY_OPERATORS = {"⿰", "⿱", "⿴", "⿵", "⿶", "⿷", "⿸", "⿹", "⿺", "⿻"}
POSITION_FOR_OPERATOR = {"⿰": ("left", "right"), "⿱": ("top", "bottom")}
# 教學常見、可單獨辨識的部首（這是介面白名單，不是題庫）。
FAMILIAR_RADICALS = set("一丨丶丿乙亅二人儿入八冂冖冫几凵刀力勹匕匚十卜卩厂厶又口囗土士夂夊夕大女子宀寸小尸山川工己巾干幺广廴弓彡彳心戈戶手支文斗斤方日月木止歹比毛氏气水火爪父片牙牛犬玉瓜瓦甘生用田疒癶白皮皿目矛矢石示禾穴立竹米糸羊羽老而耳舌舟艮色艸虫血行衣見角言谷豆豕貝赤走足身車辛辰邑酉里金長門隹雨青非面革音頁風飛食首香馬骨高鬼魚鳥鹿麥麻黃黑鼠鼻齊齒龍龜氵扌忄艹灬礻衤辶阝")


class MoeRateLimiter:
    """自適應節流：以較快但保守的速度起跑，對 429 明確退避。"""

    def __init__(self) -> None:
        self.delay = INITIAL_DELAY_SECONDS
        self.last_request = 0.0
        self.successes = 0

    def wait(self) -> None:
        remaining = self.delay - (time.monotonic() - self.last_request)
        if remaining > 0:
            time.sleep(remaining)

    def requested(self) -> None:
        self.last_request = time.monotonic()

    def succeeded(self) -> None:
        self.successes += 1
        # 每 12 次成功請求僅縮短 0.05 秒，最低維持 0.7 秒，避免突發加速。
        if self.successes % 12 == 0:
            self.delay = max(MIN_DELAY_SECONDS, self.delay - 0.05)

    def back_off(self, response: requests.Response | None = None) -> None:
        retry_after = response.headers.get("Retry-After", "") if response is not None else ""
        try:
            server_delay = float(retry_after)
        except ValueError:
            server_delay = 0.0
        self.delay = min(MAX_DELAY_SECONDS, max(self.delay * 2, server_delay, 2.0))
        self.successes = 0
        # 429 回應後才開始計算等待時間，確實留出冷卻空檔。
        self.last_request = time.monotonic()


def get(session: requests.Session, url: str) -> BeautifulSoup:
    limiter: MoeRateLimiter = session.moe_rate_limiter
    last_error: Exception | None = None
    for attempt in range(6):
        limiter.wait()
        limiter.requested()
        try:
            response = session.get(url, timeout=30)
        except requests.RequestException as error:
            # RemoteDisconnected、逾時、暫時 DNS 錯誤等都先退避，不直接中止整個題庫更新。
            last_error = error
            limiter.back_off()
            continue
        if response.status_code == 429 or 500 <= response.status_code < 600:
            limiter.back_off(response)
            last_error = requests.HTTPError(f"HTTP {response.status_code}")
            continue
        response.raise_for_status()
        limiter.succeeded()
        return BeautifulSoup(response.text, "html.parser")
    raise RuntimeError("教育部辭典連線連續中斷，已自動退避重試 6 次；請稍後再按重爬。") from last_error


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


def load_lookup_cache() -> tuple[dict[str, bool], dict[str, str | None]]:
    """讀取已確認的常見字與詞條網址，避免每次重爬都重複查同一個字。"""
    common: dict[str, bool] = {}
    entries: dict[str, str | None] = {}
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            common = {key: bool(value) for key, value in data.get("common", {}).items()}
            entries = {key: value if isinstance(value, str) else None for key, value in data.get("entries", {}).items()}
        except (json.JSONDecodeError, OSError):
            pass
    # 現有題庫本身已含官方精確網址，可直接作為第一批快取。
    questions_file = ROOT / "questions.json"
    if questions_file.exists():
        try:
            for question in json.loads(questions_file.read_text(encoding="utf-8")):
                if question.get("answer") and question.get("dictionary_url"):
                    entries.setdefault(question["answer"], question["dictionary_url"])
        except (json.JSONDecodeError, OSError):
            pass
    return common, entries


def save_lookup_cache(common: dict[str, bool], entries: dict[str, str | None]) -> None:
    temporary = CACHE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps({"common": common, "entries": entries}, ensure_ascii=False), encoding="utf-8")
    temporary.replace(CACHE_FILE)


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
        part = radical_form(first, first_position)
        return {"base": second, "radical": first, "position": first_position, "radicals": [part], "answer": word}
    part = radical_form(second, second_position)
    return {"base": first, "radical": second, "position": second_position, "radicals": [part], "answer": word}


def leaf_paths(node, path: tuple[str, ...] = ()) -> list[tuple[str, tuple[str, ...]]]:
    """取得三構件字每個葉節點的位置路徑，用來推算相對於中央部件的方向。"""
    component = simple_component(node)
    if component:
        return [(component, path)]
    if not isinstance(node, tuple) or node[0] not in POSITION_FOR_OPERATOR:
        return []
    first_position, second_position = POSITION_FOR_OPERATOR[node[0]]
    first, second = node[1]
    return leaf_paths(first, path + (first_position,)) + leaf_paths(second, path + (second_position,))


def three_part_leaf_paths(tree, decompositions: dict[str, str]) -> list[tuple[str, tuple[str, ...]]]:
    """取得恰好三個部件；必要時只展開根節點的一個子字，避免過度拆解。"""
    direct = leaf_paths(tree)
    if len(direct) == 3:
        return direct
    if not isinstance(tree, tuple) or tree[0] not in POSITION_FOR_OPERATOR:
        return []
    positions = POSITION_FOR_OPERATOR[tree[0]]
    for nested_index, nested_char in enumerate(tree[1]):
        other_index = 1 - nested_index
        if not simple_component(nested_char) or not simple_component(tree[1][other_index]):
            continue
        nested_tree, _ = parse_ids(decompositions.get(nested_char, ""))
        nested_leaves = leaf_paths(nested_tree)
        if len(nested_leaves) != 2:
            continue
        result = [(tree[1][other_index], (positions[other_index],))]
        result.extend((component, (positions[nested_index],) + path) for component, path in nested_leaves)
        return result
    return []


def multi_radical_question_from_ids(word: str, decomposition: str, min_parts: int, decompositions: dict[str, str]) -> dict | None:
    """建立一個中央部件加兩個偏旁的題目，只採用位置清楚的三個單一構件。"""
    tree, _ = parse_ids(decomposition)
    if not isinstance(tree, tuple) or expanded_leaf_count(tree, decompositions) < min_parts:
        return None
    leaves = three_part_leaf_paths(tree, decompositions)
    if len(leaves) != 3 or len({component for component, _path in leaves}) != 3:
        return None

    choices = []
    for base_index, (base, base_path) in enumerate(leaves):
        radicals = []
        for index, (component, component_path) in enumerate(leaves):
            if index == base_index:
                continue
            shared = 0
            while shared < min(len(base_path), len(component_path)) and base_path[shared] == component_path[shared]:
                shared += 1
            if shared == len(component_path):
                break
            radicals.append({"char": component, "position": component_path[shared]})
        if len(radicals) == 2 and len({part["position"] for part in radicals}) == 2:
            choices.append({"base": base, "radicals": [radical_form(part["char"], part["position"]) for part in radicals], "answer": word})
    return random.choice(choices) if choices else None


def exact_entry_url(session: requests.Session, word: str, cache: dict[str, str | None], persist: Callable[[], None] | None = None) -> str | None:
    if word in cache:
        return cache[word]
    if persist:
        persist()
    soup = get(session, urljoin(BASE_URL, "search.jsp?word=" + quote(word)))
    for link in soup.select('a[href*="dictView.jsp"]'):
        if link.get_text("", strip=True) == word:
            cache[word] = urljoin(BASE_URL, link["href"])
            return cache[word]
    cache[word] = None
    return cache[word]


def is_common_character(session: requests.Session, word: str, cache: dict[str, bool], persist: Callable[[], None] | None = None) -> bool:
    """以教育部《國語辭典簡編本》是否收錄單字作為「非生僻」的實用門檻。"""
    if word in cache:
        return cache[word]
    if persist:
        persist()
    soup = get(session, urljoin(CONCISE_URL, "search.jsp?md=1&word=" + quote(word)))
    cache[word] = any(link.get_text("", strip=True) == word for link in soup.select('a[href*="dictView.jsp"]'))
    return cache[word]


def build_questions(
    limit: int = 60,
    max_radicals: int = 24,
    min_parts: int = 3,
    allow_rare: bool = False,
    max_common_strokes: int = 18,
    multi_radical_chance: float = 0.35,
    exact_entry_links: bool = False,
    seed: int | None = None,
    progress: Callable[[int, str], None] | None = None,
) -> list[dict]:
    """建立題庫，並可將 0～100 的進度傳給本機網頁介面。"""
    report = progress or (lambda _percent, _message: None)
    if not 0 <= multi_radical_chance <= 1:
        raise ValueError("multi_radical_chance 必須介於 0 與 1 之間")
    if seed is not None:
        random.seed(seed)
    session = requests.Session(); session.headers.update(HEADERS)
    session.moe_rate_limiter = MoeRateLimiter()
    report(2, "正在讀取漢字構形資料…")
    decompositions, reverse_ids = ids_map(session, ROOT / "ids.txt")
    report(6, "正在準備常用字篩選資料…")
    strokes = {} if allow_rare else stroke_map(session, ROOT / "unihan_strokes.json")
    common_cache, entry_cache = load_lookup_cache()
    persist_cache = lambda: save_lookup_cache(common_cache, entry_cache)
    report(10, "正在取得教育部部首索引…")
    radical_pages = official_radical_pages(session, max_radicals)
    candidates: list[str] = []
    seen: set[str] = set()
    total_pages = max(len(radical_pages), 1)
    for number, page in enumerate(radical_pages, start=1):
        report(10 + int(number / total_pages * 35), f"第 1/2 階段：掃描部首索引（{number}/{len(radical_pages)}），目標 {limit} 題…")
        for word in words_from_radical_page(session, page):
            if word not in seen and question_from_ids(word, decompositions.get(word, ""), min_parts, reverse_ids, decompositions):
                seen.add(word); candidates.append(word)
    # 先抽樣避免題目固定，再以 IDS 遞迴構形數優先，讓橋、媽等複雜字更容易入選。
    random.shuffle(candidates)
    candidates.sort(key=lambda w: expanded_leaf_count(parse_ids(decompositions[w])[0], decompositions), reverse=True)
    questions = []
    total_candidates = max(len(candidates), 1)
    for number, word in enumerate(candidates, start=1):
        report(45 + int(number / total_candidates * 52), f"第 2/2 階段：查核詞條（已取得 {len(questions)}/{limit} 題）…")
        if len(questions) >= limit:
            break
        question = None
        if random.random() < multi_radical_chance:
            question = multi_radical_question_from_ids(word, decompositions[word], min_parts, decompositions)
        question = question or question_from_ids(word, decompositions[word], min_parts, reverse_ids, decompositions)
        if not question:
            continue
        if not allow_rare:
            # 答案、中央部件、偏旁都要容易辨認；高筆畫字和冷僻組件均不出題。
            radical_parts = question.get("radicals") or [{"char": question["radical"]}]
            parts = (word, question["base"], *(part["char"] for part in radical_parts))
            if strokes.get(word, 99) > max_common_strokes:
                continue
            if not is_common_character(session, word, common_cache, persist_cache):
                continue
            if any(part not in FAMILIAR_RADICALS and not is_common_character(session, part, common_cache, persist_cache) for part in parts[1:]):
                continue
        # 快速模式不另抓 dictView：官方搜尋頁在答對後才開啟，可省下每題一次網路請求。
        url = exact_entry_url(session, word, entry_cache, persist_cache) if exact_entry_links else entry_cache.get(word)
        if not url:
            url = urljoin(BASE_URL, "search.jsp?word=" + quote(word))
        if question and url:
            questions.append({**question, "dictionary_url": url})
    output = ROOT / "questions.json"
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output)
    save_lookup_cache(common_cache, entry_cache)
    report(100, f"完成：已更新 {len(questions)} 題題庫。")
    return questions


def main() -> None:
    parser = argparse.ArgumentParser(description="實際爬取教育部辭典並建立 IDS 偏旁題庫")
    parser.add_argument("--limit", type=int, default=60, help="要輸出的題數（預設 60）")
    parser.add_argument("--max-radicals", type=int, default=24, help="要掃描的官方部首數；0 表示全部")
    parser.add_argument("--min-parts", type=int, default=3, help="遞迴字形至少包含的構件數（預設 3）")
    parser.add_argument("--allow-rare", action="store_true", help="接受未收錄於教育部《國語辭典簡編本》的生僻字")
    parser.add_argument("--max-common-strokes", type=int, default=18, help="非生僻模式的總筆畫上限（預設 18）")
    parser.add_argument("--multi-radical-chance", type=float, default=0.35, help="雙偏旁題比例（0～1，預設 0.35）")
    parser.add_argument("--exact-entry-links", action="store_true", help="逐題查詢精確 dictView 詞條（較慢）")
    parser.add_argument("--seed", type=int, default=None, help="僅控制題目抽樣順序，方便重現結果")
    args = parser.parse_args()
    build_questions(**vars(args), progress=lambda _percent, message: print(message))


if __name__ == "__main__":
    main()
