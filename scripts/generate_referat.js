const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, AlignmentType, LevelFormat, BorderStyle } = require("docx");

// Helper: bold label + normal text on same line
function labeledField(label, text, options = {}) {
  return new Paragraph({
    spacing: { before: 120, after: 120 },
    ...options,
    children: [
      new TextRun({ text: label, bold: true, font: "Times New Roman", size: 24 }),
      new TextRun({ text: text, font: "Times New Roman", size: 24 }),
    ],
  });
}

// Helper: normal paragraph
function normalPara(text, options = {}) {
  return new Paragraph({
    spacing: { before: 60, after: 60 },
    alignment: AlignmentType.JUSTIFIED,
    ...options,
    children: [
      new TextRun({ text, font: "Times New Roman", size: 24 }),
    ],
  });
}

// Helper: bold paragraph
function boldPara(text, options = {}) {
  return new Paragraph({
    spacing: { before: 120, after: 120 },
    ...options,
    children: [
      new TextRun({ text, bold: true, font: "Times New Roman", size: 24 }),
    ],
  });
}

const doc = new Document({
  numbering: {
    config: [
      {
        reference: "dash-bullets",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "\u2013",
            alignment: AlignmentType.LEFT,
            style: {
              paragraph: {
                indent: { left: 720, hanging: 360 },
              },
            },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: {
            width: 11906,  // A4
            height: 16838,
          },
          margin: {
            top: 1440,
            right: 1440,
            bottom: 1440,
            left: 1440,
          },
        },
      },
      children: [
        // Title section
        new Paragraph({
          alignment: AlignmentType.RIGHT,
          spacing: { after: 120 },
          children: [
            new TextRun({ text: "\u04AE\u043B\u0433\u0456", font: "Times New Roman", size: 24, italics: true }),
          ],
        }),

        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 120, after: 60 },
          children: [
            new TextRun({
              text: "\u00AB\u0410\u0432\u0442\u043E\u0440\u043B\u044B\u049B \u049B\u04B1\u049B\u044B\u049B \u0436\u04D9\u043D\u0435 \u0441\u0430\u0431\u0430\u049B\u0442\u0430\u0441 \u049B\u04B1\u049B\u044B\u049B\u0442\u0430\u0440 \u0442\u0443\u0440\u0430\u043B\u044B\u00BB",
              font: "Times New Roman", size: 24,
            }),
          ],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 60, after: 240 },
          children: [
            new TextRun({
              text: "\u049A\u0420 1996 \u0436\u044B\u043B\u0493\u044B 10 \u043C\u0430\u0443\u0441\u044B\u043C\u0434\u0430\u0493\u044B \u0417\u0430\u04A3\u044B\u043D\u044B\u04A3 9-1 \u0411\u0430\u0431\u044B",
              font: "Times New Roman", size: 24,
            }),
          ],
        }),

        // Horizontal line
        new Paragraph({
          spacing: { before: 120, after: 240 },
          border: {
            bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 },
          },
          children: [],
        }),

        // Реферат heading
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 240, after: 120 },
          children: [
            new TextRun({ text: "\u0420\u0415\u0424\u0415\u0420\u0410\u0422", bold: true, font: "Times New Roman", size: 28 }),
          ],
        }),

        // ЭЕМ арналған бағдарлама
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 120, after: 360 },
          children: [
            new TextRun({
              text: "\u042D\u0415\u041C \u0430\u0440\u043D\u0430\u043B\u0493\u0430\u043D \u0431\u0430\u0493\u0434\u0430\u0440\u043B\u0430\u043C\u0430",
              font: "Times New Roman", size: 24, italics: true,
            }),
          ],
        }),

        // Атауы
        labeledField(
          "\u0410\u0442\u0430\u0443\u044B: ",
          "ntFAST \u2014 \u049A\u0430\u0440\u0436\u044B\u043B\u044B\u049B \u0442\u0440\u0430\u043D\u0437\u0430\u043A\u0446\u0438\u044F\u043B\u0430\u0440\u0434\u044B \u0442\u0430\u043B\u0434\u0430\u0443 \u0436\u04AF\u0439\u0435\u0441\u0456 (Financial Analysis System for Transactions)"
        ),

        // Автор
        labeledField(
          "\u0410\u0432\u0442\u043E\u0440: ",
          "\u0422\u0430\u0436\u0438 \u041D\u0443\u0440\u0434\u0430\u0443\u043B\u0435\u0442 [\u04D8\u043A\u0435\u0441\u0456\u043D\u0456\u04A3 \u0430\u0442\u044B]"
        ),

        // Объектінің құрылған күні
        labeledField(
          "\u041E\u0431\u044A\u0435\u043A\u0442\u0456\u043D\u0456\u04A3 \u049B\u04B1\u0440\u044B\u043B\u0493\u0430\u043D \u043A\u04AF\u043D\u0456: ",
          "2026 \u0436\u044B\u043B\u0493\u044B 15 \u0430\u049B\u043F\u0430\u043D"
        ),

        // Spacer
        new Paragraph({ spacing: { before: 120, after: 60 }, children: [] }),

        // Қолдану саласы
        boldPara("\u049A\u043E\u043B\u0434\u0430\u043D\u0443 \u0441\u0430\u043B\u0430\u0441\u044B:"),
        normalPara(
          "\u0411\u0430\u0493\u0434\u0430\u0440\u043B\u0430\u043C\u0430 \u049B\u0430\u0440\u0436\u044B\u043B\u044B\u049B \u0442\u0435\u0445\u043D\u043E\u043B\u043E\u0433\u0438\u044F\u043B\u0430\u0440 (FinTech) \u0441\u0430\u043B\u0430\u0441\u044B\u043D\u0434\u0430 \u049B\u043E\u043B\u0434\u0430\u043D\u044B\u043B\u0430\u0434\u044B. \u0416\u04AF\u0439\u0435 \u0431\u0430\u043D\u043A \u0442\u0440\u0430\u043D\u0437\u0430\u043A\u0446\u0438\u044F\u043B\u0430\u0440\u044B\u043D \u0430\u0432\u0442\u043E\u043C\u0430\u0442\u0442\u044B \u0442\u04AF\u0440\u0434\u0435 \u0442\u0430\u043B\u0434\u0430\u0443, \u0430\u043B\u0430\u044F\u049B\u0442\u044B\u049B\u0442\u044B \u0430\u043D\u044B\u049B\u0442\u0430\u0443, \u0442\u04D9\u0443\u0435\u043A\u0435\u043B\u0434\u0435\u0440\u0434\u0456 \u0431\u0430\u0493\u0430\u043B\u0430\u0443 \u0436\u04D9\u043D\u0435 \u049B\u0430\u0440\u0436\u044B\u043B\u044B\u049B \u043C\u043E\u043D\u0438\u0442\u043E\u0440\u0438\u043D\u0433 \u0436\u04AF\u0440\u0433\u0456\u0437\u0443 \u04AF\u0448\u0456\u043D \u0430\u0440\u043D\u0430\u043B\u0493\u0430\u043D. \u049A\u043E\u043B\u0434\u0430\u043D\u0443\u0448\u044B\u043B\u0430\u0440: \u049B\u0430\u0440\u0436\u044B \u0430\u043D\u0430\u043B\u0438\u0442\u0438\u043A\u0442\u0435\u0440\u0456, \u0431\u0430\u043D\u043A \u049B\u044B\u0437\u043C\u0435\u0442\u043A\u0435\u0440\u043B\u0435\u0440\u0456, \u0430\u0443\u0434\u0438\u0442\u043E\u0440\u043B\u0430\u0440, \u049B\u04B1\u049B\u044B\u049B \u049B\u043E\u0440\u0493\u0430\u0443 \u043E\u0440\u0433\u0430\u043D\u0434\u0430\u0440\u044B."
        ),

        // Spacer
        new Paragraph({ spacing: { before: 120, after: 60 }, children: [] }),

        // Мақсаты
        boldPara("\u041C\u0430\u049B\u0441\u0430\u0442\u044B:"),
        normalPara(
          "\u0411\u0430\u0493\u0434\u0430\u0440\u043B\u0430\u043C\u0430\u043D\u044B\u04A3 \u043C\u0430\u049B\u0441\u0430\u0442\u044B \u2014 \u0431\u0430\u043D\u043A \u04AF\u0437\u0456\u043D\u0434\u0456\u043B\u0435\u0440\u0456\u043D (PDF \u0444\u043E\u0440\u043C\u0430\u0442\u044B\u043D\u0434\u0430) \u0430\u0432\u0442\u043E\u043C\u0430\u0442\u0442\u044B \u0442\u04AF\u0440\u0434\u0435 \u04E9\u04A3\u0434\u0435\u0443, \u0442\u0440\u0430\u043D\u0437\u0430\u043A\u0446\u0438\u044F\u043B\u0430\u0440\u0434\u044B \u043A\u0430\u0442\u0435\u0433\u043E\u0440\u0438\u044F\u043B\u0430\u0443, \u043A\u04AF\u0434\u0456\u043A\u0442\u0456 \u043E\u043F\u0435\u0440\u0430\u0446\u0438\u044F\u043B\u0430\u0440\u0434\u044B \u0430\u043D\u044B\u049B\u0442\u0430\u0443 \u0436\u04D9\u043D\u0435 \u049B\u0430\u0440\u0436\u044B\u043B\u044B\u049B \u0442\u04D9\u0443\u0435\u043A\u0435\u043B\u0434\u0435\u0440\u0434\u0456 \u0431\u0430\u0493\u0430\u043B\u0430\u0443. \u0416\u04AF\u0439\u0435 \u0436\u0430\u0441\u0430\u043D\u0434\u044B \u0438\u043D\u0442\u0435\u043B\u043B\u0435\u043A\u0442 \u0442\u0435\u0445\u043D\u043E\u043B\u043E\u0433\u0438\u044F\u043B\u0430\u0440\u044B\u043D \u049B\u043E\u043B\u0434\u0430\u043D\u0430 \u043E\u0442\u044B\u0440\u044B\u043F, \u049B\u0430\u0440\u0436\u044B\u043B\u044B\u049B \u0434\u0435\u0440\u0435\u043A\u0442\u0435\u0440\u0434\u0456 \u0442\u0435\u0440\u0435\u04A3 \u0442\u0430\u043B\u0434\u0430\u0443 \u0436\u0430\u0441\u0430\u0439\u0434\u044B."
        ),

        // Spacer
        new Paragraph({ spacing: { before: 120, after: 60 }, children: [] }),

        // Функционалдық мүмкіндігі
        boldPara("\u0424\u0443\u043D\u043A\u0446\u0438\u043E\u043D\u0430\u043B\u0434\u044B\u049B \u043C\u04AF\u043C\u043A\u0456\u043D\u0434\u0456\u0433\u0456:"),

        // Bullet items
        ...[
          "PDF \u0431\u0430\u043D\u043A \u04AF\u0437\u0456\u043D\u0434\u0456\u043B\u0435\u0440\u0456\u043D \u0430\u0432\u0442\u043E\u043C\u0430\u0442\u0442\u044B \u0442\u0430\u043B\u0434\u0430\u0443 (Kaspi Bank, Halyk Bank \u049B\u043E\u043B\u0434\u0430\u0443\u044B)",
          "\u0422\u0440\u0430\u043D\u0437\u0430\u043A\u0446\u0438\u044F\u043B\u0430\u0440\u0434\u044B 50+ \u0441\u0430\u043D\u0430\u0442\u049B\u0430 \u0430\u0432\u0442\u043E\u043C\u0430\u0442\u0442\u044B \u043A\u0430\u0442\u0435\u0433\u043E\u0440\u0438\u044F\u043B\u0430\u0443",
          "10 \u043C\u043E\u0434\u0443\u043B\u044C\u0434\u0456 \u0430\u043B\u0430\u044F\u049B\u0442\u044B\u049B \u0434\u0435\u0442\u0435\u043A\u0442\u043E\u0440\u044B (velocity analysis, graph analysis, behavioral analysis, structuring detection, cross-reference analysis, merchant risk, night transactions, duplicate payments, round amounts, profile mismatch)",
          "\u041D\u0430\u049B\u0442\u044B \u0443\u0430\u049B\u044B\u0442 \u0440\u0435\u0436\u0438\u043C\u0456\u043D\u0434\u0435 WebSocket \u0430\u0440\u049B\u044B\u043B\u044B \u0442\u0430\u043B\u0434\u0430\u0443 \u043F\u0440\u043E\u0433\u0440\u0435\u0441\u0456\u043D \u0431\u0430\u049B\u044B\u043B\u0430\u0443",
          "\u041A\u04E9\u043F \u0442\u0456\u043B\u0434\u0456 \u0438\u043D\u0442\u0435\u0440\u0444\u0435\u0439\u0441 (\u049B\u0430\u0437\u0430\u049B, \u043E\u0440\u044B\u0441, \u0430\u0493\u044B\u043B\u0448\u044B\u043D)",
          "PDF \u0435\u0441\u0435\u043F \u0433\u0435\u043D\u0435\u0440\u0430\u0446\u0438\u044F\u0441\u044B",
          "\u041F\u0430\u0439\u0434\u0430\u043B\u0430\u043D\u0443\u0448\u044B\u043B\u0430\u0440\u0434\u044B \u0431\u0430\u0441\u049B\u0430\u0440\u0443 \u0436\u04AF\u0439\u0435\u0441\u0456 (\u0440\u04E9\u043B\u0434\u0435\u0440: admin, analyst, viewer)",
          "\u049A\u0430\u0443\u0456\u043F\u0441\u0456\u0437 \u0430\u0443\u0442\u0435\u043D\u0442\u0438\u0444\u0438\u043A\u0430\u0446\u0438\u044F (JWT \u0442\u043E\u043A\u0435\u043D\u0434\u0435\u0440, email \u0432\u0435\u0440\u0438\u0444\u0438\u043A\u0430\u0446\u0438\u044F)",
          "\u041A\u0456\u0440\u0443 \u0442\u0430\u0440\u0438\u0445\u044B \u0436\u04D9\u043D\u0435 \u0441\u0435\u0441\u0441\u0438\u044F \u0431\u0430\u049B\u044B\u043B\u0430\u0443",
        ].map(
          (text) =>
            new Paragraph({
              numbering: { reference: "dash-bullets", level: 0 },
              spacing: { before: 40, after: 40 },
              children: [new TextRun({ text, font: "Times New Roman", size: 24 })],
            })
        ),

        // Spacer
        new Paragraph({ spacing: { before: 120, after: 60 }, children: [] }),

        // Негізгі техникалық сипаттамалары
        boldPara("\u041D\u0435\u0433\u0456\u0437\u0433\u0456 \u0442\u0435\u0445\u043D\u0438\u043A\u0430\u043B\u044B\u049B \u0441\u0438\u043F\u0430\u0442\u0442\u0430\u043C\u0430\u043B\u0430\u0440\u044B:"),

        ...[
          "Клиент-сервер архитектурасы (REST API + WebSocket)",
          "Backend: Python 3.11, FastAPI, SQLAlchemy ORM, Celery, Redis",
          "Frontend: React 18, TypeScript, Vite",
          "\u0414\u0435\u0440\u0435\u043A\u049B\u043E\u0440: PostgreSQL",
          "\u0416\u0430\u0441\u0430\u043D\u0434\u044B \u0438\u043D\u0442\u0435\u043B\u043B\u0435\u043A\u0442: Claude API (Anthropic), Ollama (\u0436\u0435\u0440\u0433\u0456\u043B\u0456\u043A\u0442\u0456 LLM)",
          "\u049A\u0430\u0443\u0456\u043F\u0441\u0456\u0437\u0434\u0456\u043A: JWT \u0430\u0443\u0442\u0435\u043D\u0442\u0438\u0444\u0438\u043A\u0430\u0446\u0438\u044F, bcrypt \u0445\u044D\u0448\u0442\u0435\u0443, CORS, HTTPS",
          "\u041A\u043E\u043D\u0442\u0435\u0439\u043D\u0435\u0440\u0438\u0437\u0430\u0446\u0438\u044F: Docker, Railway.app \u0441\u0435\u0440\u0432\u0435\u0440\u0456\u043D\u0434\u0435 \u043E\u0440\u043D\u0430\u043B\u0430\u0441\u0442\u044B\u0440\u044B\u043B\u0493\u0430\u043D",
        ].map(
          (text) =>
            new Paragraph({
              numbering: { reference: "dash-bullets", level: 0 },
              spacing: { before: 40, after: 40 },
              children: [new TextRun({ text, font: "Times New Roman", size: 24 })],
            })
        ),

        // Spacer
        new Paragraph({ spacing: { before: 120, after: 60 }, children: [] }),

        // Бағдарламалау тілі
        labeledField(
          "\u0411\u0430\u0493\u0434\u0430\u0440\u043B\u0430\u043C\u0430\u043B\u0430\u0443 \u0442\u0456\u043B\u0456: ",
          "Python 3.11, TypeScript 5.x, JavaScript (ES2022), SQL, HTML5, CSS3"
        ),

        // Spacer
        new Paragraph({ spacing: { before: 120, after: 60 }, children: [] }),

        // ЭЕМ жүзеге асырушы
        boldPara("\u042D\u0415\u041C \u0436\u04AF\u0437\u0435\u0433\u0435 \u0430\u0441\u044B\u0440\u0443\u0448\u044B:"),

        ...[
          "\u041E\u043F\u0435\u0440\u0430\u0446\u0438\u044F\u043B\u044B\u049B \u0436\u04AF\u0439\u0435: Windows 10/11, Linux (Ubuntu 20.04+), macOS 12+",
          "\u041F\u0440\u043E\u0446\u0435\u0441\u0441\u043E\u0440: Intel Core i5 / AMD Ryzen 5 \u043D\u0435\u043C\u0435\u0441\u0435 \u043E\u0434\u0430\u043D \u0436\u043E\u0493\u0430\u0440\u044B",
          "\u0416\u0435\u0434\u0435\u043B \u0436\u0430\u0434\u044B (RAM): 4 \u0413\u0411 \u043C\u0438\u043D\u0438\u043C\u0443\u043C, 8 \u0413\u0411 \u04B1\u0441\u044B\u043D\u044B\u043B\u0430\u0434\u044B",
          "\u049A\u0430\u0442\u0442\u044B \u0434\u0438\u0441\u043A: 1 \u0413\u0411 \u0431\u043E\u0441 \u043E\u0440\u044B\u043D",
          "\u0411\u0440\u0430\u0443\u0437\u0435\u0440: Google Chrome 90+, Firefox 90+, Safari 15+, Edge 90+",
          "\u0418\u043D\u0442\u0435\u0440\u043D\u0435\u0442 \u0431\u0430\u0439\u043B\u0430\u043D\u044B\u0441\u044B \u049B\u0430\u0436\u0435\u0442 (\u0441\u0435\u0440\u0432\u0435\u0440\u043B\u0456\u043A \u043D\u04B1\u0441\u049B\u0430 \u04AF\u0448\u0456\u043D)",
        ].map(
          (text) =>
            new Paragraph({
              numbering: { reference: "dash-bullets", level: 0 },
              spacing: { before: 40, after: 40 },
              children: [new TextRun({ text, font: "Times New Roman", size: 24 })],
            })
        ),
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync("C:\\Users\\Admin\\Desktop\\FinancialAnalysisSystem\\ntFAST_Referat_Copyright.docx", buffer);
  console.log("Document created successfully.");
});
