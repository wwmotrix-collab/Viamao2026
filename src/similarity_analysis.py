"""Módulo de análise de similaridade por seção eleitoral."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class SimilarityAnalyzer:
    """Analisador de perfil estatisticamente semelhante entre seções."""

    def __init__(self, secoes_path: Path, output_path: Path):
        self.secoes_path = secoes_path
        self.output_path = output_path
        self.secoes = []

    def load(self) -> List[Dict]:
        """Carrega seções normalizadas."""
        with open(self.secoes_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.secoes = data.get('secoes', [])
        logger.info(f"Carregadas {len(self.secoes)} seções")
        return self.secoes

    def build_profile(self, secao: Dict) -> Dict:
        """Constrói vetor de características da seção."""
        votos = secao.get('votos', {})
        pct = secao.get('percentuais', {})

        return {
            'secao_numero': secao.get('secao_numero', 0),
            'zona_eleitoral': secao.get('zona_eleitoral', 0),
            'bairro': secao.get('bairro', 'N/A'),
            'local': secao.get('local', 'N/A'),
            'denise_pct': pct.get('denise', 0.0),
            'helenir_pct': pct.get('helenir', 0.0),
            'total_votos': votos.get('total', 0),
            'denise_votos': votos.get('denise', 0),
            'helenir_votos': votos.get('helenir', 0),
        }

    def calculate_similarity(self, a: Dict, b: Dict) -> float:
        """Calcula similaridade entre duas seções."""
        # Diferença em zona, bairro e perfis de votação
        score = 0.0

        if a['zona_eleitoral'] == b['zona_eleitoral']:
            score += 0.25

        if a['bairro'] == b['bairro']:
            score += 0.20

        # Similaridade de proporção de votos
        diff_denise = abs(a['denise_pct'] - b['denise_pct'])
        diff_helenir = abs(a['helenir_pct'] - b['helenir_pct'])
        score += max(0.0, 1.0 - (diff_denise + diff_helenir) / 100.0) * 0.40

        # Similaridade no volume de votos
        volume_ratio = 1.0 - (abs(a['total_votos'] - b['total_votos']) / max(a['total_votos'], b['total_votos'], 1))
        score += max(0.0, volume_ratio) * 0.15

        return round(max(0.0, min(1.0, score)), 4)

    def analyze(self) -> Dict:
        """Executa análise de similaridade."""
        if not self.secoes:
            self.load()

        profiles = [self.build_profile(s) for s in self.secoes]
        patterns = []

        # Encontrar padrões principais por zona e perfil
        by_zone = {}
        for secao in profiles:
            by_zone.setdefault(secao['zona_eleitoral'], []).append(secao)

        for zona, zonas_secoes in by_zone.items():
            if not zonas_secoes:
                continue

            # Selecionar a seção com maior volume de votos nesta zona
            anchor = max(zonas_secoes, key=lambda s: s['total_votos'])
            similar_sections = []

            for other in zonas_secoes:
                if other['secao_numero'] == anchor['secao_numero']:
                    continue
                similarity = self.calculate_similarity(anchor, other)
                if similarity >= 0.70:
                    similar_sections.append({
                        'secao': other['secao_numero'],
                        'similaridade': similarity,
                        'motivo': 'Perfil de voto semelhante'
                    })

            patterns.append({
                'padrao_id': f'P{zona:03d}',
                'nome': f'Perfil dominante - Zona {zona}',
                'caracteristicas': {
                    'zona_eleitoral': zona,
                    'percentual_denise_media': round(sum(s['denise_pct'] for s in zonas_secoes) / len(zonas_secoes), 2),
                    'percentual_helenir_media': round(sum(s['helenir_pct'] for s in zonas_secoes) / len(zonas_secoes), 2),
                    'total_votos_medio': round(sum(s['total_votos'] for s in zonas_secoes) / len(zonas_secoes), 2),
                },
                'secoes_principais': [anchor['secao_numero']],
                'secoes_similares': sorted(similar_sections, key=lambda x: x['similaridade'], reverse=True)[:10],
            })

        analysis = {
            'analise_global': {
                'total_secoes': len(self.secoes),
                'data_geracao': pd.Timestamp.utcnow().isoformat() + 'Z',
                'metodo': 'similaridade_descritiva_por_secao',
            },
            'padroes': patterns,
        }

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)

        logger.info(f"Análise salva em {self.output_path}")
        return analysis


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    base = Path(__file__).resolve().parent.parent
    analyzer = SimilarityAnalyzer(
        secoes_path=base / 'data' / 'processed' / 'secoes_normalized.json',
        output_path=base / 'data' / 'processed' / 'similarity_analysis.json'
    )
    analyzer.analyze()
