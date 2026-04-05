const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, WidthType, BorderStyle, Footer, PageNumber,
  ShadingType, VerticalAlign, TableLayoutType, PageOrientation } = require('docx');
const fs = require('fs');

const F = "Times New Roman";
const SZ = 22; // 11pt for diagram
const SZ_SM = 18; // 9pt
const SZ_TITLE = 28; // 14pt

const ML = 851, MR = 851, MT = 851, MB = 851; // smaller margins for landscape
const PW = 16838; // A4 landscape width
const PH = 11906; // A4 landscape height
const CW = PW - ML - MR; // ~15136

const thin = { style: BorderStyle.SINGLE, size: 1, color: "000000" };
const thick = { style: BorderStyle.SINGLE, size: 3, color: "000000" };
const borders = { top: thin, bottom: thin, left: thin, right: thin };
const thickBorders = { top: thick, bottom: thick, left: thick, right: thick };
const noBorder = { style: BorderStyle.NONE, size: 0 };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

const mkCell = (texts, opts = {}) => new TableCell({
  borders: opts.thick ? thickBorders : (opts.noBorders ? noBorders : borders),
  width: opts.w ? { size: opts.w, type: WidthType.DXA } : undefined,
  columnSpan: opts.cs || 1,
  rowSpan: opts.rs || 1,
  verticalAlign: VerticalAlign.CENTER,
  shading: opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR } : undefined,
  margins: { top: 30, bottom: 30, left: 60, right: 60 },
  children: (Array.isArray(texts) ? texts : [texts]).map(t =>
    typeof t === 'object' && t.type === 'Paragraph' ? t :
    new Paragraph({
      spacing: { after: 0, before: 0, line: 220 },
      alignment: opts.align || AlignmentType.CENTER,
      children: [new TextRun({
        text: typeof t === 'string' ? t : '', font: F,
        size: opts.sz || SZ, bold: opts.bold || false, italics: opts.italic || false,
        color: opts.color || "000000"
      })]
    })
  )
});

const arrowCell = (text, opts = {}) => mkCell(text || "▼", { ...opts, noBorders: true, sz: opts.sz || 28, bold: true });

const emptyNB = (opts = {}) => mkCell("", { ...opts, noBorders: true });

// Column widths for 5-column layout
const COL_W = Math.floor(CW / 5); // ~3027 each

// ======================== PAGE 1: MAIN SYSTEM DIAGRAM ========================
const page1Children = [
  new Paragraph({
    spacing: { after: 120, before: 0, line: 240 },
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Сурет 1 — ntFAST жүйесінің блок-схемасы", font: F, size: SZ_TITLE, bold: true })]
  }),

  // ===== ROW 1: EXTERNAL DATA SOURCES =====
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [COL_W, COL_W, COL_W, COL_W, COL_W],
    rows: [
      new TableRow({ children: [
        mkCell("СЫРТҚЫ ДЕРЕКТЕР КӨЗДЕРІ", { cs: 5, fill: "D5E8D4", bold: true, sz: 24, thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell(["Банктік АБЖ", "(Core Banking)"], { fill: "D5E8D4", sz: SZ_SM }),
        mkCell(["Карталық", "процессинг"], { fill: "D5E8D4", sz: SZ_SM }),
        mkCell(["Төлем шлюздері", "(Kaspi, Halyk QR)"], { fill: "D5E8D4", sz: SZ_SM }),
        mkCell(["Электрондық ақша", "(Wooppay, QIWI)"], { fill: "D5E8D4", sz: SZ_SM }),
        mkCell(["Валюта айырбастау", "бюросы"], { fill: "D5E8D4", sz: SZ_SM }),
      ]}),
    ]
  }),

  // Arrow down
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [CW],
    rows: [new TableRow({ children: [arrowCell("▼  HTTP/HTTPS API  ▼", { sz: 22 })] })]
  }),

  // ===== ROW 2: INPUT LAYER =====
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW/3), Math.floor(CW/3), Math.floor(CW/3)],
    rows: [
      new TableRow({ children: [
        mkCell("ДЕРЕКТЕР КІРУ ҚАБАТЫ", { cs: 3, fill: "DAE8FC", bold: true, sz: 24, thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell(["API шлюзі (FastAPI)", "JWT аутентификация"], { fill: "DAE8FC", sz: SZ_SM }),
        mkCell(["Деректер валидациясы", "(Pydantic схемалар)"], { fill: "DAE8FC", sz: SZ_SM }),
        mkCell(["Деректер коннекторлары", "(REST, CSV, JSON)"], { fill: "DAE8FC", sz: SZ_SM }),
      ]}),
    ]
  }),

  // Arrow down
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [CW],
    rows: [new TableRow({ children: [arrowCell("▼  Redis Message Queue  ▼", { sz: 22 })] })]
  }),

  // ===== ROW 3: ANALYSIS LAYER - 10 MODULES =====
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [COL_W, COL_W, COL_W, COL_W, COL_W],
    rows: [
      new TableRow({ children: [
        mkCell("ТАЛДАУ ҚАБАТЫ — 10 МАМАНДАНДЫРЫЛҒАН МОДУЛЬ", { cs: 5, fill: "FFF2CC", bold: true, sz: 24, thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell(["М1: Жылдамдық", "талдау", "(Velocity)"], { fill: "FFF2CC", sz: SZ_SM }),
        mkCell(["М2: Сома", "талдау", "(Amount)"], { fill: "FFF2CC", sz: SZ_SM }),
        mkCell(["М3: Географиялық", "талдау", "(Geo)"], { fill: "FFF2CC", sz: SZ_SM }),
        mkCell(["М4: Уақыттық", "заңдылықтар", "(Time)"], { fill: "FFF2CC", sz: SZ_SM }),
        mkCell(["М5: Алушы", "талдау", "(Beneficiary)"], { fill: "FFF2CC", sz: SZ_SM }),
      ]}),
      new TableRow({ children: [
        mkCell(["М6: Құрылымдау", "талдау", "(Structuring)"], { fill: "FFF2CC", sz: SZ_SM }),
        mkCell(["М7: Мінез-құлық", "талдау", "(Behavioral)"], { fill: "FFF2CC", sz: SZ_SM }),
        mkCell(["М8: Құрылғы", "талдау", "(Device)"], { fill: "FFF2CC", sz: SZ_SM }),
        mkCell(["М9: Трансшекаралық", "талдау", "(Cross-Border)"], { fill: "FFF2CC", sz: SZ_SM }),
        mkCell(["М10: ML тәуекел", "бағалау", "(Risk Scoring)"], { fill: "FFE0B2", sz: SZ_SM, bold: true }),
      ]}),
    ]
  }),

  // Arrow down
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [CW],
    rows: [new TableRow({ children: [arrowCell("▼  Ансамбль: XGBoost + Random Forest + Logistic Regression  ▼", { sz: 20 })] })]
  }),

  // ===== ROW 4: DECISION LAYER =====
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW/4), Math.floor(CW/4), Math.floor(CW/4), Math.floor(CW/4)],
    rows: [
      new TableRow({ children: [
        mkCell("ШЕШІМ ҚАБЫЛДАУ ҚАБАТЫ (0-100 тәуекел баллы)", { cs: 4, fill: "F8CECC", bold: true, sz: 24, thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell(["LOW (0-30)", "✓ Автоматты рұқсат"], { fill: "C8E6C9", sz: SZ_SM, bold: true }),
        mkCell(["MEDIUM (31-60)", "⚠ Рұқсат + мониторинг"], { fill: "FFF9C4", sz: SZ_SM, bold: true }),
        mkCell(["HIGH (61-85)", "⏸ Тоқтату + тексеру"], { fill: "FFCC80", sz: SZ_SM, bold: true }),
        mkCell(["CRITICAL (86-100)", "✕ Бұғаттау + хабарлау"], { fill: "EF9A9A", sz: SZ_SM, bold: true }),
      ]}),
    ]
  }),

  // Arrow down - splits
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW/3), Math.floor(CW/3), Math.floor(CW/3)],
    rows: [new TableRow({ children: [
      arrowCell("▼"),
      arrowCell("▼"),
      arrowCell("▼"),
    ]})]
  }),

  // ===== ROW 5: OUTPUT LAYER =====
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW/3), Math.floor(CW/3), Math.floor(CW/3)],
    rows: [
      new TableRow({ children: [
        mkCell("НӘТИЖЕЛЕР ҚАБАТЫ", { cs: 3, fill: "E1BEE7", bold: true, sz: 24, thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell(["Бақылау тақтасы", "(Dashboard)", "KPI, графиктер, карта"], { fill: "E1BEE7", sz: SZ_SM }),
        mkCell(["Ескерту жүйесі", "(Alert System)", "Email, SMS, Dashboard"], { fill: "E1BEE7", sz: SZ_SM }),
        mkCell(["Есептеу жүйесі", "(Reports)", "ПОД/ФТ есептер, PDF, CSV"], { fill: "E1BEE7", sz: SZ_SM }),
      ]}),
    ]
  }),

  // Arrow down to government
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW/3), Math.floor(CW/3), Math.floor(CW/3)],
    rows: [new TableRow({ children: [
      arrowCell("▼"),
      arrowCell("▼"),
      arrowCell("▼"),
    ]})]
  }),

  // ===== ROW 6: GOVERNMENT STRUCTURES =====
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW/3), Math.floor(CW/3), Math.floor(CW/3)],
    rows: [
      new TableRow({ children: [
        mkCell("МЕМЛЕКЕТТІК ОРГАНДАР ЖӘНЕ РЕТТЕУШІЛЕР", { cs: 3, fill: "BBDEFB", bold: true, sz: 24, thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell(["ҚР Қаржылық", "мониторинг агенттігі", "(ҚМА)", "Күдікті транзакция", "хабарламалары (STR)"], { fill: "BBDEFB", sz: SZ_SM }),
        mkCell(["ҚР Ұлттық Банк", "(НБ РК)", "Нормативтік сәйкестік", "есептері, ПОД/ФТ", "статистикасы"], { fill: "BBDEFB", sz: SZ_SM }),
        mkCell(["ҚР Ішкі істер", "министрлігі (ІІМ)", "Алаяқтық оқиғалары", "туралы ақпарат", "алмасу"], { fill: "BBDEFB", sz: SZ_SM }),
      ]}),
    ]
  }),
];

// ======================== PAGE 2: DETAILED DATA FLOW ========================
const page2Children = [
  new Paragraph({
    spacing: { after: 120, before: 0, line: 240 },
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Сурет 2 — Деректер ағынының блок-схемасы және мемлекеттік құрылымдармен байланысы", font: F, size: SZ_TITLE, bold: true })]
  }),

  // Main flow diagram
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW * 0.3), Math.floor(CW * 0.05), Math.floor(CW * 0.3), Math.floor(CW * 0.05), Math.floor(CW * 0.3)],
    rows: [
      // Row 1: Sources
      new TableRow({ children: [
        mkCell(["ҚАРЖЫЛЫҚ ҰЙЫМДАР", "", "• Банктер (22)", "• Төлем жүйелері", "• Сақтандыру (31)", "• МҚҰ (189)", "• Бағалы қағаздар (40)"], { fill: "C8E6C9", sz: SZ_SM, thick: true }),
        arrowCell("→", { sz: 28 }),
        mkCell(["ntFAST ЖҮЙЕСІ", "", "1. Деректер қабылдау", "2. 10 модуль талдау", "3. ML тәуекел бағалау", "4. Шешім қабылдау", "5. Есеп қалыптастыру"], { fill: "FFF2CC", sz: SZ_SM, thick: true, bold: true }),
        arrowCell("→", { sz: 28 }),
        mkCell(["МЕМЛЕКЕТТІК ОРГАНДАР", "", "• ҚМА (ПОД/ФТ)", "• НБ РК (реттеуші)", "• ІІМ (тергеу)", "• Салық комитеті", "• Прокуратура"], { fill: "BBDEFB", sz: SZ_SM, thick: true }),
      ]}),
      // Empty row
      new TableRow({ children: [
        emptyNB(), emptyNB(), arrowCell("▼", { sz: 24 }), emptyNB(), emptyNB(),
      ]}),
      // Row 2: Database and Integration
      new TableRow({ children: [
        mkCell(["ФАТФ СТАНДАРТТАРЫ", "", "• 40 ұсыныс", "• 11 тікелей нәтиже", "• Өзара бағалау", "• «Сұр» / «Қара» тізімдер"], { fill: "E8EAF6", sz: SZ_SM, thick: true }),
        arrowCell("→", { sz: 28 }),
        mkCell(["ДЕРЕКТЕР ҚОРЫ", "", "PostgreSQL:", "• Транзакциялар", "• Тәуекел бағалаулар", "• Аудит журналы", "Redis: кэш + кезек"], { fill: "F3E5F5", sz: SZ_SM, thick: true }),
        arrowCell("→", { sz: 28 }),
        mkCell(["ҚР ЗАҢНАМАСЫ", "", "• ПОД/ФТ Заңы №191-IV", "• ҰБ Қаулысы №28", "• АЕК шекті мәні", "• Санкциялар тізімі", "• Цифрлы Қазақстан"], { fill: "E8EAF6", sz: SZ_SM, thick: true }),
      ]}),
    ]
  }),

  new Paragraph({ spacing: { after: 80, before: 150, line: 240 }, children: [] }),

  // Benefits to state table
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW/2), Math.floor(CW/2)],
    rows: [
      new TableRow({ children: [
        mkCell("МЕМЛЕКЕТКЕ ТИГІЗЕТІН ПАЙДА", { cs: 2, fill: "1565C0", bold: true, sz: 24, color: "FFFFFF", thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell([
          "Экономикалық пайда:",
          "",
          "• Импорт алмастыру — шет елдік ПО орнына",
          "  отандық шешім (жылына $200K-1M үнемдеу)",
          "• Алаяқтықтан қорғау — жылына 15-40 млрд ₸",
          "  шығынның алдын алу",
          "• IT мамандарға 20-30 жұмыс орны",
          "• Экспорт потенциалы — ТМД, ЕАЭО елдеріне"
        ], { fill: "E3F2FD", sz: SZ_SM, align: AlignmentType.LEFT }),
        mkCell([
          "Стратегиялық пайда:",
          "",
          "• ПОД/ФТ жүйесін нығайту — ФАТФ бағалауын",
          "  жақсарту",
          "• Мемлекеттік тілді қолдау — қазақ тілінде",
          "  толық жұмыс істейді",
          "• «Цифрлы Қазақстан» бағдарламасына сәйкес",
          "• Ұлттық қауіпсіздік — деректер елде қалады"
        ], { fill: "E3F2FD", sz: SZ_SM, align: AlignmentType.LEFT }),
      ]}),
    ]
  }),

  new Paragraph({ spacing: { after: 80, before: 150, line: 240 }, children: [] }),

  // Technology stack
  new Table({
    width: { size: CW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    columnWidths: [Math.floor(CW/5), Math.floor(CW/5), Math.floor(CW/5), Math.floor(CW/5), Math.floor(CW/5)],
    rows: [
      new TableRow({ children: [
        mkCell("ТЕХНОЛОГИЯЛЫҚ СТЕК", { cs: 5, fill: "424242", bold: true, sz: 24, color: "FFFFFF", thick: true }),
      ]}),
      new TableRow({ children: [
        mkCell(["Backend", "Python 3.11", "FastAPI"], { fill: "E0E0E0", sz: SZ_SM, bold: true }),
        mkCell(["Frontend", "React 18", "TypeScript 5"], { fill: "E0E0E0", sz: SZ_SM, bold: true }),
        mkCell(["Database", "PostgreSQL 15", "Redis 7"], { fill: "E0E0E0", sz: SZ_SM, bold: true }),
        mkCell(["ML", "XGBoost", "Scikit-learn"], { fill: "E0E0E0", sz: SZ_SM, bold: true }),
        mkCell(["Deploy", "Docker", "Railway / K8s"], { fill: "E0E0E0", sz: SZ_SM, bold: true }),
      ]}),
    ]
  }),
];

// ======================== BUILD DOCUMENT ========================
const doc = new Document({
  styles: { default: { document: { run: { font: F, size: SZ } } } },
  sections: [
    // Page 1: Main System Block Diagram (Landscape)
    {
      properties: {
        page: {
          size: { width: PW, height: PH, orientation: PageOrientation.LANDSCAPE },
          margin: { top: MT, right: MR, bottom: MB, left: ML }
        }
      },
      children: page1Children
    },
    // Page 2: Data Flow + Government + Benefits (Landscape)
    {
      properties: {
        page: {
          size: { width: PW, height: PH, orientation: PageOrientation.LANDSCAPE },
          margin: { top: MT, right: MR, bottom: MB, left: ML }
        }
      },
      children: page2Children
    }
  ]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("ntFAST_Block_Diagram.docx", buf);
  console.log("OK: Block Diagram created (" + (buf.length / 1024).toFixed(0) + " KB)");
});
