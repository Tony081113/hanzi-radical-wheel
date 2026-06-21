// 每個輪盤只使用符合該空間位置的部件，避免把「氵／礻」等左偏旁放到下方。
const RADICALS_BY_POSITION = {
  left: ["氵", "忄", "日", "言", "木", "扌", "女"],
  right: ["子", "馬", "月", "口", "力", "貝"],
  top: ["宀", "艹", "雨", "日", "竹"],
  bottom: ["口", "心", "力", "儿", "八", "子", "田"]
};
let questions = [], current, selected = {};
const $ = id => document.getElementById(id);

async function loadQuestions() {
  try {
    const r = await fetch("questions.json", { cache: "no-store" });
    questions = r.ok ? await r.json() : [];
  } catch (_) { questions = []; }
  if (!Array.isArray(questions) || !questions.length) {
    $("prompt").textContent = "尚無題庫。請先執行 scrape_dictionary.py，再以本機伺服器開啟遊戲。";
    $("status").textContent = "題庫讀取失敗";
    $("submit").disabled = $("next").disabled = true;
    return;
  }
  nextQuestion();
}
function shuffledOptions(answer, position) {
  const pool = RADICALS_BY_POSITION[position] || [];
  const options = [...new Set([answer, ...pool.filter(x => x !== answer).sort(() => Math.random() - .5).slice(0, 4)])];
  return options.sort(() => Math.random() - .5);
}
function nextQuestion() {
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
  const url = current.dictionary_url || `https://dict.revised.moe.edu.tw/search.jsp?word=${encodeURIComponent(current.answer)}`;
  setTimeout(() => window.open(url, "_blank", "noopener"), 500);
});
$("next").addEventListener("click", nextQuestion);
loadQuestions();
