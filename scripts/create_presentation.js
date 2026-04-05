const pptxgen = require("pptxgenjs");

// Color palette
const C = {
  navy: "1B2A4A",
  darkNavy: "0F1B33",
  accent: "3B82F6",
  gold: "F59E0B",
  white: "FFFFFF",
  offWhite: "F8FAFC",
  lightGray: "E2E8F0",
  midGray: "94A3B8",
  text: "1E293B",
  textSec: "64748B",
  green: "10B981",
  red: "EF4444",
  orange: "F97316",
  purple: "8B5CF6",
  teal: "14B8A6",
};

const SW = 10;    // slide width
const SH = 5.625; // slide height

function makeShadow() {
  return { type: "outer", blur: 3, offset: 1, angle: 135, color: "000000", opacity: 0.1 };
}

async function main() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.author = "ntFAST";
  pres.title = "ntFAST - Diploma Presentation";

  // ============================================================
  // SLIDE 1 — TITLE
  // ============================================================
  let s1 = pres.addSlide();
  s1.background = { color: C.darkNavy };
  s1.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: SW, h: 0.05, fill: { color: C.gold } });

  s1.addText("ДИПЛОМДЫҚ ЖҰМЫС", {
    x: 1, y: 1.0, w: 8, h: 0.5,
    fontSize: 14, fontFace: "Calibri", color: C.gold,
    charSpacing: 6, align: "center", bold: true
  });
  s1.addText("ntFAST", {
    x: 1, y: 1.5, w: 8, h: 0.8,
    fontSize: 48, fontFace: "Arial Black", color: C.white, align: "center"
  });
  s1.addText("Қаржылық транзакцияларды талдау және\nалаяқтықты анықтау жүйесі", {
    x: 1.5, y: 2.4, w: 7, h: 0.7,
    fontSize: 16, fontFace: "Calibri", color: C.lightGray, align: "center"
  });
  s1.addShape(pres.shapes.LINE, { x: 3.5, y: 3.3, w: 3, h: 0, line: { color: C.gold, width: 1 } });
  s1.addText([
    { text: "Орындаған: [Студент аты-жөні]", options: { breakLine: true } },
    { text: "Ғылыми жетекші: [Жетекші аты-жөні]", options: { breakLine: true } },
    { text: "Мамандық: [Мамандық коды және атауы]", options: {} },
  ], {
    x: 2, y: 3.55, w: 6, h: 1.1,
    fontSize: 12, fontFace: "Calibri", color: C.midGray, align: "center",
    paraSpaceAfter: 4
  });
  s1.addText("2026", {
    x: 1, y: 5.1, w: 8, h: 0.3,
    fontSize: 11, fontFace: "Calibri", color: C.midGray, align: "center"
  });

  // ============================================================
  // HELPER — content slide header
  // ============================================================
  function header(slide, title) {
    slide.background = { color: C.offWhite };
    slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: SW, h: 0.75, fill: { color: C.navy } });
    slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0.75, w: SW, h: 0.035, fill: { color: C.gold } });
    slide.addText(title, {
      x: 0.6, y: 0.1, w: 8.8, h: 0.55,
      fontSize: 20, fontFace: "Arial Black", color: C.white, valign: "middle"
    });
    slide.addText("ntFAST  |  Дипломдық жұмыс", {
      x: 0.5, y: 5.25, w: 4, h: 0.25,
      fontSize: 7, fontFace: "Calibri", color: C.midGray
    });
  }

  function card(slide, x, y, w, h, accent) {
    slide.addShape(pres.shapes.RECTANGLE, {
      x, y, w, h, fill: { color: C.white }, shadow: makeShadow()
    });
    if (accent) {
      slide.addShape(pres.shapes.RECTANGLE, {
        x, y, w: 0.05, h, fill: { color: accent }
      });
    }
  }

  function numCircle(slide, x, y, num, color) {
    slide.addShape(pres.shapes.OVAL, { x, y, w: 0.38, h: 0.38, fill: { color: color || C.accent } });
    slide.addText(String(num), {
      x, y, w: 0.38, h: 0.38,
      fontSize: 13, fontFace: "Arial Black", color: C.white, align: "center", valign: "middle"
    });
  }

  // ============================================================
  // SLIDE 2 — RELEVANCE
  // ============================================================
  let s2 = pres.addSlide();
  header(s2, "ӨЗЕКТІЛІГІ");

  const relItems = [
    "Қазақстанда цифрлық төлемдер көлемі жыл сайын 40%+ өсуде",
    "Kaspi, Halyk банктеріндегі онлайн транзакциялар саны күрт артуда",
    "Қаржылық алаяқтық пен ақша жылыстату қаупі артуда",
    "Қолмен талдау — баяу, қателікке бейім, субъективті",
    "Автоматтандырылған интеллектуалды жүйе қажеттілігі туындауда",
    "AML/CFT халықаралық стандарттарға сай болу талабы",
  ];

  relItems.forEach((txt, i) => {
    const yy = 1.1 + i * 0.68;
    card(s2, 0.6, yy, 8.8, 0.55, C.accent);
    numCircle(s2, 0.85, yy + 0.08, i + 1, C.accent);
    s2.addText(txt, {
      x: 1.4, y: yy + 0.05, w: 7.8, h: 0.45,
      fontSize: 13, fontFace: "Calibri", color: C.text, valign: "middle"
    });
  });

  // ============================================================
  // SLIDE 3 — PURPOSE
  // ============================================================
  let s3 = pres.addSlide();
  header(s3, "ЖҰМЫСТЫҢ МАҚСАТЫ");

  // Main purpose
  card(s3, 0.6, 1.1, 8.8, 1.1, C.gold);
  s3.addText("Банктік үзінділерді автоматты түрде талдайтын, алаяқтық белгілерін анықтайтын және тәуекел деңгейін бағалайтын интеллектуалды веб-жүйе әзірлеу", {
    x: 0.85, y: 1.15, w: 8.35, h: 1.0,
    fontSize: 14, fontFace: "Calibri", color: C.text, valign: "middle", bold: true
  });

  // Three sub-goals
  const goals = [
    { title: "Rule-Based Detection", desc: "11 модульді ереже негізіндегі фрод-детекция жүйесін құру", color: C.accent },
    { title: "AI Integration", desc: "Жасанды интеллект арқылы талдау нәтижелерін түсіндіру", color: C.purple },
    { title: "Web Application", desc: "Көп тілді, қауіпсіз, масштабталатын веб-қосымша жасау", color: C.teal },
  ];

  goals.forEach((g, i) => {
    const xx = 0.6 + i * 3.1;
    card(s3, xx, 2.6, 2.85, 2.3, g.color);
    s3.addShape(pres.shapes.RECTANGLE, { x: xx + 0.05, y: 2.6, w: 2.8, h: 0.5, fill: { color: g.color } });
    s3.addText(g.title, {
      x: xx + 0.15, y: 2.62, w: 2.55, h: 0.45,
      fontSize: 13, fontFace: "Arial Black", color: C.white, align: "center", valign: "middle"
    });
    s3.addText(g.desc, {
      x: xx + 0.2, y: 3.25, w: 2.45, h: 1.5,
      fontSize: 12, fontFace: "Calibri", color: C.text, align: "center", valign: "top"
    });
  });

  // ============================================================
  // SLIDE 4 — TASKS
  // ============================================================
  let s4 = pres.addSlide();
  header(s4, "ДИПЛОМДЫҚ ЖҰМЫСТЫҢ МІНДЕТТЕРІ");

  const tasks = [
    "Қаржылық алаяқтық түрлерін және анықтау әдістерін зерттеу",
    "Банктік үзінділерді автоматты талдау алгоритмдерін әзірлеу",
    "11 rule-based фрод-детекция модулін жобалау және іске асыру",
    "Жасанды интеллект (Claude AI / Ollama) интеграциясын жүзеге асыру",
    "Көп тілді (қаз/рус/ағыл) веб-интерфейс жасау",
    "Жүйені нақты банктік деректерде тестілеу және нәтижелерді бағалау",
  ];

  tasks.forEach((t, i) => {
    const yy = 1.1 + i * 0.7;
    numCircle(s4, 0.8, yy + 0.09, i + 1, C.navy);
    s4.addText(t, {
      x: 1.35, y: yy + 0.05, w: 8, h: 0.45,
      fontSize: 13, fontFace: "Calibri", color: C.text, valign: "middle"
    });
    if (i < tasks.length - 1) {
      s4.addShape(pres.shapes.LINE, {
        x: 0.99, y: yy + 0.47, w: 0, h: 0.23,
        line: { color: C.lightGray, width: 2 }
      });
    }
  });

  // ============================================================
  // SLIDE 5 — THREE CHAPTERS
  // ============================================================
  let s5 = pres.addSlide();
  header(s5, "ДИПЛОМДЫҚ ЖҰМЫС ҮШ ТАРАУДАН ТҰРАДЫ");

  const chapters = [
    {
      num: "I", title: "ТЕОРИЯЛЫҚ\nНЕГІЗДЕР", color: C.accent,
      items: "Қаржылық алаяқтық түрлері\nAML/CFT стандарттары\nRule-based детекция\nҚолданыстағы шешімдерге шолу"
    },
    {
      num: "II", title: "ЖОБАЛАУ ЖӘНЕ\nӘЗІРЛЕУ", color: C.gold,
      items: "Архитектура, тех. стек\nФрод-детекция модульдері\nAI интеграциясы\nДеректер қоры құрылымы"
    },
    {
      num: "III", title: "ТЕСТІЛЕУ ЖӘНЕ\nНӘТИЖЕЛЕР", color: C.green,
      items: "Нақты деректерде тестілеу\nМодульдер тиімділігі\nСалыстырмалы талдау\nҚорытынды ұсыныстар"
    },
  ];

  chapters.forEach((ch, i) => {
    const xx = 0.5 + i * 3.15;
    // Card background
    s5.addShape(pres.shapes.RECTANGLE, {
      x: xx, y: 1.1, w: 2.95, h: 4.0, fill: { color: C.white }, shadow: makeShadow()
    });
    // Colored top section
    s5.addShape(pres.shapes.RECTANGLE, {
      x: xx, y: 1.1, w: 2.95, h: 1.5, fill: { color: ch.color }
    });
    // Roman numeral
    s5.addText(ch.num, {
      x: xx, y: 1.15, w: 2.95, h: 0.6,
      fontSize: 28, fontFace: "Arial Black", color: C.white, align: "center", valign: "middle"
    });
    // Chapter title
    s5.addText(ch.title, {
      x: xx + 0.15, y: 1.8, w: 2.65, h: 0.7,
      fontSize: 11, fontFace: "Arial Black", color: C.white, align: "center", valign: "middle"
    });
    // Items
    s5.addText(ch.items.split("\n").map((item, j, arr) => ({
      text: item,
      options: { bullet: true, breakLine: j < arr.length - 1 }
    })), {
      x: xx + 0.2, y: 2.75, w: 2.55, h: 2.2,
      fontSize: 11, fontFace: "Calibri", color: C.text, paraSpaceAfter: 6
    });
  });

  // ============================================================
  // SLIDE 6 — ARCHITECTURE
  // ============================================================
  let s6 = pres.addSlide();
  header(s6, "ЖҮЙЕ АРХИТЕКТУРАСЫ");

  const layers = [
    { label: "FRONTEND", tech: "React 18  +  TypeScript  +  Tailwind CSS  +  Vite 5", color: C.accent },
    { label: "WEBSOCKET", tech: "Нақты уақыт  |  Прогресс  |  Онлайн статус  |  Хабарламалар", color: C.teal },
    { label: "BACKEND API", tech: "FastAPI  +  SQLAlchemy ORM  +  Pydantic  +  JWT Auth", color: C.navy },
    { label: "SERVICES", tech: "FraudEngine (11 mod)  |  BankParser  |  AI Manager  |  Celery + Redis", color: C.purple },
    { label: "DATABASE", tech: "PostgreSQL  |  5 кесте  |  JSON fields  |  Full-text search", color: C.gold },
  ];

  layers.forEach((l, i) => {
    const yy = 1.1 + i * 0.82;
    s6.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y: yy, w: 9, h: 0.65, fill: { color: l.color }, shadow: makeShadow()
    });
    s6.addText(l.label, {
      x: 0.7, y: yy + 0.05, w: 2.2, h: 0.55,
      fontSize: 13, fontFace: "Arial Black", color: C.white, valign: "middle"
    });
    s6.addText(l.tech, {
      x: 2.9, y: yy + 0.05, w: 6.4, h: 0.55,
      fontSize: 11, fontFace: "Calibri", color: C.white, valign: "middle"
    });
  });

  // ============================================================
  // SLIDE 7 — DATABASE
  // ============================================================
  let s7 = pres.addSlide();
  header(s7, "ДЕРЕКТЕР ҚОРЫ ҚҰРЫЛЫМЫ");

  const tables = [
    { name: "Users", fields: "id, email, role,\nis_online, last_login", color: C.accent },
    { name: "Analyses", fields: "id, subject_id, status,\nfraud_score, risk_level", color: C.navy },
    { name: "Transactions", fields: "id, analysis_id, amount,\ncounterparty, category", color: C.gold },
  ];
  const tables2 = [
    { name: "Subjects", fields: "id, name, iin_bin,\ntype, risk_level", color: C.green },
    { name: "LoginHistory", fields: "id, user_id, ip,\nuser_agent, login_time", color: C.purple },
  ];

  tables.forEach((t, i) => {
    const xx = 0.5 + i * 3.15;
    s7.addShape(pres.shapes.RECTANGLE, { x: xx, y: 1.1, w: 2.9, h: 1.7, fill: { color: C.white }, shadow: makeShadow() });
    s7.addShape(pres.shapes.RECTANGLE, { x: xx, y: 1.1, w: 2.9, h: 0.45, fill: { color: t.color } });
    s7.addText(t.name, {
      x: xx, y: 1.1, w: 2.9, h: 0.45,
      fontSize: 14, fontFace: "Arial Black", color: C.white, align: "center", valign: "middle"
    });
    s7.addText(t.fields, {
      x: xx + 0.15, y: 1.65, w: 2.6, h: 1.0,
      fontSize: 10, fontFace: "Calibri", color: C.text
    });
  });

  tables2.forEach((t, i) => {
    const xx = 2.05 + i * 3.15;
    s7.addShape(pres.shapes.RECTANGLE, { x: xx, y: 3.1, w: 2.9, h: 1.7, fill: { color: C.white }, shadow: makeShadow() });
    s7.addShape(pres.shapes.RECTANGLE, { x: xx, y: 3.1, w: 2.9, h: 0.45, fill: { color: t.color } });
    s7.addText(t.name, {
      x: xx, y: 3.1, w: 2.9, h: 0.45,
      fontSize: 14, fontFace: "Arial Black", color: C.white, align: "center", valign: "middle"
    });
    s7.addText(t.fields, {
      x: xx + 0.15, y: 3.65, w: 2.6, h: 1.0,
      fontSize: 10, fontFace: "Calibri", color: C.text
    });
  });

  // ============================================================
  // SLIDE 8 — FILE PROCESSING PIPELINE
  // ============================================================
  let s8 = pres.addSlide();
  header(s8, "ФАЙЛДЫ ӨҢДЕУ ПРОЦЕСІ");

  const pipeline = [
    { n: "1", t: "Файл жүктеу\n(PDF/XLSX/CSV)", c: C.accent },
    { n: "2", t: "Банк типін\nанықтау", c: C.navy },
    { n: "3", t: "Транзакцияларды\nпарсинг", c: C.teal },
    { n: "4", t: "Категориялау", c: C.green },
    { n: "5", t: "Қаржылық\nаналитика", c: C.purple },
    { n: "6", t: "Фрод-детекция\n(11 модуль)", c: C.red },
    { n: "7", t: "AI талдау\nмен баяндама", c: C.gold },
    { n: "8", t: "Нәтижелерді\nсақтау", c: C.green },
  ];

  // Two rows of 4
  pipeline.forEach((p, i) => {
    const row = Math.floor(i / 4);
    const col = i % 4;
    const xx = 0.5 + col * 2.35;
    const yy = 1.2 + row * 2.0;

    s8.addShape(pres.shapes.RECTANGLE, {
      x: xx, y: yy, w: 2.0, h: 1.5, fill: { color: C.white }, shadow: makeShadow()
    });
    // Number circle
    s8.addShape(pres.shapes.OVAL, {
      x: xx + 0.75, y: yy + 0.12, w: 0.5, h: 0.5, fill: { color: p.c }
    });
    s8.addText(p.n, {
      x: xx + 0.75, y: yy + 0.12, w: 0.5, h: 0.5,
      fontSize: 16, fontFace: "Arial Black", color: C.white, align: "center", valign: "middle"
    });
    s8.addText(p.t, {
      x: xx + 0.1, y: yy + 0.75, w: 1.8, h: 0.65,
      fontSize: 11, fontFace: "Calibri", color: C.text, align: "center", valign: "top"
    });

    // Arrow
    if (col < 3) {
      s8.addText("\u2192", {
        x: xx + 2.0, y: yy + 0.5, w: 0.35, h: 0.4,
        fontSize: 18, color: C.midGray, align: "center", valign: "middle"
      });
    }
  });

  // Down arrow between rows
  s8.addText("\u2193", {
    x: 8.3, y: 2.75, w: 0.4, h: 0.4,
    fontSize: 20, color: C.midGray, align: "center"
  });

  // ============================================================
  // SLIDE 9 — FRAUD DETECTION SYSTEM
  // ============================================================
  let s9 = pres.addSlide();
  header(s9, "ФРОД-ДЕТЕКЦИЯ ЖҮЙЕСІ");

  // Pipeline boxes
  const fdSteps = [
    { l: "Account\nProfiler", c: C.accent },
    { l: "Whitelist", c: C.green },
    { l: "11 Detection\nModules", c: C.navy },
    { l: "Pattern\nDetector", c: C.purple },
    { l: "Composite\nScore", c: C.gold },
  ];

  fdSteps.forEach((f, i) => {
    const xx = 0.3 + i * 1.95;
    s9.addShape(pres.shapes.RECTANGLE, {
      x: xx, y: 1.1, w: 1.7, h: 0.95, fill: { color: f.c }, shadow: makeShadow()
    });
    s9.addText(f.l, {
      x: xx, y: 1.1, w: 1.7, h: 0.95,
      fontSize: 11, fontFace: "Arial Black", color: C.white, align: "center", valign: "middle"
    });
    if (i < 4) {
      s9.addText("\u2192", {
        x: xx + 1.65, y: 1.35, w: 0.35, h: 0.4,
        fontSize: 16, color: C.midGray, align: "center", valign: "middle"
      });
    }
  });

  // Risk levels
  s9.addText("Тәуекел деңгейлері:", {
    x: 0.5, y: 2.35, w: 3, h: 0.35,
    fontSize: 13, fontFace: "Arial Black", color: C.navy
  });

  const risks = [
    { l: "LOW", r: "0-25", c: C.green },
    { l: "MEDIUM", r: "25-50", c: C.orange },
    { l: "HIGH", r: "50-70", c: C.red },
    { l: "CRITICAL", r: "70-100", c: "991B1B" },
  ];

  risks.forEach((r, i) => {
    const xx = 0.5 + i * 2.35;
    s9.addShape(pres.shapes.RECTANGLE, {
      x: xx, y: 2.8, w: 2.1, h: 0.55, fill: { color: r.c }
    });
    s9.addText(`${r.l}  (${r.r})`, {
      x: xx, y: 2.8, w: 2.1, h: 0.55,
      fontSize: 12, fontFace: "Arial Black", color: C.white, align: "center", valign: "middle"
    });
  });

  // Key features
  const features = [
    "Контекстуалды салмақтау — аккаунт типі бойынша модуль салмақтары автоматты бейімделеді",
    "Corroboration bonus — бірнеше модуль бірдей қауіпті анықтаса, балл көтеріледі",
    "Pattern Override — жоғары сенімділікті схема табылса, минимум балл қойылады",
  ];

  features.forEach((f, i) => {
    const yy = 3.65 + i * 0.55;
    card(s9, 0.5, yy, 9, 0.45, C.accent);
    s9.addText(f, {
      x: 0.75, y: yy + 0.03, w: 8.5, h: 0.4,
      fontSize: 11, fontFace: "Calibri", color: C.text, valign: "middle"
    });
  });

  // ============================================================
  // SLIDE 10 — CORE MODULES PART 1
  // ============================================================
  let s10 = pres.addSlide();
  header(s10, "НЕГІЗГІ МОДУЛЬДЕР — 1-БӨЛІМ");

  const mods1 = [
    { name: "Velocity Analyzer", w: "15%", desc: "Жылдам транзакция серияларын анықтау, күнделікті шығын шоғырлануы, Z-score > 3.0", c: C.accent },
    { name: "Graph Analysis", w: "15%", desc: "Транзакция желісін графикалық талдау, циклдік аударымдар, hub/star паттерндер", c: C.navy },
    { name: "Structuring Detector", w: "18%", desc: "Сомаларды бөлшектеу анықтау (1М KZT-ден төмен), split groups, consecutive patterns", c: C.purple },
    { name: "Merchant Risk Scorer", w: "15%", desc: "Қауіпті мерчант категорияларын бағалау: казино, крипто, ATM, gaming", c: C.gold },
  ];

  mods1.forEach((m, i) => {
    const yy = 1.1 + i * 1.05;
    card(s10, 0.5, yy, 9, 0.9, m.c);
    s10.addShape(pres.shapes.OVAL, { x: 0.75, y: yy + 0.18, w: 0.55, h: 0.55, fill: { color: m.c } });
    s10.addText(m.w, {
      x: 0.75, y: yy + 0.18, w: 0.55, h: 0.55,
      fontSize: 11, fontFace: "Arial Black", color: C.white, align: "center", valign: "middle"
    });
    s10.addText(m.name, {
      x: 1.5, y: yy + 0.1, w: 7.7, h: 0.35,
      fontSize: 13, fontFace: "Arial Black", color: C.navy
    });
    s10.addText(m.desc, {
      x: 1.5, y: yy + 0.45, w: 7.7, h: 0.38,
      fontSize: 11, fontFace: "Calibri", color: C.textSec
    });
  });

  // ============================================================
  // SLIDE 11 — CORE MODULES PART 2
  // ============================================================
  let s11 = pres.addSlide();
  header(s11, "НЕГІЗГІ МОДУЛЬДЕР — 2-БӨЛІМ");

  const mods2 = [
    { name: "Pattern Detector", w: "10%", desc: "Алаяқтық схемаларын анықтау: gambling, laundering, P2P", c: C.accent },
    { name: "Cross-Reference", w: "7%", desc: "Кіріс/шығыс талдау, pass-through операциялар", c: C.navy },
    { name: "Night Transactions", w: "5%", desc: "Түнгі транзакциялар мониторингі (23:00-06:00)", c: C.purple },
    { name: "Duplicate Payments", w: "5%", desc: "Қайталанатын төлемдерді анықтау", c: C.gold },
    { name: "Round Amounts", w: "5%", desc: "Дөңгелектенген сомаларды талдау", c: C.teal },
    { name: "Profile Mismatch", w: "5%", desc: "Профильге сәйкес емес әрекеттерді табу", c: C.green },
  ];

  mods2.forEach((m, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const xx = 0.5 + col * 4.7;
    const yy = 1.1 + row * 1.35;

    card(s11, xx, yy, 4.4, 1.15, m.c);
    s11.addShape(pres.shapes.OVAL, { x: xx + 0.2, y: yy + 0.3, w: 0.5, h: 0.5, fill: { color: m.c } });
    s11.addText(m.w, {
      x: xx + 0.2, y: yy + 0.3, w: 0.5, h: 0.5,
      fontSize: 10, fontFace: "Arial Black", color: C.white, align: "center", valign: "middle"
    });
    s11.addText(m.name, {
      x: xx + 0.9, y: yy + 0.1, w: 3.2, h: 0.35,
      fontSize: 12, fontFace: "Arial Black", color: C.navy
    });
    s11.addText(m.desc, {
      x: xx + 0.9, y: yy + 0.48, w: 3.2, h: 0.55,
      fontSize: 11, fontFace: "Calibri", color: C.textSec
    });
  });

  // ============================================================
  // SLIDE 12 — CONTEXTUAL WEIGHTING
  // ============================================================
  let s12 = pres.addSlide();
  header(s12, "КОНТЕКСТУАЛДЫ САЛМАҚТАУ ЖҮЙЕСІ");

  const tblRows = [
    [
      { text: "Аккаунт типі", options: { fill: { color: C.navy }, color: C.white, bold: true, fontSize: 11, fontFace: "Arial Black", align: "center", valign: "middle" } },
      { text: "Velocity", options: { fill: { color: C.navy }, color: C.white, bold: true, fontSize: 10, align: "center", valign: "middle" } },
      { text: "Graph", options: { fill: { color: C.navy }, color: C.white, bold: true, fontSize: 10, align: "center", valign: "middle" } },
      { text: "Structuring", options: { fill: { color: C.navy }, color: C.white, bold: true, fontSize: 10, align: "center", valign: "middle" } },
      { text: "Night Tx", options: { fill: { color: C.navy }, color: C.white, bold: true, fontSize: 10, align: "center", valign: "middle" } },
      { text: "Profile", options: { fill: { color: C.navy }, color: C.white, bold: true, fontSize: 10, align: "center", valign: "middle" } },
    ],
  ];

  const dataRows = [
    ["Business Owner", "0.5x", "0.5x", "1.0x", "0.3x", "1.0x"],
    ["Salary Employee", "1.0x", "1.0x", "1.0x", "1.0x", "1.0x"],
    ["Pensioner", "1.0x", "1.0x", "1.5x", "3.0x", "2.0x"],
    ["Trader", "0.3x", "0.5x", "0.5x", "0.5x", "1.0x"],
    ["Student", "0.8x", "1.0x", "1.0x", "0.5x", "1.5x"],
    ["Freelancer", "0.5x", "0.8x", "0.8x", "0.8x", "1.0x"],
  ];

  dataRows.forEach((row) => {
    tblRows.push(row.map((cell, ci) => {
      const val = parseFloat(cell);
      let clr = C.text;
      if (ci > 0) {
        if (val < 1) clr = C.green;
        else if (val > 1) clr = C.red;
        else clr = C.midGray;
      }
      return {
        text: cell,
        options: {
          fontSize: 10, fontFace: "Calibri", align: ci === 0 ? "left" : "center",
          valign: "middle", color: clr, bold: ci === 0
        }
      };
    }));
  });

  s12.addTable(tblRows, {
    x: 0.5, y: 1.1, w: 9,
    colW: [2.0, 1.2, 1.1, 1.3, 1.2, 1.2],
    rowH: [0.42, 0.38, 0.38, 0.38, 0.38, 0.38, 0.38],
    border: { pt: 0.5, color: C.lightGray },
  });

  s12.addText("Принцип: бизнесменнің жоғары айналымы қалыпты (Velocity 0.5x), ал зейнеткердің түнгі аударымы ерекше қауіпті (Night Tx 3.0x)", {
    x: 0.5, y: 4.2, w: 9, h: 0.6,
    fontSize: 12, fontFace: "Calibri", color: C.text, italic: true
  });

  // ============================================================
  // SLIDE 13 — AI INTEGRATION
  // ============================================================
  let s13 = pres.addSlide();
  header(s13, "ЖАСАНДЫ ИНТЕЛЛЕКТ ИНТЕГРАЦИЯСЫ");

  // Provider cards
  const providers = [
    { name: "Claude API", sub: "Anthropic", desc: "Негізгі AI провайдер\nJSON output schema\nСтруктурланған нәтижелер", c: C.accent },
    { name: "Ollama", sub: "Local LLM", desc: "Резервті провайдер\nОффлайн режим\nllama3:8b моделі", c: C.navy },
  ];

  providers.forEach((p, i) => {
    const xx = 0.5 + i * 4.7;
    s13.addShape(pres.shapes.RECTANGLE, { x: xx, y: 1.1, w: 4.4, h: 1.6, fill: { color: p.c }, shadow: makeShadow() });
    s13.addText(p.name, {
      x: xx + 0.3, y: 1.15, w: 3.8, h: 0.4,
      fontSize: 18, fontFace: "Arial Black", color: C.white
    });
    s13.addText(p.sub, {
      x: xx + 0.3, y: 1.5, w: 3.8, h: 0.3,
      fontSize: 11, fontFace: "Calibri", color: C.lightGray
    });
    s13.addText(p.desc, {
      x: xx + 0.3, y: 1.85, w: 3.8, h: 0.75,
      fontSize: 11, fontFace: "Calibri", color: C.white
    });
  });

  // AI use cases
  s13.addText("AI қолданылу аймақтары:", {
    x: 0.5, y: 3.0, w: 4, h: 0.35,
    fontSize: 13, fontFace: "Arial Black", color: C.navy
  });

  const aiUses = [
    { t: "Risk Assessment Narrative", d: "Тәуекелді бағалау баяндамасы — адам тілінде қорытынды" },
    { t: "Financial Summary", d: "Қаржылық талдау — кіріс/шығыс паттерндері, аномалиялар" },
    { t: "Recommendations", d: "Ұсыныстар генерациясы — EDD, SAR, нақты қадамдар" },
  ];

  aiUses.forEach((u, i) => {
    const yy = 3.5 + i * 0.6;
    card(s13, 0.5, yy, 9, 0.48, C.gold);
    s13.addText(u.t, {
      x: 0.75, y: yy + 0.04, w: 2.5, h: 0.4,
      fontSize: 11, fontFace: "Arial Black", color: C.navy, valign: "middle"
    });
    s13.addText(u.d, {
      x: 3.3, y: yy + 0.04, w: 6, h: 0.4,
      fontSize: 11, fontFace: "Calibri", color: C.text, valign: "middle"
    });
  });

  // ============================================================
  // SLIDE 14 — SECURITY
  // ============================================================
  let s14 = pres.addSlide();
  header(s14, "ҚАУІПСІЗДІК ЖҮЙЕСІ");

  const secItems = [
    { t: "JWT Аутентификация", d: "HS256 алгоритмі, 30 күн мерзімі\nBearer token, localStorage", c: C.accent },
    { t: "RBAC", d: "Admin — толық қол жеткізу\nAnalyst — талдау жүргізу\nViewer — тек оқу", c: C.navy },
    { t: "Құрылғы бақылау", d: "User-Agent fingerprinting\nIP tracking, кіру тарихы\nПараллель сессияларды анықтау", c: C.purple },
    { t: "Қорғаныс", d: "Rate Limiting\nCORS, Security Headers\nBcrypt хэштеу", c: C.gold },
  ];

  secItems.forEach((s, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const xx = 0.5 + col * 4.7;
    const yy = 1.1 + row * 2.0;

    card(s14, xx, yy, 4.4, 1.75, s.c);
    s14.addShape(pres.shapes.RECTANGLE, { x: xx + 0.05, y: yy, w: 4.35, h: 0.45, fill: { color: s.c } });
    s14.addText(s.t, {
      x: xx + 0.2, y: yy + 0.02, w: 4, h: 0.42,
      fontSize: 13, fontFace: "Arial Black", color: C.white, valign: "middle"
    });
    s14.addText(s.d, {
      x: xx + 0.2, y: yy + 0.55, w: 4, h: 1.1,
      fontSize: 11, fontFace: "Calibri", color: C.text
    });
  });

  // ============================================================
  // SLIDE 15 — MULTILINGUAL
  // ============================================================
  let s15 = pres.addSlide();
  header(s15, "КӨП ТІЛДІ ИНТЕРФЕЙС");

  const langs = [
    { code: "KK", name: "Қазақша", items: "Толық локализация\nБарлық UI элементтері\nФрод нәтижелері", c: C.accent },
    { code: "RU", name: "Русский", items: "Полная локализация\nВсе элементы интерфейса\nОтчёты и рекомендации", c: C.navy },
    { code: "EN", name: "English", items: "Full localization\nAll UI elements\nReports & recommendations", c: C.gold },
  ];

  langs.forEach((l, i) => {
    const xx = 0.5 + i * 3.15;
    s15.addShape(pres.shapes.RECTANGLE, { x: xx, y: 1.1, w: 2.95, h: 2.8, fill: { color: C.white }, shadow: makeShadow() });
    s15.addShape(pres.shapes.RECTANGLE, { x: xx, y: 1.1, w: 2.95, h: 0.9, fill: { color: l.c } });
    s15.addText(l.code, {
      x: xx, y: 1.12, w: 2.95, h: 0.45,
      fontSize: 26, fontFace: "Arial Black", color: C.white, align: "center"
    });
    s15.addText(l.name, {
      x: xx, y: 1.55, w: 2.95, h: 0.35,
      fontSize: 12, fontFace: "Calibri", color: C.white, align: "center"
    });
    s15.addText(l.items, {
      x: xx + 0.2, y: 2.15, w: 2.55, h: 1.5,
      fontSize: 11, fontFace: "Calibri", color: C.text, align: "center"
    });
  });

  s15.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 4.2, w: 9, h: 0.6, fill: { color: C.white }, shadow: makeShadow() });
  s15.addText("Технология:  i18next + react-i18next  |  JSON locale файлдар  |  Динамикалық тіл ауыстыру", {
    x: 0.7, y: 4.2, w: 8.6, h: 0.6,
    fontSize: 12, fontFace: "Calibri", color: C.text, align: "center", valign: "middle"
  });

  // ============================================================
  // SLIDE 16 — FUNCTIONAL CAPABILITIES
  // ============================================================
  let s16 = pres.addSlide();
  header(s16, "«ntFAST» ФУНКЦИОНАЛДЫҚ МҮМКІНДІКТЕРІ");

  const funcs = [
    "Банктік үзінділерді автоматты жүктеу және талдау (PDF, XLSX, CSV)",
    "4 банкті қолдау: Kaspi, Halyk, Binance, Generic",
    "11 модульді фрод-детекция жүйесі (rule-based)",
    "AI-негізделген тәуекел баяндамасы",
    "Нақты уақыттағы талдау прогресі (WebSocket)",
    "Фондық режимде талдау (навигацияны тоқтатпай)",
    "PDF есеп экспорты (брендтелген есеп)",
    "Dashboard — жүйелік статистика, 6 айлық тренд",
    "Транзакцияларды іздеу, сүзгілеу, сұрыптау",
    "Субъектілерді басқару (физикалық/заңды тұлғалар)",
    "Пайдаланушыларды басқару (admin панелі)",
    "Қараңғы/жарық тема + адаптивті дизайн",
  ];

  const fHalf = Math.ceil(funcs.length / 2);
  funcs.forEach((f, i) => {
    const col = i < fHalf ? 0 : 1;
    const row = i < fHalf ? i : i - fHalf;
    const xx = 0.5 + col * 4.7;
    const yy = 1.1 + row * 0.66;

    s16.addShape(pres.shapes.OVAL, { x: xx + 0.1, y: yy + 0.12, w: 0.28, h: 0.28, fill: { color: C.green } });
    s16.addText("\u2713", {
      x: xx + 0.1, y: yy + 0.1, w: 0.28, h: 0.3,
      fontSize: 11, color: C.white, align: "center", valign: "middle"
    });
    s16.addText(f, {
      x: xx + 0.5, y: yy + 0.05, w: 4.1, h: 0.45,
      fontSize: 11, fontFace: "Calibri", color: C.text, valign: "middle"
    });
  });

  // ============================================================
  // SLIDE 17 — EXPECTED RESULTS
  // ============================================================
  let s17 = pres.addSlide();
  header(s17, "КҮТІЛЕТІН НӘТИЖЕЛЕР");

  // Big stat cards
  const stats = [
    { big: "2-5 мин", desc: "Талдау уақыты\n(қолмен 2-4 сағат)", c: C.accent },
    { big: "11", desc: "Тәуелсіз фрод-\nдетекция модулі", c: C.navy },
    { big: "60-80%", desc: "Анықтау тиімділігін\nарттыру", c: C.green },
    { big: "3 тіл", desc: "Қазақша, Русский,\nEnglish", c: C.gold },
  ];

  stats.forEach((st, i) => {
    const xx = 0.5 + i * 2.35;
    s17.addShape(pres.shapes.RECTANGLE, { x: xx, y: 1.1, w: 2.1, h: 1.35, fill: { color: st.c }, shadow: makeShadow() });
    s17.addText(st.big, {
      x: xx, y: 1.12, w: 2.1, h: 0.6,
      fontSize: 26, fontFace: "Arial Black", color: C.white, align: "center", valign: "middle"
    });
    s17.addText(st.desc, {
      x: xx + 0.1, y: 1.72, w: 1.9, h: 0.65,
      fontSize: 10, fontFace: "Calibri", color: C.white, align: "center"
    });
  });

  const moreRes = [
    "False positive деңгейін минимизациялау (контекстуалды салмақтау арқылы)",
    "Қазақстан нарығына бейімделген шешім (Kaspi, Halyk банктері)",
    "AML/CFT халықаралық стандарттарына сәйкес талдау",
    "AI арқылы адам тілінде түсінікті баяндама генерациясы",
    "Көп тілді, қауіпсіз, масштабталатын веб-қосымша",
  ];

  moreRes.forEach((r, i) => {
    const yy = 2.75 + i * 0.52;
    card(s17, 0.5, yy, 9, 0.42, C.green);
    s17.addText(`\u2713  ${r}`, {
      x: 0.75, y: yy + 0.02, w: 8.5, h: 0.38,
      fontSize: 11, fontFace: "Calibri", color: C.text, valign: "middle"
    });
  });

  // ============================================================
  // SLIDE 18 — TECH STACK
  // ============================================================
  let s18 = pres.addSlide();
  header(s18, "ТЕХНОЛОГИЯЛЫҚ СТЕК");

  const techItems = [
    { cat: "Frontend", tech: "React 18, TypeScript, Tailwind CSS, Recharts, Framer Motion, Vite 5", c: C.accent },
    { cat: "Backend", tech: "Python 3.11+, FastAPI, SQLAlchemy 2.0, Celery 5.3, Redis 5.0", c: C.navy },
    { cat: "Database", tech: "PostgreSQL, JSON fields, Full-text search", c: C.gold },
    { cat: "AI", tech: "Claude API (Anthropic), Ollama (Local LLM)", c: C.purple },
    { cat: "Security", tech: "JWT (HS256), Bcrypt, RBAC, Rate Limiting, CORS", c: C.teal },
    { cat: "Real-time", tech: "WebSocket, Celery async tasks, Background analysis", c: C.green },
  ];

  techItems.forEach((t, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const xx = 0.5 + col * 4.7;
    const yy = 1.1 + row * 1.4;

    card(s18, xx, yy, 4.4, 1.2, t.c);
    s18.addShape(pres.shapes.RECTANGLE, { x: xx + 0.05, y: yy, w: 4.35, h: 0.4, fill: { color: t.c } });
    s18.addText(t.cat, {
      x: xx + 0.2, y: yy + 0.02, w: 4, h: 0.36,
      fontSize: 13, fontFace: "Arial Black", color: C.white, valign: "middle"
    });
    s18.addText(t.tech, {
      x: xx + 0.2, y: yy + 0.5, w: 4, h: 0.6,
      fontSize: 11, fontFace: "Calibri", color: C.text
    });
  });

  // ============================================================
  // SLIDE 19 — CONCLUSION
  // ============================================================
  let s19 = pres.addSlide();
  header(s19, "ҚОРЫТЫНДЫ");

  const conclusions = [
    { t: "ntFAST — Қазақстан нарығына арналған алғашқы отандық фрод-детекция жүйесі", bold: true, c: C.gold },
    { t: "11 модульді rule-based тәсіл — түсінікті, бақылауға ыңғайлы, аудитке дайын", c: C.accent },
    { t: "AI интеграциясы (Claude + Ollama) — заманауи технологиялар", c: C.accent },
    { t: "Көп тілді қолдау — қазақ, орыс, ағылшын тілдерінде", c: C.accent },
    { t: "Жүйе нақты банктік деректермен жұмыс істеуге дайын", c: C.accent },
  ];

  conclusions.forEach((c, i) => {
    const yy = 1.1 + i * 0.68;
    card(s19, 0.5, yy, 9, 0.55, c.c);
    s19.addText(c.t, {
      x: 0.8, y: yy + 0.05, w: 8.5, h: 0.45,
      fontSize: c.bold ? 13 : 12, fontFace: c.bold ? "Arial Black" : "Calibri",
      color: C.text, valign: "middle", bold: !!c.bold
    });
  });

  // Future
  s19.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 4.55, w: 9, h: 0.7, fill: { color: C.navy }, shadow: makeShadow() });
  s19.addText("БОЛАШАҚ ДАМУ:", {
    x: 0.7, y: 4.57, w: 2.5, h: 0.3,
    fontSize: 11, fontFace: "Arial Black", color: C.gold
  });
  s19.addText("Көп субъектілі талдау  |  Мобильді қосымша  |  Real-time мониторинг  |  Банк API", {
    x: 0.7, y: 4.88, w: 8.5, h: 0.3,
    fontSize: 11, fontFace: "Calibri", color: C.white
  });

  // ============================================================
  // SLIDE 20 — THANK YOU
  // ============================================================
  let s20 = pres.addSlide();
  s20.background = { color: C.darkNavy };
  s20.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: SW, h: 0.05, fill: { color: C.gold } });

  s20.addText("НАЗАРЛАРЫҢЫЗҒА", {
    x: 1, y: 1.6, w: 8, h: 0.7,
    fontSize: 40, fontFace: "Arial Black", color: C.white, align: "center"
  });
  s20.addText("РАХМЕТ!", {
    x: 1, y: 2.3, w: 8, h: 0.8,
    fontSize: 52, fontFace: "Arial Black", color: C.gold, align: "center"
  });

  s20.addShape(pres.shapes.LINE, { x: 3.5, y: 3.3, w: 3, h: 0, line: { color: C.gold, width: 1 } });

  s20.addText("ntFAST — Financial Analysis System for Transactions", {
    x: 1, y: 3.5, w: 8, h: 0.4,
    fontSize: 13, fontFace: "Calibri", color: C.lightGray, align: "center"
  });
  s20.addText("[Студент аты-жөні]  |  [email@example.com]", {
    x: 1, y: 4.1, w: 8, h: 0.35,
    fontSize: 12, fontFace: "Calibri", color: C.midGray, align: "center"
  });
  s20.addText("2026", {
    x: 1, y: 5.0, w: 8, h: 0.3,
    fontSize: 11, fontFace: "Calibri", color: C.midGray, align: "center"
  });

  // ============================================================
  // WRITE
  // ============================================================
  await pres.writeFile({ fileName: "C:/Users/Admin/Desktop/FinancialAnalysisSystem/ntFAST_Presentation.pptx" });
  console.log("OK: ntFAST_Presentation.pptx created");
}

main().catch(e => { console.error(e); process.exit(1); });
