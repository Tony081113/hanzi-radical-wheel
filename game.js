// 每個輪盤只使用符合該空間位置的部件，避免把「氵／礻」等左偏旁放到下方。
const RADICALS_BY_POSITION = {
  left: ["氵", "忄", "日", "言", "木", "扌", "女"],
  right: ["子", "馬", "月", "口", "力", "貝"],
  top: ["宀", "艹", "雨", "日", "竹"],
  bottom: ["口", "心", "力", "儿", "八", "子", "田"]
};
let questions = [], current, selected = {};
let crawlTimer;
let nextQuestionTimer;
const $ = id => document.getElementById(id);

function setGameEnabled(enabled) {
  $("submit").disabled = $("next").disabled = !enabled;
}

async function loadQuestions() {
  try {
    const r = await fetch("questions.json", { cache: "no-store" });
    questions = r.ok ? await r.json() : [];
  } catch (_) { questions = []; }
  if (!Array.isArray(questions) || !questions.length) {
    $("prompt").textContent = "尚無題庫。請先執行 scrape_dictionary.py，再以本機伺服器開啟遊戲。";
    $("status").textContent = "題庫讀取失敗";
    setGameEnabled(false);
    return;
  }
  setGameEnabled(true);
  nextQuestion();
}
function shuffledOptions(answer, position) {
  const pool = RADICALS_BY_POSITION[position] || [];
  const options = [...new Set([answer, ...pool.filter(x => x !== answer).sort(() => Math.random() - .5).slice(0, 4)])];
  return options.sort(() => Math.random() - .5);
}
function nextQuestion() {
  clearTimeout(nextQuestionTimer);
  $("submit").disabled = false;
  current = questions[Math.floor(Math.random() * questions.length)];
  selected = {};
  const direction = ({left:"左",right:"右",top:"上",bottom:"下"})[current.position];
  $("base").textContent = current.base; $("prompt").textContent = `組字方向：偏旁在中央部件的「${direction}」方。請轉動亮起的輪盤。`;
  document.querySelectorAll(".wheel").forEach(wheel => {
    const active = wheel.dataset.position === current.position;
    wheel.classList.toggle("active", active); wheel.classList.toggle("inactive", !active);
    if (active) { wheel.options = shuffledOptions(current.radical, current.position); wheel.index = 0; wheel.querySelector(".option").textContent = wheel.options[0]; selected[current.position] = wheel.options[0]; }
    else wheel.querySelector(".option").textContent = "—";
  });
  $("answerPreview").textContent = "？"; $("status").textContent = ""; $("status").className = "";
}
function moveWheel(wheel, amount) {
  wheel.index = (wheel.index + amount + wheel.options.length) % wheel.options.length;
  const value = wheel.options[wheel.index]; wheel.querySelector(".option").textContent = value; selected[wheel.dataset.position] = value; $("answerPreview").textContent = "…";
}
document.querySelectorAll(".wheel").forEach(wheel => {
  wheel.addEventListener("wheel", e => { if (!wheel.classList.contains("active")) return; e.preventDefault(); moveWheel(wheel, e.deltaY > 0 ? 1 : -1); }, {passive:false});
  wheel.querySelector(".option").addEventListener("click", () => moveWheel(wheel, 1));
  wheel.querySelector(".option").addEventListener("keydown", e => { if (e.key === "ArrowDown" || e.key === "ArrowRight") { e.preventDefault(); moveWheel(wheel,1); } if (e.key === "ArrowUp" || e.key === "ArrowLeft") { e.preventDefault(); moveWheel(wheel,-1); } });
});
$("submit").addEventListener("click", () => {
  const correct = selected[current.position] === current.radical;
  $("answerPreview").textContent = correct ? current.answer : "不對";
  $("status").className = correct ? "correct" : "wrong";
  if (!correct) { $("status").textContent = "再轉轉看，找到合適的偏旁。"; return; }
  $("status").textContent = `答對了！正在開啟「${current.answer}」的辭典頁…`;
  $("submit").disabled = true;
  const url = current.dictionary_url || `https://dict.revised.moe.edu.tw/search.jsp?word=${encodeURIComponent(current.answer)}`;
  setTimeout(() => window.open(url, "_blank", "noopener"), 500);
  nextQuestionTimer = setTimeout(nextQuestion, 1200);
});
$("next").addEventListener("click", nextQuestion);

function showCrawlProgress(state) {
  $("crawlProgress").hidden = false;
  $("crawlProgressBar").value = state.progress || 0;
  $("crawlStatus").textContent = state.error ? `更新失敗：${state.error}` : state.message;
}
async function checkCrawlStatus() {
  try {
    const response = await fetch("/api/crawl-status", {cache:"no-store"});
    if (!response.ok) throw new Error();
    const state = await response.json();
    showCrawlProgress(state);
    if (state.running) return;
    clearInterval(crawlTimer); crawlTimer = undefined;
    $("refreshQuestions").disabled = false;
    if (!state.error && state.progress === 100) {
      await loadQuestions();
      $("crawlStatus").textContent = `${state.message} 已自動載入新題庫。`;
    }
  } catch (_) {
    clearInterval(crawlTimer); crawlTimer = undefined;
    $("refreshQuestions").disabled = false;
    $("crawlProgress").hidden = false;
    $("crawlStatus").textContent = "無法連上更新服務。請使用 python app.py 啟動遊戲。";
  }
}
$("refreshQuestions").addEventListener("click", async () => {
  const token = $("crawlToken").value.trim();
  if (!token) {
    $("crawlProgress").hidden = false;
    $("crawlStatus").textContent = "請先輸入啟動視窗顯示的更新密鑰。";
    $("crawlToken").focus();
    return;
  }
  $("refreshQuestions").disabled = true;
  setGameEnabled(false);
  try {
    const response = await fetch("/api/refresh-questions", {method:"POST", headers:{"X-Crawl-Token":token}});
    const state = await response.json();
    if (response.status === 401) {
      $("crawlStatus").textContent = "更新密鑰無效，請確認後再試一次。";
      $("crawlToken").focus();
      $("refreshQuestions").disabled = false;
      setGameEnabled(true);
      return;
    }
    if (!response.ok && response.status !== 409) throw new Error();
    showCrawlProgress(state);
    if (!crawlTimer) crawlTimer = setInterval(checkCrawlStatus, 800);
  } catch (_) {
    $("refreshQuestions").disabled = false;
    setGameEnabled(true);
    $("crawlProgress").hidden = false;
    $("crawlStatus").textContent = "無法開始更新。請確認以 python app.py 啟動遊戲。";
  }
});
loadQuestions();
