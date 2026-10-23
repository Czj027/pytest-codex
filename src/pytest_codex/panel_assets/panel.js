"use strict";
const $ = id => document.getElementById(id);
let token = location.hash.slice(1) || sessionStorage.getItem("pytest-codex-panel-token") || "";
if (token) { sessionStorage.setItem("pytest-codex-panel-token", token); history.replaceState(null, "", location.pathname); }
let state = null;
let selected = null;
const fmt = value => value === null || value === undefined ? "—" : Number(value).toLocaleString("zh-CN");
function el(tag, text, cls) { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; }
function pill(text, cls) { return el("span", text, "pill " + cls); }
function showError(text) { $("alert").textContent = text; $("alert").hidden = !text; }
async function api(path, data) {
  const headers = {"X-Panel-Token": token};
  const options = {headers, cache: "no-store", credentials: "omit"};
  if (data !== undefined) { options.method = "POST"; headers["Content-Type"] = "application/json"; options.body = JSON.stringify(data); }
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "本地请求失败");
  return result;
}
function stat(label, value, caption) { const n = el("div", undefined, "stat"); n.append(el("div", label, "label"), el("div", value, "value"), el("div", caption, "caption")); return n; }
function checkLabel(task) { return task.check.status === "fail" ? "命中禁令" : task.check.status === "pass" ? "已配置命令通过" : "未知"; }
function render(data) {
  state = data;
  const tasks = data.tasks;
  const known = tasks.filter(t => t.usage !== null);
  const sum = field => known.reduce((total, t) => total + t.usage[field], 0);
  $("summary").replaceChildren(stat("已载入任务", fmt(tasks.length), "当前指定项目 · " + data.matching_sessions + " 个会话"), stat("禁令命中任务", fmt(tasks.filter(t => t.check.status === "fail").length), "仅检查已配置的命令 / 路径模式"), stat("输入 Token · 含缓存", known.length ? fmt(sum("input")) : "—", known.length + "/" + tasks.length + " 项用量已知 · 非费用账单"), stat("缓存 / 非缓存输入", known.length ? fmt(sum("cached")) + " / " + fmt(sum("uncached")) : "—", "未知用量不作为零消耗"));
  $("project").textContent = data.project;
  $("scan-info").textContent = "检查了 " + data.scanned + " 个近期日志的元数据，仅加载本项目。" + (data.task_limited ? "已按时间截取最近任务。" : "");
  const warnings = data.errors.map(e => e.reason);
  if (data.scan_limited) warnings.push("已达到最近 500 个日志的扫描上限，较早会话可能未加载。");
  if (data.agents.truncated) warnings.push("AGENTS.md 展示已截断，候选规则可能不完整。");
  showError(warnings.join("\n"));
  $("agents-text").textContent = data.agents.text || "未找到可安全读取的本项目 AGENTS.md。";
  $("suggest").disabled = !data.suggestions.commands.length && !data.suggestions.files.length;
  $("suggest-note").textContent = "候选命令 " + data.suggestions.commands.length + " 条 / 路径 " + data.suggestions.files.length + " 条；请核对后点击应用。";
  $("tasks").replaceChildren();
  for (const task of tasks) {
    const row = el("tr");
    const title = el("td"); const button = el("button", "任务 " + task.turn_id.slice(0, 10), "task-button");
    button.addEventListener("click", () => detail(task.id));
    title.append(button, el("span", task.started_at ? new Date(task.started_at).toLocaleString("zh-CN", {hour12:false}) : "时间未知 · 按日志更新时间排序", "subtext"));
    const status = el("td"); status.append(pill(({completed:"已完成",aborted:"已中断",incomplete:"未完成"})[task.status] || "未知", task.status === "completed" ? "neutral" : "unknown"));
    const checks = el("td"); checks.append(pill(checkLabel(task), task.check.status));
    if (!task.commands_complete) checks.append(el("span", "命令覆盖不完整", "subtext"));
    const counts = el("td", task.commands.length + " / " + task.files.length); counts.append(el("span", "文件仅为日志报告", "subtext"));
    const usage = el("td", task.usage ? [task.usage.cached,task.usage.uncached,task.usage.output].map(fmt).join(" / ") : "—");
    row.append(title,status,checks,counts,usage); $("tasks").append(row);
  }
  $("empty").hidden = !!tasks.length;
  $("rule-note").textContent = data.rules.commands.length || data.rules.files.length ? "当前检查 " + data.rules.commands.length + " 条命令规则、" + data.rules.files.length + " 条路径规则，仅本次内存有效。" : "尚未配置规则。规则只保留在本次面板内存中。";
  if (selected) detail(selected, false);
}
function detail(id, scroll=true) {
  selected = id; const task = state.tasks.find(t => t.id === id); if (!task) { $("detail").hidden = true; return; }
  $("detail").hidden = false; $("detail-title").textContent = "任务详情 · " + task.turn_id;
  const body = el("div", undefined, "detail-grid"), left = el("div"), right = el("div");
  left.append(el("h3", "观察到的命令"));
  for (const c of task.commands) left.append(el("pre", "[退出码 " + (c.exit_code ?? "未知") + "] " + c.command));
  if (!task.commands.length) left.append(el("p", "没有观察到命令。请结合覆盖范围判断。", "muted"));
  right.append(el("h3", "规则检查"), pill(checkLabel(task),task.check.status), el("p", task.check.reason, "muted small"));
  for (const hit of task.check.hits) right.append(el("pre", (hit.kind === "reported_file" ? "文件报告命中" : "命令命中") + "：" + hit.rule + "\n" + hit.value, "hit"));
  right.append(el("h3", "文件改动报告（未核对快照）"), el("pre", task.files.join("\n") || "无文件报告；不代表没有文件变化"));
  right.append(el("h3", "MCP 调用"), el("pre", task.mcp.map(m => m.server + "." + m.tool + " · " + m.status).join("\n") || "没有可显示的 MCP 调用"));
  if (task.display_limited) right.append(el("p", "界面已限制为 100 条命令、每条 2,000 字、500 个路径和 100 个 MCP 调用；未命中不能据此判为通过。", "muted small"));
  if (task.unsupported_items.length) right.append(el("h3", "不完整的观察范围"), el("pre", task.unsupported_items.join("\n")));
  body.append(left,right); $("detail-body").replaceChildren(body); if (scroll) $("detail").scrollIntoView({behavior:"smooth",block:"nearest"});
}
async function busy(button, action) { button.disabled = true; try { await action(); } catch (error) { showError(error.message || "无法读取本地数据"); } finally { button.disabled = false; } }
function tab(compare) { $("recent-view").hidden = compare; $("compare-view").hidden = !compare; for (const [id, active] of [["recent-tab",!compare],["compare-tab",compare]]) { $(id).classList.toggle("selected",active); $(id).setAttribute("aria-selected",String(active)); } }
$("recent-tab").addEventListener("click", () => tab(false));
$("compare-tab").addEventListener("click", () => tab(true));
$("refresh").addEventListener("click", () => busy($("refresh"), async () => render(await api("/api/refresh", {}))));
$("rule-form").addEventListener("submit", event => { event.preventDefault(); const button = event.submitter; busy(button, async () => { const lines = id => $(id).value.split(/\r?\n/).map(s=>s.trim()).filter(Boolean); render(await api("/api/rules", {commands:lines("command-rules"),files:lines("file-rules")})); }); });
$("suggest").addEventListener("click", () => { $("command-rules").value = state.suggestions.commands.join("\n"); $("file-rules").value = state.suggestions.files.join("\n"); $("rule-note").textContent = "候选已填入，尚未应用。请核对适用条件后点击应用并检查。"; });
$("close-detail").addEventListener("click", () => { selected = null; $("detail").hidden = true; });
function score(value) { return value.passed + "/" + value.completed + (value.rate === null ? " · —" : " · " + (100*value.rate).toFixed(1) + "%"); }
function renderCompare(result) {
  const card = el("section",undefined,"card compare-result"), heading = el("div",undefined,"card-heading");
  heading.append(el("h2", "匹配结果"), pill("小样本观察 · 不作模型排名","neutral")); card.append(heading);
  const wrapper=el("div",undefined,"table-wrap"), table=el("table"), head=el("thead"), hr=el("tr");
  for (const text of ["测试任务","基线通过","候选通过","错误 / 跳过（基线→候选）","观察"]) hr.append(el("th",text)); head.append(hr); table.append(head); const body=el("tbody");
  for (const row of result.cases) { const tr=el("tr"); const direction={inconclusive:"无法判定",observed_increase:"观察到上升",observed_decrease:"观察到下降",unchanged:"无变化"}; tr.append(el("td",row.case),el("td",score(row.baseline)),el("td",score(row.candidate)),el("td",(row.baseline.error+row.baseline.skipped)+" → "+(row.candidate.error+row.candidate.skipped))); const td=el("td"); td.append(pill(direction[row.direction],row.direction==="inconclusive"?"unknown":row.direction==="observed_decrease"?"fail":"neutral")); tr.append(td); body.append(tr); }
  table.append(body);wrapper.append(table);card.append(wrapper);
  for (const [index,label] of ["baseline","candidate"].entries()) { const u=result.usage[label],c=result.cohorts[index]; card.append(el("p",(index?"候选":"基线")+" · "+c.model+" / CLI "+c.cli+" · 缓存 "+fmt(u.cached_input_tokens)+" / 非缓存 "+fmt(u.input_tokens-u.cached_input_tokens)+" / 输出 "+fmt(u.output_tokens),"footnote")); }
  card.append(el("p","有执行错误或跳过时保持无法判定。通过率分母仅为完成尝试，用量不是 API 费用账单。","footnote")); $("comparison").replaceChildren(card);
}
$("compare-form").addEventListener("submit", event => { event.preventDefault(); busy(event.submitter, async () => { const a=$("baseline-file").files[0],b=$("candidate-file").files[0]; if (!a || !b) throw new Error("请选择两份结果 JSON"); if (a.size+b.size > 4*1024*1024-1024) throw new Error("两份结果总大小需小于 4 MiB"); const result=await api("/api/compare",{baseline:JSON.parse(await a.text()),candidate:JSON.parse(await b.text()),factor:$("factor").value}); showError("");renderCompare(result); }); });
api("/api/state").then(render).catch(error => showError(error.message));
