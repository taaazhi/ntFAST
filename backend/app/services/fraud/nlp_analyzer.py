"""
ntFAST AI — NLP Analyzer for Transaction Descriptions
Анализ текстовых описаний транзакций для обнаружения мошенничества.

СТАТУС: НЕ ПОДКЛЮЧЁН К СКОРИНГУ (WIP). Модуль полон и работает, но
FraudEngine его не вызывает: балл риска считают правила и статистика, а не
текстовый NLP. Нулевых потребителей у него по замыслу, а не по забвению —
оставлен как основа для пересмотра в фазе агента-следователя (Ф3), где
решится, давать ли эти находки модели на вход или держать отдельным
сигналом. Требует sklearn/numpy; без sklearn детектор шаблонов молчит,
остальные пять методов работают.

Что обнаруживает:
  1. Шаблонные описания (одинаковый текст от разных контрагентов)
  2. Подозрительные ключевые слова ("обнал", "наличка", "конверт")
  3. Несоответствие описания типу операции
  4. Copy-paste fraud (дубликаты описаний)
  5. Подозрительные паттерны нумерации ("по договору №1001, №1002, №1003")
  6. Language mixing (переключение языков)

Использование:
    from app.services.fraud.nlp_analyzer import NtFastNLPAnalyzer

    analyzer = NtFastNLPAnalyzer()
    results = analyzer.analyze(transactions)
    # results.risk_score: 0-100
    # results.findings: список подозрительных паттернов
"""
import re
import math
import logging
from typing import List, Dict, Optional, Tuple, Any, Set
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import numpy as np

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.cluster import DBSCAN
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  ПОДОЗРИТЕЛЬНЫЕ СЛОВАРИ
# ══════════════════════════════════════════════════════════════════════════════

# Прямые маркеры мошенничества (каждое слово = красный флаг)
FRAUD_KEYWORDS_CRITICAL = {
    # Русский
    "обнал", "обналичка", "обналичивание", "наличка", "кэш",
    "конверт", "откат", "взятка", "подкуп",
    "серая", "серую", "чёрная", "чёрную", "левая", "левую",
    "отмыв", "отмывание", "отмыть",
    "обход", "уход от налогов",
    "фиктивн", "подставн", "липов",
    "хавала", "hawala",
    # Крипто
    "mixer", "миксер", "tumbler", "тумблер", "tornado",
    "laundering", "launder",
}

# Средние маркеры (подозрительны в контексте)
FRAUD_KEYWORDS_MEDIUM = {
    "возврат предоплаты", "возврат аванса", "перерасчёт",
    "беспроцентный займ", "займ без процентов",
    "по устной", "устная договорённость",
    "материальная помощь", "благотворительн",
    "пожертвование", "donation",
    "инвестици", "invest",
    "криптовалют", "crypto", "bitcoin", "btc", "usdt",
    "p2p", "peer",
    "без назначения", "без комментари",
}

# Шаблоны для обнаружения серийных номеров / договоров
SERIAL_PATTERN = re.compile(
    r'(?:договор|счёт|счет|invoice|contract|№|#)\s*(\d{3,})',
    re.IGNORECASE
)

# Паттерн для обнаружения подозрительных сумм в описании
AMOUNT_IN_DESC_PATTERN = re.compile(r'\d{1,3}[\s,.]?\d{3,}')

# Признаки смешения языков
CYRILLIC_PATTERN = re.compile(r'[а-яА-ЯёЁ]')
LATIN_PATTERN = re.compile(r'[a-zA-Z]')


# ══════════════════════════════════════════════════════════════════════════════
#  DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class NLPFinding:
    """Одна находка NLP-анализа."""
    category: str          # "keyword_critical", "template_fraud", "mismatch", etc.
    severity: str          # "critical", "high", "medium", "low"
    description: str       # Человекочитаемое описание
    evidence: str          # Конкретный текст-доказательство
    score_impact: float    # Влияние на итоговый score (0-30)
    tx_indices: List[int] = field(default_factory=list)  # Индексы подозрительных транзакций


@dataclass
class NLPAnalysisResult:
    """Результат NLP-анализа всех транзакций."""
    risk_score: float              # 0-100
    findings: List[NLPFinding]     # Все находки
    n_transactions: int
    n_suspicious: int              # Сколько транзакций подозрительных
    description_clusters: int      # Сколько кластеров описаний
    template_ratio: float          # % шаблонных описаний
    keyword_hits: Dict[str, int]   # Найденные ключевые слова
    similarity_matrix: Optional[np.ndarray] = None  # Матрица схожести (для фронтенда)


# ══════════════════════════════════════════════════════════════════════════════
#  ntFAST NLP ANALYZER
# ══════════════════════════════════════════════════════════════════════════════

class NtFastNLPAnalyzer:
    """
    ntFAST AI NLP Analyzer — анализ текстовых описаний транзакций.

    Комбинирует 6 методов:
    1. Keyword detection (подозрительные слова)
    2. Template detection (TF-IDF + cosine similarity + DBSCAN)
    3. Mismatch detection (описание vs тип операции)
    4. Copy-paste detection (точные дубликаты от разных контрагентов)
    5. Serial number analysis (подозрительные серии номеров)
    6. Language mixing detection (смешение языков в одном описании)
    """

    def __init__(
        self,
        similarity_threshold: float = 0.85,
        min_cluster_size: int = 3,
        template_min_occurrences: int = 5,
    ):
        """
        Parameters
        ----------
        similarity_threshold : float
            Порог cosine similarity для обнаружения шаблонных описаний
        min_cluster_size : int
            Минимальный размер кластера для DBSCAN
        template_min_occurrences : int
            Минимальное кол-во повторений для обнаружения шаблона
        """
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size
        self.template_min_occurrences = template_min_occurrences

    def analyze(self, transactions: List[Any]) -> NLPAnalysisResult:
        """
        Полный NLP-анализ списка транзакций.

        Parameters
        ----------
        transactions : List[Any]
            Список объектов Transaction с полем description, counterparty, type, amount

        Returns
        -------
        NLPAnalysisResult
        """
        n = len(transactions)
        if n == 0:
            return NLPAnalysisResult(
                risk_score=0.0, findings=[], n_transactions=0,
                n_suspicious=0, description_clusters=0,
                template_ratio=0.0, keyword_hits={},
            )

        # Извлекаем описания
        descriptions = []
        counterparties = []
        tx_types = []
        amounts = []

        for tx in transactions:
            desc = self._get_field(tx, 'description', '')
            cp = self._get_field(tx, 'counterparty', '')
            tx_type = self._get_field(tx, 'type', self._get_field(tx, 'category', ''))
            amount = self._get_field(tx, 'amount', 0.0)

            descriptions.append(str(desc).strip())
            counterparties.append(str(cp).strip())
            tx_types.append(str(tx_type).lower())
            amounts.append(float(amount) if amount else 0.0)

        findings: List[NLPFinding] = []
        suspicious_indices: Set[int] = set()

        # ── 1. Keyword Detection ──
        kw_findings, kw_hits = self._detect_keywords(descriptions)
        findings.extend(kw_findings)
        for f in kw_findings:
            suspicious_indices.update(f.tx_indices)

        # ── 2. Template / Copy-Paste Detection ──
        tpl_findings, n_clusters, tpl_ratio, sim_matrix = self._detect_templates(
            descriptions, counterparties
        )
        findings.extend(tpl_findings)
        for f in tpl_findings:
            suspicious_indices.update(f.tx_indices)

        # ── 3. Mismatch Detection ──
        mm_findings = self._detect_mismatches(descriptions, tx_types, amounts)
        findings.extend(mm_findings)
        for f in mm_findings:
            suspicious_indices.update(f.tx_indices)

        # ── 4. Serial Number Analysis ──
        sn_findings = self._detect_serial_numbers(descriptions)
        findings.extend(sn_findings)
        for f in sn_findings:
            suspicious_indices.update(f.tx_indices)

        # ── 5. Language Mixing ──
        lm_findings = self._detect_language_mixing(descriptions)
        findings.extend(lm_findings)
        for f in lm_findings:
            suspicious_indices.update(f.tx_indices)

        # ── Итоговый score ──
        total_impact = sum(f.score_impact for f in findings)
        risk_score = min(100.0, total_impact)

        return NLPAnalysisResult(
            risk_score=round(risk_score, 1),
            findings=findings,
            n_transactions=n,
            n_suspicious=len(suspicious_indices),
            description_clusters=n_clusters,
            template_ratio=round(tpl_ratio, 3),
            keyword_hits=kw_hits,
            similarity_matrix=sim_matrix,
        )

    # ═════════════════════════════════════════════════════════════════════
    #  1. KEYWORD DETECTION
    # ═════════════════════════════════════════════════════════════════════

    def _detect_keywords(
        self, descriptions: List[str]
    ) -> Tuple[List[NLPFinding], Dict[str, int]]:
        """Обнаружение подозрительных ключевых слов."""
        findings = []
        keyword_hits: Dict[str, int] = {}

        for i, desc in enumerate(descriptions):
            desc_lower = desc.lower()

            # Critical keywords
            for kw in FRAUD_KEYWORDS_CRITICAL:
                if kw in desc_lower:
                    keyword_hits[kw] = keyword_hits.get(kw, 0) + 1
                    findings.append(NLPFinding(
                        category="keyword_critical",
                        severity="critical",
                        description=f"Критическое ключевое слово: '{kw}'",
                        evidence=desc[:100],
                        score_impact=15.0,
                        tx_indices=[i],
                    ))

            # Medium keywords
            for kw in FRAUD_KEYWORDS_MEDIUM:
                if kw in desc_lower:
                    keyword_hits[kw] = keyword_hits.get(kw, 0) + 1
                    if keyword_hits[kw] <= 2:  # Не повторяем для каждого вхождения
                        findings.append(NLPFinding(
                            category="keyword_medium",
                            severity="medium",
                            description=f"Подозрительное ключевое слово: '{kw}'",
                            evidence=desc[:100],
                            score_impact=5.0,
                            tx_indices=[i],
                        ))

        return findings, keyword_hits

    # ═════════════════════════════════════════════════════════════════════
    #  2. TEMPLATE / COPY-PASTE DETECTION (TF-IDF + DBSCAN)
    # ═════════════════════════════════════════════════════════════════════

    def _detect_templates(
        self, descriptions: List[str], counterparties: List[str]
    ) -> Tuple[List[NLPFinding], int, float, Optional[np.ndarray]]:
        """Обнаружение шаблонных описаний с помощью TF-IDF + DBSCAN."""
        findings = []
        n_clusters = 0
        template_ratio = 0.0
        sim_matrix = None

        if not SKLEARN_AVAILABLE or len(descriptions) < 5:
            return findings, n_clusters, template_ratio, sim_matrix

        # Фильтруем пустые описания
        valid_mask = [bool(d.strip()) for d in descriptions]
        valid_descs = [d for d, v in zip(descriptions, valid_mask) if v]
        valid_indices = [i for i, v in enumerate(valid_mask) if v]

        if len(valid_descs) < 5:
            return findings, n_clusters, template_ratio, sim_matrix

        # TF-IDF
        try:
            tfidf = TfidfVectorizer(
                max_features=500,
                ngram_range=(1, 2),
                min_df=2,
                max_df=0.95,
            )
            tfidf_matrix = tfidf.fit_transform(valid_descs)
        except ValueError:
            return findings, n_clusters, template_ratio, sim_matrix

        # Cosine similarity matrix
        sim_matrix = cosine_similarity(tfidf_matrix)

        # DBSCAN кластеризация
        distance_matrix = 1.0 - sim_matrix
        np.fill_diagonal(distance_matrix, 0)
        distance_matrix = np.clip(distance_matrix, 0, 2)

        clustering = DBSCAN(
            eps=1.0 - self.similarity_threshold,
            min_samples=self.min_cluster_size,
            metric='precomputed',
        )
        cluster_labels = clustering.fit_predict(distance_matrix)

        n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
        n_in_clusters = sum(1 for l in cluster_labels if l != -1)
        template_ratio = n_in_clusters / len(valid_descs) if valid_descs else 0.0

        # Анализ кластеров
        for cluster_id in set(cluster_labels):
            if cluster_id == -1:
                continue

            cluster_indices = [valid_indices[j] for j, l in enumerate(cluster_labels) if l == cluster_id]
            cluster_descs = [descriptions[i] for i in cluster_indices]
            cluster_cps = [counterparties[i] for i in cluster_indices]

            # Если одинаковые описания от РАЗНЫХ контрагентов — очень подозрительно
            unique_cps = len(set(cluster_cps))
            cluster_size = len(cluster_indices)

            if unique_cps >= 3 and cluster_size >= self.template_min_occurrences:
                severity = "high" if unique_cps >= 5 else "medium"
                impact = min(20.0, 5.0 + unique_cps * 1.5)

                sample_desc = cluster_descs[0][:80]
                findings.append(NLPFinding(
                    category="template_fraud",
                    severity=severity,
                    description=(
                        f"Шаблонное описание '{sample_desc}...' "
                        f"повторяется {cluster_size}× от {unique_cps} разных контрагентов"
                    ),
                    evidence=f"Кластер #{cluster_id}: {cluster_size} txs, {unique_cps} уникальных контрагентов",
                    score_impact=impact,
                    tx_indices=cluster_indices,
                ))

        # Точные дубликаты от разных контрагентов (Copy-Paste)
        desc_cp_map: Dict[str, Set[str]] = defaultdict(set)
        desc_idx_map: Dict[str, List[int]] = defaultdict(list)

        for i, (desc, cp) in enumerate(zip(descriptions, counterparties)):
            normalized = desc.strip().lower()
            if len(normalized) > 5:
                desc_cp_map[normalized].add(cp)
                desc_idx_map[normalized].append(i)

        for desc_norm, cps in desc_cp_map.items():
            if len(cps) >= 3:
                indices = desc_idx_map[desc_norm]
                findings.append(NLPFinding(
                    category="copy_paste",
                    severity="high",
                    description=f"Идентичное описание от {len(cps)} разных контрагентов",
                    evidence=f"'{desc_norm[:60]}...' → {', '.join(list(cps)[:3])}...",
                    score_impact=min(15.0, len(cps) * 2.5),
                    tx_indices=indices,
                ))

        return findings, n_clusters, template_ratio, sim_matrix

    # ═════════════════════════════════════════════════════════════════════
    #  3. MISMATCH DETECTION
    # ═════════════════════════════════════════════════════════════════════

    def _detect_mismatches(
        self,
        descriptions: List[str],
        tx_types: List[str],
        amounts: List[float],
    ) -> List[NLPFinding]:
        """Обнаружение несоответствий между описанием и типом операции."""
        findings = []

        income_keywords = {"зарплата", "salary", "пенсия", "пособие", "стипендия", "доход"}
        expense_keywords = {"покупка", "оплата", "purchase", "payment", "расход"}

        for i, (desc, tx_type, amount) in enumerate(zip(descriptions, tx_types, amounts)):
            desc_lower = desc.lower()

            # Описание "зарплата" но тип = расход / transfer_out
            if any(kw in desc_lower for kw in income_keywords):
                if amount < 0 and "transfer" in tx_type:
                    findings.append(NLPFinding(
                        category="mismatch",
                        severity="medium",
                        description="Описание указывает на доход, но операция исходящая",
                        evidence=f"'{desc[:60]}' (тип: {tx_type}, сумма: {amount})",
                        score_impact=8.0,
                        tx_indices=[i],
                    ))

            # Описание "покупка/оплата" но тип = income
            if any(kw in desc_lower for kw in expense_keywords):
                if amount > 0 and ("income" in tx_type or "transfer_in" in tx_type):
                    findings.append(NLPFinding(
                        category="mismatch",
                        severity="medium",
                        description="Описание указывает на расход, но операция входящая",
                        evidence=f"'{desc[:60]}' (тип: {tx_type}, сумма: {amount})",
                        score_impact=8.0,
                        tx_indices=[i],
                    ))

        return findings

    # ═════════════════════════════════════════════════════════════════════
    #  4. SERIAL NUMBER ANALYSIS
    # ═════════════════════════════════════════════════════════════════════

    def _detect_serial_numbers(self, descriptions: List[str]) -> List[NLPFinding]:
        """Обнаружение подозрительных серий номеров договоров/счетов."""
        findings = []

        # Извлекаем все номера
        numbers_by_prefix: Dict[str, List[Tuple[int, int]]] = defaultdict(list)

        for i, desc in enumerate(descriptions):
            for match in SERIAL_PATTERN.finditer(desc):
                prefix = match.group(0)[:match.start(1) - match.start(0)]
                number = int(match.group(1))
                numbers_by_prefix[prefix.strip().lower()].append((i, number))

        # Ищем последовательные номера (1001, 1002, 1003...)
        for prefix, num_list in numbers_by_prefix.items():
            if len(num_list) < 3:
                continue

            num_list.sort(key=lambda x: x[1])
            numbers = [n for _, n in num_list]
            indices = [i for i, _ in num_list]

            # Проверяем последовательность
            consecutive_count = 1
            max_consecutive = 1
            for j in range(1, len(numbers)):
                if numbers[j] - numbers[j - 1] == 1:
                    consecutive_count += 1
                    max_consecutive = max(max_consecutive, consecutive_count)
                else:
                    consecutive_count = 1

            if max_consecutive >= 3:
                findings.append(NLPFinding(
                    category="serial_numbers",
                    severity="high",
                    description=(
                        f"Последовательные номера документов: "
                        f"{max_consecutive} подряд ('{prefix}' {numbers[:5]}...)"
                    ),
                    evidence=f"Серия: {numbers[:10]}",
                    score_impact=min(15.0, max_consecutive * 2.0),
                    tx_indices=indices[:max_consecutive],
                ))

        return findings

    # ═════════════════════════════════════════════════════════════════════
    #  5. LANGUAGE MIXING DETECTION
    # ═════════════════════════════════════════════════════════════════════

    def _detect_language_mixing(self, descriptions: List[str]) -> List[NLPFinding]:
        """Обнаружение подозрительного смешения языков в описаниях."""
        findings = []
        mixed_indices = []

        for i, desc in enumerate(descriptions):
            if len(desc) < 10:
                continue

            has_cyrillic = bool(CYRILLIC_PATTERN.search(desc))
            has_latin = bool(LATIN_PATTERN.search(desc))

            if has_cyrillic and has_latin:
                # Проверяем что это не просто бренд-неймы
                # Считаем долю кириллицы vs латиницы
                n_cyr = len(CYRILLIC_PATTERN.findall(desc))
                n_lat = len(LATIN_PATTERN.findall(desc))
                total = n_cyr + n_lat

                # Если обе доли значительные (>20%) — подозрительно
                if min(n_cyr, n_lat) / total > 0.2:
                    mixed_indices.append(i)

        if len(mixed_indices) >= 3:
            findings.append(NLPFinding(
                category="language_mixing",
                severity="low",
                description=f"Смешение языков в {len(mixed_indices)} описаниях",
                evidence=f"Индексы: {mixed_indices[:5]}",
                score_impact=3.0,
                tx_indices=mixed_indices[:10],
            ))

        return findings

    # ═════════════════════════════════════════════════════════════════════
    #  HELPERS
    # ═════════════════════════════════════════════════════════════════════

    @staticmethod
    def _get_field(obj: Any, field: str, default: Any = None) -> Any:
        """Безопасно получает поле объекта или ключ словаря."""
        if isinstance(obj, dict):
            return obj.get(field, default)
        return getattr(obj, field, default)
