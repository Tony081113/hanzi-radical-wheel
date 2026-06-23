// 每個輪盤只使用符合該空間位置的部件，避免把「氵／礻」等左偏旁放到下方。
const RADICALS_BY_POSITION = {
  left: ["水", "心", "手", "言", "木", "女", "示"],
  right: ["子", "馬", "月", "口", "力", "貝"],
  top: ["宀", "艸", "雨", "日", "竹"],
  bottom: ["口", "心", "力", "儿", "八", "子", "田"]
};
const RADICAL_VARIANTS = {
  left: {水:"氵", 心:"忄", 手:"扌", 言:"訁", 示:"礻", 人:"亻", 刀:"刂", 犬:"犭", 食:"飠", 衣:"衤", 火:"灬", 糸:"糹"},
  top: {艸:"艹", 竹:"⺮", 人:"𠆢", 爪:"爫", 网:"罒"},
  right: {刀:"刂", 阜:"阝", 邑:"阝"},
  bottom: {心:"㣺", 火:"灬"}
};
const SVG_GLYPHS = new Set(["氵", "忄", "扌", "訁", "礻", "亻", "刂", "阝", "艹", "⺮", "𠆢", "爫", "罒", "㣺", "灬", "犭", "飠", "衤", "糹", "雨"]);
const DIRECTION_NAMES = {left:"左", right:"右", top:"上", bottom:"下"};
let questions = [], current, selected = {}, usingFallback = false;
let crawlTimer, nextQuestionTimer;
const $ = id => document.getElementById(id);

try { $("openDictionary").checked = localStorage.getItem("openDictionary") !== "false"; } catch (_) {}
$("openDictionary").addEventListener("change", () => {
  try { localStorage.setItem("openDictionary", String($("openDictionary").checked)); } catch (_) {}
});

function setGameEnabled(enabled) { $("submit").disabled = $("next").disabled = !enabled; }
function radicalsFor(question) {
  return question.radicals || [{char:question.radical, position:question.position}];
}
function optionFor(char, position, form = {}) {
  const display = form.display || RADICAL_VARIANTS[position]?.[char] || char;
  return {
    char, position,
    display,
    asset: form.asset || (SVG_GLYPHS.has(display) ? `assets/radicals/u${display.codePointAt(0).toString(16)}.svg` : ""),
    rain: position === "top" && char === "雨"
  };
}
async function loadQuestions() {
  try {
    const r = await fetch("questions.json", {cache:"no-store"});
    questions = r.ok ? await r.json() : [];
  } catch (_) { questions = []; }
  if (!Array.isArray(questions) || !questions.length) {
    try {
      const fallback = await fetch("fallback_questions.json", {cache:"no-store"});
      questions = fallback.ok ? await fallback.json() : [];
    } catch (_) { questions = []; }
    usingFallback = true;
    if (!Array.isArray(questions) || !questions.length) {
      $("prompt").textContent = "題庫讀取失敗。"; $("status").textContent = "沒有可用題庫"; setGameEnabled(false); return;
    }
    $("status").textContent = "正式題庫尚未就緒，目前使用應急題庫。";
    checkCrawlStatus();
  } else {
    usingFallback = false;
  }
  setGameEnabled(true); nextQuestion();
  if (usingFallback) $("status").textContent = "正式題庫尚未就緒，目前使用應急題庫。";
}
function shuffledOptions(answer, position, answerForm) {
  const pool = RADICALS_BY_POSITION[position] || [];
  return [...new Set([answer, ...pool.filter(x => x !== answer).sort(() => Math.random() - .5).slice(0, 4)])]
    .sort(() => Math.random() - .5).map(char => optionFor(char, position, char === answer ? answerForm : {}));
}
function renderOption(button, option) {
  button.replaceChildren();
  if (!option.asset) { button.textContent = option.display; return; }
  const image = document.createElement("img");
  image.src = option.asset; image.alt = option.display; image.className = "radical-svg";
  image.addEventListener("error", () => { button.replaceChildren(option.display); }, {once:true});
  button.append(image);
}
function nextQuestion() {
  clearTimeout(nextQuestionTimer); $("submit").disabled = false;
  current = questions[Math.floor(Math.random() * questions.length)]; selected = {};
  const radicals = radicalsFor(current);
  const expected = new Map(radicals.map(part => [part.position, part]));
  const directions = radicals.map(part => `「${DIRECTION_NAMES[part.position]}」`).join("、");
  $("base").textContent = current.base;
  $("prompt").textContent = `組字方向：請在亮起的 ${directions} 方輪盤選擇偏旁。`;
  document.querySelectorAll(".wheel").forEach(wheel => {
    const part = expected.get(wheel.dataset.position);
    const active = Boolean(part);
    wheel.classList.toggle("active", active); wheel.classList.toggle("inactive", !active);
    const button = wheel.querySelector(".option");
    button.classList.remove("rain-radical", "ids-top", "ids-left", "ids-right", "ids-bottom");
    if (active) {
      wheel.options = shuffledOptions(part.char, part.position, part); wheel.index = 0;
      renderOption(button, wheel.options[0]);
      button.classList.add(`ids-${wheel.options[0].position}`); button.classList.toggle("rain-radical", wheel.options[0].rain);
      selected[part.position] = wheel.options[0].char;
    } else button.textContent = "—";
  });
  $("answerPreview").textContent = "？"; $("status").textContent = ""; $("status").className = "";
}
function moveWheel(wheel, amount) {
  wheel.index = (wheel.index + amount + wheel.options.length) % wheel.options.length;
  const option = wheel.options[wheel.index], button = wheel.querySelector(".option");
  renderOption(button, option);
  button.classList.remove("ids-top", "ids-left", "ids-right", "ids-bottom");
  button.classList.add(`ids-${option.position}`); button.classList.toggle("rain-radical", option.rain);
  selected[wheel.dataset.position] = option.char; $("answerPreview").textContent = "…";
}
document.querySelectorAll(".wheel").forEach(wheel => {
  wheel.addEventListener("wheel", e => { if (!wheel.classList.contains("active")) return; e.preventDefault(); moveWheel(wheel, e.deltaY > 0 ? 1 : -1); }, {passive:false});
  wheel.querySelector(".option").addEventListener("click", () => moveWheel(wheel, 1));
  wheel.querySelector(".option").addEventListener("keydown", e => {
    if (["ArrowDown", "ArrowRight"].includes(e.key)) { e.preventDefault(); moveWheel(wheel, 1); }
    if (["ArrowUp", "ArrowLeft"].includes(e.key)) { e.preventDefault(); moveWheel(wheel, -1); }
  });
});
$("submit").addEventListener("click", () => {
  const correct = radicalsFor(current).every(part => selected[part.position] === part.char);
  $("answerPreview").textContent = correct ? current.answer : "不對"; $("status").className = correct ? "correct" : "wrong";
  if (!correct) { $("status").textContent = "再轉轉看，找到合適的偏旁。"; return; }
  $("status").textContent = $("openDictionary").checked ? `答對了！正在開啟「${current.answer}」的辭典頁…` : `答對了！「${current.answer}」`;
  $("submit").disabled = true;
  if ($("openDictionary").checked) {
    const url = current.dictionary_url || `https://dict.revised.moe.edu.tw/search.jsp?word=${encodeURIComponent(current.answer)}`;
    setTimeout(() => window.open(url, "_blank", "noopener"), 500);
  }
  nextQuestionTimer = setTimeout(nextQuestion, 1200);
});
$("next").addEventListener("click", nextQuestion);

function showCrawlProgress(state) {
  $("crawlProgress").hidden = false; $("crawlProgressBar").value = state.progress || 0;
  $("crawlStatus").textContent = state.error ? `更新失敗：${state.error}` : state.message;
}
async function checkCrawlStatus() {
  try {
    const response = await fetch("/api/crawl-status", {cache:"no-store"}); if (!response.ok) throw new Error();
    const state = await response.json(); showCrawlProgress(state);
    if (state.running) {
      if (!crawlTimer) crawlTimer = setInterval(checkCrawlStatus, 800);
      return;
    }
    clearInterval(crawlTimer); crawlTimer = undefined; $("refreshQuestions").disabled = false;
    if (!state.error && state.progress === 100) {
      await loadQuestions(); $("crawlStatus").textContent = `${state.message} 已自動載入新題庫。`;
    } else if (usingFallback) {
      $("crawlStatus").textContent = state.error ? `正式題庫建立失敗：${state.error}` : "目前使用應急題庫。";
    }
  } catch (_) {
    clearInterval(crawlTimer); crawlTimer = undefined; $("refreshQuestions").disabled = false; $("crawlProgress").hidden = false;
    $("crawlStatus").textContent = "無法連上更新服務。請使用 python app.py 啟動遊戲。";
  }
}
$("refreshQuestions").addEventListener("click", async () => {
  const token = $("crawlToken").value.trim();
  if (!token) { $("crawlProgress").hidden = false; $("crawlStatus").textContent = "請先輸入啟動視窗顯示的更新密鑰。"; $("crawlToken").focus(); return; }
  $("refreshQuestions").disabled = true; setGameEnabled(false);
  try {
    const response = await fetch("/api/refresh-questions", {method:"POST", headers:{"X-Crawl-Token":token}}), state = await response.json();
    if (response.status === 401) { $("crawlStatus").textContent = "更新密鑰無效，請確認後再試一次。"; $("crawlToken").focus(); $("refreshQuestions").disabled = false; setGameEnabled(true); return; }
    if (!response.ok && response.status !== 409) throw new Error(); showCrawlProgress(state); if (!crawlTimer) crawlTimer = setInterval(checkCrawlStatus, 800);
  } catch (_) {
    $("refreshQuestions").disabled = false; setGameEnabled(true); $("crawlProgress").hidden = false;
    $("crawlStatus").textContent = "無法開始更新。請確認以 python app.py 啟動遊戲。";
  }
});
loadQuestions();
