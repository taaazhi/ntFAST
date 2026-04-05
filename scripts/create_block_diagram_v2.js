const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, WidthType, BorderStyle, ShadingType, VerticalAlign,
  TableLayoutType, PageOrientation, Footer, PageNumber, NumberFormat } = require('docx');
const fs = require('fs');

const F = "Times New Roman";
const SZ = 22;
const SZ_SM = 18;
const SZ_XS = 16;
const SZ_TITLE = 28;
const SZ_SUBTITLE = 24;

const ML = 851, MR = 851, MT = 851, MB = 851;
const PW = 16838, PH = 11906;
const CW = PW - ML - MR;

const thin = { style: BorderStyle.SINGLE, size: 1, color: "000000" };
const thick = { style: BorderStyle.SINGLE, size: 3, color: "000000" };
const dashed = { style: BorderStyle.DASHED, size: 1, color: "666666" };
const borders = { top: thin, bottom: thin, left: thin, right: thin };
const thickBorders = { top: thick, bottom: thick, left: thick, right: thick };
const dashedBorders = { top: dashed, bottom: dashed, left: dashed, right: dashed };
const noBorder = { style: BorderStyle.NONE, size: 0 };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

const mkCell = (texts, opts = {}) => new TableCell({
  borders: opts.thick ? thickBorders : (opts.dashed ? dashedBorders : (opts.noBorders ? noBorders : borders)),
  width: opts.w ? { size: opts.w, type: WidthType.DXA } : undefined,
  columnSpan: opts.cs || 1,
  rowSpan: opts.rs || 1,
  verticalAlign: VerticalAlign.CENTER,
  shading: opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR } : undefined,
  margins: { top: 25, bottom: 25, left: 50, right: 50 },
  children: (Array.isArray(texts) ? texts : [texts]).map(t =>
    typeof t === 'object' && t.type === 'Paragraph' ? t :
    new Paragraph({
      spacing: { after: 0, before: 0, line: opts.line || 210 },
      alignment: opts.align || AlignmentType.CENTER,
      children: [new TextRun({
        text: typeof t === 'string' ? t : '', font: F,
        size: opts.sz || SZ, bold: opts.bold || false, italics: opts.italic || false,
        color: opts.color || "000000"
      })]
    })
  )
});

const arrowCell = (text, opts = {}) => mkCell(text || "▼", { ...opts, noBorders: true, sz: opts.sz || 26, bold: true });
const emptyNB = (opts = {}) => mkCell("", { ...opts, noBorders: true });
const spacer = (h = 60) => new Paragraph({ spacing: { after: h, before: 0, line: 240 }, children: [] });

const title = (text) => new Paragraph({
  spacing: { after: 100, before: 0, line: 240 },
  alignment: AlignmentType.CENTER,
  children: [new TextRun({ text, font: F, size: SZ_TITLE, bold: true })]
});

const subtitle = (text) => new Paragraph({
  spacing: { after: 60, before: 60, line: 240 },
  alignment: AlignmentType.CENTER,
  children: [new TextRun({ text, font: F, size: SZ_SM, italics: true, color: "555555" })]
});

const COL5 = Math.floor(CW / 5);
const COL4 = Math.floor(CW / 4);
const COL3 = Math.floor(CW / 3);
const COL2 = Math.floor(CW / 2);

const pageProps = {
  page: {
    size: { width: PW, height: PH, orientation: PageOrientation.LANDSCAPE },
    margin: { top: MT, right: MR, bottom: MB, left: ML }
  }
};

// ═══════════════════════════════════════════════════════════════════
// PAGE 1: ЖАЛПЫ ЖҮЙЕ АРХИТЕКТУРАСЫ (Overall System Architecture)
// ═══════════════════════════════════════════════════════════════════
const page1 = [
  title("Сурет 1 — ntFAST жүйесінің жалпы архитектурасы"),
  subtitle("Қаржылық транзакцияларды талдау жүйесі — Financial Analysis System for Transactions"),

  // TOP: External sources
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [COL5, COL5, COL5, COL5, COL5],
    rows: [
      new TableRow({ children: [
        mkCell("СЫРТҚЫ ДЕРЕКТЕР КӨЗДЕРІ (Қаржылық ұйымдар)", { cs: 5, fill: "1B5E20", bold: true, sz: SZ_SM, color: "FFFFFF", thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell(["Екінші деңгейдегі", "банктер (22)", "Kaspi, Halyk, Forte,", "Jusan, BCC, Bereke"], { fill: "C8E6C9", sz: SZ_XS }),
        mkCell(["Төлем жүйелері", "және процессинг", "Visa, Mastercard,", "SWIFT, KASPPI"], { fill: "C8E6C9", sz: SZ_XS }),
        mkCell(["Электрондық ақша", "операторлары", "Wooppay, QIWI,", "Kaspi Gold"], { fill: "C8E6C9", sz: SZ_XS }),
        mkCell(["Микроқаржы", "ұйымдары (189)", "Несие серіктестіктері", "Ломбардтар"], { fill: "C8E6C9", sz: SZ_XS }),
        mkCell(["Валюта айырбастау", "бюросы (2500+)", "Криптобиржалар", "(Binance, Bybit)"], { fill: "C8E6C9", sz: SZ_XS }),
      ]}),
    ]
  }),

  new Table({
    width: { size: CW, type: WidthType.DXA }, layout: TableLayoutType.FIXED,
    columnWidths: [CW],
    rows: [new TableRow({ children: [arrowCell("▼  PDF / XLSX / CSV / JSON / API  ▼", { sz: 20 })] })]
  }),

  // ntFAST CORE SYSTEM - 3 layers
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW * 0.25), Math.floor(CW * 0.50), Math.floor(CW * 0.25)],
    rows: [
      new TableRow({ children: [
        mkCell("ntFAST ЖҮЙЕСІ — НЕГІЗГІ ЯДРО", { cs: 3, fill: "0D47A1", bold: true, sz: SZ_SUBTITLE, color: "FFFFFF", thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell([
          "КІРУ ҚАБАТЫ",
          "━━━━━━━━━━",
          "FastAPI REST API",
          "JWT аутентификация",
          "Pydantic валидация",
          "Rate Limiting",
          "CORS қауіпсіздік",
          "WebSocket (real-time)",
        ], { fill: "BBDEFB", sz: SZ_XS, thick: true }),
        mkCell([
          "ТАЛДАУ ЯДРОСЫ — FraudEngine v4",
          "━━━━━━━━━━━━━━━━━━━━━━━━━",
          "11 мамандандырылған модуль:",
          "Velocity | Amount | Geo | Time | Beneficiary",
          "Structuring | Behavioral | Night | Duplicate | Round | Pattern",
          "ML Ensemble: XGBoost + Random Forest + Logistic Regression",
          "Контекст мультипликаторлар: қызметкер / фрилансер / трейдер / бизнес",
          "Композиттік тәуекел бағалау: 0–100 балл",
        ], { fill: "FFF3E0", sz: SZ_XS, thick: true, bold: true }),
        mkCell([
          "ШЫҒУ ҚАБАТЫ",
          "━━━━━━━━━━",
          "Dashboard (KPI)",
          "Графиктер (Chart.js)",
          "PDF есептер",
          "CSV экспорт",
          "Email хабарлама",
          "Claude AI талдау",
        ], { fill: "E1BEE7", sz: SZ_XS, thick: true }),
      ]}),
    ]
  }),

  new Table({
    width: { size: CW, type: WidthType.DXA }, layout: TableLayoutType.FIXED,
    columnWidths: [COL3, COL3, COL3],
    rows: [new TableRow({ children: [
      arrowCell("▼", { sz: 22 }),
      arrowCell("▼  PostgreSQL + Redis  ▼", { sz: 20 }),
      arrowCell("▼", { sz: 22 }),
    ]})]
  }),

  // BOTTOM: Government + DB + Compliance
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW * 0.30), Math.floor(CW * 0.40), Math.floor(CW * 0.30)],
    rows: [
      new TableRow({ children: [
        mkCell([
          "МЕМЛЕКЕТТІК ОРГАНДАР",
          "━━━━━━━━━━━━━━━━━",
          "ҚМА — Күдікті транзакция",
          "хабарламалары (STR/CTR)",
          "ҰБ РК — Нормативтік есеп",
          "ІІМ — Алаяқтық тергеу",
          "Салық комитеті — Салық",
          "жүктемелерін тексеру",
        ], { fill: "BBDEFB", sz: SZ_XS, thick: true }),
        mkCell([
          "ДЕРЕКТЕР ҚОЙМАСЫ",
          "━━━━━━━━━━━━━━━━━━━",
          "PostgreSQL 15: Транзакциялар, Талдаулар,",
          "Субъектілер, Пайдаланушылар, Аудит журналы",
          "Redis 7: Кэш, хабарлама кезегі, сессиялар",
          "SQLite (dev mode): жергілікті әзірлеу",
        ], { fill: "F3E5F5", sz: SZ_XS, thick: true }),
        mkCell([
          "НОРМАТИВТІК БАЗА",
          "━━━━━━━━━━━━━━━━",
          "ҚР ПОД/ФТ Заңы №191-IV",
          "ҰБ Қаулысы №28",
          "ФАТФ 40 ұсынысы",
          "АЕК шекті мәні: 1000 АЕК",
          "ЕО/БҰҰ санкция тізімдері",
          "«Цифрлы Қазақстан» б/б",
        ], { fill: "E8EAF6", sz: SZ_XS, thick: true }),
      ]}),
    ]
  }),
];

// ═══════════════════════════════════════════════════════════════════
// PAGE 2: МЕМЛЕКЕТТІК ҚҰРЫЛЫМДАРМЕН БАЙЛАНЫС (Government Integration)
// ═══════════════════════════════════════════════════════════════════
const page2 = [
  title("Сурет 2 — Мемлекеттік құрылымдармен өзара байланыс схемасы"),
  subtitle("ntFAST жүйесі мен ҚР мемлекеттік органдары арасындағы деректер ағыны"),

  // Central ntFAST system
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW * 0.28), Math.floor(CW * 0.04), Math.floor(CW * 0.36), Math.floor(CW * 0.04), Math.floor(CW * 0.28)],
    rows: [
      // Row 1: ҚМА ← ntFAST → ҰБ РК
      new TableRow({ children: [
        mkCell([
          "ҚР ҚАРЖЫЛЫҚ МОНИТОРИНГ",
          "АГЕНТТІГІ (ҚМА / АФМ)",
          "━━━━━━━━━━━━━━━━━━━━",
          "Қабылдайтын деректер:",
          "• STR — күдікті транзакция",
          "  хабарламалары",
          "• CTR — ақшалай транзакция",
          "  есептері (1000+ АЕК)",
          "• Алаяқтық заңдылықтарды",
          "  талдау нәтижелері",
          "• Ай сайынғы жиынтық есеп",
          "",
          "Формат: XML/JSON (ISO 20022)",
        ], { fill: "E3F2FD", sz: SZ_XS, thick: true, align: AlignmentType.LEFT }),
        arrowCell("←", { sz: 26 }),
        mkCell([
          "ntFAST",
          "ЖҮЙЕСІ",
          "━━━━━━━━━━━━━━━",
          "Орталық талдау платформасы",
          "",
          "Автоматты:",
          "• Күдікті транзакцияларды",
          "  анықтау және жіктеу",
          "• Тәуекел бағалау (0-100)",
          "• Есеп қалыптастыру",
          "• Хабарлама жіберу",
          "",
          "11 модуль + ML ансамбль",
        ], { fill: "FFF8E1", sz: SZ_XS, thick: true, bold: true }),
        arrowCell("→", { sz: 26 }),
        mkCell([
          "ҚР ҰЛТТЫҚ БАНКІ",
          "(ҰБ РК / НБ РК)",
          "━━━━━━━━━━━━━━━━",
          "Қабылдайтын деректер:",
          "• Нормативтік сәйкестік",
          "  есебі (ПОД/ФТ)",
          "• Қаржы ұйымдарының",
          "  тәуекел профилі",
          "• Статистикалық деректер",
          "• Ішкі бақылау нәтижелері",
          "",
          "Формат: Электрондық есеп",
        ], { fill: "E8F5E9", sz: SZ_XS, thick: true, align: AlignmentType.LEFT }),
      ]}),
    ]
  }),

  // Arrows down
  new Table({
    width: { size: CW, type: WidthType.DXA }, layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW * 0.28), Math.floor(CW * 0.04), Math.floor(CW * 0.36), Math.floor(CW * 0.04), Math.floor(CW * 0.28)],
    rows: [new TableRow({ children: [
      emptyNB(), emptyNB(), arrowCell("▼", { sz: 22 }), emptyNB(), emptyNB(),
    ]})]
  }),

  // Row 2: ІІМ ← ntFAST → Салық + Прокуратура
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW * 0.28), Math.floor(CW * 0.04), Math.floor(CW * 0.36), Math.floor(CW * 0.04), Math.floor(CW * 0.28)],
    rows: [
      new TableRow({ children: [
        mkCell([
          "ҚР ІШКІ ІСТЕР",
          "МИНИСТРЛІГІ (ІІМ / МВД)",
          "━━━━━━━━━━━━━━━━━━",
          "Қабылдайтын деректер:",
          "• Алаяқтық фактілері бойынша",
          "  автоматты хабарлама",
          "• Транзакция тізбектерінің",
          "  граф-талдау нәтижелері",
          "• Күдікті субъектілер тізімі",
          "• Цифрлық дәлелдемелер",
          "",
          "Байланыс: API / Жедел хабарлама",
        ], { fill: "FCE4EC", sz: SZ_XS, thick: true, align: AlignmentType.LEFT }),
        arrowCell("←", { sz: 26 }),
        mkCell([
          "ПАЙДАЛАНУШЫЛАР",
          "ИНТЕРФЕЙСІ",
          "━━━━━━━━━━━━━━━━",
          "Комплаенс-офицерлер:",
          "• Бақылау тақтасы (Dashboard)",
          "• Талдау нәтижелерін қарау",
          "• Есеп қалыптастыру (PDF)",
          "• CSV/Excel экспорт",
          "• Субъект профильдерін басқару",
          "",
          "3 тіл: қазақша, орысша, ағылшын",
          "Dark/Light режим",
        ], { fill: "FFF8E1", sz: SZ_XS, thick: true }),
        arrowCell("→", { sz: 26 }),
        mkCell([
          "САЛЫҚ КОМИТЕТІ (МҚМ)",
          "+ ҚР ПРОКУРАТУРАСЫ",
          "━━━━━━━━━━━━━━━━━━",
          "Қабылдайтын деректер:",
          "МҚМ:",
          "• Салық жүктемесінен ауытқу",
          "• Жасанды шығындар талдауы",
          "• Кіріс-шығыс сәйкессіздігі",
          "Прокуратура:",
          "• Ірі алаяқтық схемалар",
          "• Ұйымдасқан қылмыс белгілері",
          "• Тергеуге дәлелдер пакеті",
        ], { fill: "F3E5F5", sz: SZ_XS, thick: true, align: AlignmentType.LEFT }),
      ]}),
    ]
  }),

  spacer(80),

  // Feedback/interaction diagram
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [COL4, COL4, COL4, COL4],
    rows: [
      new TableRow({ children: [
        mkCell("МЕМЛЕКЕТТІК ОРГАНДАРДАН КЕРІ БАЙЛАНЫС", { cs: 4, fill: "1565C0", bold: true, sz: SZ_SM, color: "FFFFFF", thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell(["ҚМА → ntFAST:", "Санкциялар тізімі", "жаңартулары, жаңа", "типология схемалары"], { fill: "E3F2FD", sz: SZ_XS }),
        mkCell(["ҰБ РК → ntFAST:", "Нормативтік талаптар", "өзгерістері, АЕК", "шекті мәні жаңарту"], { fill: "E8F5E9", sz: SZ_XS }),
        mkCell(["ІІМ → ntFAST:", "Расталған алаяқтық", "оқиғалары (ML модельді", "жаттықтыру үшін)"], { fill: "FCE4EC", sz: SZ_XS }),
        mkCell(["Халықаралық:", "ФАТФ жаңартулары,", "Egmont Group,", "ЕО/БҰҰ санкциялар"], { fill: "E8EAF6", sz: SZ_XS }),
      ]}),
    ]
  }),
];

// ═══════════════════════════════════════════════════════════════════
// PAGE 3: 11 МОДУЛЬДІҢ ТОЛЫҚ СИПАТТАМАСЫ (Fraud Detection Modules)
// ═══════════════════════════════════════════════════════════════════
const page3 = [
  title("Сурет 3 — FraudEngine v4: 11 талдау модулінің блок-схемасы"),
  subtitle("Әрбір модульдің кіру деректері, алгоритмдері және шығу нәтижелері"),

  // Input
  new Table({
    width: { size: CW, type: WidthType.DXA }, layout: TableLayoutType.FIXED,
    columnWidths: [CW],
    rows: [
      new TableRow({ children: [
        mkCell(["КІРУ: Банктік көшірме транзакциялары (сома, уақыт, алушы, сипаттама, валюта, түрі)"], { fill: "B2DFDB", bold: true, sz: SZ_SM, thick: true }),
      ]}),
    ]
  }),

  new Table({
    width: { size: CW, type: WidthType.DXA }, layout: TableLayoutType.FIXED,
    columnWidths: [CW],
    rows: [new TableRow({ children: [arrowCell("▼  Параллельді өңдеу  ▼", { sz: 18 })] })]
  }),

  // 11 modules in a compact grid
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW * 0.08), Math.floor(CW * 0.20), Math.floor(CW * 0.36), Math.floor(CW * 0.36)],
    rows: [
      new TableRow({ children: [
        mkCell("№", { fill: "37474F", bold: true, sz: SZ_XS, color: "FFFFFF" }),
        mkCell("МОДУЛЬ", { fill: "37474F", bold: true, sz: SZ_XS, color: "FFFFFF" }),
        mkCell("АЛГОРИТМ / ЛОГИКА", { fill: "37474F", bold: true, sz: SZ_XS, color: "FFFFFF" }),
        mkCell("АНЫҚТАЙТЫН ҚАУІПТЕР", { fill: "37474F", bold: true, sz: SZ_XS, color: "FFFFFF" }),
      ]}),
      // Module 1
      new TableRow({ children: [
        mkCell("М1", { fill: "E3F2FD", bold: true, sz: SZ_XS }),
        mkCell(["Жылдамдық талдау", "(Velocity Analysis)"], { fill: "E3F2FD", sz: SZ_XS }),
        mkCell("Уақыт терезесіндегі транзакция жиілігін есептеу, Z-score ауытқуын анықтау", { fill: "E3F2FD", sz: SZ_XS, align: AlignmentType.LEFT }),
        mkCell("Карта/шот ұрлау, автоматтандырылған шабуылдар, бот операциялары", { fill: "E3F2FD", sz: SZ_XS, align: AlignmentType.LEFT }),
      ]}),
      // Module 2
      new TableRow({ children: [
        mkCell("М2", { fill: "FFF3E0", bold: true, sz: SZ_XS }),
        mkCell(["Сома талдау", "(Amount Analysis)"], { fill: "FFF3E0", sz: SZ_XS }),
        mkCell("Сома үлгілерін талдау, орташадан ауытқу, дөңгелек сомалар, жиілік таралуы", { fill: "FFF3E0", sz: SZ_XS, align: AlignmentType.LEFT }),
        mkCell("Ақша жылыстату, жасанды операциялар, шектен асу әрекеттері", { fill: "FFF3E0", sz: SZ_XS, align: AlignmentType.LEFT }),
      ]}),
      // Module 3
      new TableRow({ children: [
        mkCell("М3", { fill: "E8F5E9", bold: true, sz: SZ_XS }),
        mkCell(["Географиялық", "(Geo Analysis)"], { fill: "E8F5E9", sz: SZ_XS }),
        mkCell("Алушылардың географиялық орналасуын картаға түсіру, кластерлеу", { fill: "E8F5E9", sz: SZ_XS, align: AlignmentType.LEFT }),
        mkCell("Офшорлық аймақтарға ақша шығару, трансшекаралық алаяқтық", { fill: "E8F5E9", sz: SZ_XS, align: AlignmentType.LEFT }),
      ]}),
      // Module 4
      new TableRow({ children: [
        mkCell("М4", { fill: "E3F2FD", bold: true, sz: SZ_XS }),
        mkCell(["Уақыттық талдау", "(Time Pattern)"], { fill: "E3F2FD", sz: SZ_XS }),
        mkCell("Сағат/апта/ай бойынша транзакция заңдылықтарын анықтау, циклдік талдау", { fill: "E3F2FD", sz: SZ_XS, align: AlignmentType.LEFT }),
        mkCell("Жұмыс уақытынан тыс операциялар, мерзімді алаяқтық схемалар", { fill: "E3F2FD", sz: SZ_XS, align: AlignmentType.LEFT }),
      ]}),
      // Module 5
      new TableRow({ children: [
        mkCell("М5", { fill: "FFF3E0", bold: true, sz: SZ_XS }),
        mkCell(["Алушы талдау", "(Beneficiary)"], { fill: "FFF3E0", sz: SZ_XS }),
        mkCell("Алушылар санын, қайталануын, концентрациясын талдау, жаңа алушыларды бақылау", { fill: "FFF3E0", sz: SZ_XS, align: AlignmentType.LEFT }),
        mkCell("Жалған контрагенттер, аралық шоттар, «арнайы» алушылар тізімі", { fill: "FFF3E0", sz: SZ_XS, align: AlignmentType.LEFT }),
      ]}),
      // Module 6
      new TableRow({ children: [
        mkCell("М6", { fill: "E8F5E9", bold: true, sz: SZ_XS }),
        mkCell(["Құрылымдау талдау", "(Structuring)"], { fill: "E8F5E9", sz: SZ_XS }),
        mkCell("АЕК шектен (1000 АЕК ≈ 3.69 млн ₸) төмен бөлшектеу әрекеттерін анықтау", { fill: "E8F5E9", sz: SZ_XS, align: AlignmentType.LEFT }),
        mkCell("Smurfing — ақша жылыстатуды жасыру мақсатында транзакцияларды бөлшектеу", { fill: "E8F5E9", sz: SZ_XS, align: AlignmentType.LEFT }),
      ]}),
      // Module 7
      new TableRow({ children: [
        mkCell("М7", { fill: "E3F2FD", bold: true, sz: SZ_XS }),
        mkCell(["Мінез-құлық", "(Behavioral)"], { fill: "E3F2FD", sz: SZ_XS }),
        mkCell("Клиент профиліне негізделген ауытқуларды анықтау, тарихи baseline салыстыру", { fill: "E3F2FD", sz: SZ_XS, align: AlignmentType.LEFT }),
        mkCell("Шот иесі ауысуы, мінез-құлық бұзылуы, есеп бұзу белгілері", { fill: "E3F2FD", sz: SZ_XS, align: AlignmentType.LEFT }),
      ]}),
      // Module 8
      new TableRow({ children: [
        mkCell("М8", { fill: "FFF3E0", bold: true, sz: SZ_XS }),
        mkCell(["Түнгі операциялар", "(Night Detection)"], { fill: "FFF3E0", sz: SZ_XS }),
        mkCell("23:00–06:00 аралығындағы транзакцияларды талдау, үлгіден ауытқу", { fill: "FFF3E0", sz: SZ_XS, align: AlignmentType.LEFT }),
        mkCell("Ұрланған құрылғыдан операциялар, мәжбүрлеп жасалған аударымдар", { fill: "FFF3E0", sz: SZ_XS, align: AlignmentType.LEFT }),
      ]}),
      // Module 9
      new TableRow({ children: [
        mkCell("М9", { fill: "E8F5E9", bold: true, sz: SZ_XS }),
        mkCell(["Қайталанатын төлем", "(Duplicate)"], { fill: "E8F5E9", sz: SZ_XS }),
        mkCell("Бірдей сома + алушы + уақыт аралығы бойынша қайталануларды анықтау", { fill: "E8F5E9", sz: SZ_XS, align: AlignmentType.LEFT }),
        mkCell("Қос төлем алаяқтығы, жүйелі қате пайдалану, техникалық қателер", { fill: "E8F5E9", sz: SZ_XS, align: AlignmentType.LEFT }),
      ]}),
      // Module 10
      new TableRow({ children: [
        mkCell("М10", { fill: "E3F2FD", bold: true, sz: SZ_XS }),
        mkCell(["Дөңгелек сома", "(Round Amount)"], { fill: "E3F2FD", sz: SZ_XS }),
        mkCell("Дөңгелек сомалар үлесін, жиілігін, жалпы көлемін бағалау", { fill: "E3F2FD", sz: SZ_XS, align: AlignmentType.LEFT }),
        mkCell("Жалған шот-фактуралар, жасанды транзакциялар, теңгерімді бұзу", { fill: "E3F2FD", sz: SZ_XS, align: AlignmentType.LEFT }),
      ]}),
      // Module 11 (ML)
      new TableRow({ children: [
        mkCell("ML", { fill: "FFE0B2", bold: true, sz: SZ_XS }),
        mkCell(["ML тәуекел бағалау", "(Risk Scoring)"], { fill: "FFE0B2", sz: SZ_XS, bold: true }),
        mkCell("XGBoost + Random Forest + Logistic Regression ансамблі, салмақталған дауыс беру", { fill: "FFE0B2", sz: SZ_XS, align: AlignmentType.LEFT }),
        mkCell("10 модуль нәтижелерін біріктіріп, жалпы тәуекел баллын есептеу (0–100)", { fill: "FFE0B2", sz: SZ_XS, align: AlignmentType.LEFT }),
      ]}),
    ]
  }),

  new Table({
    width: { size: CW, type: WidthType.DXA }, layout: TableLayoutType.FIXED,
    columnWidths: [CW],
    rows: [new TableRow({ children: [arrowCell("▼  Композиттік тәуекел баллы  ▼", { sz: 18 })] })]
  }),

  // Decision output
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [COL4, COL4, COL4, COL4],
    rows: [
      new TableRow({ children: [
        mkCell("ШЫҒУ НӘТИЖЕСІ: ШЕШІМ ҚАБЫЛДАУ", { cs: 4, fill: "37474F", bold: true, sz: SZ_SM, color: "FFFFFF", thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell(["LOW (0–30)", "━━━━━━━", "✓ Автоматты рұқсат", "Транзакция қалыпты"], { fill: "C8E6C9", sz: SZ_XS, bold: true }),
        mkCell(["MEDIUM (31–60)", "━━━━━━━━━", "⚠ Рұқсат + мониторинг", "Қосымша бақылауға алу"], { fill: "FFF9C4", sz: SZ_XS, bold: true }),
        mkCell(["HIGH (61–85)", "━━━━━━━━", "⏸ Тоқтату + тексеру", "Комплаенс-офицер тексеру"], { fill: "FFCC80", sz: SZ_XS, bold: true }),
        mkCell(["CRITICAL (86–100)", "━━━━━━━━━━━", "✕ Бұғаттау + STR жіберу", "ҚМА-ға автоматты хабарлама"], { fill: "EF9A9A", sz: SZ_XS, bold: true }),
      ]}),
    ]
  }),
];

// ═══════════════════════════════════════════════════════════════════
// PAGE 4: ДЕРЕКТЕР АҒЫНЫ МЕН ПАЙДАЛАНУШЫ РӨЛДЕРІ (Data Flow + Roles)
// ═══════════════════════════════════════════════════════════════════
const page4 = [
  title("Сурет 4 — Деректер ағыны, пайдаланушы рөлдері және қауіпсіздік қабаттары"),
  subtitle("End-to-end процесс: деректер кіруден мемлекеттік есепке дейін"),

  // Full data flow
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW * 0.14), Math.floor(CW * 0.02), Math.floor(CW * 0.14), Math.floor(CW * 0.02), Math.floor(CW * 0.14), Math.floor(CW * 0.02), Math.floor(CW * 0.14), Math.floor(CW * 0.02), Math.floor(CW * 0.14), Math.floor(CW * 0.02), Math.floor(CW * 0.14), Math.floor(CW * 0.02), Math.floor(CW * 0.04)],
    rows: [
      new TableRow({ children: [
        mkCell("ДЕРЕКТЕР АҒЫНЫ (PIPELINE)", { cs: 13, fill: "0D47A1", bold: true, sz: SZ_SM, color: "FFFFFF", thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell(["1. ЖҮКТЕУ", "PDF/XLSX", "файлын жүктеу"], { fill: "C8E6C9", sz: SZ_XS, bold: true }),
        arrowCell("→", { sz: 20 }),
        mkCell(["2. ПАРСИНГ", "Банк түрін", "автоанықтау"], { fill: "B2DFDB", sz: SZ_XS, bold: true }),
        arrowCell("→", { sz: 20 }),
        mkCell(["3. ВАЛИДАЦИЯ", "Деректер", "тексеру"], { fill: "BBDEFB", sz: SZ_XS, bold: true }),
        arrowCell("→", { sz: 20 }),
        mkCell(["4. ТАЛДАУ", "11 модуль +", "ML скоринг"], { fill: "FFF3E0", sz: SZ_XS, bold: true }),
        arrowCell("→", { sz: 20 }),
        mkCell(["5. ШЕШІМ", "Тәуекел", "деңгейі"], { fill: "FFCCBC", sz: SZ_XS, bold: true }),
        arrowCell("→", { sz: 20 }),
        mkCell(["6. ЕСЕП", "PDF, CSV", "Dashboard"], { fill: "E1BEE7", sz: SZ_XS, bold: true }),
        arrowCell("→", { sz: 20 }),
        mkCell(["7.", "STR"], { fill: "EF9A9A", sz: SZ_XS, bold: true }),
      ]}),
    ]
  }),

  spacer(60),

  // User roles
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [COL3, COL3, COL3],
    rows: [
      new TableRow({ children: [
        mkCell("ПАЙДАЛАНУШЫ РӨЛДЕРІ МЕН ҚАТЫНАС ДЕҢГЕЙЛЕРІ", { cs: 3, fill: "4A148C", bold: true, sz: SZ_SM, color: "FFFFFF", thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell([
          "АДМИНИСТРАТОР (Admin)",
          "━━━━━━━━━━━━━━━━━━━",
          "• Жүйені толық басқару",
          "• Пайдаланушыларды қосу/жою",
          "• Рөлдер мен рұқсаттарды басқару",
          "• Жүйе параметрлерін баптау",
          "• Аудит журналын қарау",
          "• Барлық талдауларға қатынас",
        ], { fill: "F3E5F5", sz: SZ_XS, align: AlignmentType.LEFT, thick: true }),
        mkCell([
          "АНАЛИТИК (Analyst)",
          "━━━━━━━━━━━━━━━━━━━",
          "• Банк көшірмелерін жүктеу",
          "• Талдау нәтижелерін қарау",
          "• Есептерді қалыптастыру",
          "• Субъект профильдерін басқару",
          "• Күдікті транзакцияларды",
          "  белгілеу және тексеру",
        ], { fill: "F3E5F5", sz: SZ_XS, align: AlignmentType.LEFT, thick: true }),
        mkCell([
          "КОМПЛАЕНС-ОФИЦЕР",
          "━━━━━━━━━━━━━━━━━━━",
          "• HIGH/CRITICAL тексеру",
          "• STR хабарламаларын бекіту",
          "• ҚМА-ға есеп жіберу",
          "• Тәуекел деңгейін қайта бағалау",
          "• Мемлекеттік органдармен",
          "  өзара іс-қимыл",
        ], { fill: "F3E5F5", sz: SZ_XS, align: AlignmentType.LEFT, thick: true }),
      ]}),
    ]
  }),

  spacer(60),

  // Security layers
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW * 0.20), Math.floor(CW * 0.20), Math.floor(CW * 0.20), Math.floor(CW * 0.20), Math.floor(CW * 0.20)],
    rows: [
      new TableRow({ children: [
        mkCell("ҚАУІПСІЗДІК ҚАБАТТАРЫ", { cs: 5, fill: "B71C1C", bold: true, sz: SZ_SM, color: "FFFFFF", thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell([
          "1-ҚАБАТ",
          "Аутентификация",
          "━━━━━━━━━━━",
          "JWT токендер",
          "bcrypt хэштеу",
          "Email верификация",
          "Құрылғы бақылау",
        ], { fill: "FFCDD2", sz: SZ_XS }),
        mkCell([
          "2-ҚАБАТ",
          "Авторизация",
          "━━━━━━━━━━━",
          "Рөлге негізделген",
          "қатынас бақылау",
          "(RBAC)",
          "Admin / Analyst",
        ], { fill: "FFCDD2", sz: SZ_XS }),
        mkCell([
          "3-ҚАБАТ",
          "Желілік қорғау",
          "━━━━━━━━━━━",
          "CORS саясаты",
          "Rate Limiting",
          "HTTPS шифрлау",
          "WebSocket TLS",
        ], { fill: "FFCDD2", sz: SZ_XS }),
        mkCell([
          "4-ҚАБАТ",
          "Деректер қорғау",
          "━━━━━━━━━━━",
          "Парольдерді хэштеу",
          "Сессия басқару",
          "Аудит журналы",
          "Белсенділік бақылау",
        ], { fill: "FFCDD2", sz: SZ_XS }),
        mkCell([
          "5-ҚАБАТ",
          "Қолданба қорғау",
          "━━━━━━━━━━━",
          "Input валидация",
          "SQL инъекция қорғау",
          "XSS қорғау",
          "CSRF токендер",
        ], { fill: "FFCDD2", sz: SZ_XS }),
      ]}),
    ]
  }),

  spacer(60),

  // Supported banks
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW / 6), Math.floor(CW / 6), Math.floor(CW / 6), Math.floor(CW / 6), Math.floor(CW / 6), Math.floor(CW / 6)],
    rows: [
      new TableRow({ children: [
        mkCell("ҚОЛДАУ КӨРСЕТІЛЕТІН БАНКТЕР МЕН ҚАРЖЫ ҰЙЫМДАРЫ", { cs: 6, fill: "1B5E20", bold: true, sz: SZ_SM, color: "FFFFFF", thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell(["Kaspi Bank", "(PDF, XLSX)"], { fill: "C8E6C9", sz: SZ_XS, bold: true }),
        mkCell(["Halyk Bank", "(PDF, XLSX)"], { fill: "C8E6C9", sz: SZ_XS, bold: true }),
        mkCell(["Forte Bank", "(XLSX)"], { fill: "C8E6C9", sz: SZ_XS, bold: true }),
        mkCell(["Jusan Bank", "(XLSX)"], { fill: "C8E6C9", sz: SZ_XS, bold: true }),
        mkCell(["Сбербанк ҚР", "(PDF)"], { fill: "C8E6C9", sz: SZ_XS, bold: true }),
        mkCell(["Binance", "(CSV)"], { fill: "C8E6C9", sz: SZ_XS, bold: true }),
      ]}),
    ]
  }),
];

// ═══════════════════════════════════════════════════════════════════
// PAGE 5: МЕМЛЕКЕТКЕ ТИГІЗЕТІН ПАЙДА + ТЕХНОЛОГИЯЛЫҚ СТЕК
// ═══════════════════════════════════════════════════════════════════
const page5 = [
  title("Сурет 5 — Мемлекетке тигізетін пайда және технологиялық сәулет"),
  subtitle("ntFAST жүйесінің ҚР экономикасы мен қауіпсіздігіне қосатын үлесі"),

  // Benefits - 3 categories
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [COL3, COL3, COL3],
    rows: [
      new TableRow({ children: [
        mkCell("МЕМЛЕКЕТКЕ ТИГІЗЕТІН ПАЙДА", { cs: 3, fill: "0D47A1", bold: true, sz: SZ_SM, color: "FFFFFF", thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell([
          "ЭКОНОМИКАЛЫҚ ПАЙДА",
          "━━━━━━━━━━━━━━━━━━",
          "• Импорт алмастыру: шетелдік",
          "  ПО орнына отандық шешім",
          "  (жылына $200K–1M үнемдеу)",
          "• Алаяқтықтан қорғау:",
          "  жылына 15–40 млрд ₸ шығынның",
          "  алдын алу",
          "• IT саласында 20–30 жаңа",
          "  жұмыс орны",
          "• ТМД/ЕАЭО елдеріне экспорт",
          "  потенциалы",
        ], { fill: "E3F2FD", sz: SZ_XS, align: AlignmentType.LEFT, thick: true }),
        mkCell([
          "СТРАТЕГИЯЛЫҚ ПАЙДА",
          "━━━━━━━━━━━━━━━━━━",
          "• ФАТФ бағалауын жақсарту —",
          "  «сұр тізімнен» шығу",
          "• ПОД/ФТ жүйесін нығайту —",
          "  цифрлық мониторинг",
          "• Мемлекеттік тілді қолдау —",
          "  қазақ тілінде толық жұмыс",
          "• «Цифрлы Қазақстан»",
          "  бағдарламасына сәйкес",
          "• Деректер егемендігі — барлық",
          "  деректер ел ішінде қалады",
        ], { fill: "E8F5E9", sz: SZ_XS, align: AlignmentType.LEFT, thick: true }),
        mkCell([
          "ҚАУІПСІЗДІК ПАЙДАСЫ",
          "━━━━━━━━━━━━━━━━━━",
          "• Терроризмді қаржыландыруға",
          "  қарсы күресті нығайту",
          "• Ұйымдасқан қылмыстың қаржы",
          "  ағындарын анықтау",
          "• Салық жалтару схемаларын",
          "  ашу",
          "• Коррупциялық ақша ағындарын",
          "  бақылау",
          "• Трансшекаралық қаржы",
          "  ағындарын мониторинг",
        ], { fill: "FCE4EC", sz: SZ_XS, align: AlignmentType.LEFT, thick: true }),
      ]}),
    ]
  }),

  spacer(60),

  // Compliance frameworks
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [COL4, COL4, COL4, COL4],
    rows: [
      new TableRow({ children: [
        mkCell("СӘЙКЕСТІК СТАНДАРТТАРЫ МЕН НОРМАТИВТІК БАЗА", { cs: 4, fill: "4A148C", bold: true, sz: SZ_SM, color: "FFFFFF", thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell([
          "ФАТФ (FATF)",
          "━━━━━━━━━",
          "40 ұсыныс",
          "11 тікелей нәтиже",
          "Risk-Based Approach",
          "Customer Due Diligence",
        ], { fill: "E8EAF6", sz: SZ_XS }),
        mkCell([
          "ҚР ЗАҢНАМАСЫ",
          "━━━━━━━━━━━━",
          "ПОД/ФТ Заңы №191-IV",
          "ҰБ Қаулысы №28",
          "АЕК шекті мәні",
          "Субъект міндеттері",
        ], { fill: "E8EAF6", sz: SZ_XS }),
        mkCell([
          "ХАЛЫҚАРАЛЫҚ",
          "━━━━━━━━━━━━",
          "ЕО/БҰҰ санкциялар",
          "Egmont Group",
          "ISO 20022 (хабарлама)",
          "Basel III стандарты",
        ], { fill: "E8EAF6", sz: SZ_XS }),
        mkCell([
          "«ЦИФРЛЫ ҚАЗАҚСТАН»",
          "━━━━━━━━━━━━━━━━━━",
          "Деректер егемендігі",
          "IT импорт алмастыру",
          "Цифрлық трансформация",
          "e-Government интеграция",
        ], { fill: "E8EAF6", sz: SZ_XS }),
      ]}),
    ]
  }),

  spacer(60),

  // Technology stack detailed
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW / 6), Math.floor(CW / 6), Math.floor(CW / 6), Math.floor(CW / 6), Math.floor(CW / 6), Math.floor(CW / 6)],
    rows: [
      new TableRow({ children: [
        mkCell("ТЕХНОЛОГИЯЛЫҚ СТЕК", { cs: 6, fill: "37474F", bold: true, sz: SZ_SM, color: "FFFFFF", thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell([
          "BACKEND",
          "━━━━━━━",
          "Python 3.11",
          "FastAPI",
          "SQLAlchemy",
          "Pydantic",
          "Uvicorn",
        ], { fill: "E0E0E0", sz: SZ_XS, bold: true }),
        mkCell([
          "FRONTEND",
          "━━━━━━━━",
          "React 19",
          "TypeScript 5",
          "Vite 6",
          "Tailwind CSS",
          "Chart.js",
        ], { fill: "E0E0E0", sz: SZ_XS, bold: true }),
        mkCell([
          "DATABASE",
          "━━━━━━━━",
          "PostgreSQL 15",
          "Redis 7",
          "SQLite (dev)",
          "Alembic",
          "Migrations",
        ], { fill: "E0E0E0", sz: SZ_XS, bold: true }),
        mkCell([
          "ML / AI",
          "━━━━━━",
          "XGBoost",
          "Scikit-learn",
          "Random Forest",
          "Logistic Reg.",
          "Claude AI",
        ], { fill: "E0E0E0", sz: SZ_XS, bold: true }),
        mkCell([
          "DEPLOY",
          "━━━━━━",
          "Docker",
          "Docker Compose",
          "Railway",
          "Kubernetes",
          "CI/CD",
        ], { fill: "E0E0E0", sz: SZ_XS, bold: true }),
        mkCell([
          "ҚОСЫМША",
          "━━━━━━━━",
          "WebSocket",
          "JWT Auth",
          "i18n (3 тіл)",
          "PDF Export",
          "Email (6 провайдер)",
        ], { fill: "E0E0E0", sz: SZ_XS, bold: true }),
      ]}),
    ]
  }),

  spacer(40),

  // Footer: system info
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [COL3, COL3, COL3],
    rows: [
      new TableRow({ children: [
        mkCell(["Әзірлеуші: ntFAST Development Team", "Нұсқа: 1.0.0"], { fill: "FAFAFA", sz: SZ_XS, dashed: true }),
        mkCell(["Мақсатты нарық: Қазақстан Республикасы", "Кеңейту: ТМД, ЕАЭО елдері"], { fill: "FAFAFA", sz: SZ_XS, dashed: true }),
        mkCell(["Интеллектуалдық меншік: НИИС РК", "Патент түрі: Пайдалы модель"], { fill: "FAFAFA", sz: SZ_XS, dashed: true }),
      ]}),
    ]
  }),
];

// ═══════════════════════════════════════════════════════════════════
// BUILD DOCUMENT
// ═══════════════════════════════════════════════════════════════════
const doc = new Document({
  styles: { default: { document: { run: { font: F, size: SZ } } } },
  sections: [
    { properties: pageProps, children: page1 },
    { properties: pageProps, children: page2 },
    { properties: pageProps, children: page3 },
    { properties: pageProps, children: page4 },
    { properties: pageProps, children: page5 },
  ]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("ntFAST_Block_Diagram_Full.docx", buf);
  console.log("OK: Full Block Diagram created — 5 pages (" + (buf.length / 1024).toFixed(0) + " KB)");
  console.log("Pages:");
  console.log("  1. Жалпы жүйе архитектурасы");
  console.log("  2. Мемлекеттік құрылымдармен байланыс");
  console.log("  3. 11 талдау модулінің блок-схемасы");
  console.log("  4. Деректер ағыны, рөлдер, қауіпсіздік");
  console.log("  5. Мемлекетке пайда + технологиялық стек");
});
