const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        AlignmentType, WidthType, BorderStyle, ShadingType, Footer, PageNumber } = require('docx');
const fs = require('fs');

const F = "Times New Roman";
const SZ = 22; // 11pt
const SZ_SM = 18; // 9pt
const SZ_TITLE = 24; // 12pt

const noBorder = { style: BorderStyle.NONE, size: 0 };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };
const thinBorder = { style: BorderStyle.SINGLE, size: 1, color: "000000" };
const borders = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder };

const cell = (text, opts = {}) => new TableCell({
  borders: opts.noBorder ? noBorders : borders,
  width: opts.width ? { size: opts.width, type: WidthType.DXA } : undefined,
  columnSpan: opts.colspan || 1,
  rowSpan: opts.rowspan || 1,
  verticalAlign: opts.valign || "center",
  margins: { top: 40, bottom: 40, left: 80, right: 80 },
  shading: opts.shading ? { fill: opts.shading, type: ShadingType.CLEAR } : undefined,
  children: Array.isArray(text) ? text : [
    new Paragraph({
      alignment: opts.align || AlignmentType.LEFT,
      spacing: { after: 0, before: 0, line: 240 },
      children: typeof text === 'string' ? [new TextRun({
        text, font: F, size: opts.size || SZ,
        bold: opts.bold || false, italics: opts.italic || false
      })] : [text]
    })
  ]
});

const emptyCell = (opts = {}) => cell("", opts);

const headerCell = (text, opts = {}) => cell(text, { ...opts, bold: true, align: AlignmentType.CENTER, shading: "F0F0F0" });

const smallText = (text, opts = {}) => new Paragraph({
  alignment: opts.align || AlignmentType.LEFT,
  spacing: { after: opts.after || 0, before: opts.before || 0, line: 220 },
  children: [new TextRun({ text, font: F, size: opts.size || SZ_SM, bold: opts.bold || false, italics: opts.italic || false })]
});

const normalText = (text, opts = {}) => new Paragraph({
  alignment: opts.align || AlignmentType.LEFT,
  spacing: { after: opts.after || 60, before: opts.before || 0, line: 240 },
  indent: opts.indent ? { firstLine: 400 } : undefined,
  children: Array.isArray(text) ? text : [new TextRun({ text, font: F, size: opts.size || SZ, bold: opts.bold || false })]
});

const centeredText = (text, opts = {}) => normalText(text, { ...opts, align: AlignmentType.CENTER });

// Page width: A4 = 11906 DXA, margins 1134 each side = 9638 content width
const PAGE_W = 11906;
const MARGIN = 1134;
const CONTENT_W = PAGE_W - MARGIN * 2; // 9638

const doc = new Document({
  styles: {
    default: { document: { run: { font: F, size: SZ } } }
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: PAGE_W, height: 16838 },
          margin: { top: 1134, right: 1134, bottom: 1134, left: 1418 } // left slightly wider for binding
        }
      },
      children: [
        // === HEADER: Form designation ===
        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [CONTENT_W * 0.6, CONTENT_W * 0.4],
          rows: [
            new TableRow({
              children: [
                cell([
                  smallText("Қазақстан Республикасы", { bold: true, align: AlignmentType.CENTER }),
                  smallText("Әділет министрлігі", { align: AlignmentType.CENTER }),
                  smallText("Зияткерлік меншік құқығы саласындағы", { align: AlignmentType.CENTER }),
                  smallText("уәкілетті орган", { align: AlignmentType.CENTER }),
                ], { noBorder: true, width: CONTENT_W * 0.6 }),
                cell([
                  smallText("ПМ-1 нысаны", { bold: true, align: AlignmentType.RIGHT }),
                  smallText("(форма ПМ-1)", { italic: true, align: AlignmentType.RIGHT, size: SZ_SM }),
                ], { noBorder: true, width: CONTENT_W * 0.4, align: AlignmentType.RIGHT })
              ]
            })
          ]
        }),

        normalText(""),

        // === TITLE ===
        centeredText("ПАЙДАЛЫ МОДЕЛЬГЕ ПАТЕНТ БЕРУГЕ ӨТІНІМ", { bold: true, size: 26, after: 20 }),
        centeredText("ЗАЯВЛЕНИЕ О ВЫДАЧЕ ПАТЕНТА НА ПОЛЕЗНУЮ МОДЕЛЬ", { italic: true, size: SZ_SM, after: 200 }),

        // === Registration fields (filled by NIIS) ===
        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [CONTENT_W * 0.5, CONTENT_W * 0.5],
          rows: [
            new TableRow({
              children: [
                cell([
                  smallText("Кіріс №  ____________________", { size: SZ }),
                  smallText("(Входящий №)"),
                ], { width: CONTENT_W * 0.5 }),
                cell([
                  smallText("Өтінім берілген күні  ____________________", { size: SZ }),
                  smallText("(Дата подачи заявки)"),
                ], { width: CONTENT_W * 0.5 })
              ]
            })
          ]
        }),

        normalText("", { after: 120 }),

        // === 1. Applicant (Өтініш беруші) ===
        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [CONTENT_W],
          rows: [
            new TableRow({
              children: [
                headerCell("(71) Өтініш беруші(лер) / Заявитель(и)")
              ]
            }),
            new TableRow({
              children: [
                cell([
                  normalText("Тажи Нурдаулет", { size: SZ_TITLE, bold: true }),
                  normalText(""),
                  smallText("Мекенжайы / Адрес:"),
                  normalText("Қазақстан Республикасы, Астана қ.", { size: SZ }),
                  normalText(""),
                  smallText("Телефон: _______________  Факс: _______________  E-mail: nurdaulet.tazhi@mail.ru"),
                ], { width: CONTENT_W })
              ]
            })
          ]
        }),

        normalText("", { after: 80 }),

        // === 2. Author (Автор) ===
        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [CONTENT_W],
          rows: [
            new TableRow({
              children: [
                headerCell("(72) Автор(лар) / Автор(ы)")
              ]
            }),
            new TableRow({
              children: [
                cell([
                  normalText("Тажи Нурдаулет", { size: SZ_TITLE, bold: true }),
                  normalText(""),
                  smallText("Мекенжайы / Адрес:"),
                  normalText("Қазақстан Республикасы, Астана қ.", { size: SZ }),
                ], { width: CONTENT_W })
              ]
            })
          ]
        }),

        normalText("", { after: 80 }),

        // === 3. Title of invention ===
        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [CONTENT_W],
          rows: [
            new TableRow({
              children: [
                headerCell("(54) Пайдалы модельдің атауы / Название полезной модели")
              ]
            }),
            new TableRow({
              children: [
                cell([
                  normalText("Қаржылық транзакцияларды талдау және алаяқтық әрекеттерді анықтау жүйесі", { size: SZ_TITLE, bold: true }),
                  normalText("(ntFAST — Financial Analysis System for Transactions)", { italic: true, size: SZ }),
                  normalText(""),
                  normalText("Система анализа финансовых транзакций и выявления мошеннических действий", { italic: true, size: SZ_SM }),
                ], { width: CONTENT_W })
              ]
            })
          ]
        }),

        normalText("", { after: 80 }),

        // === 4. Address for correspondence ===
        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [CONTENT_W],
          rows: [
            new TableRow({
              children: [
                headerCell("Хат-хабар алуға арналған мекенжай / Адрес для переписки")
              ]
            }),
            new TableRow({
              children: [
                cell([
                  normalText("Қазақстан Республикасы, Астана қ.", { size: SZ }),
                  normalText(""),
                  smallText("Телефон: _______________  E-mail: nurdaulet.tazhi@mail.ru"),
                ], { width: CONTENT_W })
              ]
            })
          ]
        }),

        normalText("", { after: 80 }),

        // === 5. Patent attorney (if any) ===
        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [CONTENT_W],
          rows: [
            new TableRow({
              children: [
                headerCell("Патенттік сенімхат иесі / Патентный поверенный")
              ]
            }),
            new TableRow({
              children: [
                cell([
                  normalText("жоқ / не имеется", { italic: true, size: SZ }),
                ], { width: CONTENT_W })
              ]
            })
          ]
        }),

        normalText("", { after: 80 }),

        // === 6. Priority request ===
        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [CONTENT_W],
          rows: [
            new TableRow({
              children: [
                headerCell("Басымдық сұратылады / Испрашивается приоритет")
              ]
            }),
            new TableRow({
              children: [
                cell([
                  normalText([
                    new TextRun({ text: "Өтінім берілген күні бойынша басымдық", font: F, size: SZ }),
                  ]),
                  smallText("(Приоритет по дате подачи заявки)"),
                ], { width: CONTENT_W })
              ]
            })
          ]
        }),

        normalText("", { after: 80 }),

        // === 7. MPK (IPC classification) ===
        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [CONTENT_W],
          rows: [
            new TableRow({
              children: [
                headerCell("(51) ПМЖ (МПК) / IPC")
              ]
            }),
            new TableRow({
              children: [
                cell([
                  normalText("G06Q 20/40 (2012.01) — Қаржылық мәліметтерді тексеру, мысалы, алаяқтық", { size: SZ }),
                  normalText("G06F 21/55 (2013.01) — Жүйеге кіруді анықтау; зиянды бағдарламаларды анықтау", { size: SZ }),
                  normalText("G06N 20/00 (2019.01) — Машиналық оқыту", { size: SZ }),
                ], { width: CONTENT_W })
              ]
            })
          ]
        }),

        normalText("", { after: 80 }),

        // === 8. Documents list ===
        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [CONTENT_W * 0.6, CONTENT_W * 0.2, CONTENT_W * 0.2],
          rows: [
            new TableRow({
              children: [
                headerCell("Құжаттар тізімі / Перечень документов", { width: CONTENT_W * 0.6 }),
                headerCell("Парақтар саны / Кол-во листов", { width: CONTENT_W * 0.2 }),
                headerCell("Данасы / Экз.", { width: CONTENT_W * 0.2 }),
              ]
            }),
            new TableRow({
              children: [
                cell("Өтінім / Заявление (ПМ-1)", { width: CONTENT_W * 0.6 }),
                cell("2", { width: CONTENT_W * 0.2, align: AlignmentType.CENTER }),
                cell("2", { width: CONTENT_W * 0.2, align: AlignmentType.CENTER }),
              ]
            }),
            new TableRow({
              children: [
                cell("Пайдалы модельдің сипаттамасы / Описание полезной модели", { width: CONTENT_W * 0.6 }),
                cell("15", { width: CONTENT_W * 0.2, align: AlignmentType.CENTER }),
                cell("2", { width: CONTENT_W * 0.2, align: AlignmentType.CENTER }),
              ]
            }),
            new TableRow({
              children: [
                cell("Пайдалы модельдің формуласы / Формула полезной модели", { width: CONTENT_W * 0.6 }),
                cell("2", { width: CONTENT_W * 0.2, align: AlignmentType.CENTER }),
                cell("2", { width: CONTENT_W * 0.2, align: AlignmentType.CENTER }),
              ]
            }),
            new TableRow({
              children: [
                cell("Реферат / Реферат", { width: CONTENT_W * 0.6 }),
                cell("1", { width: CONTENT_W * 0.2, align: AlignmentType.CENTER }),
                cell("2", { width: CONTENT_W * 0.2, align: AlignmentType.CENTER }),
              ]
            }),
            new TableRow({
              children: [
                cell("Сызбалар / Чертежи (блок-схема)", { width: CONTENT_W * 0.6 }),
                cell("1", { width: CONTENT_W * 0.2, align: AlignmentType.CENTER }),
                cell("2", { width: CONTENT_W * 0.2, align: AlignmentType.CENTER }),
              ]
            }),
            new TableRow({
              children: [
                cell("Баж салығын төлегенін растайтын құжат / Документ об оплате пошлины", { width: CONTENT_W * 0.6 }),
                cell("1", { width: CONTENT_W * 0.2, align: AlignmentType.CENTER }),
                cell("1", { width: CONTENT_W * 0.2, align: AlignmentType.CENTER }),
              ]
            }),
          ]
        }),

        normalText("", { after: 80 }),

        // === 9. Signature section ===
        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [CONTENT_W],
          rows: [
            new TableRow({
              children: [
                headerCell("Қолы / Подпись")
              ]
            }),
            new TableRow({
              children: [
                cell([
                  normalText(""),
                  normalText([
                    new TextRun({ text: "Өтініш беруші: ", font: F, size: SZ }),
                    new TextRun({ text: "Тажи Нурдаулет", font: F, size: SZ, bold: true }),
                  ]),
                  normalText(""),
                  normalText("Қолы: _________________________"),
                  normalText(""),
                  normalText("Күні / Дата: «____» ________________ 2026 ж."),
                  normalText(""),
                ], { width: CONTENT_W })
              ]
            })
          ]
        }),

        normalText("", { after: 200 }),

        // === FOOTER NOTE ===
        smallText("Ескертпе: Өтінімге қоса берілетін құжаттар екі данада ұсынылады.", { italic: true }),
        smallText("Примечание: Документы, прилагаемые к заявке, представляются в двух экземплярах.", { italic: true }),
      ],

      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({ text: "— ", font: F, size: SZ_SM }),
                new TextRun({ children: [PageNumber.CURRENT], font: F, size: SZ_SM }),
                new TextRun({ text: " —", font: F, size: SZ_SM }),
              ]
            })
          ]
        })
      }
    }
  ]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("ntFAST_PM1_Application.docx", buffer);
  console.log("OK: PM-1 Application form created");
});
