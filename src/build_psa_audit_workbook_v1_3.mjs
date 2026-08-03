import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const artifactModule = path.join(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES, "@oai/artifact-tool/dist/artifact_tool.mjs");
const { SpreadsheetFile, Workbook } = await import(artifactModule);

const bundle = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const data = JSON.parse(await fs.readFile(path.join(bundle, "workbook_data_v1.3.json"), "utf8"));
const previewDir = path.join(bundle, "workbook_previews_v1.3");
await fs.mkdir(previewDir, { recursive: true });

const workbook = Workbook.create();
const colors = {
  navy: "#153B5B",
  teal: "#0F766E",
  blue: "#2457A6",
  paleBlue: "#EAF2F8",
  paleTeal: "#E7F4F1",
  paleGold: "#FFF4D6",
  paleRed: "#FDECEC",
  green: "#1F7A4D",
  amber: "#A86612",
  red: "#B42318",
  gray: "#667085",
  border: "#D0D5DD",
  white: "#FFFFFF",
};

function colName(n) {
  let x = n + 1;
  let out = "";
  while (x > 0) {
    const r = (x - 1) % 26;
    out = String.fromCharCode(65 + r) + out;
    x = Math.floor((x - 1) / 26);
  }
  return out;
}

let tableCounter = 0;
function writeDataSheet(name, payload, options = {}) {
  const sheet = workbook.worksheets.add(name);
  const headers = payload.headers;
  const rows = payload.rows;
  const endCol = colName(headers.length - 1);
  const endRow = rows.length + 1;
  sheet.getRange(`A1:${endCol}${endRow}`).values = [headers, ...rows];
  sheet.getRange(`A1:${endCol}1`).format = {
    fill: colors.navy,
    font: { bold: true, color: colors.white, size: 10 },
    verticalAlignment: "center",
    horizontalAlignment: "center",
    wrapText: true,
    borders: { bottom: { style: "continuous", color: colors.navy, weight: 2 } },
  };
  if (rows.length > 0) {
    tableCounter += 1;
    sheet.tables.add(`A1:${endCol}${endRow}`, true, `AuditTable${tableCounter}`).style = "TableStyleMedium2";
    sheet.getRange(`A2:${endCol}${endRow}`).format = { font: { size: 9, color: "#1D2939" }, verticalAlignment: "center" };
  }
  sheet.freezePanes.freezeRows(1);
  sheet.getRange(`A1:${endCol}${endRow}`).format.autofitColumns();
  sheet.getRange(`A1:${endCol}${endRow}`).format.autofitRows();
  headers.forEach((header, idx) => {
    const h = String(header);
    let width = 14;
    if (/status|rule|source|evidence|boundary|note|method|citation|url|distribution|correlation|use/i.test(h)) width = 30;
    if (/parameter|outcome|component|scenario|metric|decision/i.test(h)) width = 22;
    if (/year|sex|choice|id$/i.test(h)) width = 12;
    sheet.getRange(`${colName(idx)}:${colName(idx)}`).format.columnWidth = width;
  });
  if (options.wrapAll && rows.length > 0) sheet.getRange(`A2:${endCol}${endRow}`).format.wrapText = true;
  return sheet;
}

const summary = workbook.worksheets.add("摘要");
summary.getRange("A1:J1").merge();
summary.getRange("A1").values = [[`${data.metadata.title} ${data.metadata.version}`]];
summary.getRange("A1:J1").format = { fill: colors.navy, font: { bold: true, color: colors.white, size: 17 }, verticalAlignment: "center" };
summary.getRange("A1:J1").format.rowHeight = 32;
summary.getRange("A2:J2").merge();
summary.getRange("A2").values = [[`GBD更新QC：${data.metadata.gbd_qc_pass}/${data.metadata.gbd_qc_total}｜确定性QC：${data.metadata.det_qc_pass}/${data.metadata.det_qc_total}｜烟雾PSA：${data.metadata.smoke_batches}批×${data.metadata.smoke_draws / data.metadata.smoke_batches}次，QC ${data.metadata.smoke_qc_pass}/${data.metadata.smoke_qc_total}｜正式10,000次PSA：待用户运行`]];
summary.getRange("A2:J2").format = { font: { color: colors.gray, italic: true, size: 10 } };

summary.getRange("A4:H4").values = [["期限", "贴现DALY均值", "2.5%", "97.5%", "政策成本均值（亿元）", "2.5%（亿元）", "97.5%（亿元）", "桥接ICER均值"]];
summary.getRange("A4:H4").format = { fill: colors.teal, font: { bold: true, color: colors.white }, horizontalAlignment: "center", wrapText: true };
[5, 10, 26].forEach((horizon, i) => {
  const r = 5 + i;
  summary.getRange(`A${r}`).values = [[horizon === 26 ? "2025—2050" : `${horizon}年`]];
  summary.getRange(`B${r}`).formulas = [[`=SUMIFS('烟雾PSA摘要'!$E$2:$E$100,'烟雾PSA摘要'!$A$2:$A$100,${horizon},'烟雾PSA摘要'!$C$2:$C$100,"discounted_dalys_averted")`]];
  summary.getRange(`C${r}`).formulas = [[`=SUMIFS('烟雾PSA摘要'!$G$2:$G$100,'烟雾PSA摘要'!$A$2:$A$100,${horizon},'烟雾PSA摘要'!$C$2:$C$100,"discounted_dalys_averted")`]];
  summary.getRange(`D${r}`).formulas = [[`=SUMIFS('烟雾PSA摘要'!$I$2:$I$100,'烟雾PSA摘要'!$A$2:$A$100,${horizon},'烟雾PSA摘要'!$C$2:$C$100,"discounted_dalys_averted")`]];
  summary.getRange(`E${r}`).formulas = [[`=SUMIFS('烟雾PSA摘要'!$E$2:$E$100,'烟雾PSA摘要'!$A$2:$A$100,${horizon},'烟雾PSA摘要'!$C$2:$C$100,"discounted_programme_cost_2025_cny")/100000000`]];
  summary.getRange(`F${r}`).formulas = [[`=SUMIFS('烟雾PSA摘要'!$G$2:$G$100,'烟雾PSA摘要'!$A$2:$A$100,${horizon},'烟雾PSA摘要'!$C$2:$C$100,"discounted_programme_cost_2025_cny")/100000000`]];
  summary.getRange(`G${r}`).formulas = [[`=SUMIFS('烟雾PSA摘要'!$I$2:$I$100,'烟雾PSA摘要'!$A$2:$A$100,${horizon},'烟雾PSA摘要'!$C$2:$C$100,"discounted_programme_cost_2025_cny")/100000000`]];
  summary.getRange(`H${r}`).formulas = [[`=SUMIFS('烟雾PSA摘要'!$E$2:$E$100,'烟雾PSA摘要'!$A$2:$A$100,${horizon},'烟雾PSA摘要'!$C$2:$C$100,"programme_only_icer_cny_per_daly")`]];
});
summary.getRange("A5:H7").format = { fill: colors.paleTeal, font: { size: 10 }, borders: { bottom: { style: "continuous", color: colors.border, weight: 1 } } };
summary.getRange("B5:D7").format.numberFormat = "#,##0";
summary.getRange("E5:G7").format.numberFormat = "#,##0.00";
summary.getRange("H5:H7").format.numberFormat = "#,##0";

summary.getRange("A9:H9").merge();
summary.getRange("A9").values = [["封库状态与报告边界"]];
summary.getRange("A9:H9").format = { fill: colors.paleGold, font: { bold: true, color: colors.amber } };
summary.getRange("A10:H16").values = [
  ["GBD", `3个ZIP共${data.metadata.gbd_new_rows.toLocaleString("zh-CN")}条；与父库2018—2023拼接为连续的2010—2023历史序列`, null, null, null, null, null, "LOCKED"],
  ["D3", "主分析使用2010—2023趋势并在2035—2040衰减；近期趋势、2023年率固定和持续外推为结构敏感性", null, null, null, null, null, "READY"],
  ["D4", `${data.metadata.d4_available}/${data.metadata.d4_total}个结局有首年费用或显式代理；缺失项不用患者年费用填充`, null, null, null, null, null, "PARTIAL"],
  ["D5", `全国桥接均值${(data.metadata.d5_mean * 100).toFixed(1)}%，宽分布约${(data.metadata.d5_low * 100).toFixed(1)}%—${(data.metadata.d5_high * 100).toFixed(1)}%；非病种特异`, null, null, null, null, null, "INTERIM"],
  ["D9", "5年和10年成本可进入正式PSA；26年长期成本仍为结构敏感性", null, null, null, null, null, "PARTIAL"],
  ["烟雾PSA", "2×100次仅验证引擎、批次、区间和CEAC/CEAF生成；不得作为论文概率结果", null, null, null, null, null, "PASS"],
  ["正式PSA", "输入封库与运行包已就绪；运行20批×500次后才生成论文概率结果", null, null, null, null, null, "READY"],
];
[10, 11, 12, 13, 14, 15, 16].forEach((r) => summary.getRange(`B${r}:G${r}`).merge());
summary.getRange("A10:H16").format = { wrapText: true, font: { size: 10 }, verticalAlignment: "center" };
summary.getRange("A10:A16").format.font = { bold: true, color: colors.navy };
summary.getRange("H10:H16").format = { fill: colors.paleGold, font: { bold: true, color: colors.amber }, horizontalAlignment: "center" };
[10, 11, 15, 16].forEach((r) => summary.getRange(`H${r}`).format = { fill: colors.paleTeal, font: { bold: true, color: colors.green }, horizontalAlignment: "center" });

summary.getRange("A19:B19").values = [["政策", "10年、10万元/DALY下成为最佳NMB的概率"]];
summary.getRange("A19:B19").format = { fill: colors.teal, font: { bold: true, color: colors.white }, wrapText: true };
for (let i = 0; i < 7; i++) {
  const r = 20 + i;
  summary.getRange(`A${r}`).values = [[`S${i}`]];
  summary.getRange(`B${r}`).formulas = [[`=SUMIFS('CEAC'!$E$2:$E$500,'CEAC'!$A$2:$A$500,10,'CEAC'!$B$2:$B$500,"PROGRAMME_ONLY",'CEAC'!$C$2:$C$500,100000,'CEAC'!$D$2:$D$500,A${r})`]];
}
summary.getRange("B20:B26").format.numberFormat = "0.0%";
const ceacChart = summary.charts.add("bar", summary.getRange("A19:B26"));
ceacChart.title = "10年CEAC烟雾测试校验（非正式结果）";
ceacChart.hasLegend = false;
ceacChart.yAxis = { numberFormatCode: "0%" };
ceacChart.setPosition("D19", "J33");

summary.freezePanes.freezeRows(2);
summary.getRange("A:A").format.columnWidth = 18;
summary.getRange("B:D").format.columnWidth = 18;
summary.getRange("E:H").format.columnWidth = 20;
summary.getRange("A10:H16").format.rowHeight = 34;

const gbdSummary = writeDataSheet("GBD更新摘要", data.gbd_summary, { wrapAll: true });
gbdSummary.getRange("A:B").format.columnWidth = 35;
const gbdQc = writeDataSheet("GBD更新QC", data.gbd_qc, { wrapAll: true });
gbdQc.getRange(`B2:B${data.gbd_qc.rows.length + 1}`).conditionalFormats.addCustom("=B2=FALSE", { fill: colors.paleRed, font: { bold: true, color: colors.red } });
gbdQc.getRange(`B2:B${data.gbd_qc.rows.length + 1}`).conditionalFormats.addCustom("=B2=TRUE", { fill: colors.paleTeal, font: { bold: true, color: colors.green } });
const detQc = writeDataSheet("确定性QC", data.det_qc, { wrapAll: true });
detQc.getRange(`B2:B${data.det_qc.rows.length + 1}`).conditionalFormats.addCustom("=B2=FALSE", { fill: colors.paleRed, font: { bold: true, color: colors.red } });
detQc.getRange(`B2:B${data.det_qc.rows.length + 1}`).conditionalFormats.addCustom("=B2=TRUE", { fill: colors.paleTeal, font: { bold: true, color: colors.green } });
const d3 = writeDataSheet("D3趋势敏感性", data.d3_structural, { wrapAll: true });
if (data.d3_structural.rows.length > 0) {
  const d3End = data.d3_structural.rows.length + 1;
  d3.getRange(`C2:D${d3End}`).format.numberFormat = "0";
  d3.getRange(`G2:Q${d3End}`).format.numberFormat = "#,##0.00";
}
const comparison = writeDataSheet("新旧结果对照", data.comparison, { wrapAll: true });
if (data.comparison.rows.length > 0) comparison.getRange(`E2:E${data.comparison.rows.length + 1}`).format.numberFormat = "0.0%";
writeDataSheet("D1-D10状态", data.methods, { wrapAll: true });
writeDataSheet("PSA参数注册", data.registry, { wrapAll: true });
const d4 = writeDataSheet("D4首年费用", data.d4, { wrapAll: true });
d4.getRange("C2:C20").format.numberFormat = "#,##0";
d4.getRange("D2:D20").format.numberFormat = "0.00";
const d5 = writeDataSheet("D5支付比例", data.d5, { wrapAll: true });
d5.getRange("B2:G3").format.numberFormat = "0.0%";
writeDataSheet("D9长期规则", data.d9, { wrapAll: true });
const policy = writeDataSheet("政策效果参数", data.policy, { wrapAll: true });
policy.getRange("D2:J20").format.numberFormat = "0.000";
const rr = writeDataSheet("RR参数", data.rr, { wrapAll: true });
rr.getRange("D2:I30").format.numberFormat = "0.000";
const pcost = writeDataSheet("政策成本参数", data.cost, { wrapAll: true });
pcost.getRange("D2:J20").format.numberFormat = "0.000";
const smoke = writeDataSheet("烟雾PSA摘要", data.smoke_summary, { wrapAll: true });
smoke.getRange("E2:I100").format.numberFormat = "#,##0.00";
const ceac = writeDataSheet("CEAC", data.ceac, { wrapAll: true });
ceac.getRange("E2:E500").format.numberFormat = "0.0%";
ceac.getRange("F2:F500").format.numberFormat = "#,##0";
const ceaf = writeDataSheet("CEAF", data.ceaf, { wrapAll: true });
ceaf.getRange("E2:E100").format.numberFormat = "0.0%";
ceaf.getRange("F2:F100").format.numberFormat = "#,##0";
const stability = writeDataSheet("批次稳定性", data.stability, { wrapAll: true });
stability.getRange("G2:G100").format.numberFormat = "0.0%";
const recon = writeDataSheet("确定性衔接", data.recon, { wrapAll: true });
recon.getRange("F2:G100").format.numberFormat = "0.0%";
const conv = writeDataSheet("收敛检查", data.convergence, { wrapAll: true });
conv.getRange("H2:H100").format.numberFormat = "0.0%";
const qc = writeDataSheet("QC", data.qc, { wrapAll: true });
qc.getRange(`B2:B${data.qc.rows.length + 1}`).conditionalFormats.addCustom("=B2=\"FAIL\"", { fill: colors.paleRed, font: { bold: true, color: colors.red } });
qc.getRange(`B2:B${data.qc.rows.length + 1}`).conditionalFormats.addCustom("=B2=\"PASS\"", { fill: colors.paleTeal, font: { bold: true, color: colors.green } });
writeDataSheet("来源", data.sources, { wrapAll: true });

for (const sheet of workbook.worksheets.items) {
  const used = sheet.getUsedRange();
  if (used) used.format.font.name = "Microsoft YaHei";
  const preview = await workbook.render({ sheetName: sheet.name, autoCrop: "all", scale: 0.7, format: "png" });
  const safe = sheet.name.replace(/[\\/:*?"<>|]/g, "_");
  await fs.writeFile(path.join(previewDir, `${safe}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const inspectSummary = await workbook.inspect({ kind: "table", range: "摘要!A1:H16", include: "values,formulas", tableMaxRows: 20, tableMaxCols: 10 });
const inspectErrors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "formula error scan" });
await fs.writeFile(path.join(previewDir, "inspect_summary.ndjson"), inspectSummary.ndjson, "utf8");
await fs.writeFile(path.join(previewDir, "formula_errors.ndjson"), inspectErrors.ndjson, "utf8");

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(path.join(bundle, "ALLdis_GBD2010_2023更新与正式PSA候选审计_v1.3.xlsx"));
