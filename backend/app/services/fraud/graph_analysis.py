"""
Графовый/Сетевой анализ контактов — обнаружение круговых переводов, сообществ и хабов
Использует NetworkX для построения и анализа графа
"""
import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict
from ..bank_analyzer.base_parser import Transaction, AccountInfo
from .models import GraphResult, AccountProfile, AccountType

logger = logging.getLogger(__name__)

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    logger.warning("networkx not installed. Graph analysis disabled. Run: pip install networkx")

# Пороги bidirectional hub по типу аккаунта
# BUSINESS_OWNER: только если > 50 уникальных контрагентов
BIDIR_HUB_THRESHOLD = {
    AccountType.BUSINESS_OWNER: 50,
    AccountType.TRADER:         20,
    AccountType.FREELANCER:     10,
    AccountType.SALARY_EMPLOYEE: 8,
    AccountType.PENSIONER:       6,
    AccountType.STUDENT:         6,
    AccountType.UNKNOWN:         8,
}


class TransactionGraphAnalyzer:
    """Анализ сети контрагентов через directed graph"""

    def __init__(self):
        self.graph = None
        self.owner = ""

    def build_and_analyze(
        self,
        transactions: List[Transaction],
        account_info: AccountInfo,
        profile: Optional[AccountProfile] = None
    ) -> GraphResult:
        result = GraphResult()

        if not HAS_NETWORKX:
            return result

        if profile is None:
            profile = AccountProfile()

        self.owner = account_info.owner or "OWNER"
        self.graph = nx.DiGraph()

        # Построить граф: узлы = сущности, рёбра = денежные потоки
        edge_data = defaultdict(lambda: {"weight": 0.0, "count": 0, "dates": []})

        for tx in transactions:
            # Извлекаем контрагента: merchant_name → counterparty → description (обрезанный)
            cp = tx.merchant_name or tx.counterparty
            if not cp:
                # Используем первые 50 символов описания как fallback
                desc = (tx.description or "").strip()
                if desc:
                    # Обрезаем длинные описания, убираем номера/даты для группировки
                    cp = desc[:50].strip()
                else:
                    continue

            if not cp or len(cp) < 2:
                continue

            if tx.amount < 0:
                key = (self.owner, cp)
            else:
                key = (cp, self.owner)

            edge_data[key]["weight"] += abs(tx.amount)
            edge_data[key]["count"] += 1
            edge_data[key]["dates"].append(tx.date.isoformat())

        for (src, tgt), data in edge_data.items():
            self.graph.add_edge(src, tgt, weight=data["weight"],
                                count=data["count"])

        result.node_count = self.graph.number_of_nodes()
        result.edge_count = self.graph.number_of_edges()

        # Анализ
        result.cycles = self._detect_cycles()
        result.communities = self._detect_communities()
        result.centrality = self._calculate_centrality()
        result.hub_nodes = self._find_hubs()
        result.nodes = self._get_nodes_data()
        result.edges = self._get_edges_data()
        result.risk_score = self._calculate_risk(result, profile)

        return result

    def _detect_cycles(self) -> List[Dict]:
        """Обнаружение круговых переводов (round-tripping)"""
        cycles = []
        try:
            for cycle in nx.simple_cycles(self.graph):
                if len(cycle) >= 3:  # 2-node cycles (A→B→A) are normal repayments
                    total_flow = 0
                    for i in range(len(cycle)):
                        src = cycle[i]
                        tgt = cycle[(i + 1) % len(cycle)]
                        if self.graph.has_edge(src, tgt):
                            total_flow += self.graph[src][tgt].get("weight", 0)

                    cycles.append({
                        "nodes": cycle,
                        "length": len(cycle),
                        "total_flow": total_flow,
                    })
        except Exception as e:
            logger.debug(f"Cycle detection error: {e}")

        return sorted(cycles, key=lambda c: c["total_flow"], reverse=True)[:20]

    def _detect_communities(self) -> List[Dict]:
        """Обнаружение сообществ (кластеров связанных контрагентов)"""
        try:
            undirected = self.graph.to_undirected()
            communities = list(nx.community.label_propagation_communities(undirected))
            return [
                {"members": sorted(list(c)), "size": len(c)}
                for c in communities if len(c) > 1
            ]
        except Exception:
            return []

    def _calculate_centrality(self) -> Dict[str, float]:
        """Betweenness centrality — узлы-посредники"""
        try:
            bc = nx.betweenness_centrality(self.graph, weight="weight")
            # Топ-10 по centrality
            sorted_bc = sorted(bc.items(), key=lambda x: x[1], reverse=True)[:10]
            return {k: round(v, 4) for k, v in sorted_bc}
        except Exception:
            return {}

    def _find_hubs(self) -> List[Dict]:
        """Найти ключевые узлы (хабы) по объёму и количеству связей"""
        hubs = []
        for node in self.graph.nodes():
            if node == self.owner:
                continue

            in_weight = sum(d.get("weight", 0) for _, _, d in self.graph.in_edges(node, data=True))
            out_weight = sum(d.get("weight", 0) for _, _, d in self.graph.out_edges(node, data=True))
            in_degree = self.graph.in_degree(node)
            out_degree = self.graph.out_degree(node)

            total_volume = in_weight + out_weight
            if total_volume > 0:
                hubs.append({
                    "name": node,
                    "total_volume": total_volume,
                    "in_volume": in_weight,
                    "out_volume": out_weight,
                    "connections": in_degree + out_degree,
                    "is_bidirectional": in_degree > 0 and out_degree > 0,
                })

        return sorted(hubs, key=lambda h: h["total_volume"], reverse=True)[:15]

    def _get_nodes_data(self) -> List[Dict]:
        """Данные узлов для визуализации"""
        nodes = []
        for node in self.graph.nodes():
            in_w = sum(d.get("weight", 0) for _, _, d in self.graph.in_edges(node, data=True))
            out_w = sum(d.get("weight", 0) for _, _, d in self.graph.out_edges(node, data=True))
            nodes.append({
                "id": node,
                "is_owner": node == self.owner,
                "in_volume": in_w,
                "out_volume": out_w,
                "total_volume": in_w + out_w,
                "connections": self.graph.degree(node),
            })
        return nodes

    def _get_edges_data(self) -> List[Dict]:
        """Данные рёбер для визуализации"""
        edges = []
        for src, tgt, data in self.graph.edges(data=True):
            edges.append({
                "source": src,
                "target": tgt,
                "weight": data.get("weight", 0),
                "count": data.get("count", 0),
            })
        return edges

    def _calculate_risk(
        self,
        result: GraphResult,
        profile: AccountProfile
    ) -> float:
        """Рассчитать риск на основе графового анализа"""
        score = 0

        # Циклы = round-tripping (только 3+ node циклы)
        if result.cycles:
            score += min(40, len(result.cycles) * 10)

        # Двунаправленные хабы — контекстный порог
        bidir_threshold = BIDIR_HUB_THRESHOLD.get(profile.account_type, 8)
        bidirectional_hubs = [h for h in result.hub_nodes if h.get("is_bidirectional")]

        significant_bidir = [
            h for h in bidirectional_hubs
            if h.get("connections", 0) > bidir_threshold
        ]
        if len(significant_bidir) > 0:
            score += 10

        # Слишком много связей у одного контрагента
        if result.hub_nodes:
            max_connections = max(h["connections"] for h in result.hub_nodes)
            connection_threshold = bidir_threshold * 3
            if max_connections > connection_threshold:
                score += 15

        # v4.2: Fan-out detection — деньги от нескольких людей уходят нескольким
        # Подозрительно: много двунаправленных P2P контактов (деньги и туда и обратно)
        # Но для Kaspi Gold 5-10 bidir контактов нормально (друзья, семья)
        if bidirectional_hubs:
            bidir_count = len(bidirectional_hubs)
            if bidir_count >= 15:
                score += 30  # 15+ контрагентов = явная сеть
            elif bidir_count >= 10:
                score += 15
            elif bidir_count >= 8:
                score += 8

        # v4.2: Высокая плотность графа — много уникальных контрагентов для зарплатника
        if profile.account_type in (AccountType.SALARY_EMPLOYEE, AccountType.PENSIONER,
                                     AccountType.STUDENT):
            if result.node_count > 30:
                score += 15  # Обычный человек не общается с 30+ контрагентами
            elif result.node_count > 20:
                score += 8

        return min(100, score)
